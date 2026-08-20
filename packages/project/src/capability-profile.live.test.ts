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
import { ProjectNotFoundError, ProjectCapabilityProfileError } from "./errors.js";

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

  it("deterministic empty profile returns version 0", async () => {
    const profile = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: project.id });
    expect(profile.version).toBe(0);
    expect(profile.capabilities).toEqual([]);
  });

  it("authorized read", async () => {
    const profile = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: project.id });
    expect(profile.projectId).toBe(project.id);
  });

  it("normalized replace (0 -> nonempty -> version 1", async () => {
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
    expect(profile.version).toBe(1);
  });

  it("nonempty -> empty -> version remains monotonic (2)", async () => {
    let profile = await capService.replaceProjectCapabilityProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 1,
      capabilities: [],
    });
    expect(profile.version).toBe(2);
    expect(profile.capabilities).toEqual([]);

    // Read back: empty but version remains 2
    profile = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: project.id });
    expect(profile.version).toBe(2);
    expect(profile.capabilities).toEqual([]);
  });

  it("empty -> nonempty continues from prior version (3)", async () => {
    const profile = await capService.replaceProjectCapabilityProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 2,
      capabilities: ["runtime/node"],
    });
    expect(profile.version).toBe(3);
    expect(profile.capabilities).toEqual(["runtime/node"]);
  });

  it("stale expectedVersion (0) after nonempty fails", async () => {
    await expect(
      capService.replaceProjectCapabilityProfile({
        accountId: alice.id,
        projectId: project.id,
        expectedVersion: 0,
        capabilities: ["runtime/node"],
      }),
    ).rejects.toBeInstanceOf(ProjectCapabilityProfileError);
    // Version should still be 3
    const profile = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: project.id });
    expect(profile.version).toBe(3);
  });

  it("duplicate keys canonicalized", async () => {
    const profile = await capService.replaceProjectCapabilityProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 3,
      capabilities: ["runtime/node", "runtime/node", "artifact/web"],
    });
    expect(profile.capabilities).toEqual(["artifact/web", "runtime/node"]);
    expect(profile.version).toBe(4);
  });

  it("malformed token rejected", async () => {
    await expect(
      capService.replaceProjectCapabilityProfile({
        accountId: alice.id,
        projectId: project.id,
        expectedVersion: 4,
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
        expectedVersion: 4,
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

  it("concurrent expectedVersion race has exactly one winner", async () => {
    // Create a separate project for this test
    const raceProject = await projectService.createProject({
      accountId: alice.id,
      organizationId: orgA.id,
      name: "Race Test Project",
    });

    // Get current version (should be 0)
    const before = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: raceProject.id });
    expect(before.version).toBe(0);

    // Launch two concurrent replacements with expectedVersion 0
    const p1 = capService.replaceProjectCapabilityProfile({
      accountId: alice.id,
      projectId: raceProject.id,
      expectedVersion: 0,
      capabilities: ["runtime/one"],
    });

    const p2 = capService.replaceProjectCapabilityProfile({
      accountId: alice.id,
      projectId: raceProject.id,
      expectedVersion: 0,
      capabilities: ["runtime/two"],
    });

    const results = await Promise.allSettled([p1, p2]);

    const fulfilled = results.filter(r => r.status === "fulfilled");
    const rejected = results.filter(r => r.status === "rejected");

    // Exactly one should succeed
    expect(fulfilled.length).toBe(1);
    expect(rejected.length).toBe(1);

    // The successful write consumed version 0 -> 1
    const after = await capService.getProjectCapabilityProfile({ accountId: alice.id, projectId: raceProject.id });
    expect(after.version).toBe(1);

    // The rejected one should be a StaleVersionError
    if (rejected[0] && rejected[0].status === "rejected") {
      expect(rejected[0].reason).toBeInstanceOf(ProjectCapabilityProfileError);
    }
  });
});