# migrations

Committed authoritative control-plane database SQL migrations.

Apply with `@vibeflow/persistence` `applyCommittedSqlMigrations`. Files matching
`NNNN_name.sql` are applied in lexical order and recorded in
`vibeflow_schema_migrations`. Re-applying an already-recorded file is a no-op.
