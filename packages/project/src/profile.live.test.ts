import { randomUUID } from "node:crypto";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

import {
  applyCommittedSqlMigrations,
  createControlPlanePool,
  defaultMigrationsDirectory,
  type AccountRow,
  type ArtifactRow,
  type ControlPlanePool,
  type OrganizationRow,
  type ProjectRow,
  ArtifactRepository,
  ProjectProfileRepository,
  ProjectRepository,
  TenantRepository,
} from "@vibeflow/persistence";
import { AuditService } from "@vibeflow/audit";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ProjectService } from "./service.js";
import { ArtifactService } from "./artifact-service.js";
import { ProjectProfileService, type ProjectProfileResult } from "./profile-service.js";
import { ProjectError, ProjectNotFoundError } from "./errors.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-015 Project Profile PostgreSQL tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-015 Project Profile service", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projectsRepo: ProjectRepository;
  let artifactsRepo: ArtifactRepository;
  let profilesRepo: ProjectProfileRepository;
  let audit: AuditService;
  let authz: TenantAuthorizationService;
  let projectService: ProjectService;
  let artifactService: ArtifactService;
  let profileService: ProjectProfileService;

  let alice: AccountRow;
  let bob: AccountRow;
  let orgA: OrganizationRow;
  let orgB: OrganizationRow;
  let project: ProjectRow;
  let artifact: ArtifactRow;

  beforeAll(async () => {
    controlPlane = createControlPlanePool(connectionString as string);
    await applyCommittedSqlMigrations(controlPlane.pool, defaultMigrationsDirectory());
    tenants = new TenantRepository(controlPlane.db);
    projectsRepo = new ProjectRepository(controlPlane.db);
    artifactsRepo = new ArtifactRepository(controlPlane.db);
    profilesRepo = new ProjectProfileRepository(controlPlane.db);
    audit = new AuditService(controlPlane.pool);

    const combined = {
      getOrganizationById: tenants.getOrganizationById.bind(tenants),
      getMembership: tenants.getMembership.bind(tenants),
      getProjectById: projectsRepo.getProjectById.bind(projectsRepo),
      getArtifactById: artifactsRepo.getArtifactById.bind(artifactsRepo),
      getArtifactRelationById: async () => { throw new Error("not needed"); },
    };

    authz = new TenantAuthorizationService(combined, audit);
    projectService = new ProjectService({ tenants, projects: projectsRepo, authz });
    artifactService = new ArtifactService({ artifacts: artifactsRepo, authz });
    profileService = new ProjectProfileService({ profiles: profilesRepo, artifacts: artifactsRepo, authz });

    alice = await tenants.createAccount({ displayName: "Profile Alice" });
    bob = await tenants.createAccount({ displayName: "Profile Bob" });
    orgA = await tenants.createOrganization({ name: "Profile Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Profile Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });

    project = await projectService.createProject({
      accountId: alice.id,
      organizationId: orgA.id,
      name: "Profile Test Project",
    });

    artifact = await artifactService.createArtifact({
      accountId: alice.id,
      projectId: project.id,
      type: "test/cover",
    });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("returns deterministic empty profile when no row exists", async () => {
    const profile = await profileService.getProjectProfile({ accountId: alice.id, projectId: project.id });
    expect(profile.version).toBe(0);
    expect(profile.description).toBeNull();
    expect(profile.coverArtifactId).toBeNull();
  });

  it("authorized description update", async () => {
    const profile = await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 0,
      description: "My project description",
    });
    expect(profile.version).toBe(1);
    expect(profile.description).toBe("My project description");
  });

  it("set same-Project cover Artifact", async () => {
    const profile = await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 1,
      coverArtifactId: artifact.id,
    });
    expect(profile.version).toBe(2);
    expect(profile.coverArtifactId).toBe(artifact.id);
  });

  it("remove cover", async () => {
    const profile = await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 2,
      coverArtifactId: null,
    });
    expect(profile.version).toBe(3);
    expect(profile.coverArtifactId).toBeNull();
  });

  it("cross-tenant Project profile read is opaque", async () => {
    await expect(
      profileService.getProjectProfile({ accountId: bob.id, projectId: project.id }),
    ).rejects.toThrow();
  });

  it("cross-tenant Project profile update denied", async () => {
    await expect(
      profileService.updateProjectProfile({ accountId: bob.id, projectId: project.id, expectedVersion: 3, description: "hacked" }),
    ).rejects.toThrow();
  });

  it("unknown Project id opaque on read", async () => {
    const unknown = randomUUID();
    await expect(
      profileService.getProjectProfile({ accountId: alice.id, projectId: unknown }),
    ).rejects.toBeInstanceOf(ProjectNotFoundError);
  });

  it("stale version rejected", async () => {
    await expect(
      profileService.updateProjectProfile({
        accountId: alice.id,
        projectId: project.id,
        expectedVersion: 999,
        description: "stale",
      }),
    ).rejects.toThrow();
  });

  it("malformed description rejected", async () => {
    await expect(
      profileService.updateProjectProfile({
        accountId: alice.id,
        projectId: project.id,
        expectedVersion: 3,
        description: "x".repeat(5001),
      }),
    ).rejects.toThrow(ProjectError);
  });
});
