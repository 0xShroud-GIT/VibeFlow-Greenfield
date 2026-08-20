-- M-014 Project archive-import / clone-plan lifecycle
--
-- These are PROJECT-DOMAIN INTERNAL implementation records. They are NOT new
-- canonical cross-surface resources: `02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml`
-- defines no top-level Import, Template, ProjectImport or Clone resource and
-- M-014 does not add one. Canonical authority remains
-- Account -> Organization membership -> Project -> Artifact / ArtifactRelation.
--
-- These tables exist only to make two things durable and provable:
--   1. archive-import provenance (server-derived manifest/fingerprints) and
--      command idempotency,
--   2. clone-plan provenance (source -> target artifact id remapping) and
--      command idempotency.
--
-- Authority invariants:
-- - Every id is a server-generated UUID; timestamps are server-controlled.
-- - Organization/Project ownership is a canonical FK, never a client claim.
-- - Archive bytes never live in these rows. Only server-derived normalized
--   metadata and cryptographic fingerprints are stored. Content-addressed
--   archive bytes live behind a private staging port; `staged_blob_ref` is an
--   opaque reference to that private staging namespace and is explicitly NOT a
--   canonical ObjectStorageBinding.
-- - No provider/repository/workspace identifier ever establishes authority.
-- - Cross-Organization clone is impossible at the database level: both the
--   source and target Project of a clone plan are pinned to the plan's single
--   canonical Organization by composite foreign keys.

-- Composite key that lets project-scoped records pin a Project to its
-- canonical Organization at the database level (same backstop pattern M-013
-- used for artifacts).
ALTER TABLE projects
  ADD CONSTRAINT projects_organization_id_id_uidx UNIQUE (organization_id, id);

-- ---------------------------------------------------------------------------
-- Archive import (VF-PRJ-004 / R2V-083)
-- ---------------------------------------------------------------------------

CREATE TABLE project_archive_imports (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations (id),
  project_id uuid NOT NULL,
  actor_account_id uuid NOT NULL REFERENCES accounts (id),
  source_kind text NOT NULL,
  archive_format text NOT NULL,
  archive_sha256 text NOT NULL,
  archive_byte_size bigint NOT NULL,
  manifest_sha256 text NOT NULL,
  manifest_entry_count integer NOT NULL,
  manifest_total_declared_size bigint NOT NULL,
  staged_blob_ref text,
  idempotency_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),

  -- M-014 owns exactly one source kind. Provider adapters (VF-PRJ-008..012)
  -- are deferred and must not widen this without their own mission.
  CONSTRAINT project_archive_imports_source_kind_valid
    CHECK (source_kind = 'archive'),
  -- Exactly the formats the master/ledger prove: "ZIP/tar upload + scanner".
  CONSTRAINT project_archive_imports_format_valid
    CHECK (archive_format IN ('zip', 'tar')),
  CONSTRAINT project_archive_imports_archive_sha256_hex
    CHECK (archive_sha256 ~ '^[0-9a-f]{64}$'),
  CONSTRAINT project_archive_imports_manifest_sha256_hex
    CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
  CONSTRAINT project_archive_imports_sizes_non_negative
    CHECK (
      archive_byte_size >= 0
      AND manifest_entry_count >= 0
      AND manifest_total_declared_size >= 0
    ),
  CONSTRAINT project_archive_imports_idempotency_key_non_empty
    CHECK (char_length(trim(idempotency_key)) > 0),
  -- The imported Project must belong to the import's canonical Organization.
  CONSTRAINT project_archive_imports_org_project_fk
    FOREIGN KEY (organization_id, project_id)
    REFERENCES projects (organization_id, id),
  -- Durable command idempotency, scoped to the canonical tenant AND the
  -- issuing actor so one member's key can never collide with, or probe,
  -- another member's command.
  CONSTRAINT project_archive_imports_idempotency_uidx
    UNIQUE (organization_id, actor_account_id, idempotency_key),
  -- An archive import materializes exactly one new canonical Project.
  CONSTRAINT project_archive_imports_project_uidx UNIQUE (project_id)
);

CREATE INDEX project_archive_imports_organization_id_idx
  ON project_archive_imports (organization_id);

CREATE INDEX project_archive_imports_org_created_at_idx
  ON project_archive_imports (organization_id, created_at DESC);

-- Normalized deterministic manifest derived by the server-side structural
-- scanner. Paths here are already normalized and proven safe; the scanner
-- rejects the archive outright otherwise, so no rejected archive ever reaches
-- this table.
CREATE TABLE project_archive_import_entries (
  id uuid PRIMARY KEY,
  import_id uuid NOT NULL REFERENCES project_archive_imports (id) ON DELETE CASCADE,
  entry_index integer NOT NULL,
  normalized_path text NOT NULL,
  entry_kind text NOT NULL,
  declared_size bigint NOT NULL,
  compressed_size bigint NOT NULL,
  content_sha256 text,
  crc32 text,

  CONSTRAINT project_archive_import_entries_kind_valid
    CHECK (entry_kind IN ('file', 'directory')),
  CONSTRAINT project_archive_import_entries_path_non_empty
    CHECK (char_length(normalized_path) > 0),
  -- Normalized paths are relative and traversal-free by construction; this is
  -- the database-level backstop for the scanner's path policy.
  CONSTRAINT project_archive_import_entries_path_relative
    CHECK (
      normalized_path !~ '^/'
      AND normalized_path !~ '(^|/)\.\.(/|$)'
      AND normalized_path !~ '^[A-Za-z]:'
      AND normalized_path !~ '\\'
    ),
  CONSTRAINT project_archive_import_entries_sizes_non_negative
    CHECK (declared_size >= 0 AND compressed_size >= 0),
  CONSTRAINT project_archive_import_entries_content_sha256_hex
    CHECK (content_sha256 IS NULL OR content_sha256 ~ '^[0-9a-f]{64}$'),
  CONSTRAINT project_archive_import_entries_crc32_hex
    CHECK (crc32 IS NULL OR crc32 ~ '^[0-9a-f]{8}$'),
  CONSTRAINT project_archive_import_entries_index_uidx
    UNIQUE (import_id, entry_index),
  -- Duplicate normalized paths are a rejected extraction collision.
  CONSTRAINT project_archive_import_entries_path_uidx
    UNIQUE (import_id, normalized_path)
);

CREATE INDEX project_archive_import_entries_import_id_idx
  ON project_archive_import_entries (import_id);

-- ---------------------------------------------------------------------------
-- Project Clone Plan (VF-PRJ-007 / R2V-086 fork/remix/template)
-- ---------------------------------------------------------------------------

CREATE TABLE project_clone_plans (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations (id),
  source_project_id uuid NOT NULL,
  target_project_id uuid NOT NULL,
  actor_account_id uuid NOT NULL REFERENCES accounts (id),
  plan_kind text NOT NULL,
  artifact_count integer NOT NULL,
  relation_count integer NOT NULL,
  idempotency_key text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),

  CONSTRAINT project_clone_plans_kind_valid
    CHECK (plan_kind = 'project_clone'),
  CONSTRAINT project_clone_plans_distinct_projects
    CHECK (source_project_id <> target_project_id),
  CONSTRAINT project_clone_plans_counts_non_negative
    CHECK (artifact_count >= 0 AND relation_count >= 0),
  CONSTRAINT project_clone_plans_idempotency_key_non_empty
    CHECK (char_length(trim(idempotency_key)) > 0),
  -- M-014 cross-tenant template policy, enforced by the database and not only
  -- by service code: both endpoints are pinned to this plan's single canonical
  -- Organization, so a cross-Organization clone cannot be persisted at all.
  -- Cross-Organization/public template catalog semantics remain deferred.
  CONSTRAINT project_clone_plans_org_source_fk
    FOREIGN KEY (organization_id, source_project_id)
    REFERENCES projects (organization_id, id),
  CONSTRAINT project_clone_plans_org_target_fk
    FOREIGN KEY (organization_id, target_project_id)
    REFERENCES projects (organization_id, id),
  CONSTRAINT project_clone_plans_idempotency_uidx
    UNIQUE (organization_id, actor_account_id, idempotency_key),
  -- A cloned Project is produced by exactly one clone plan.
  CONSTRAINT project_clone_plans_target_uidx UNIQUE (target_project_id)
);

CREATE INDEX project_clone_plans_organization_id_idx
  ON project_clone_plans (organization_id);

CREATE INDEX project_clone_plans_source_project_id_idx
  ON project_clone_plans (source_project_id);

-- Clone provenance: the source -> target Artifact id remapping.
--
-- This is deliberately NOT an ArtifactRelation. ArtifactRelation is M-013
-- same-Project canonical graph state; it is never cross-Project clone
-- provenance. The mapping lives here, inside the internal clone-plan evidence.
CREATE TABLE project_clone_artifact_map (
  id uuid PRIMARY KEY,
  clone_plan_id uuid NOT NULL REFERENCES project_clone_plans (id) ON DELETE CASCADE,
  source_artifact_id uuid NOT NULL REFERENCES artifacts (id),
  target_artifact_id uuid NOT NULL REFERENCES artifacts (id),

  CONSTRAINT project_clone_artifact_map_distinct
    CHECK (source_artifact_id <> target_artifact_id),
  CONSTRAINT project_clone_artifact_map_source_uidx
    UNIQUE (clone_plan_id, source_artifact_id),
  CONSTRAINT project_clone_artifact_map_target_uidx
    UNIQUE (clone_plan_id, target_artifact_id)
);

CREATE INDEX project_clone_artifact_map_clone_plan_id_idx
  ON project_clone_artifact_map (clone_plan_id);
