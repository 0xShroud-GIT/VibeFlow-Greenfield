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
  ArtifactRepository,
  ProjectCapabilityRepository,
  ProjectProfileRepository,
  ProjectRepository,
  TenantRepository,
} from "@vibeflow/persistence";
import { AuditService } from "@vibeflow/audit";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ProjectService } from "./service.js";
import { ArtifactService } from "./artifact-service.js";
import { ProjectProfileService } from "./profile-service.js";
import { ProjectCapabilityProfileService } from "./capability-profile-service.js";
import { ProjectOverviewService } from "./overview-service.js";
import { ProjectImportService } from "./import-service.js";
import { ProjectCloneService } from "./clone-service.js";
import { ProjectNotFoundError } from "./errors.js";

const connectionString = process.env["VIBEFLOW_DATABASE_URL"] ?? process.env["DATABASE_URL"];

if (connectionString === undefined && process.env["CI"] === "true") {
  throw new Error("M-015 Project Overview PostgreSQL tests require DATABASE_URL in CI");
}

const describePostgres = connectionString === undefined ? describe.skip : describe;

describePostgres("M-015 Project Overview service", () => {
  let controlPlane: ControlPlanePool;
  let tenants: TenantRepository;
  let projectsRepo: ProjectRepository;
  let artifactsRepo: ArtifactRepository;
  let profilesRepo: ProjectProfileRepository;
  let capabilitiesRepo: ProjectCapabilityRepository;
  let audit: AuditService;
  let authz: TenantAuthorizationService;
  let projectService: ProjectService;
  let artifactService: ArtifactService;
  let profileService: ProjectProfileService;
  let capService: ProjectCapabilityProfileService;
  let overviewService: ProjectOverviewService;

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
    artifactsRepo = new ArtifactRepository(controlPlane.db);
    profilesRepo = new ProjectProfileRepository(controlPlane.db);
    capabilitiesRepo = new ProjectCapabilityRepository(controlPlane.db);
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
    capService = new ProjectCapabilityProfileService({ capabilities: capabilitiesRepo, authz });

    alice = await tenants.createAccount({ displayName: "Overview Alice" });
    bob = await tenants.createAccount({ displayName: "Overview Bob" });
    orgA = await tenants.createOrganization({ name: "Overview Org A", kind: "standard" });
    orgB = await tenants.createOrganization({ name: "Overview Org B", kind: "standard" });
    await tenants.addMembership({ organizationId: orgA.id, accountId: alice.id });
    await tenants.addMembership({ organizationId: orgB.id, accountId: bob.id });

    project = await projectService.createProject({
      accountId: alice.id,
      organizationId: orgA.id,
      name: "Overview Test Project",
    });
  });

  afterAll(async () => {
    await controlPlane.close();
  });

  it("authorized empty Project overview", async () => {
    const overview = await overviewService.getProjectOverview({ accountId: alice.id, projectId: project.id });
    expect(overview.project.id).toBe(project.id);
    expect(overview.project.organizationId).toBe(orgA.id);
    expect(overview.profile.version).toBe(0);
    expect(overview.capabilityProfile.version).toBe(0);
    expect(overview.artifacts).toEqual([]);
    expect(overview.artifactRelations).toEqual([]);
  });

  it("cross-tenant overview denied", async () => {
    await expect(
      overviewService.getProjectOverview({ accountId: bob.id, projectId: project.id }),
    ).rejects.toThrow();
  });

  it("unknown Project overview opaque", async () => {
    const unknown = randomUUID();
    await expect(
      overviewService.getProjectOverview({ accountId: alice.id, projectId: unknown }),
    ).rejects.toBeInstanceOf(ProjectNotFoundError);
  });
});
