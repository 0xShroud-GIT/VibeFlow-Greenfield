import { afterAll, beforeAll, describe, expect, it } from "vitest";
import {
  applyCommittedSqlMigrations,
  createControlPlanePool,
  defaultMigrationsDirectory,
  type AccountRow,
  type ControlPlanePool,
  type OrganizationRow,
  type ProjectRow,
  ProjectRepository,
  TenantRepository,
} from "@vibeflow/persistence";
import { TenantAuthorizationService, deny } from "@vibeflow/authorization";

import { AuditService, type AuditDatabase } from "./service.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];
if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-012 Project audit fail-closed regression requires DATABASE_URL in CI");
}
const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-012 Project authorization audit scope failure", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let alice: AccountRow;
  let organization: OrganizationRow;
  let project: ProjectRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    alice = await tenants.createAccount({ displayName: "Audit Scope Alice" });
    organization = await tenants.createOrganization({ name: "Audit Scope Org", kind: "standard" });
    await tenants.addMembership({ organizationId: organization.id, accountId: alice.id });
    project = await projects.createProject({ organizationId: organization.id, name: "Audit Scope Project" });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("turns an otherwise-allowed Project decision into audit_unavailable when canonical audit scope resolution fails", async () => {
    const faultingDatabase: AuditDatabase = {
      async query(text, values) {
        if (text.includes("SELECT organization_id FROM projects WHERE id = $1")) {
          throw new Error("forced Project audit scope resolution failure");
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
    };
    const authorization = new TenantAuthorizationService(authority, audit);

    await expect(authorization.authorize({
      accountId: alice.id,
      action: "read",
      resource: { type: "project", id: project.id },
    })).resolves.toEqual(deny("audit_unavailable"));

    const rows = await controlPlane.pool.query<{ count: string }>(
      "SELECT count(*)::text AS count FROM audit_events WHERE resource_type = 'project' AND resource_id = $1 AND outcome = 'allowed'",
      [project.id],
    );
    expect(rows.rows[0]?.count).toBe("0");
  });
});
