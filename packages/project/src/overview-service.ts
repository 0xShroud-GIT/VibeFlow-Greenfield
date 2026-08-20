/**
 * M-015 Project Overview / E2E read model.
 *
 * Tenant-safe Project-domain aggregate suitable for the FE-002
 * "Project Overview" read contract. Returns a server-derived projection
 * of currently available canonical Project-domain state.
 *
 * This is a read model / projection, NOT a canonical resource.
 * No provider bindings, Task/Execution/Release are fabricated here.
 */

import { isUuid } from "@vibeflow/persistence";
import type { ArtifactRelationRow, ArtifactRow } from "@vibeflow/persistence";
import { TenantAuthorizationService } from "@vibeflow/authorization";
import { ProjectService } from "./service.js";
import {
  ProjectProfileService,
  type ProjectProfileResult,
} from "./profile-service.js";
import {
  ProjectCapabilityProfileService,
  type ProjectCapabilityProfileResult,
} from "./capability-profile-service.js";
import { ProjectNotFoundError, ProjectOverviewError } from "./errors.js";
import { ArtifactService } from "./artifact-service.js";
import { ProjectImportService } from "./import-service.js";
import { ProjectCloneService } from "./clone-service.js";

export interface ProjectOverviewServiceOptions {
  projectService: ProjectService;
  projectProfileService: ProjectProfileService;
  projectCapabilityProfileService: ProjectCapabilityProfileService;
  artifactService: ArtifactService;
  importService: ProjectImportService;
  cloneService: ProjectCloneService;
  authz: TenantAuthorizationService;
}

export interface GetProjectOverviewInput {
  accountId: string;
  projectId: string;
}

export interface ImportProvenance {
  importId: string;
  archiveFormat: string;
  archiveSha256: string;
  archiveByteSize: number;
  importedAt: Date;
}

export interface CloneProvenance {
  clonePlanId: string;
  sourceProjectId: string;
  targetProjectId: string;
  clonedAt: Date;
}

export interface ProjectOverview {
  project: {
    id: string;
    organizationId: string;
    name: string;
    createdAt: Date;
    updatedAt: Date;
  };
  profile: ProjectProfileResult;
  capabilityProfile: ProjectCapabilityProfileResult;
  artifacts: ArtifactRow[];
   artifactRelations: ArtifactRelationRow[];
  importProvenance: ImportProvenance | null;
  cloneProvenance: CloneProvenance | null;
}

function requireUuid(name: string, value: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ProjectOverviewError(name + " is required");
  }
  if (!isUuid(value)) {
    throw new ProjectOverviewError(name + " must be a UUID");
  }
  return value;
}

export class ProjectOverviewService {
  public constructor(private readonly options: ProjectOverviewServiceOptions) {}

  public async getProjectOverview(
    input: GetProjectOverviewInput,
  ): Promise<ProjectOverview> {
    const accountId = requireUuid("accountId", input.accountId);
    const projectId = requireUuid("projectId", input.projectId);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "read",
      resource: { type: "project", id: projectId },
    });

    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ProjectNotFoundError("Project not found: " + projectId);
      }
      throw new ProjectOverviewError("Project overview denied: " + decision.reason);
    }

    const project = await this.options.projectService.getProject({ accountId, projectId });
    const profile = await this.options.projectProfileService.getProjectProfile({ accountId, projectId });
    const capabilityProfile = await this.options.projectCapabilityProfileService.getProjectCapabilityProfile({ accountId, projectId });
    const artifacts = await this.options.artifactService.listArtifacts({ accountId, projectId });
    const artifactRelations = await this.options.artifactService.listArtifactRelations({ accountId, projectId });

    // Import provenance
    let importProvenance: ImportProvenance | null = null;
    try {
      const imp = await this.options.importService.getImportByProjectId({ accountId, projectId });
      if (imp) {
        importProvenance = {
          importId: imp.id,
          archiveFormat: imp.archiveFormat,
          archiveSha256: imp.archiveSha256,
          archiveByteSize: imp.archiveByteSize,
          importedAt: imp.createdAt,
        };
      }
    } catch {
      // No import provenance
    }

    // Clone provenance
    let cloneProvenance: CloneProvenance | null = null;
    try {
      const plan = await this.options.cloneService.getClonePlanByProjectId({ accountId, projectId });
      if (plan) {
        cloneProvenance = {
          clonePlanId: plan.id,
          sourceProjectId: plan.sourceProjectId,
          targetProjectId: plan.targetProjectId,
          clonedAt: plan.createdAt,
        };
      }
    } catch {
      // No clone provenance
    }

    return {
      project: {
        id: project.id,
        organizationId: project.organizationId,
        name: project.name,
        createdAt: project.createdAt,
        updatedAt: project.updatedAt,
      },
      profile,
      capabilityProfile,
      artifacts,
      artifactRelations,
      importProvenance,
      cloneProvenance,
    };
  }
}
