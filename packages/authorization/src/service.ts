/**
 * Server-side tenant/resource authorization, deny-by-default.
 *
 * The service consumes an Account id already proven by M-009 authentication
 * and resolves every membership/tenant relationship from canonical VibeFlow
 * persistence at decision time. It never trusts a client/provider-supplied
 * organization id, role, permission, ownership claim, or resource relationship
 * as authority, and it never returns `allowed` unless membership is proven.
 *
 * Only the `organization` resource type is registered in M-010. Later resource
 * types (Project, Task, Connection, Workspace, repository, deployment, ...)
 * register a canonical tenant resolver in their owning mission; until then
 * they are denied by default, which is the correct fail-closed posture.
 */

import type {
  OrganizationMembershipRow,
  OrganizationRow,
  TenantRepository,
} from "@vibeflow/persistence";

import { validateRequest } from "./decision.js";
import { ALLOW, deny } from "./types.js";
import type {
  AuthorizationDecision,
  AuthorizationRequest,
} from "./types.js";

/**
 * Narrow canonical-persistence authority the boundary depends on.
 * `TenantRepository` satisfies it structurally, and tests may provide a fake.
 */
export interface MembershipAuthority {
  getOrganizationById(organizationId: string): Promise<OrganizationRow>;
  getMembership(input: {
    organizationId: string;
    accountId: string;
  }): Promise<OrganizationMembershipRow>;
}

export class TenantAuthorizationService {
  public constructor(private readonly tenants: MembershipAuthority) {}

  /**
   * Decide whether the authenticated `accountId` may perform `action` on the
   * canonical resource. Never throws for an authorization outcome; every
   * malformed, unknown, or unauthorized request yields an explicit deny.
   */
  public async authorize(request: AuthorizationRequest): Promise<AuthorizationDecision> {
    const invalid = validateRequest(request);
    if (invalid !== null) {
      return invalid;
    }

    // Dispatch on the canonical resource type. Each type registers its own
    // tenant resolution so provider semantics never leak into the boundary.
    switch (request.resource.type) {
      case "organization":
        return this.authorizeOrganizationResource(request);
      default:
        // Defensive: validateRequest already rejects unknown types.
        return deny("unknown_resource_type");
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
}
