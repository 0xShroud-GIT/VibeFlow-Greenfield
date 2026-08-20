-- M-013 Artifact / ArtifactRelation authority
-- VibeFlow-owned durable typed Artifact metadata plus durable ArtifactRelation
-- edges, both rooted in canonical Project ownership.
--
-- Authority invariants:
-- - Artifact id is server-generated UUID; Project ownership is a canonical FK.
-- - Artifact `type` is a bounded, syntax-validated typed-output token (not a
--   closed canonical enum; no normalized registry is invented here).
-- - Server-controlled created_at/updated_at.
-- - ArtifactRelation is a directed subject/object edge whose relation_kind is
--   one of the canonical kinds named by the resource model: lineage, variant,
--   derived-from, contains.
-- - Cross-Project edges are impossible at the database level even if
--   application code is bypassed: the composite (project_id, id) unique key on
--   artifacts plus the composite foreign keys below enforce it.
-- - No client/provider/external identifier ever establishes authority.

CREATE TABLE artifacts (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES projects (id),
  type text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT artifacts_type_non_empty CHECK (char_length(trim(type)) > 0),
  CONSTRAINT artifacts_project_id_id_uidx UNIQUE (project_id, id)
);

CREATE INDEX artifacts_project_id_idx
  ON artifacts (project_id);

CREATE INDEX artifacts_project_id_created_at_idx
  ON artifacts (project_id, created_at DESC);

CREATE TABLE artifact_relations (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL,
  subject_artifact_id uuid NOT NULL,
  object_artifact_id uuid NOT NULL,
  relation_kind text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT artifact_relations_self_edge
    CHECK (subject_artifact_id <> object_artifact_id),
  CONSTRAINT artifact_relations_kind_valid
    CHECK (relation_kind IN ('lineage', 'variant', 'derived-from', 'contains')),
  CONSTRAINT artifact_relations_project_subject_fk
    FOREIGN KEY (project_id, subject_artifact_id)
    REFERENCES artifacts (project_id, id),
  CONSTRAINT artifact_relations_project_object_fk
    FOREIGN KEY (project_id, object_artifact_id)
    REFERENCES artifacts (project_id, id),
  CONSTRAINT artifact_relations_unique_edge
    UNIQUE (project_id, subject_artifact_id, relation_kind, object_artifact_id)
);

CREATE INDEX artifact_relations_project_id_idx
  ON artifact_relations (project_id);

CREATE INDEX artifact_relations_subject_idx
  ON artifact_relations (project_id, subject_artifact_id);

CREATE INDEX artifact_relations_object_idx
  ON artifact_relations (project_id, object_artifact_id);
