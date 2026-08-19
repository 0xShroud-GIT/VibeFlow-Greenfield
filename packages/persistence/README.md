# `@vibeflow/persistence`

VibeFlow-owned PostgreSQL persistence for Account, Organization, and
organization membership.

This package is the M-008 control-plane repository/query boundary. It does not
implement authentication (M-009), authorization roles/policy (M-010), audit
(M-011), or Project persistence (M-012).

Tenant relationships are canonical server-side rows. Client or provider IDs
are never stored as authority and cannot create membership.
