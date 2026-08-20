import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  ArtifactRepository,
  createControlPlanePool,
  defaultMigrationsDirectory,
  ProjectRepository,
  TenantRepository,
  type AccountRow,
  type ControlPlanePool,
  type OrganizationRow,
  type ProjectRow,
} from "@vibeflow/persistence";
import { AuditService } from "@vibeflow/audit";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ArtifactService } from "./artifact-service.js";
import {
  ArtifactAuthorizationError,
  ArtifactInputError,
  ArtifactNotFoundError,
  ArtifactRelationError,
} from "./errors.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-013 Artifact service PostgreSQL tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-013 Artifact/ArtifactRelation service authority", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let artifacts: ArtifactRepository;
  let audit: AuditService;
  let authz: TenantAuthorizationService;
  let service: ArtifactService;

  let alice: AccountRow;
  let bob: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;
  let projectA: ProjectRow;
  let projectA2: ProjectRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    artifacts = new ArtifactRepository(controlPlane.db);
    audit = new AuditService(controlPlane.pool);

    const combined = {
      getOrganizationById: tenants.getOrganizationById.bind(tenants),
      getMembership: tenants.getMembership.bind(tenants),
      getProjectById: projects.getProjectById.bind(projects),
      getArtifactById: artifacts.getArtifactById.bind(artifacts),
      getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
    };

    authz = new TenantAuthorizationService(combined, audit);
    service = new ArtifactService({ artifacts, authz });

    alice = await tenants.createAccount({ displayName: "Artifact Svc Alice" });
    bob = await tenants.createAccount({ displayName: "Artifact Svc Bob" });
    orgA = await tenants.createOrganization({ name: "Artifact Svc Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Artifact Svc Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });
    projectA = await projects.createProject({ organizationId: orgA.id, name: "Artifact Svc Project A" });
    projectA2 = await projects.createProject({ organizationId: orgA.id, name: "Artifact Svc Project A2" });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("canonical Artifact creation with server-generated id and Project ownership", async () => {
    const artifact = await service.createArtifact({
      accountId: alice.id,
      projectId: projectA.id,
      type: "website",
    });
    expect(artifact.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(artifact.projectId).toBe(projectA.id);
    expect(artifact.type).toBe("website");
    expect(artifact.createdAt).toBeInstanceOf(Date);
  });

  it("Artifact type is a syntax-validated opaque token (positive and negative)", async () => {
    // Namespaced/compound opaque token accepted and canonicalized.
    const ok = await service.createArtifact({
      accountId: alice.id,
      projectId: projectA.id,
      type: "  com.acme.website:v2  ",
    });
    expect(ok.type).toBe("com.acme.website:v2");

    // Malformed tokens are rejected at the service boundary.
    for (const bad of ["", "   ", "two words", "a\nb", ".leading", "trailing.", "a+b", "🙂"]) {
      await expect(
        service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: bad }),
      ).rejects.toBeInstanceOf(ArtifactInputError);
    }
  });

  it("same-tenant authorized read succeeds", async () => {
    const artifact = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "slides" });
    const fetched = await service.getArtifact({ accountId: alice.id, artifactId: artifact.id });
    expect(fetched.id).toBe(artifact.id);
  });

  it("cross-tenant Artifact read fails closed", async () => {
    const artifact = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "report" });
    await expect(
      service.getArtifact({ accountId: bob.id, artifactId: artifact.id }),
    ).rejects.toBeInstanceOf(ArtifactAuthorizationError);
  });

  it("cross-tenant Artifact creation under another Project fails closed", async () => {
    await expect(
      service.createArtifact({ accountId: bob.id, projectId: projectA.id, type: "hacked" }),
    ).rejects.toBeInstanceOf(ArtifactAuthorizationError);
  });

  it("forged Project ID fails closed", async () => {
    await expect(
      service.createArtifact({ accountId: alice.id, projectId: randomUUID(), type: "forged" }),
    ).rejects.toThrow();
  });

  it("forged actor/Account identity fails closed", async () => {
    const artifact = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "data" });
    await expect(
      service.getArtifact({ accountId: randomUUID(), artifactId: artifact.id }),
    ).rejects.toBeInstanceOf(ArtifactAuthorizationError);
  });

  it("unknown/random Artifact UUID fails closed", async () => {
    await expect(
      service.getArtifact({ accountId: alice.id, artifactId: randomUUID() }),
    ).rejects.toBeInstanceOf(ArtifactNotFoundError);
  });

  it("revoked/stale membership fails closed", async () => {
    const artifact = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "revoked" });
    await controlPlane.pool.query(
      "DELETE FROM organization_memberships WHERE organization_id = $1 AND account_id = $2",
      [orgA.id, alice.id],
    );
    await expect(
      service.getArtifact({ accountId: alice.id, artifactId: artifact.id }),
    ).rejects.toBeInstanceOf(ArtifactAuthorizationError);
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
  });

  it("Artifact authorization derives Project/Organization from persistence", async () => {
    const artifact = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "derived" });
    const fetched = await service.getArtifact({ accountId: alice.id, artifactId: artifact.id });
    expect(fetched.projectId).toBe(projectA.id);

    const page = await audit.list({
      authenticatedAccountId: alice.id,
      accountId: alice.id,
      organizationId: orgA.id,
    });
    const event = page.events.find(
      (e: { resourceType: string; resourceId: string | null; action: string }) =>
        e.resourceType === "artifact" && e.resourceId === artifact.id && e.action === "authorization.read",
    );
    if (event) {
      expect(event.actorAccountId).toBe(alice.id);
      expect(event.organizationId).toBe(orgA.id);
      expect(event.outcome).toBe("allowed");
    }
  });

  it("valid same-Project relation persists", async () => {
    const subject = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "design" });
    const object = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "app" });
    const relation = await service.createArtifactRelation({
      accountId: alice.id,
      subjectArtifactId: subject.id,
      objectArtifactId: object.id,
      relationKind: "derived-from",
    });
    expect(relation.projectId).toBe(projectA.id);
  });

  it("unknown relation object endpoint fails closed", async () => {
    const subject = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "x" });
    await expect(
      service.createArtifactRelation({
        accountId: alice.id,
        subjectArtifactId: subject.id,
        objectArtifactId: randomUUID(),
        relationKind: "contains",
      }),
    ).rejects.toBeInstanceOf(ArtifactNotFoundError);
  });

  it("unknown/forged relation subject endpoint fails closed", async () => {
    const object = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "y" });
    await expect(
      service.createArtifactRelation({
        accountId: alice.id,
        subjectArtifactId: randomUUID(),
        objectArtifactId: object.id,
        relationKind: "contains",
      }),
    ).rejects.toBeInstanceOf(ArtifactNotFoundError);
  });

  it("cross-Project relation fails even when both Projects belong to the same Organization", async () => {
    const subject = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "p1" });
    const object = await service.createArtifact({ accountId: alice.id, projectId: projectA2.id, type: "p2" });
    await expect(
      service.createArtifactRelation({
        accountId: alice.id,
        subjectArtifactId: subject.id,
        objectArtifactId: object.id,
        relationKind: "lineage",
      }),
    ).rejects.toBeInstanceOf(ArtifactRelationError);
  });

  it("cross-tenant relation fails closed at the endpoint authorization boundary", async () => {
    // alice (orgA) attempts a relation whose object belongs to bob's orgB
    // project. Authorization of the foreign object endpoint must fail closed
    // BEFORE any same-project/relationship logic runs, so no cross-project or
    // endpoint relationship detail is disclosed.
    const subject = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "ct-s" });
    const projectB = await projects.createProject({ organizationId: orgB.id, name: "Artifact Svc Project B" });
    const object = await artifacts.createArtifact({ projectId: projectB.id, type: "ct-o" });
    await expect(
      service.createArtifactRelation({
        accountId: alice.id,
        subjectArtifactId: subject.id,
        objectArtifactId: object.id,
        relationKind: "variant",
      }),
    ).rejects.toBeInstanceOf(ArtifactAuthorizationError);
  });

  it("a caller probing a foreign-tenant Artifact does not learn endpoint/project existence before authorization", async () => {
    // alice owns two same-Project artifacts. bob (orgB) probes BOTH by their
    // opaque ids. The subject endpoint authorization must fail closed with an
    // authorization denial (no_membership), never a not-found and never a
    // same-project/cross-project relationship error — so bob learns nothing
    // about endpoint existence or their shared Project.
    const subject = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "probe-s" });
    const object = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "probe-o" });

    await expect(
      service.createArtifactRelation({
        accountId: bob.id,
        subjectArtifactId: subject.id,
        objectArtifactId: object.id,
        relationKind: "lineage",
      }),
    ).rejects.toBeInstanceOf(ArtifactAuthorizationError);
  });

  it("revoked membership fails closed for relation creation", async () => {
    const subject = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "rev-s" });
    const object = await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "rev-o" });
    await controlPlane.pool.query(
      "DELETE FROM organization_memberships WHERE organization_id = $1 AND account_id = $2",
      [orgA.id, alice.id],
    );
    await expect(
      service.createArtifactRelation({
        accountId: alice.id,
        subjectArtifactId: subject.id,
        objectArtifactId: object.id,
        relationKind: "derived-from",
      }),
    ).rejects.toBeInstanceOf(ArtifactAuthorizationError);
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
  });

  it("forged relation ID fails closed", async () => {
    await expect(
      service.getArtifactRelation({ accountId: alice.id, relationId: randomUUID() }),
    ).rejects.toBeInstanceOf(ArtifactNotFoundError);
  });

  it("tenant-safe list returns only own project's artifacts", async () => {
    await service.createArtifact({ accountId: alice.id, projectId: projectA.id, type: "listable" });
    const list = await service.listArtifacts({ accountId: alice.id, projectId: projectA.id });
    expect(list.every((a) => a.projectId === projectA.id)).toBe(true);
    await expect(
      service.listArtifacts({ accountId: alice.id, projectId: projectA2.id }),
    ).resolves.toBeDefined();
    await expect(
      service.listArtifacts({ accountId: bob.id, projectId: projectA.id }),
    ).rejects.toBeInstanceOf(ArtifactAuthorizationError);
  });
});
