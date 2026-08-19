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

The M-009 tables support authentication mechanics only. They do not define
Organization/Project authorization, roles, OpenFGA tuples, audit events, or
Project authority.
