-- M-011 VibeFlow authoritative audit baseline.
-- AuditEvent is append-only security/control-plane evidence, not an application log.

CREATE TABLE audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  occurred_at timestamptz NOT NULL DEFAULT clock_timestamp(),
  actor_account_id uuid REFERENCES accounts (id) ON DELETE RESTRICT,
  subject_account_id uuid NOT NULL REFERENCES accounts (id) ON DELETE RESTRICT,
  organization_id uuid REFERENCES organizations (id) ON DELETE RESTRICT,
  action text NOT NULL,
  resource_type text NOT NULL,
  resource_id uuid,
  outcome text NOT NULL,
  reason text,
  request_id uuid,
  source text NOT NULL,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  CONSTRAINT audit_events_outcome_check CHECK (outcome IN ('allowed', 'denied', 'succeeded', 'failed')),
  CONSTRAINT audit_events_source_check CHECK (source IN ('identity', 'authorization', 'audit')),
  CONSTRAINT audit_events_metadata_object_check CHECK (jsonb_typeof(metadata) = 'object')
);

CREATE INDEX audit_events_account_order_idx
  ON audit_events (subject_account_id, occurred_at DESC, id DESC);
CREATE INDEX audit_events_organization_account_order_idx
  ON audit_events (organization_id, subject_account_id, occurred_at DESC, id DESC)
  WHERE organization_id IS NOT NULL;
CREATE INDEX audit_events_request_id_idx
  ON audit_events (request_id)
  WHERE request_id IS NOT NULL;

CREATE FUNCTION audit_events_reject_mutation()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
  RAISE EXCEPTION 'audit_events are append-only';
END;
$$;

CREATE TRIGGER audit_events_append_only
BEFORE UPDATE OR DELETE ON audit_events
FOR EACH ROW
EXECUTE FUNCTION audit_events_reject_mutation();

-- Session creation and revocation are recorded in the same PostgreSQL
-- transaction as the library-owned session mutation. A required audit insert
-- failure therefore rolls back the security-critical session operation.
CREATE FUNCTION identity_sessions_audit_created()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  canonical_account_id uuid;
BEGIN
  SELECT vibeflow_account_id INTO STRICT canonical_account_id
  FROM identity_users
  WHERE id = NEW.user_id;

  INSERT INTO audit_events (
    actor_account_id, subject_account_id, action, resource_type, resource_id,
    outcome, source, metadata
  ) VALUES (
    canonical_account_id, canonical_account_id, 'session.created', 'session', NEW.id,
    'succeeded', 'identity', '{}'::jsonb
  );
  RETURN NEW;
END;
$$;

CREATE TRIGGER identity_sessions_audit_created
AFTER INSERT ON identity_sessions
FOR EACH ROW
EXECUTE FUNCTION identity_sessions_audit_created();

CREATE FUNCTION identity_sessions_audit_revoked()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  canonical_account_id uuid;
BEGIN
  SELECT vibeflow_account_id INTO STRICT canonical_account_id
  FROM identity_users
  WHERE id = OLD.user_id;

  INSERT INTO audit_events (
    actor_account_id, subject_account_id, action, resource_type, resource_id,
    outcome, source, metadata
  ) VALUES (
    canonical_account_id, canonical_account_id, 'session.revoked', 'session', OLD.id,
    'succeeded', 'identity', '{}'::jsonb
  );
  RETURN OLD;
END;
$$;

CREATE TRIGGER identity_sessions_audit_revoked
BEFORE DELETE ON identity_sessions
FOR EACH ROW
EXECUTE FUNCTION identity_sessions_audit_revoked();
