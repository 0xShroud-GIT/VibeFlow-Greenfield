# `@vibeflow/persistence`

VibeFlow-owned PostgreSQL persistence for Account, Organization, and
organization membership.

This package is the M-008 control-plane repository/query boundary. Its
`TenantRepository` does not implement authentication; M-009's
`@vibeflow/identity` boundary owns Better Auth credential/session mechanics and
the canonical `identity_users.vibeflow_account_id` Account link. This package
still does not implement authorization roles/policy (M-010), audit (M-011), or
Project persistence (M-012).

Tenant relationships are canonical server-side rows. Client or provider IDs
are never stored as authority and cannot create membership.
