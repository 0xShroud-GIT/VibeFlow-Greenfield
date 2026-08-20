/**
 * M-015 ProjectCapabilityProfile authority service.
 *
 * VibeFlow-owned, provider-neutral Project state representing the Project's
 * normalized capability/trait manifest. NOT a ProviderCapability, provider
 * capability discovery, binding health, workspace capability negotiation,
 * provider advertisement, or credential/configuration surface.
 */

import {
  isCapabilityKeyToken,
  isUuid,
  CAPABILITY_KEY_MAX_LENGTH,
  ProjectCapabilityRepository,
  StaleVersionError,
} from "@vibeflow/persistence";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import { ProjectInputError, ProjectNotFoundError, ProjectCapabilityProfileError } from "./errors.js";

export interface ProjectCapabilityProfileServiceOptions {
  capabilities: ProjectCapabilityRepository;
  authz: TenantAuthorizationService;
}

export interface GetProjectCapabilityProfileInput {
  accountId: string;
  projectId: string;
}

export interface ReplaceProjectCapabilityProfileInput {
  accountId: string;
  projectId: string;
  expectedVersion: number;
  capabilities: readonly string[];
}

export interface ProjectCapabilityProfileResult {
  projectId: string;
  capabilities: readonly string[];
  version: number;
  createdAt: Date | null;
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

function requireCapabilityTokens(capabilities: readonly string[]): string[] {
  if (!Array.isArray(capabilities)) {
    throw new ProjectInputError("capabilities must be an array");
  }
  const valid: string[] = [];
  for (const raw of capabilities) {
    if (typeof raw !== "string") {
      throw new ProjectInputError("each capability must be a string");
    }
    const trimmed = raw.trim();
    if (trimmed.length === 0) {
      throw new ProjectInputError("capability key must not be empty");
    }
    if (trimmed.length > CAPABILITY_KEY_MAX_LENGTH) {
      throw new ProjectInputError("capability key must be " + CAPABILITY_KEY_MAX_LENGTH + " characters or fewer");
    }
    if (!isCapabilityKeyToken(trimmed)) {
      throw new ProjectInputError("capability key must be two or more lower-case '/' separated segments");
    }
    valid.push(trimmed);
  }
  return valid;
}

export class ProjectCapabilityProfileService {
  public constructor(private readonly options: ProjectCapabilityProfileServiceOptions) {}

  public async getProjectCapabilityProfile(
    input: GetProjectCapabilityProfileInput,
  ): Promise<ProjectCapabilityProfileResult> {
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
      throw new ProjectCapabilityProfileError("Capability profile read denied: " + decision.reason);
    }

    const rows = await this.options.capabilities.getCapabilitiesByProjectId(projectId);
    const capabilities = rows.map((r) => r.capabilityKey);
    const version = await this.options.capabilities.getVersionByProjectId(projectId);
    const createdAt = rows.length > 0 ? rows[0]!.createdAt : null;

    return {
      projectId,
      capabilities,
      version,
      createdAt,
    };
  }

  public async replaceProjectCapabilityProfile(
    input: ReplaceProjectCapabilityProfileInput,
  ): Promise<ProjectCapabilityProfileResult> {
    const accountId = requireUuid("accountId", input.accountId);
    const projectId = requireUuid("projectId", input.projectId);
    const expectedVersion = requireVersion("expectedVersion", input.expectedVersion);
    const capabilities = requireCapabilityTokens(input.capabilities);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "update",
      resource: { type: "project", id: projectId },
    });

    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ProjectNotFoundError("Project not found: " + projectId);
      }
      throw new ProjectCapabilityProfileError("Capability profile update denied: " + decision.reason);
    }

    try {
      const rows = await this.options.capabilities.replaceCapabilities({
        projectId,
        expectedVersion,
        capabilities,
      });

      const resultCapabilities = rows.map((r) => r.capabilityKey);
      // Version is authoritative from the durable profile row, not from capability rows
      const newVersion = await this.options.capabilities.getVersionByProjectId(projectId);
      const createdAt = rows.length > 0 ? rows[0]!.createdAt : new Date();

      return {
        projectId,
        capabilities: resultCapabilities,
        version: newVersion,
        createdAt,
      };
    } catch (error) {
      if (error instanceof StaleVersionError) {
        throw new ProjectCapabilityProfileError("Capability profile replace failed: " + error.message);
      }
      throw error instanceof Error ? error : new Error(String(error));
    }
  }
}
