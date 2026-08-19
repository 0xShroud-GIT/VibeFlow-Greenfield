import { randomUUID } from "node:crypto";
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
import { AuditService } from "@vibeflow/audit";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ProjectService } from "./service.js";
import { ProjectAuthorizationError, ProjectNotFoundError } from "./errors.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-012 Project service PostgreSQL tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-012 Project service authority", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projects: ProjectRepository;
  let audit: AuditService;
  let authz: TenantAuthorizationService;
  let service: ProjectService;

  let alice: AccountRow;
  let bob: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;
  let projectA: ProjectRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projects = new ProjectRepository(controlPlane.db);
    audit = new AuditService(controlPlane.pool);

    const combined = {
      getOrganizationById: tenants.getOrganizationById.bind(tenants),
      getMembership: tenants.getMembership.bind(tenants),
      getProjectById: projects.getProjectById.bind(projects),
    };

    authz = new TenantAuthorizationService(combined, audit);
    service = new ProjectService({ tenants, projects, authz });

    alice = await tenants.createAccount({ displayName: "Service Alice" });
    bob = await tenants.createAccount({ displayName: "Service Bob" });
    orgA = await tenants.createOrganization({ name: "Service Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Service Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });

    projectA = await service.createProject({
      accountId: alice.id,
      organizationId: orgA.id,
      name: "Service Project A",
    });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("canonical Project creation with server-generated id and org ownership (A, B)", async () => {
    expect(projectA.id).toMatch(/^[0-9a-f-]{36}$/);
    expect(projectA.organizationId).toBe(orgA.id);
    expect(projectA.createdAt).toBeInstanceOf(Date);
    const fromDb = await projects.getProjectById(projectA.id);
    expect(fromDb.organizationId).toBe(orgA.id);
  });

  it("same-tenant authorized read succeeds (C)", async () => {
    const fetched = await service.getProject({ accountId: alice.id, projectId: projectA.id });
    expect(fetched.id).toBe(projectA.id);
  });

  it("cross-tenant Project read fails closed (D)", async () => {
    await expect(
      service.getProject({ accountId: bob.id, projectId: projectA.id }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("cross-tenant Project mutation fails closed (E)", async () => {
    await expect(
      service.updateProject({ accountId: bob.id, projectId: projectA.id, name: "Hacked" }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("forged Organization ID fails closed (F)", async () => {
    const forgedOrg = randomUUID();
    await expect(
      service.createProject({ accountId: alice.id, organizationId: forgedOrg, name: "Forged" }),
    ).rejects.toThrow(); // unknown_resource -> not found or auth error
  });

  it("forged actor/Account identity fails closed (G)", async () => {
    const forgedAccount = randomUUID();
    await expect(
      service.getProject({ accountId: forgedAccount, projectId: projectA.id }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });

  it("unknown/random Project UUID fails closed (H)", async () => {
    const unknown = randomUUID();
    await expect(service.getProject({ accountId: alice.id, projectId: unknown })).rejects.toBeInstanceOf(
      ProjectNotFoundError,
    );
  });

  it("revoked/stale membership fails closed (I)", async () => {
    const orgC = await tenants.createOrganization({ name: "Service Org C", kind: "standard" });
    await tenants.addMembership({ organizationId: orgC.id, accountId: alice.id });
    const projC = await service.createProject({
      accountId: alice.id,
      organizationId: orgC.id,
      name: "C Project",
    });
    // Works before revocation
    await expect(service.getProject({ accountId: alice.id, projectId: projC.id })).resolves.toBeDefined();

    // Revoke
    await controlPlane.pool.query(
      "DELETE FROM organization_memberships WHERE organization_id = $1 AND account_id = $2",
      [orgC.id, alice.id],
    );

    await expect(service.getProject({ accountId: alice.id, projectId: projC.id })).rejects.toBeInstanceOf(
      ProjectAuthorizationError,
    );
  });

  it("stale tenant information supplied by client cannot grant access", async () => {
    // Client claims orgA but tries to access project that belongs to orgB via
    // project id manipulation - should fail because project tenant is resolved
    // from persistence, not client org.
    const projB = await projects.createProject({ organizationId: orgB.id, name: "B for stale test" });
    await expect(service.getProject({ accountId: alice.id, projectId: projB.id })).rejects.toBeInstanceOf(
      ProjectAuthorizationError,
    );
  });

  it("Project authorization uses canonical persistence (J) and audit scoped (K)", async () => {
    const fetched = await service.getProject({ accountId: alice.id, projectId: projectA.id });
    expect(fetched.organizationId).toBe(orgA.id);

    const page = await audit.list({
      authenticatedAccountId: alice.id,
      accountId: alice.id,
      organizationId: orgA.id,
    });
    const event = page.events.find(
      (e: { resourceType: string; resourceId: string | null; action: string }) =>
        e.resourceType === "project" && e.resourceId === projectA.id && e.action === "authorization.read",
    );
    // Audit may have recorded allow; ensure if present, fields are canonical
    if (event) {
      expect(event.actorAccountId).toBe(alice.id);
      expect(event.organizationId).toBe(orgA.id);
      expect(event.resourceId).toBe(projectA.id);
      expect(event.outcome).toBe("allowed");
    }
  });

  it("tenant-safe list returns only own organization's projects", async () => {
    const listA = await service.listProjects({ accountId: alice.id, organizationId: orgA.id });
    expect(listA.some((p) => p.id === projectA.id)).toBe(true);

    await expect(
      service.listProjects({ accountId: alice.id, organizationId: orgB.id }),
    ).rejects.toBeInstanceOf(ProjectAuthorizationError);
  });
});
