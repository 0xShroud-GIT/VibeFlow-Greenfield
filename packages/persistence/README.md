# `@vibeflow/persistence`

VibeFlow-owned PostgreSQL persistence for Account, Organization,
organization membership, and Project.

This package is the M-008/M-012 control-plane repository/query boundary. Its
`TenantRepository` does not implement authentication; M-009's
`@vibeflow/identity` boundary owns Better Auth credential/session mechanics and
the canonical `identity_users.vibeflow_account_id` Account link. Its
`ProjectRepository` is M-012's authoritative Project persistence: server-generated
Project identity, canonical Organization ownership, server-controlled timestamps,
FK integrity, tenant indexes, and tenant-safe reads. This package still does not
implement authorization roles/policy beyond membership resolution (M-010) or
later Artifact/ArtifactRelation lifecycle (M-013+).

Tenant and Project relationships are canonical server-side rows. Client or
provider IDs are never stored as authority and cannot create membership or
Project ownership.
