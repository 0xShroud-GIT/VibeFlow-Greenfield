# migrations

Committed authoritative control-plane database SQL migrations.

Apply with `@vibeflow/persistence` `applyCommittedSqlMigrations`. Files matching
`NNNN_name.sql` are applied in lexical order and recorded in
`vibeflow_schema_migrations`. Re-applying an already-recorded file is a no-op;
a PostgreSQL advisory lock makes concurrent startup/test callers wait for the
same recorded result rather than racing migration application.

- `0001_account_organization.sql` is M-008's VibeFlow Account, Organization,
  and membership authority.
- `0002_identity_auth_sessions.sql` is M-009's Better Auth-compatible
  credential/session persistence plus its foreign-key link to a canonical
  VibeFlow Account.
- `0003_audit_event_ledger.sql` is M-011's append-only AuditEvent ledger plus
  transactional session creation/revocation audit triggers.
- `0004_project_authority.sql` is M-012's authoritative Project resource with
  canonical Organization ownership, server-controlled timestamps, FK
  integrity, and tenant indexes. No provider/external identifier ever
  establishes Project authority.
- `0005_artifact_authority.sql` is M-013's authoritative Artifact and
  ArtifactRelation resources, both rooted in canonical Project ownership.
  Artifact metadata is server-owned (id, project FK, bounded type token,
  timestamps); ArtifactRelation is a directed subject/object edge restricted
  to the canonical kinds (lineage, variant, derived-from, contains). Composite
  `(project_id, id)` uniqueness on artifacts plus composite foreign keys make
  cross-Project edges impossible at the database level.

The M-009 tables support authentication mechanics only. They do not define
Organization authorization beyond membership, roles, OpenFGA tuples, or later
Project/Artifact lifecycle. Audit events are isolated in the M-011 table and
never contain raw session tokens. Project rows are VibeFlow-owned and require
canonical Organization ownership.
