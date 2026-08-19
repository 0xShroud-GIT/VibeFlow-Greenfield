#!/usr/bin/env python3
"""M-009 authentication/session boundary contract tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
IDENTITY_PACKAGE = REPO_ROOT / "packages" / "identity" / "package.json"
IDENTITY_SERVICE = REPO_ROOT / "packages" / "identity" / "src" / "service.ts"
IDENTITY_LIVE_TEST = REPO_ROOT / "packages" / "identity" / "src" / "session.live.test.ts"
IDENTITY_SCHEMA = REPO_ROOT / "packages" / "persistence" / "src" / "schema.ts"
MIGRATION = REPO_ROOT / "migrations" / "0002_identity_auth_sessions.sql"
ROOT_PACKAGE = REPO_ROOT / "package.json"


class M009AuthenticationSessionContractTests(unittest.TestCase):
    def test_identity_package_uses_exact_ratified_better_auth(self) -> None:
        manifest = json.loads(IDENTITY_PACKAGE.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "@vibeflow/identity")
        self.assertEqual(manifest["dependencies"]["better-auth"], "1.6.30")
        self.assertEqual(manifest["dependencies"]["kysely"], "0.29.5")
        self.assertEqual(manifest["dependencies"]["@vibeflow/persistence"], "workspace:*")

    def test_committed_sql_persists_library_auth_and_canonical_account_link(self) -> None:
        self.assertTrue(MIGRATION.is_file())
        sql = MIGRATION.read_text(encoding="utf-8")
        for table in (
            "identity_users",
            "identity_sessions",
            "identity_accounts",
            "identity_verifications",
        ):
            self.assertIn(f"CREATE TABLE {table}", sql)
        self.assertIn("vibeflow_account_id uuid NOT NULL UNIQUE REFERENCES accounts", sql)
        self.assertIn("CREATE FUNCTION identity_users_create_vibeflow_account()", sql)
        self.assertIn("CREATE TRIGGER identity_users_create_vibeflow_account", sql)
        self.assertIn("token text NOT NULL UNIQUE", sql)
        self.assertIn("user_id uuid NOT NULL REFERENCES identity_users", sql)
        self.assertIn("password text", sql)

    def test_drizzle_schema_resolves_auth_users_to_canonical_accounts(self) -> None:
        source = IDENTITY_SCHEMA.read_text(encoding="utf-8")
        self.assertIn("identityUsers", source)
        self.assertIn("vibeflowAccountId", source)
        self.assertIn("references(() => accounts.id)", source)
        self.assertIn("CONTROL_PLANE_TABLES", source)

    def test_service_enforces_secure_cookie_and_server_side_linkage(self) -> None:
        source = IDENTITY_SERVICE.read_text(encoding="utf-8")
        for required in (
            'useSecureCookies: true',
            'httpOnly: true',
            'sameSite: "lax"',
            'cookieCache: {',
            'enabled: false',
            'trustedOrigins: [this.baseOrigin]',
            'findAccountByIdentityUserId',
            'input: false',
            'transaction: true',
            'PostgresDialect',
            'vibeflowAccountId: crypto.randomUUID()',
            'authenticated: false',
        ):
            self.assertIn(required, source)
        for forbidden in ("openfga", "organizationId:", "projectId:", "permissions:", "role:"):
            self.assertNotIn(forbidden, source.lower())

    def test_live_suite_requires_database_in_ci_and_covers_replay_revocation_staleness(self) -> None:
        source = IDENTITY_LIVE_TEST.read_text(encoding="utf-8")
        self.assertIn('process.env["CI"] === "true"', source)
        self.assertIn("M-009 PostgreSQL integration requires DATABASE_URL in CI", source)
        for required in (
            "secure HttpOnly session cookies",
            "rolls back the canonical Account",
            "untrusted origin",
            "invalid credentials",
            "revokes logout sessions and rejects replay",
            "expired/stale persisted session",
            "does not project tenant/resource authority",
        ):
            self.assertIn(required, source)

    def test_root_check_retains_m009_contract_and_explicit_live_runner(self) -> None:
        manifest = json.loads(ROOT_PACKAGE.read_text(encoding="utf-8"))
        self.assertIn("test_m009_auth_session.py", manifest["scripts"]["check"])
        self.assertIn("run-m009-auth-integration.py", manifest["scripts"]["check"])
        runner = (REPO_ROOT / "scripts" / "run-m009-auth-integration.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("required in CI", runner)
        self.assertIn("not verification evidence", runner)


if __name__ == "__main__":
    unittest.main()
