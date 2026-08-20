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
import { ProjectError, ProjectNotFoundError, ProjectProfileError } from "./errors.js";

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

  it("update description only preserves cover", async () => {
    // First set both description and cover
    await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 1,
      description: "With cover",
      coverArtifactId: artifact.id,
    });

    // Now update only description (coverArtifactId undefined)
    const profile = await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 2,
      description: "Updated description only",
    });
    expect(profile.description).toBe("Updated description only");
    expect(profile.coverArtifactId).toBe(artifact.id);
  });

  it("update cover only preserves description", async () => {
    const profile = await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 3,
      coverArtifactId: null,  // clear cover
    });
    expect(profile.description).toBe("Updated description only");
    expect(profile.coverArtifactId).toBeNull();
  });

  it("explicit null clears description", async () => {
    const profile = await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 4,
      description: null,
    });
    expect(profile.description).toBeNull();
  });

  it("set same-Project cover Artifact", async () => {
    const profile = await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 5,
      coverArtifactId: artifact.id,
    });
    expect(profile.version).toBe(6);
    expect(profile.coverArtifactId).toBe(artifact.id);
  });

  it("explicit null clears cover", async () => {
    const profile = await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: project.id,
      expectedVersion: 6,
      coverArtifactId: null,
    });
    expect(profile.version).toBe(7);
    expect(profile.coverArtifactId).toBeNull();
  });

  it("cross-tenant Project profile read is opaque", async () => {
    await expect(
      profileService.getProjectProfile({ accountId: bob.id, projectId: project.id }),
    ).rejects.toThrow();
  });

  it("cross-tenant Project profile update denied", async () => {
    await expect(
      profileService.updateProjectProfile({ accountId: bob.id, projectId: project.id, expectedVersion: 7, description: "hacked" }),
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
        expectedVersion: 7,
        description: "x".repeat(5001),
      }),
    ).rejects.toThrow(ProjectError);
  });

  it("concurrent initial expectedVersion=0 has exactly one winner", async () => {
    const raceProject = await projectService.createProject({
      accountId: alice.id,
      organizationId: orgA.id,
      name: "Profile Race Test",
    });

    // Two concurrent upserts with expectedVersion=0
    const p1 = profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: raceProject.id,
      expectedVersion: 0,
      description: "Winner 1",
    });

    const p2 = profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: raceProject.id,
      expectedVersion: 0,
      description: "Winner 2",
    });

    const results = await Promise.allSettled([p1, p2]);
    const fulfilled = results.filter(r => r.status === "fulfilled");
    const rejected = results.filter(r => r.status === "rejected");

    expect(fulfilled.length).toBe(1);
    expect(rejected.length).toBe(1);

    const after = await profileService.getProjectProfile({ accountId: alice.id, projectId: raceProject.id });
    expect(after.version).toBe(1);
  });

  it("empty historical profile rejects stale version 0", async () => {
    // After the race test, the profile has version 1. Using 0 should fail.
    const raceProject = await projectService.createProject({
      accountId: alice.id,
      organizationId: orgA.id,
      name: "Stale Reject Test",
    });
    // Create it first with version 0
    await profileService.updateProjectProfile({
      accountId: alice.id,
      projectId: raceProject.id,
      expectedVersion: 0,
      description: "Initial",
    });
    // Now try with version 0 again - should fail
    await expect(
      profileService.updateProjectProfile({
        accountId: alice.id,
        projectId: raceProject.id,
        expectedVersion: 0,
        description: "Stale attempt",
      }),
    ).rejects.toThrow(ProjectProfileError);
  });
});