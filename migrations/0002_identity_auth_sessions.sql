-- M-009 VibeFlow Identity authentication/session persistence.
-- Better Auth owns credential hashing and session mechanics. VibeFlow owns the
-- link from each auth user to its canonical product Account.

CREATE TABLE identity_users (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  email text NOT NULL UNIQUE,
  email_verified boolean NOT NULL DEFAULT false,
  image text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  vibeflow_account_id uuid NOT NULL UNIQUE REFERENCES accounts (id) ON DELETE RESTRICT
);

-- The trigger is deliberately BEFORE INSERT: it creates the canonical VibeFlow
-- Account before the identity_users foreign key is checked, inside Better Auth's
-- surrounding PostgreSQL signup transaction.
CREATE FUNCTION identity_users_create_vibeflow_account()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  INSERT INTO accounts (id, display_name, created_at, updated_at)
  VALUES (
    NEW.vibeflow_account_id,
    NEW.name,
    COALESCE(NEW.created_at, now()),
    COALESCE(NEW.updated_at, now())
  );
  RETURN NEW;
END;
$$;

CREATE TRIGGER identity_users_create_vibeflow_account
BEFORE INSERT ON identity_users
FOR EACH ROW
EXECUTE FUNCTION identity_users_create_vibeflow_account();

CREATE TABLE identity_sessions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  expires_at timestamptz NOT NULL,
  token text NOT NULL UNIQUE,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  ip_address text,
  user_agent text,
  user_id uuid NOT NULL REFERENCES identity_users (id) ON DELETE CASCADE
);

CREATE INDEX identity_sessions_user_id_idx ON identity_sessions (user_id);

CREATE TABLE identity_accounts (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  account_id text NOT NULL,
  provider_id text NOT NULL,
  user_id uuid NOT NULL REFERENCES identity_users (id) ON DELETE CASCADE,
  access_token text,
  refresh_token text,
  id_token text,
  access_token_expires_at timestamptz,
  refresh_token_expires_at timestamptz,
  scope text,
  password text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT identity_accounts_provider_account_uidx UNIQUE (provider_id, account_id)
);

CREATE INDEX identity_accounts_user_id_idx ON identity_accounts (user_id);

CREATE TABLE identity_verifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  identifier text NOT NULL,
  value text NOT NULL,
  expires_at timestamptz NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX identity_verifications_identifier_idx ON identity_verifications (identifier);
