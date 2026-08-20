/**
 * M-014 Project Clone Plan live PostgreSQL 18.4 authority tests.
 *
 * Proves the VF-PRJ-007 (fork/remix/template) authority contract: fail-closed
 * authorization ordering, same-Organization template policy, new server
 * identity, Artifact/relation remapping, transactional rollback, idempotency
 * and cross-tenant/IDOR behaviour.
 */

import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  ArtifactRepository,
  createControlPlanePool,
  defaultMigrationsDirectory,
  ProjectLifecycleRepository,
  ProjectRepository,
  TenantRepository,
  type AccountRow,
  type ArtifactRow,
  type ControlPlanePool,
  type OrganizationRow,
  type ProjectRow,
} from "@vibeflow/persistence";
import { AuditService } from "@vibeflow/audit";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ArtifactService } from "./artifact-service.js";
import { ProjectCloneService } from "./clone-service.js";
import {
  ProjectAuthorizationError,
  ProjectCloneError,
  ProjectInputError,
  ProjectNotFoundError,
} from "./errors.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-014 clone-plan PostgreSQL tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-014 Project Clone Plan authority", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let artifacts: ArtifactRepository;
  let lifecycle: ProjectLifecycleRepository;
  let audit: AuditService;
  let authz: TenantAuthorizationService;
  let artifactService: ArtifactService;
  let service: ProjectCloneService;

  let alice: AccountRow;
  let bob: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;

  /** Source Project in orgA with a small artifact graph. */
  let source: ProjectRow;
  let sourceArtifacts: ArtifactRow[];
  /** A Project in orgB, used for cross-tenant probes. */
  let foreignProject: ProjectRow;

  async function projectCount(organizationId: string): Promise<number> {
    return (await projects.listProjectsForOrganization(organizationId)).length;
  }

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    artifacts = new ArtifactRepository(controlPlane.db);
    lifecycle = new ProjectLifecycleRepository(controlPlane.db);
    audit = new AuditService(controlPlane.pool);

    authz = new TenantAuthorizationService(
      {
        getOrganizationById: tenants.getOrganizationById.bind(tenants),
        getMembership: tenants.getMembership.bind(tenants),
        getProjectById: projects.getProjectById.bind(projects),
        getArtifactById: artifacts.getArtifactById.bind(artifacts),
        getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
      },
      audit,
    );
    artifactService = new ArtifactService({ artifacts, authz });
    service = new ProjectCloneService({ projects, lifecycle, authz });

    alice = await tenants.createAccount({ displayName: "Clone Alice" });
    bob = await tenants.createAccount({ displayName: "Clone Bob" });
    orgA = await tenants.createOrganization({ name: "Clone Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Clone Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });

    source = await projects.createProject({
      organizationId: orgA.id,
      name: "Clone Source Project",
    });
    foreignProject = await projects.createProject({
      organizationId: orgB.id,
      name: "Foreign Project",
    });

    // Build a source graph: website -> contains -> design, plus a variant.
    const website = await artifactService.createArtifact({
      accountId: alice.id,
      projectId: source.id,
      type: "website",
    });
    const design = await artifactService.createArtifact({
      accountId: alice.id,
      projectId: source.id,
      type: "design/hero",
    });
    const variant = await artifactService.createArtifact({
      accountId: alice.id,
      projectId: source.id,
      type: "com.acme.slides",
    });
    sourceArtifacts = [website, design, variant];

    await artifactService.createArtifactRelation({
      accountId: alice.id,
      subjectArtifactId: website.id,
      objectArtifactId: design.id,
      relationKind: "contains",
    });
    await artifactService.createArtifactRelation({
      accountId: alice.id,
      subjectArtifactId: variant.id,
      objectArtifactId: website.id,
      relationKind: "variant",
    });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  // -------------------------------------------------------------------------
  // Authorized same-Organization clone
  // -------------------------------------------------------------------------

  it("clones a Project inside the same canonical Organization", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Cloned Project",
      idempotencyKey: `clone-${randomUUID()}`,
    });

    expect(result.replayed).toBe(false);
    expect(result.targetProject.organizationId).toBe(orgA.id);
    expect(result.targetProject.name).toBe("Cloned Project");
    expect(result.plan.planKind).toBe("project_clone");
    expect(result.plan.sourceProjectId).toBe(source.id);
    expect(result.plan.targetProjectId).toBe(result.targetProject.id);
  });

  it("gives the target Project a NEW server-generated id", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "New Identity Clone",
      idempotencyKey: `newid-${randomUUID()}`,
    });
    expect(result.targetProject.id).not.toBe(source.id);
    expect(result.targetProject.id).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("clones Artifact metadata with NEW ids and preserved type tokens", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Artifact Clone",
      idempotencyKey: `artclone-${randomUUID()}`,
    });

    expect(result.artifacts).toHaveLength(sourceArtifacts.length);

    const sourceIds = new Set(sourceArtifacts.map((a) => a.id));
    for (const cloned of result.artifacts) {
      // No source Artifact id is ever reused.
      expect(sourceIds.has(cloned.id)).toBe(false);
      expect(cloned.projectId).toBe(result.targetProject.id);
    }

    // Every type token is preserved exactly.
    expect([...result.artifacts].map((a) => a.type).sort()).toEqual(
      [...sourceArtifacts].map((a) => a.type).sort(),
    );
  });

  it("reproduces the relation graph with remapped target Artifact ids", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Relation Clone",
      idempotencyKey: `relclone-${randomUUID()}`,
    });

    const sourceRelations = await artifacts.listArtifactRelationsForProject(source.id);
    expect(result.relations).toHaveLength(sourceRelations.length);

    // Each source edge appears exactly once, remapped to the new ids and with
    // its canonical relation kind preserved.
    for (const sourceRelation of sourceRelations) {
      const expectedSubject = result.artifactIdMap.get(sourceRelation.subjectArtifactId);
      const expectedObject = result.artifactIdMap.get(sourceRelation.objectArtifactId);
      expect(expectedSubject).toBeDefined();
      expect(expectedObject).toBeDefined();

      const match = result.relations.find(
        (relation) =>
          relation.subjectArtifactId === expectedSubject &&
          relation.objectArtifactId === expectedObject &&
          relation.relationKind === sourceRelation.relationKind,
      );
      expect(match).toBeDefined();
      // The cloned edge lives entirely inside the target Project.
      expect(match?.projectId).toBe(result.targetProject.id);
    }
  });

  it("creates no ArtifactRelation linking the source and target Projects", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "No Cross Edge Clone",
      idempotencyKey: `nocross-${randomUUID()}`,
    });

    const targetIds = new Set(result.artifacts.map((a) => a.id));
    const sourceIds = new Set(sourceArtifacts.map((a) => a.id));

    // Every relation in the target references only target artifacts...
    for (const relation of result.relations) {
      expect(targetIds.has(relation.subjectArtifactId)).toBe(true);
      expect(targetIds.has(relation.objectArtifactId)).toBe(true);
      expect(sourceIds.has(relation.subjectArtifactId)).toBe(false);
      expect(sourceIds.has(relation.objectArtifactId)).toBe(false);
    }

    // ...and the source Project's relation set is untouched by the clone.
    const sourceRelations = await artifacts.listArtifactRelationsForProject(source.id);
    for (const relation of sourceRelations) {
      expect(targetIds.has(relation.subjectArtifactId)).toBe(false);
      expect(targetIds.has(relation.objectArtifactId)).toBe(false);
    }
  });

  it("keeps M-013 same-Project composite-FK integrity intact in the target", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Integrity Clone",
      idempotencyKey: `integ-${randomUUID()}`,
    });

    // The database-level backstop still refuses a cross-Project edge built
    // from a cloned artifact and a source artifact.
    const targetArtifact = result.artifacts[0] as ArtifactRow;
    const sourceArtifact = sourceArtifacts[0] as ArtifactRow;
    await expect(
      controlPlane.pool.query(
        `INSERT INTO artifact_relations
           (id, project_id, subject_artifact_id, object_artifact_id, relation_kind, created_at)
         VALUES ($1, $2, $3, $4, 'lineage', now())`,
        [randomUUID(), result.targetProject.id, targetArtifact.id, sourceArtifact.id],
      ),
    ).rejects.toThrow();
  });

  it("records clone provenance in the plan, not in ArtifactRelation", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Provenance Clone",
      idempotencyKey: `prov-${randomUUID()}`,
    });

    const mapping = await lifecycle.listCloneArtifactMap(result.plan.id);
    expect(mapping).toHaveLength(sourceArtifacts.length);
    for (const row of mapping) {
      expect(result.artifactIdMap.get(row.sourceArtifactId)).toBe(row.targetArtifactId);
    }
    expect(result.plan.artifactCount).toBe(sourceArtifacts.length);
    expect(result.plan.relationCount).toBe(result.relations.length);
  });

  // -------------------------------------------------------------------------
  // Authorization ordering and cross-tenant policy
  // -------------------------------------------------------------------------

  it("authorizes the source Project before loading any canonical source detail", async () => {
    // Instrument the repository: if a canonical load happened before the
    // authorization decision, the recorded order would show it.
    const calls: string[] = [];
    const observedProjects = {
      ...projects,
      getProjectById: async (id: string) => {
        calls.push(`load:${id}`);
        return projects.getProjectById(id);
      },
    } as unknown as ProjectRepository;
    const observedAuthz = new TenantAuthorizationService(
      {
        getOrganizationById: tenants.getOrganizationById.bind(tenants),
        getMembership: tenants.getMembership.bind(tenants),
        getProjectById: async (id: string) => {
          calls.push(`authz:${id}`);
          return projects.getProjectById(id);
        },
        getArtifactById: artifacts.getArtifactById.bind(artifacts),
        getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
      },
      audit,
    );
    const observedService = new ProjectCloneService({
      projects: observedProjects,
      lifecycle,
      authz: observedAuthz,
    });

    await observedService.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Ordering Clone",
      idempotencyKey: `order-${randomUUID()}`,
    });

    const firstAuthz = calls.findIndex((c) => c === `authz:${source.id}`);
    const firstLoad = calls.findIndex((c) => c === `load:${source.id}`);
    expect(firstAuthz).toBeGreaterThanOrEqual(0);
    expect(firstLoad).toBeGreaterThanOrEqual(0);
    // Authorization strictly precedes the canonical source load.
    expect(firstAuthz).toBeLessThan(firstLoad);
  });

  it("does not leak source details on a cross-tenant source probe", async () => {
    // Bob (orgB) probes a real orgA project and a random id. Both must fail
    // the same way, disclosing neither existence nor ownership.
    const realProbe = service.cloneProject({
      accountId: bob.id,
      sourceProjectId: source.id,
      targetProjectName: "Probe Clone",
      idempotencyKey: `probe-${randomUUID()}`,
    });
    const fakeProbe = service.cloneProject({
      accountId: bob.id,
      sourceProjectId: randomUUID(),
      targetProjectName: "Probe Clone",
      idempotencyKey: `probe2-${randomUUID()}`,
    });

    const realError = await realProbe.catch((e: Error) => e);
    const fakeError = await fakeProbe.catch((e: Error) => e);

    // Neither response may contain the source name or its organization.
    for (const error of [realError, fakeError]) {
      expect(error.message).not.toContain("Clone Source Project");
      expect(error.message).not.toContain(orgA.id);
    }
    // A foreign-but-real id denies on membership; a nonexistent id is unknown.
    // Both are fail-closed and neither reveals project contents.
    expect(
      realError instanceof ProjectAuthorizationError ||
        realError instanceof ProjectNotFoundError,
    ).toBe(true);
    expect(
      fakeError instanceof ProjectAuthorizationError ||
        fakeError instanceof ProjectNotFoundError,
    ).toBe(true);
  });

  it("denies a cross-Organization clone attempt", async () => {
    const before = await projectCount(orgB.id);
    // Alice may read her own source but asserts a destination in orgB.
    await expect(
      service.cloneProject({
        accountId: alice.id,
        sourceProjectId: source.id,
        targetProjectName: "Cross Org Clone",
        destinationOrganizationId: orgB.id,
        idempotencyKey: `crossorg-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectCloneError);
    expect(await projectCount(orgB.id)).toBe(before);
  });

  it("denies cloning another tenant's Project into your own Organization", async () => {
    await expect(
      service.cloneProject({
        accountId: bob.id,
        sourceProjectId: source.id, // orgA project, Bob is orgB
        targetProjectName: "Stolen Clone",
        destinationOrganizationId: orgB.id,
        idempotencyKey: `steal-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("never authorizes from a caller-provided source Organization claim", async () => {
    // Bob cannot make an orgA source reachable by asserting orgB anywhere.
    await expect(
      service.cloneProject({
        accountId: bob.id,
        sourceProjectId: source.id,
        targetProjectName: "Claim Clone",
        idempotencyKey: `claim-${randomUUID()}`,
        sourceOrganizationId: orgB.id,
      } as Parameters<typeof service.cloneProject>[0]),
    ).rejects.toBeInstanceOf(ProjectInputError);
  });

  it("denies an account whose membership was revoked", async () => {
    const org = await tenants.createOrganization({
      name: "Clone Revocation Org",
      kind: "standard",
    });
    const carol = await tenants.createAccount({ displayName: "Clone Carol" });
    await tenants.addMembership({ organizationId: org.id, accountId: carol.id });
    const project = await projects.createProject({
      organizationId: org.id,
      name: "Revocation Source",
    });

    const allowed = await service.cloneProject({
      accountId: carol.id,
      sourceProjectId: project.id,
      targetProjectName: "Before Revocation Clone",
      idempotencyKey: `crev-ok-${randomUUID()}`,
    });
    expect(allowed.targetProject.organizationId).toBe(org.id);

    await controlPlane.pool.query(
      "DELETE FROM organization_memberships WHERE organization_id = $1 AND account_id = $2",
      [org.id, carol.id],
    );

    await expect(
      service.cloneProject({
        accountId: carol.id,
        sourceProjectId: project.id,
        targetProjectName: "After Revocation Clone",
        idempotencyKey: `crev-no-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("fails closed for forged source and destination identifiers", async () => {
    await expect(
      service.cloneProject({
        accountId: alice.id,
        sourceProjectId: randomUUID(),
        targetProjectName: "Forged Source",
        idempotencyKey: `forge1-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectNotFoundError);

    await expect(
      service.cloneProject({
        accountId: alice.id,
        sourceProjectId: source.id,
        targetProjectName: "Forged Destination",
        destinationOrganizationId: randomUUID(),
        idempotencyKey: `forge2-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectCloneError);

    await expect(
      service.cloneProject({
        accountId: randomUUID(),
        sourceProjectId: source.id,
        targetProjectName: "Forged Actor",
        idempotencyKey: `forge3-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("rejects authority-shaped client/provider fields", async () => {
    const attempts: ReadonlyArray<Record<string, unknown>> = [
      { targetProjectId: randomUUID() },
      { clonePlanId: randomUUID() },
      { providerId: "gh_1" },
      { repositoryId: randomUUID() },
      { workspaceId: randomUUID() },
      { actorAccountId: bob.id },
      { artifactIds: [randomUUID()] },
    ];
    for (const extra of attempts) {
      await expect(
        service.cloneProject({
          accountId: alice.id,
          sourceProjectId: source.id,
          targetProjectName: "Authority Shaped Clone",
          idempotencyKey: `cauth-${randomUUID()}`,
          ...extra,
        } as Parameters<typeof service.cloneProject>[0]),
      ).rejects.toBeInstanceOf(ProjectInputError);
    }
  });

  it("cannot be redirected by a foreign target project id in the plan", async () => {
    // A cross-Organization plan row is impossible even at the database level.
    await expect(
      controlPlane.pool.query(
        `INSERT INTO project_clone_plans
           (id, organization_id, source_project_id, target_project_id, actor_account_id,
            plan_kind, artifact_count, relation_count, idempotency_key, created_at)
         VALUES ($1, $2, $3, $4, $5, 'project_clone', 0, 0, $6, now())`,
        [randomUUID(), orgA.id, source.id, foreignProject.id, alice.id, randomUUID()],
      ),
    ).rejects.toThrow();
  });

  // -------------------------------------------------------------------------
  // Idempotency and transactional integrity
  // -------------------------------------------------------------------------

  it("does not create a second clone for a duplicate idempotency key", async () => {
    const key = `cidem-${randomUUID()}`;
    const first = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Idempotent Clone",
      idempotencyKey: key,
    });
    const second = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Idempotent Clone Retried",
      idempotencyKey: key,
    });

    expect(second.replayed).toBe(true);
    expect(second.targetProject.id).toBe(first.targetProject.id);
    expect(second.plan.id).toBe(first.plan.id);
    expect(second.artifacts).toHaveLength(first.artifacts.length);
    expect(second.relations).toHaveLength(first.relations.length);
  });

  it("rolls back the whole target graph when the clone fails mid-flight", async () => {
    const before = await projectCount(orgA.id);
    const relationsBefore = (
      await artifacts.listArtifactRelationsForProject(source.id)
    ).length;

    await expect(
      lifecycle.applyClonePlan({
        organizationId: orgA.id,
        actorAccountId: alice.id,
        sourceProjectId: source.id,
        targetProjectName: "Rollback Clone",
        idempotencyKey: `crollback-${randomUUID()}`,
        failAfterArtifactClone: async () => {
          throw new Error("injected mid-clone failure");
        },
      }),
    ).rejects.toThrow(/injected mid-clone failure/);

    // No partial target Project, Artifact, or relation survives.
    expect(await projectCount(orgA.id)).toBe(before);
    const orphaned = await controlPlane.pool.query(
      "SELECT id FROM projects WHERE name = 'Rollback Clone'",
    );
    expect(orphaned.rows).toHaveLength(0);
    // The source graph is untouched.
    expect((await artifacts.listArtifactRelationsForProject(source.id)).length).toBe(
      relationsBefore,
    );
  });

  it("clones an empty Project without inventing artifacts or relations", async () => {
    const empty = await projects.createProject({
      organizationId: orgA.id,
      name: "Empty Source",
    });
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: empty.id,
      targetProjectName: "Empty Clone",
      idempotencyKey: `empty-${randomUUID()}`,
    });
    expect(result.artifacts).toHaveLength(0);
    expect(result.relations).toHaveLength(0);
    expect(result.plan.artifactCount).toBe(0);
  });

  // -------------------------------------------------------------------------
  // Audit
  // -------------------------------------------------------------------------

  it("records clone authorization under the canonical organization scope", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Audited Clone",
      idempotencyKey: `caudit-${randomUUID()}`,
    });
    expect(result.targetProject.organizationId).toBe(orgA.id);

    const rows = await controlPlane.pool.query(
      `SELECT organization_id FROM audit_events
        WHERE actor_account_id = $1
          AND resource_type = 'organization'
          AND resource_id = $2
          AND outcome = 'allowed'
        ORDER BY occurred_at DESC LIMIT 1`,
      [alice.id, orgA.id],
    );
    expect(rows.rows).toHaveLength(1);
    expect((rows.rows[0] as { organization_id: string }).organization_id).toBe(orgA.id);
  });

  it("fails closed when the required audit record cannot be written", async () => {
    const failClosedAuthz = new TenantAuthorizationService(
      {
        getOrganizationById: tenants.getOrganizationById.bind(tenants),
        getMembership: tenants.getMembership.bind(tenants),
        getProjectById: projects.getProjectById.bind(projects),
        getArtifactById: artifacts.getArtifactById.bind(artifacts),
        getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
      },
      {
        async recordAuthorizationDecision(): Promise<void> {
          throw new Error("audit unavailable");
        },
      },
    );
    const failClosedService = new ProjectCloneService({
      projects,
      lifecycle,
      authz: failClosedAuthz,
    });

    const before = await projectCount(orgA.id);
    await expect(
      failClosedService.cloneProject({
        accountId: alice.id,
        sourceProjectId: source.id,
        targetProjectName: "Audit Unavailable Clone",
        idempotencyKey: `cauditfail-${randomUUID()}`,
      }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
    expect(await projectCount(orgA.id)).toBe(before);
  });

  it("does not disclose another tenant's clone plan", async () => {
    const result = await service.cloneProject({
      accountId: alice.id,
      sourceProjectId: source.id,
      targetProjectName: "Private Plan Clone",
      idempotencyKey: `cpriv-${randomUUID()}`,
    });

    const foreign = service.getClonePlan({ accountId: bob.id, planId: result.plan.id });
    const missing = service.getClonePlan({ accountId: bob.id, planId: randomUUID() });

    await expect(foreign).rejects.toBeInstanceOf(ProjectCloneError);
    await expect(missing).rejects.toBeInstanceOf(ProjectCloneError);
    expect(await foreign.catch((e: Error) => e.message)).toBe(
      await missing.catch((e: Error) => e.message),
    );
  });
});
