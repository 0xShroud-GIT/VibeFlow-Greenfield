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
  ProjectCapabilityRepository,
  ProjectRepository,
  TenantRepository,
} from "@vibeflow/persistence";
import { AuditService } from "@vibeflow/audit";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ProjectService } from "./service.js";
import { ProjectCapabilityProfileService } from "./capability-profile-service.js";
import { ProjectNotFoundError } from "./errors.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-015 Capability Profile PostgreSQL tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-015 Project Capability Profile service", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projectsRepo: ProjectRepository;
  let capabilitiesRepo: ProjectCapabilityRepository;
  let audit: AuditService;
  let authz: TenantAuthorizationService;
  let projectService: ProjectService;
  let capService: ProjectCapabilityProfileService;

  let alice: AccountRow;
  let bob: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;
  let project: ProjectRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projectsRepo = new ProjectRepository(controlPlane.db);
    capabilitiesRepo = new ProjectCapabilityRepository(controlPlane.db);
    audit = new AuditService(controlPlane.pool);

    const combined = {
      getOrganizationById: tenants.getOrganizationById.bind(tenants),
      getMembership: tenants.getMembership.bind(tenants),
      getProjectById: projectsRepo.getProjectById.bind(projectsRepo),
      getArtifactById: async () => { throw new Error("not needed"); },
      getArtifactRelationById: async () => { throw new Error("not needed"); },
    };

    authz = new TenantAuthorizationService(combined, audit);
    projectService = new ProjectService({ tenants, projects: projectsRepo, authz });
    capService = new ProjectCapabilityProfileService({ capabilities: capabilitiesRepo, authz });

    alice = await tenants.createAccount({ displayName: "Cap Alice" });
    bob = await tenants.createAccount({ displayName: "Cap Bob" });
    orgA = await tenants.createOrganization({ name: "Cap Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Cap Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });

    project = await projectService.createProject({
      accountId: alice.id,
      organizationId: orgA.id,
      name: "Cap Profile Test Project",
    });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("deterministic empty profile", async () => {
    const profile = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: project.id });
    expect(profile.version).toBe(0);
    expect(profile.capabilities).toEqual([]);
  });

  it("authorized read", async () => {
    const profile = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: project.id });
    expect(profile.projectId).toBe(project.id);
  });

  it("normalized replace", async () => {
    const profile = await capService.replaceProjectCapabilityProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 0,
      capabilities: ["runtime/node", "artifact/web", "tooling/typescript"],
    });
    expect(profile.version).toBe(1);
    expect(profile.capabilities).toEqual(["artifact/web", "runtime/node", "tooling/typescript"]);
  });

  it("deterministic returned ordering", async () => {
    const profile = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: project.id });
    expect(profile.capabilities).toEqual(["artifact/web", "runtime/node", "tooling/typescript"]);
  });

  it("duplicate keys canonicalized", async () => {
    const profile = await capService.replaceProjectCapabilityProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 1,
      capabilities: ["runtime/node", "runtime/node", "artifact/web"],
    });
    expect(profile.capabilities).toEqual(["artifact/web", "runtime/node"]);
    expect(profile.version).toBe(2);
  });

  it("malformed token rejected", async () => {
    await expect(
      capService.replaceProjectCapabilityProfile({
        accountId: alice.id,
        projectId: project.id,
        expectedVersion: 2,
        capabilities: ["invalid"],
      }),
    ).rejects.toThrow();
  });

  it("cross-tenant read denied", async () => {
    await expect(
      capService.getProjectCapabilityProfile({ accountId: bob.id, projectId: project.id }),
    ).rejects.toThrow();
  });

  it("cross-tenant update denied", async () => {
    await expect(
      capService.replaceProjectCapabilityProfile({
        accountId: bob.id,
        projectId: project.id,
        expectedVersion: 2,
        capabilities: ["runtime/node"],
      }),
    ).rejects.toThrow();
  });

  it("stale expectedVersion rejected", async () => {
    await expect(
      capService.replaceProjectCapabilityProfile({
        accountId: alice.id,
        projectId: project.id,
        expectedVersion: 999,
        capabilities: ["runtime/node"],
      }),
    ).rejects.toThrow();
  });

  it("random Project id opaque", async () => {
    const unknown = randomUUID();
    await expect(
      capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: unknown }),
    ).rejects.toBeInstanceOf(ProjectNotFoundError);
  });
});
