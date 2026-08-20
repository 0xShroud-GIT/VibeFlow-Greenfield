/**
 * Server-side tenant/resource authorization, deny-by-default.
 *
 * The service consumes an Account id already proven by M-009 authentication
 * and resolves every membership/tenant relationship from canonical VibeFlow
 * persistence at decision time. It never trusts a client/provider-supplied
 * organization id, role, permission, ownership claim, or resource relationship
 * as authority, and it never returns `allowed` unless membership is proven.
 *
 * M-010 registered `organization`. M-012 registers `project` as a first-class
 * protected resource: its canonical Organization ownership is resolved from
 * persistence and membership is proven against that Organization. Unknown
 * types continue to fail closed.
 */

import type {
  ArtifactRelationRow,
  ArtifactRow,
  OrganizationMembershipRow,
  OrganizationRow,
  ProjectRow,
} from "@vibeflow/persistence";

import { validateRequest } from "./decision.js";
import { ALLOW, deny } from "./types.js";
import type {
  AuthorizationDecision,
  AuthorizationRequest,
} from "./types.js";

/**
 * Narrow canonical-persistence authority the boundary depends on.
 * `TenantRepository` + `ProjectRepository` + `ArtifactRepository` satisfy it
 * structurally, and tests may provide a fake.
 */
export interface MembershipAuthority {
  getOrganizationById(organizationId: string): Promise<OrganizationRow>;
  getMembership(input: {
    organizationId: string;
    accountId: string;
  }): Promise<OrganizationMembershipRow>;
  getProjectById(projectId: string): Promise<ProjectRow>;
  getArtifactById(artifactId: string): Promise<ArtifactRow>;
  getArtifactRelationById(relationId: string): Promise<ArtifactRelationRow>;
}

/** Narrow trusted integration implemented by @vibeflow/audit AuditService. */
export interface AuthorizationAuditRecorder {
  recordAuthorizationDecision(input: {
    actorAccountId: string;
    action: string;
    resource: { type: string; id: string };
    decision: AuthorizationDecision;
  }): Promise<void>;
}

export class TenantAuthorizationService {
  public constructor(
    private readonly tenants: MembershipAuthority,
    private readonly audit: AuthorizationAuditRecorder,
  ) {}

  /**
   * Decide whether the authenticated `accountId` may perform `action` on the
   * canonical resource. Never throws for an authorization outcome; every
   * malformed, unknown, or unauthorized request yields an explicit deny.
   */
  public async authorize(request: AuthorizationRequest): Promise<AuthorizationDecision> {
    const invalid = validateRequest(request);
    if (invalid !== null) {
      return this.recordRequiredAudit(request, invalid);
    }

    // Dispatch on the canonical resource type. Each type registers its own
    // tenant resolution so provider semantics never leak into the boundary.
    let decision: AuthorizationDecision;
    switch (request.resource.type) {
      case "organization":
        decision = await this.authorizeOrganizationResource(request);
        break;
      case "project":
        decision = await this.authorizeProjectResource(request);
        break;
      case "artifact":
        decision = await this.authorizeArtifactResource(request);
        break;
      case "artifact_relation":
        decision = await this.authorizeArtifactRelationResource(request);
        break;
      default:
        // Defensive: validateRequest already rejects unknown types.
        decision = deny("unknown_resource_type");
    }
    return this.recordRequiredAudit(request, decision);
  }

  private async recordRequiredAudit(
    request: AuthorizationRequest,
    decision: AuthorizationDecision,
  ): Promise<AuthorizationDecision> {
    try {
      await this.audit.recordAuthorizationDecision({
        actorAccountId: request.accountId,
        action: request.action,
        resource: request.resource,
        decision,
      });
      return decision;
    } catch {
      // Security Master failure stance: an allow without its required durable
      // security record is not permitted. Existing denials remain fail-closed.
      return decision.allowed ? deny("audit_unavailable") : decision;
    }
  }

  /**
   * Organization is its own tenant. Access requires a canonical membership
   * row in `organization_memberships` for the authenticated Account.
   */
  private async authorizeOrganizationResource(
    request: AuthorizationRequest,
  ): Promise<AuthorizationDecision> {
    const orgId = request.resource.id;

    // The organization must exist as a canonical VibeFlow row. A forged or
    // swapped id that is not a real organization fails closed as unknown.
    let organization: OrganizationRow;
    try {
      organization = await this.tenants.getOrganizationById(orgId);
    } catch {
      return deny("unknown_resource");
    }

    // Membership is resolved from canonical persistence on every decision.
    try {
      await this.tenants.getMembership({
        organizationId: organization.id,
        accountId: request.accountId,
      });
    } catch {
      return deny("no_membership");
    }

    return ALLOW;
  }

  /**
   * Project authority: canonical Project ownership is resolved from
   * persistence. The Project's canonical Organization is its tenant.
   * Access requires a membership row for that Organization.
   *
   * Never trusts client/provider supplied organization id, ownership claim,
   * or resource relationship; only the canonical Project row establishes the
   * tenant.
   */
  private async authorizeProjectResource(
    request: AuthorizationRequest,
  ): Promise<AuthorizationDecision> {
    const projectId = request.resource.id;

    // The project must exist as a canonical VibeFlow row. A forged, swapped,
    // or random UUID that is not a real project fails closed as unknown.
    let project: ProjectRow;
    try {
      project = await this.tenants.getProjectById(projectId);
    } catch {
      return deny("unknown_resource");
    }

    // The project's canonical organization must exist; if it does not,
    // treat as unknown to avoid leaking tenant existence.
    let organization: OrganizationRow;
    try {
      organization = await this.tenants.getOrganizationById(project.organizationId);
    } catch {
      return deny("unknown_resource");
    }

    // Membership is resolved from canonical persistence on every decision.
    // Revoked/stale membership fails closed.
    try {
      await this.tenants.getMembership({
        organizationId: organization.id,
        accountId: request.accountId,
      });
    } catch {
      return deny("no_membership");
    }

    return ALLOW;
  }

  /**
   * Artifact authority: canonical Artifact ownership is resolved from
   * persistence through Artifact -> Project -> Organization. Membership is
   * proven against that canonical Organization. A forged, swapped, or random
   * UUID that is not a real Artifact fails closed as unknown.
   */
  private async authorizeArtifactResource(
    request: AuthorizationRequest,
  ): Promise<AuthorizationDecision> {
    const artifactId = request.resource.id;

    let artifact: ArtifactRow;
    try {
      artifact = await this.tenants.getArtifactById(artifactId);
    } catch {
      return deny("unknown_resource");
    }

    let project: ProjectRow;
    try {
      project = await this.tenants.getProjectById(artifact.projectId);
    } catch {
      return deny("unknown_resource");
    }

    let organization: OrganizationRow;
    try {
      organization = await this.tenants.getOrganizationById(project.organizationId);
    } catch {
      return deny("unknown_resource");
    }

    try {
      await this.tenants.getMembership({
        organizationId: organization.id,
        accountId: request.accountId,
      });
    } catch {
      return deny("no_membership");
    }

    return ALLOW;
  }

  /**
   * ArtifactRelation authority: the relation's canonical Project is resolved
   * from persistence, then Project -> Organization -> membership. A forged,
   * swapped, or random UUID fails closed as unknown.
   */
  private async authorizeArtifactRelationResource(
    request: AuthorizationRequest,
  ): Promise<AuthorizationDecision> {
    const relationId = request.resource.id;

    let relation: ArtifactRelationRow;
    try {
      relation = await this.tenants.getArtifactRelationById(relationId);
    } catch {
      return deny("unknown_resource");
    }

    let project: ProjectRow;
    try {
      project = await this.tenants.getProjectById(relation.projectId);
    } catch {
      return deny("unknown_resource");
    }

    let organization: OrganizationRow;
    try {
      organization = await this.tenants.getOrganizationById(project.organizationId);
    } catch {
      return deny("unknown_resource");
    }

    try {
      await this.tenants.getMembership({
        organizationId: organization.id,
        accountId: request.accountId,
      });
    } catch {
      return deny("no_membership");
    }

    return ALLOW;
  }
}
