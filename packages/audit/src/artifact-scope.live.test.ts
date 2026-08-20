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
import { TenantAuthorizationService, deny } from "@vibeflow/authorization";

import { AuditService, type AuditDatabase } from "./service.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];
if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-013 Artifact audit fail-closed regression requires DATABASE_URL in CI");
}
const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-013 Artifact/ArtifactRelation authorization audit scope failure", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let artifacts: ArtifactRepository;
  let alice: AccountRow;
  let organization: OrganizationRow;
  let project: ProjectRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    artifacts = new ArtifactRepository(controlPlane.db);
    alice = await tenants.createAccount({ displayName: "Artifact Audit Alice" });
    organization = await tenants.createOrganization({ name: "Artifact Audit Org", kind: "standard" });
    await tenants.addMembership({ organizationId: organization.id, accountId: alice.id });
    project = await projects.createProject({ organizationId: organization.id, name: "Artifact Audit Project" });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("turns an otherwise-allowed Artifact decision into audit_unavailable when canonical scope resolution fails", async () => {
    const artifact = await artifacts.createArtifact({ projectId: project.id, type: "website" });
    const faultingDatabase: AuditDatabase = {
      async query(text, values) {
        if (text.includes("FROM artifacts a JOIN projects p")) {
          throw new Error("forced Artifact audit scope resolution failure");
        }
        const result = await controlPlane.pool.query(text, values);
        return { rows: result.rows as unknown[] };
      },
    };
    const audit = new AuditService(faultingDatabase);
    const authority = {
      getOrganizationById: tenants.getOrganizationById.bind(tenants),
      getMembership: tenants.getMembership.bind(tenants),
      getProjectById: projects.getProjectById.bind(projects),
      getArtifactById: artifacts.getArtifactById.bind(artifacts),
      getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
    };
    const authorization = new TenantAuthorizationService(authority, audit);

    await expect(
      authorization.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "artifact", id: artifact.id },
      }),
    ).resolves.toEqual(deny("audit_unavailable"));

    const rows = await controlPlane.pool.query<{ count: string }>(
      "SELECT count(*)::text AS count FROM audit_events WHERE resource_type = 'artifact' AND resource_id = $1 AND outcome = 'allowed'",
      [artifact.id],
    );
    expect(rows.rows[0]?.count).toBe("0");
  });

  it("turns an otherwise-allowed ArtifactRelation decision into audit_unavailable when canonical scope resolution fails", async () => {
    const subject = await artifacts.createArtifact({ projectId: project.id, type: "design" });
    const object = await artifacts.createArtifact({ projectId: project.id, type: "app" });
    const relation = await artifacts.createArtifactRelation({
      subjectArtifactId: subject.id,
      objectArtifactId: object.id,
      relationKind: "derived-from",
    });
    const faultingDatabase: AuditDatabase = {
      async query(text, values) {
        if (text.includes("FROM artifact_relations r JOIN projects p")) {
          throw new Error("forced ArtifactRelation audit scope resolution failure");
        }
        const result = await controlPlane.pool.query(text, values);
        return { rows: result.rows as unknown[] };
      },
    };
    const audit = new AuditService(faultingDatabase);
    const authority = {
      getOrganizationById: tenants.getOrganizationById.bind(tenants),
      getMembership: tenants.getMembership.bind(tenants),
      getProjectById: projects.getProjectById.bind(projects),
      getArtifactById: artifacts.getArtifactById.bind(artifacts),
      getArtifactRelationById: artifacts.getArtifactRelationById.bind(artifacts),
    };
    const authorization = new TenantAuthorizationService(authority, audit);

    await expect(
      authorization.authorize({
        accountId: alice.id,
        action: "read",
        resource: { type: "artifact_relation", id: relation.id },
      }),
    ).resolves.toEqual(deny("audit_unavailable"));

    const rows = await controlPlane.pool.query<{ count: string }>(
      "SELECT count(*)::text AS count FROM audit_events WHERE resource_type = 'artifact_relation' AND resource_id = $1 AND outcome = 'allowed'",
      [relation.id],
    );
    expect(rows.rows[0]?.count).toBe("0");
  });
});
