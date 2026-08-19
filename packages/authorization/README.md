# `@vibeflow/authorization`

M-010/M-012's server-side tenant/resource authorization decision boundary.

Authentication (M-009's `@vibeflow/identity`) proves an Account identity. It is
a **precondition, never a grant**. Authorization is a separate, server-side,
**deny-by-default** decision. `@vibeflow/authorization` resolves Organization
membership and Project canonical Organization ownership from canonical VibeFlow
persistence at every decision and never trusts client/provider-supplied
organization ids, project ids, roles, permissions, ownership claims, or resource
relationships.

## Authority split

- **M-009 authentication** produces the canonical `accountId` and nothing else.
  It carries no Organization, Project, role, grant, or permission.
- **M-010/M-012 authorization** consumes that proven `accountId`, validates the
  request, resolves the resource's canonical tenant (Organization itself, or
  Project's canonical Organization), and requires a canonical
  `organization_memberships` row before allowing anything.
- Canonical UUIDs and registered resource-type/action tokens are required.
  Client/provider/external ids, sloppy ids, unknown resource types, and unknown
  actions all fail closed.

## Decision boundary

`TenantAuthorizationService.authorize(request)` returns an explicit
`AuthorizationDecision`:

- `{ allowed: true }` only when membership is proven against canonical rows.
- `{ allowed: false, reason }` with a typed `DenyReason`
  (`malformed_request`, `invalid_identifier`, `unknown_resource_type`,
  `unknown_action`, `unknown_resource`, `no_membership`).

The boundary never throws for an authorization outcome. In M-010 only the
`organization` resource type is registered (its tenant is the organization
itself). M-012 registers `project` as a first-class protected resource:
its canonical tenant is the Project's `organization_id` resolved from
persistence, and access requires membership in that Organization. Later
canonical resources (Task, Connection, Workspace, repository, deployment, ...)
register their own tenant resolution in their owning mission; until they do
they are denied by default.

## Scope limits

M-012 does not implement Artifact/ArtifactRelation (M-013), imports/templates
lifecycle (M-014), full Project lifecycle E2E beyond M-012, provider bindings,
AgentBinding, ModelBinding, WorkspaceBinding, RepositoryBinding, DataBinding,
ObjectStorageBinding, DeploymentBinding, roles/group binding, enterprise SSO,
MFA, OAuth breadth, ConnectionGrant, approvals, or provider policy. No external
authorization engine is used; the decision boundary is plain TypeScript over
the canonical PostgreSQL authority.

Project authority is derived from trusted server-side VibeFlow state. Never
trusts client/provider supplied claims for Project ownership, Organization
ownership, membership, authorization, creator/actor identity, tenant scope, or
resource relationships. Cross-tenant Project access fails closed.
