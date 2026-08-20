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
- `0006_project_import_clone.sql` is M-014's project-domain internal lifecycle
  state for archive import and Project clone plans. It adds
  `project_archive_imports` (+ `project_archive_import_entries`) and
  `project_clone_plans` (+ `project_clone_artifact_map`). These are INTERNAL
  project-domain records, not canonical resources: M-014 adds no `Import`,
  `Template`, or `Clone` entry to the canonical resource model, registers no
  new authorization resource type, and defines no new public lifecycle state
  machine. Archive bytes are never stored in a row — only server-derived
  SHA-256 digests, a normalized manifest, and an opaque content-addressed
  staging reference. Source kind is fixed to `archive` and format to
  `zip`/`tar`; database CHECKs re-reject unsafe manifest paths (absolute,
  `..`, backslash, drive-letter) as a backstop behind the structural scanner.
  Clone plans pin BOTH endpoints to the same canonical Organization via
  composite foreign keys onto `projects (organization_id, id)` (added here as
  `projects_organization_id_id_uidx`), so a cross-Organization clone is
  impossible at the database level. Both tables carry a unique
  `(organization_id, actor_account_id, idempotency_key)` triple so a replayed
  command can never create a second Project.

The M-009 tables support authentication mechanics only. They do not define
Organization authorization beyond membership, roles, OpenFGA tuples, or later
Project/Artifact lifecycle. Audit events are isolated in the M-011 table and
never contain raw session tokens. Project rows are VibeFlow-owned and require
canonical Organization ownership.
