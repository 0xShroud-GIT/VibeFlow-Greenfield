-- M-008 Account / Organization / membership
-- VibeFlow-owned control-plane truth. Client and external IDs are not stored.

CREATE TABLE accounts (
  id uuid PRIMARY KEY,
  display_name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE organizations (
  id uuid PRIMARY KEY,
  name text NOT NULL,
  kind text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT organizations_kind_check CHECK (kind IN ('personal', 'standard'))
);

CREATE TABLE organization_memberships (
  id uuid PRIMARY KEY,
  organization_id uuid NOT NULL REFERENCES organizations (id),
  account_id uuid NOT NULL REFERENCES accounts (id),
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT organization_memberships_org_account_uidx UNIQUE (organization_id, account_id)
);

CREATE INDEX organization_memberships_organization_id_idx
  ON organization_memberships (organization_id);

CREATE INDEX organization_memberships_account_id_idx
  ON organization_memberships (account_id);
