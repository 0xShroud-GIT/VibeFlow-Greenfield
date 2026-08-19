#!/usr/bin/env python3
"""M-012 Project authority contract tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/0004_project_authority.sql"
PERSISTENCE_SCHEMA = ROOT / "packages/persistence/src/schema.ts"
PERSISTENCE_REPO = ROOT / "packages/persistence/src/repositories.ts"
PERSISTENCE_LIVE = ROOT / "packages/persistence/src/project.live.test.ts"
AUTHZ_SERVICE = ROOT / "packages/authorization/src/service.ts"
AUTHZ_TYPES = ROOT / "packages/authorization/src/types.ts"
AUTHZ_PROJECT_LIVE = ROOT / "packages/authorization/src/project.live.test.ts"
PROJECT_SERVICE = ROOT / "packages/project/src/service.ts"
PROJECT_LIVE = ROOT / "packages/project/src/project.live.test.ts"
PROJECT_PACKAGE = ROOT / "packages/project/package.json"
AUDIT_SERVICE = ROOT / "packages/audit/src/service.ts"
ROOT_PACKAGE = ROOT / "package.json"


class M012ProjectContractTests(unittest.TestCase):
    def test_migration_is_durable_scoped_indexed(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        for required in (
            "CREATE TABLE projects",
            "id uuid PRIMARY KEY",
            "organization_id uuid NOT NULL REFERENCES organizations",
            "name text NOT NULL",
            "created_at timestamptz",
            "updated_at timestamptz",
            "projects_organization_id_idx",
            "char_length(trim(name)) > 0",
        ):
            self.assertIn(required, sql)
        # No provider/external identifier ever establishes authority
        self.assertNotIn("provider_id", sql.lower())
        self.assertNotIn("external_id", sql.lower())

    def test_persistence_schema_defines_project(self) -> None:
        source = PERSISTENCE_SCHEMA.read_text(encoding="utf-8")
        for required in (
            "export const projects",
            "organizationId",
            "ProjectRow",
            "projects,",
        ):
            self.assertIn(required, source)

    def test_persistence_repo_rejects_provider_authority_and_has_tenant_safe_methods(self) -> None:
        source = PERSISTENCE_REPO.read_text(encoding="utf-8")
        for required in (
            "class ProjectRepository",
            "createProject",
            "getProjectById",
            "listProjectsForOrganization",
            "rejectProviderAuthority",
            "organizationId",
            "ProjectRow",
        ):
            self.assertIn(required, source)

    def test_authorization_registers_project_and_resolves_canonical_tenant(self) -> None:
        types_src = AUTHZ_TYPES.read_text(encoding="utf-8")
        service_src = AUTHZ_SERVICE.read_text(encoding="utf-8")
        # RESOURCE_TYPES must include project
        self.assertIn('"project"', types_src)
        self.assertIn("getProjectById", service_src)
        self.assertIn("authorizeProjectResource", service_src)
        self.assertIn("project.organizationId", service_src)
        self.assertIn("no_membership", service_src)
        self.assertIn("unknown_resource", service_src)

    def test_project_service_is_server_authoritative_and_tenant_safe(self) -> None:
        source = PROJECT_SERVICE.read_text(encoding="utf-8")
        for required in (
            "server-generated",
            "canonical Organization",
            "server-controlled",
            "cross-tenant",
            "fails closed",
            "ProjectService",
            "createProject",
            "getProject",
            "listProjects",
            "updateProject",
            "requireUuid",
            "TenantAuthorizationService",
            "ProjectRepository",
            "TenantRepository",
        ):
            # case-insensitive check for descriptive comments
            self.assertIn(required.split()[0].lower(), source.lower())
        # Explicit checks
        self.assertIn("createProject", source)
        self.assertIn("getProject", source)
        self.assertIn("listProjects", source)
        self.assertIn("authorize", source)
        self.assertNotIn("providerId", source)
        self.assertNotIn("clientTenantId", source)

    def test_audit_service_scopes_project_authorization(self) -> None:
        source = AUDIT_SERVICE.read_text(encoding="utf-8")
        self.assertIn("resource.type === \"project\"", source)
        self.assertIn("SELECT organization_id FROM projects", source)

    def test_project_package_uses_only_ratified_deps(self) -> None:
        manifest = json.loads(PROJECT_PACKAGE.read_text(encoding="utf-8"))
        self.assertEqual(manifest["name"], "@vibeflow/project")
        deps = manifest.get("dependencies", {})
        # Only workspace deps that are ratified
        for dep in deps:
            self.assertTrue(dep.startswith("@vibeflow/"))
        self.assertNotIn("openfga", json.dumps(manifest).lower())

    def test_live_suites_require_database_in_ci_and_cover_negatives(self) -> None:
        for path, label in (
            (PERSISTENCE_LIVE, "persistence"),
            (AUTHZ_PROJECT_LIVE, "authorization"),
            (PROJECT_LIVE, "service"),
        ):
            source = path.read_text(encoding="utf-8")
            self.assertIn('process.env["CI"] === "true"', source, f"{label} live must require DATABASE_URL in CI")
            lowered = source.lower()
            # persistence live covers tenant-safe and forged; authorization and service cover cross-tenant
            if label == "persistence":
                for required in ("tenant-safe", "forged", "unknown", "provider authority"):
                    self.assertIn(required, lowered, f"{label} live must cover {required}")
            else:
                for required in (
                    "cross-tenant",
                    "forged",
                    "unknown",
                    "revoked",
                    "stale",
                ):
                    self.assertIn(required, lowered, f"{label} live must cover {required}")

    def test_root_check_wires_m012_contract(self) -> None:
        manifest = json.loads(ROOT_PACKAGE.read_text(encoding="utf-8"))
        check = manifest["scripts"]["check"]
        self.assertIn("test_m012_project.py", check)


if __name__ == "__main__":
    unittest.main()
