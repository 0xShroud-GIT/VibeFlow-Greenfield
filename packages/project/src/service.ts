/**
 * M-012 Project authority service.
 *
 * VibeFlow owns Project identity, Organization ownership, timestamps and
 * security context. A client/provider cannot lie about any of that.
 *
 * Authority invariants:
 * - Project id is server-generated UUID.
 * - Organization ownership is canonical Organization row resolved from
 *   persistence, never a client claim.
 * - Timestamps are server-controlled.
 * - Authorization resolves canonical membership on every decision.
 * - Cross-tenant access fails closed.
 * - Revoked/stale membership fails closed.
 * - Forged organization id fails closed.
 */

import {
  isUuid,
  type ProjectRow,
  type ProjectRepository,
  type TenantRepository,
} from "@vibeflow/persistence";
import { TenantAuthorizationService } from "@vibeflow/authorization";

import {
  ProjectAuthorizationError,
  ProjectInputError,
  ProjectNotFoundError,
} from "./errors.js";

export interface ProjectServiceOptions {
  tenants: TenantRepository;
  projects: ProjectRepository;
  authz: TenantAuthorizationService;
}

export interface CreateProjectInput {
  accountId: string;
  organizationId: string;
  name: string;
}

export interface GetProjectInput {
  accountId: string;
  projectId: string;
}

export interface ListProjectsInput {
  accountId: string;
  organizationId: string;
}

export interface UpdateProjectInput {
  accountId: string;
  projectId: string;
  name: string;
}

function requireUuid(name: string, value: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ProjectInputError(`${name} is required`);
  }
  if (!isUuid(value)) {
    throw new ProjectInputError(`${name} must be a UUID`);
  }
  return value;
}

function requireNonEmpty(name: string, value: string): string {
  if (typeof value !== "string" || value.trim().length === 0) {
    throw new ProjectInputError(`${name} is required`);
  }
  const trimmed = value.trim();
  if (trimmed.length === 0) {
    throw new ProjectInputError(`${name} is required`);
  }
  if (trimmed.length > 200) {
    throw new ProjectInputError(`${name} must be 200 characters or fewer`);
  }
  return trimmed;
}

export class ProjectService {
  public constructor(private readonly options: ProjectServiceOptions) {}

  /**
   * Create a canonical Project under a canonical Organization.
   * The caller must be a current member of the Organization.
   * Server generates id and timestamps; organizationId is resolved as
   * canonical tenant, never trusted from client claim alone.
   */
  public async createProject(input: CreateProjectInput): Promise<ProjectRow> {
    const accountId = requireUuid("accountId", input.accountId);
    const organizationId = requireUuid("organizationId", input.organizationId);
    const name = requireNonEmpty("name", input.name);

    // Authorization: creating a project requires membership in the target org.
    // We authorize against the organization resource to prove tenant access.
    const decision = await this.options.authz.authorize({
      accountId,
      action: "create",
      resource: { type: "organization", id: organizationId },
    });

    if (!decision.allowed) {
      throw new ProjectAuthorizationError(
        `Project creation denied: ${decision.reason}`,
        decision.reason,
      );
    }

    // Ensure organization exists canonically (FK will also enforce).
    try {
      await this.options.tenants.getOrganizationById(organizationId);
    } catch {
      throw new ProjectNotFoundError(`Organization not found: ${organizationId}`);
    }

    return this.options.projects.createProject({ organizationId, name });
  }

  /**
   * Get a Project by canonical id. Same-tenant authorized access succeeds;
   * cross-tenant, forged, revoked, unknown, and unauthenticated fail closed.
   */
  public async getProject(input: GetProjectInput): Promise<ProjectRow> {
    const accountId = requireUuid("accountId", input.accountId);
    const projectId = requireUuid("projectId", input.projectId);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "read",
      resource: { type: "project", id: projectId },
    });

    if (!decision.allowed) {
      // For unknown_resource we surface as not-found to avoid leaking,
      // for no_membership as authorization error (both fail closed).
      if (decision.reason === "unknown_resource") {
        throw new ProjectNotFoundError(`Project not found: ${projectId}`);
      }
      throw new ProjectAuthorizationError(
        `Project read denied: ${decision.reason}`,
        decision.reason,
      );
    }

    try {
      return await this.options.projects.getProjectById(projectId);
    } catch {
      throw new ProjectNotFoundError(`Project not found: ${projectId}`);
    }
  }

  /**
   * List Projects for a canonical Organization.
   * Tenant-safe: only returns projects whose canonical organization matches
   * and where caller is member of that organization.
   */
  public async listProjects(input: ListProjectsInput): Promise<ProjectRow[]> {
    const accountId = requireUuid("accountId", input.accountId);
    const organizationId = requireUuid("organizationId", input.organizationId);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "read",
      resource: { type: "organization", id: organizationId },
    });

    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ProjectNotFoundError(`Organization not found: ${organizationId}`);
      }
      throw new ProjectAuthorizationError(
        `Project list denied: ${decision.reason}`,
        decision.reason,
      );
    }

    return this.options.projects.listProjectsForOrganization(organizationId);
  }

  /**
   * Update Project name. Tenant-safe mutation: requires membership in the
   * Project's canonical Organization.
   */
  public async updateProject(input: UpdateProjectInput): Promise<ProjectRow> {
    const accountId = requireUuid("accountId", input.accountId);
    const projectId = requireUuid("projectId", input.projectId);
    const name = requireNonEmpty("name", input.name);

    const decision = await this.options.authz.authorize({
      accountId,
      action: "update",
      resource: { type: "project", id: projectId },
    });

    if (!decision.allowed) {
      if (decision.reason === "unknown_resource") {
        throw new ProjectNotFoundError(`Project not found: ${projectId}`);
      }
      throw new ProjectAuthorizationError(
        `Project update denied: ${decision.reason}`,
        decision.reason,
      );
    }

    try {
      return await this.options.projects.updateProject({ id: projectId, name });
    } catch {
      throw new ProjectNotFoundError(`Project not found: ${projectId}`);
    }
  }
}
