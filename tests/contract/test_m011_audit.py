#!/usr/bin/env python3
"""M-011 authoritative audit baseline contract tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/0003_audit_event_ledger.sql"
SERVICE = ROOT / "packages/audit/src/service.ts"
METADATA = ROOT / "packages/audit/src/metadata.ts"
LIVE = ROOT / "packages/audit/src/audit.live.test.ts"
IDENTITY = ROOT / "packages/identity/src/service.ts"
AUTHZ = ROOT / "packages/authorization/src/service.ts"
ROOT_PACKAGE = ROOT / "package.json"


class M011AuditContractTests(unittest.TestCase):
    def test_schema_is_durable_scoped_indexed_and_append_only(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        for required in (
            "CREATE TABLE audit_events", "actor_account_id", "subject_account_id",
            "organization_id", "occurred_at", "request_id", "metadata jsonb",
            "audit_events_account_order_idx", "audit_events_organization_account_order_idx",
            "BEFORE UPDATE OR DELETE", "audit_events are append-only",
        ):
            self.assertIn(required, sql)

    def test_session_audits_are_transactional_and_canonical(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        for required in (
            "identity_sessions_audit_created", "identity_sessions_audit_revoked",
            "vibeflow_account_id", "session.created", "session.revoked",
            "AFTER INSERT ON identity_sessions", "BEFORE DELETE ON identity_sessions",
        ):
            self.assertIn(required, sql)
        self.assertNotIn("NEW.token", sql)
        self.assertNotIn("OLD.token", sql)

    def test_no_generic_client_audit_create_surface_exists(self) -> None:
        source = SERVICE.read_text(encoding="utf-8")
        self.assertNotIn("public async create", source)
        self.assertIn("recordAuthorizationDecision", source)
        self.assertIn("recordAuthenticationFailure", source)
        self.assertIn("canonical", source.lower())

    def test_audit_reads_enforce_account_and_tenant_scope(self) -> None:
        source = SERVICE.read_text(encoding="utf-8")
        for required in (
            "cross-account audit access denied", "cross-tenant audit access denied",
            "organization_memberships", "authenticated !== accountId", "subjectAccountId",
            "occurredAt", "auditEventId",
        ):
            self.assertIn(required, source)

    def test_metadata_is_bounded_and_secret_safe(self) -> None:
        source = METADATA.read_text(encoding="utf-8")
        for required in (
            "MAX_SERIALIZED_BYTES", "AUTHORITY_KEY", "SECRET_KEY", "SECRET_VALUE",
            "[REDACTED]", "plain object", "too deeply nested",
        ):
            self.assertIn(required, source)

    def test_identity_and_authorization_integrations_preserve_boundaries(self) -> None:
        identity = IDENTITY.read_text(encoding="utf-8")
        authz = AUTHZ.read_text(encoding="utf-8")
        self.assertIn("AuthenticationAuditRecorder", identity)
        self.assertIn("recordAuthenticationFailure", identity)
        self.assertNotIn("password: input.password,\n        metadata", identity)
        self.assertIn("AuthorizationAuditRecorder", authz)
        self.assertIn("recordAuthorizationDecision", authz)
        self.assertIn('deny("audit_unavailable")', authz)

    def test_live_security_suite_is_required_in_ci(self) -> None:
        source = LIVE.read_text(encoding="utf-8")
        self.assertIn('process.env["CI"] === "true"', source)
        for required in (
            "cross-account", "cross-tenant", "cannot forge", "redacts secret",
            "stable descending cursor", "append-only", "session creation",
            "authorization denial", "fresh service instance",
        ):
            self.assertIn(required, source)

    def test_root_check_wires_contract_and_explicit_postgres_runner(self) -> None:
        manifest = json.loads(ROOT_PACKAGE.read_text(encoding="utf-8"))
        check = manifest["scripts"]["check"]
        self.assertIn("test_m011_audit.py", check)
        self.assertIn("run-m011-audit-integration.py", check)
        runner = (ROOT / "scripts/run-m011-audit-integration.py").read_text(encoding="utf-8")
        self.assertIn("required in CI", runner)
        self.assertIn("not verification evidence", runner)


if __name__ == "__main__":
    unittest.main()
