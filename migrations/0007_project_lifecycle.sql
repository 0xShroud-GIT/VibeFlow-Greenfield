-- M-015 Project Profile and ProjectCapabilityProfile subordinate state
--
-- These are PROJECT-DOMAIN SUBORDINATE implementations, NOT new canonical
-- resources. `02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml` defines no
-- ProjectProfile, ProjectCapabilityProfile, ProjectLifecycle, ProjectOverview,
-- Import, Template or Clone resource, and M-015 adds none. Canonical authority
-- remains Account -> Organization membership -> Project -> Artifact/ArtifactRelation.
--
-- project_profiles:
--   Durable profile metadata for a canonical Project: optional description and
--   optional cover Artifact reference. The cover Artifact MUST belong to the
--   same canonical Project, enforced by a composite foreign key. Version is
--   used for optimistic concurrency control on profile mutations.
--
-- project_capabilities:
--   Normalized set of capability/trait keys for a canonical Project. This is
--   VibeFlow-owned, provider-neutral state representing the Project's
--   capability manifest. NOT a ProviderCapability, provider advertisement,
--   binding health, workspace capability negotiation, or credential surface.
--   Each capability key is a bounded token, and the set is versioned for
--   optimistic concurrency.
--
-- Authority invariants:
-- - Every id is a server-generated UUID; timestamps are server-controlled.
-- - Project ownership is a canonical FK, never a client claim.
-- - Cover Artifact reference is constrained to the same canonical Project by
--   a composite foreign key (project_id, cover_artifact_id).
-- - Capability keys are bounded, syntax-validated tokens.
-- - Version is a non-negative integer used for optimistic locking.
-- - No provider/external identifier ever establishes authority.
-- - No sharing/collaboration/settings columns (deferred to M-117+).

CREATE TABLE project_profiles (
  project_id uuid PRIMARY KEY REFERENCES projects (id),
  description text,
  cover_artifact_id uuid,
  version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  capability_profile_version integer NOT NULL DEFAULT 0,

  -- Description is a safety-bound text field. The Master defines no numeric
  -- length; the chosen bound is a conservative implementation constant.
  CONSTRAINT project_profiles_description_length
    CHECK (description IS NULL OR char_length(description) <= 5000),

  -- Cover Artifact must belong to the same canonical Project, enforced at the
  -- database level so a cross-Project cover reference is impossible even if
  -- the service layer is bypassed.
  CONSTRAINT project_profiles_cover_fk
    FOREIGN KEY (project_id, cover_artifact_id)
    REFERENCES artifacts (project_id, id)
    DEFERRABLE INITIALLY DEFERRED,

  -- Version is a non-negative integer; zero is reserved for the "no profile
  -- row exists yet" sentinel, and every persisted row starts at 1.
  CONSTRAINT project_profiles_version_non_negative
    CHECK (version >= 0)
);

CREATE INDEX project_profiles_project_id_idx
  ON project_profiles (project_id);

CREATE TABLE project_capabilities (
  id uuid PRIMARY KEY,
  project_id uuid NOT NULL REFERENCES projects (id),
  capability_key text NOT NULL,
  version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),

  -- Capability keys use a namespaced grammar with bounded length.
  -- Grammar: two or more lower-case segments separated by '/',
  -- each segment is [a-z][a-z0-9]* (starts with a letter, follows
  -- with letters/digits), max 200 characters total.
  -- This is deliberately open and provider-neutral — not a closed taxonomy.
  CONSTRAINT project_capabilities_key_valid
    CHECK (capability_key ~ '^[a-z][a-z0-9]*(/[a-z][a-z0-9]*)+$'),
  CONSTRAINT project_capabilities_key_length
    CHECK (char_length(capability_key) <= 200),

  -- Version is the EPOCH version of the whole set, incremented atomically
  -- on each replacement. Each row in the set carries the same version.
  CONSTRAINT project_capabilities_version_non_negative
    CHECK (version >= 0),

  -- One logical capability key per Project.
  CONSTRAINT project_capabilities_project_key_uidx
    UNIQUE (project_id, capability_key)
);

CREATE INDEX project_capabilities_project_id_idx
  ON project_capabilities (project_id);