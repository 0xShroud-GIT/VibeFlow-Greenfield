-- M-012 Project authority
-- VibeFlow-owned durable Project with canonical Organization ownership.
-- Server-generated identity, server-controlled timestamps, FK integrity, tenant indexes.
-- Client/provider/external ids never establish authority.

CREATE TABLE projects (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations (id),
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT projects_name_non_empty CHECK (char_length(trim(name)) > 0)
);

CREATE INDEX projects_organization_id_idx
  ON projects (organization_id);

CREATE INDEX projects_organization_id_created_at_idx
  ON projects (organization_id, created_at DESC);
