#!/usr/bin/env python3
"""M-008 Account/Organization persistence contract tests."""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIGRATION = REPO_ROOT / "migrations" / "0001_account_organization.sql"
SCHEMA = REPO_ROOT / "packages" / "persistence" / "src" / "schema.ts"
REPOSITORY = REPO_ROOT / "packages" / "persistence" / "src" / "repositories.ts"
ERRORS = REPO_ROOT / "packages" / "persistence" / "src" / "errors.ts"
PACKAGE = REPO_ROOT / "packages" / "persistence" / "package.json"


class M008PersistenceContractTests(unittest.TestCase):
    def test_committed_sql_migration_exists(self) -> None:
        self.assertTrue(MIGRATION.is_file())
        sql = MIGRATION.read_text(encoding="utf-8")
        for table in ("accounts", "organizations", "organization_memberships"):
            self.assertIn(f"CREATE TABLE {table}", sql)

    def test_sql_enforces_membership_uniqueness_and_fks(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("REFERENCES organizations", sql)
        self.assertIn("REFERENCES accounts", sql)
        self.assertRegex(sql, r"UNIQUE\s*\(\s*organization_id\s*,\s*account_id\s*\)")
        self.assertIn("kind IN ('personal', 'standard')", sql)

    def test_sql_and_schema_have_no_provider_or_authz_columns(self) -> None:
        blob = MIGRATION.read_text(encoding="utf-8") + SCHEMA.read_text(encoding="utf-8")
        forbidden = (
            r"provider_id",
            r"external_id",
            r"client_tenant",
            r"\brole\b",
            r"password",
            r"openfga",
            r"session_token",
        )
        for pattern in forbidden:
            self.assertIsNone(re.search(pattern, blob, re.I), pattern)

    def test_repository_scopes_membership_queries_by_organization(self) -> None:
        source = REPOSITORY.read_text(encoding="utf-8")
        self.assertIn("listMembershipsForOrganization", source)
        self.assertIn("rejectProviderAuthority", source)
        self.assertNotIn("listAllMemberships", source)

    def test_provider_authority_is_rejected_in_code(self) -> None:
        source = ERRORS.read_text(encoding="utf-8")
        self.assertIn("ProviderAuthorityRejectedError", source)
        self.assertIn("never establish tenant authority", source)

    def test_exact_runtime_pins(self) -> None:
        manifest = PACKAGE.read_text(encoding="utf-8")
        self.assertIn('"drizzle-orm": "0.45.2"', manifest)
        self.assertIn('"pg": "8.23.0"', manifest)
        self.assertIn('"@types/pg": "8.23.1"', manifest)
        self.assertNotIn("drizzle-kit", manifest)

    def test_does_not_claim_later_iam_missions(self) -> None:
        readme = (REPO_ROOT / "packages" / "persistence" / "README.md").read_text(encoding="utf-8")
        collapsed = " ".join(readme.lower().split())
        self.assertIn("m-009", collapsed)
        self.assertIn("does not implement authentication", collapsed)


if __name__ == "__main__":
    unittest.main()
