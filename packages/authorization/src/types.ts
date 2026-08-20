/**
 * M-010 typed authorization decision boundary.
 *
 * Authentication (M-009) proves an Account identity and nothing else. It never
 * implicitly authorizes an Organization or a resource. Authorization is a
 * separate, server-side, deny-by-default decision that resolves Organization
 * membership and resource relationships from canonical VibeFlow persistence on
 * every decision that requires them.
 *
 * The boundary is deliberately resource-type agnostic so later canonical
 * resources (Project, Task, Connection, Workspace, repository, deployment,
 * ...) can be registered in their owning mission without hard-wiring provider
 * semantics. It never trusts a client/provider-supplied organization id, role,
 * permission, ownership claim, or resource relationship as authority.
 */

/** Canonical resource types registered in the authorization boundary.
 * M-010 registered `organization`; M-012 registers `project` as a first-class
 * protected resource with canonical Organization ownership resolved from
 * persistence. M-013 registers `artifact` and `artifact_relation`, whose
 * tenant is resolved through canonical Project ownership. Future resources
 * (Task, Connection, ...) register in their owning mission; unknown types
 * continue to fail closed.
 */
export const RESOURCE_TYPES = [
  "organization",
  "project",
  "artifact",
  "artifact_relation",
] as const;
export type ResourceType = (typeof RESOURCE_TYPES)[number];

/** Canonical action tokens recognized by the boundary. */
export const ACTIONS = ["read", "create", "update", "delete", "list"] as const;
export type Action = (typeof ACTIONS)[number];

/**
 * A canonical VibeFlow resource reference. `type` is a canonical resource
 * type token and `id` a canonical VibeFlow UUID; neither is ever a
 * client/provider/external identifier.
 */
export interface ResourceRef {
  readonly type: string;
  readonly id: string;
}

/**
 * A decision request. `accountId` is the canonical Account id already proven
 * by M-009 authentication; the authorization boundary consumes that proof and
 * never re-derives or extends it into a tenant/resource grant.
 */
export interface AuthorizationRequest {
  readonly accountId: string;
  readonly action: string;
  readonly resource: ResourceRef;
}

/**
 * Why a request was denied. Each reason is a distinct fail-closed outcome that
 * callers and tests can assert against; none of them leak existence of a
 * credential, session, or resource beyond what the caller already supplied.
 */
export type DenyReason =
  | "malformed_request"
  | "invalid_identifier"
  | "unknown_resource_type"
  | "unknown_action"
  | "unknown_resource"
  | "no_membership"
  | "audit_unavailable";

export type AuthorizationDecision =
  | { readonly allowed: true }
  | { readonly allowed: false; readonly reason: DenyReason };

/** The only positive outcome: every require path must be proven, never assumed. */
export const ALLOW: AuthorizationDecision = Object.freeze({ allowed: true });

export function deny(reason: DenyReason): AuthorizationDecision {
  return Object.freeze({ allowed: false, reason });
}
