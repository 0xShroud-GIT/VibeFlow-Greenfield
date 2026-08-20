/**
 * M-015 Project Profile authority service.
 *
 * Subordinate Project-domain state: optional description and optional cover
 * Artifact reference. The cover Artifact MUST belong to the same canonical
 * Project, enforced at the database level by a composite FK.
 */

import {
  isUuid,
  type ArtifactRepository,
  type ArtifactRow,
  ProjectProfileRepository,
  StaleVersionError,
} from "@vibeflow/persistence";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ProjectInputError, ProjectNotFoundError, ProjectProfileError } from "./errors.js";

export interface ProjectProfileServiceOptions {
  profiles: ProjectProfileRepository;
  artifacts: ArtifactRepository;
  authz: TenantAuthorizationService;
}

export interface GetProjectProfileInput {
  accountId: string;
  projectId: string;
}

export interface UpdateProjectProfileInput {
  accountId: string;
  projectId: string;
  expectedVersion: number;
  description?: string | null;
  coverArtifactId?: string | null;
}

export interface ProjectProfileResult {
  projectId: string;
  description: string | null;
  coverArtifactId: string | null;
  version: number;
  createdAt: Date;
  updatedAt: Date;
}

function requireUuid(name: string, value: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ProjectInputError(name + " is required");
  }
  if (!isUuid(value)) {
    throw new ProjectInputError(name + " must be a UUID");
  }
  return value;
}

function requireVersion(name: string, value: number): number {
  if (!Number.isInteger(value) || value < 0) {
    throw new ProjectInputError(name + " must be a non-negative integer");
  }
  return value;
}

function requireDescription(value: string | null | undefined): string | null {
  if (value === null || value === undefined) {
    return null;
  }
  if (typeof value !== "string") {
    throw new ProjectInputError("description must be a string");
  }
  const trimmed = value.trim();
  if (trimmed.length > 5000) {
    throw new ProjectInputError("description must be 5000 characters or fewer");
  }
  return trimmed.length > 0 ? trimmed : null;
}

export class ProjectProfileService {
  public constructor(private readonly options: ProjectProfileServiceOptions) {}

  public async getProjectProfile(input: GetProjectProfileInput): Promise<ProjectProfileResult> {
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
      throw new ProjectProfileError("Project profile read denied: " + decision.reason);
    }

    const profile = await this.options.profiles.getProfileByProjectId(projectId);

    if (!profile) {
      return {
        projectId,
        description: null,
        coverArtifactId: null,
        version: 0,
        createdAt: new Date(0),
        updatedAt: new Date(0),
      };
    }

    return {
      projectId: profile.projectId,
      description: profile.description,
      coverArtifactId: profile.coverArtifactId,
      version: profile.version,
      createdAt: profile.createdAt,
      updatedAt: profile.updatedAt,
    };
  }

  public async updateProjectProfile(input: UpdateProjectProfileInput): Promise<ProjectProfileResult> {
    const accountId = requireUuid("accountId", input.accountId);
    const projectId = requireUuid("projectId", input.projectId);
    const expectedVersion = requireVersion("expectedVersion", input.expectedVersion);
    const description = requireDescription(input.description ?? null);

    let coverArtifactId: string | null = null;
    if (input.coverArtifactId !== undefined && input.coverArtifactId !== null) {
      coverArtifactId = requireUuid("coverArtifactId", input.coverArtifactId);
    }

    const decision = await this.options.authz.authorize({
      accountId,
      action: "update",
      resource: { type: "project", id: projectId },
    });

    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ProjectNotFoundError("Project not found: " + projectId);
      }
      throw new ProjectProfileError("Project profile update denied: " + decision.reason);
    }

    if (coverArtifactId !== null) {
      const artifactDecision = await this.options.authz.authorize({
        accountId,
        action: "read",
        resource: { type: "artifact", id: coverArtifactId },
      });

      if (!artifactDecision.allowed) {
        if (artifactDecision.reason === "unknown_resource") {
          throw new ProjectNotFoundError("Artifact not found: " + coverArtifactId);
        }
        throw new ProjectProfileError("Cover artifact access denied: " + artifactDecision.reason);
      }

      let coverArtifact: ArtifactRow;
      try {
        coverArtifact = await this.options.artifacts.getArtifactById(coverArtifactId);
      } catch {
        throw new ProjectNotFoundError("Cover artifact not found: " + coverArtifactId);
      }

      if (coverArtifact.projectId !== projectId) {
        throw new ProjectProfileError("Cover artifact must belong to the same canonical Project");
      }
    }

    try {
      const profile = await this.options.profiles.upsertProfile({
        projectId,
        expectedVersion,
        description,
        coverArtifactId,
      });

      return {
        projectId: profile.projectId,
        description: profile.description,
        coverArtifactId: profile.coverArtifactId,
        version: profile.version,
        createdAt: profile.createdAt,
        updatedAt: profile.updatedAt,
      };
    } catch (error) {
      if (error instanceof StaleVersionError) {
        throw new ProjectProfileError("Project profile update failed: " + error.message);
      }
      throw error instanceof Error ? error : new Error(String(error));
    }
  }
}
