#!/usr/bin/env python3
"""M-013 Artifact/ArtifactRelation authority contract tests."""

from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MIGRATION = ROOT / "migrations/0005_artifact_authority.sql"
PERSISTENCE_SCHEMA = ROOT / "packages/persistence/src/schema.ts"
PERSISTENCE_REPO = ROOT / "packages/persistence/src/repositories.ts"
PERSISTENCE_LIVE = ROOT / "packages/persistence/src/artifact.live.test.ts"
AUTHZ_TYPES = ROOT / "packages/authorization/src/types.ts"
AUTHZ_SERVICE = ROOT / "packages/authorization/src/service.ts"
AUTHZ_LIVE = ROOT / "packages/authorization/src/artifact.live.test.ts"
PROJECT_SERVICE = ROOT / "packages/project/src/artifact-service.ts"
PROJECT_LIVE = ROOT / "packages/project/src/artifact.live.test.ts"
AUDIT_SERVICE = ROOT / "packages/audit/src/service.ts"
AUDIT_SCOPE_LIVE = ROOT / "packages/audit/src/artifact-scope.live.test.ts"
ROOT_PACKAGE = ROOT / "package.json"


class M013ArtifactContractTests(unittest.TestCase):
    def test_migration_is_durable_scoped_indexed(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        for required in (
            "CREATE TABLE artifacts",
            "CREATE TABLE artifact_relations",
            "id uuid PRIMARY KEY",
            "project_id uuid NOT NULL REFERENCES projects (id)",
            "type text NOT NULL",
            "relation_kind text NOT NULL",
            "artifact_relations_project_subject_fk",
            "artifact_relations_project_object_fk",
            "artifacts_project_id_id_uidx",
            "artifact_relations_unique_edge",
            "artifact_relations_self_edge",
            "subject_artifact_id <> object_artifact_id",
            "artifact_relations_kind_valid",
            "artifact_relations_project_id_idx",
        ):
            self.assertIn(required, sql)
        # relation kinds are the exact canonical resource-model semantics
        for kind in ("lineage", "variant", "derived-from", "contains"):
            self.assertIn(f"'{kind}'", sql)
        # No provider/external identifier ever establishes authority
        self.assertNotIn("provider_id", sql.lower())
        self.assertNotIn("external_id", sql.lower())

    def test_persistence_schema_defines_artifacts_and_relations(self) -> None:
        source = PERSISTENCE_SCHEMA.read_text(encoding="utf-8")
        for required in (
            "export const artifacts",
            "export const artifactRelations",
            "ARTIFACT_RELATION_KINDS",
            "projectId",
            "relationKind",
            "ArtifactRow",
            "ArtifactRelationRow",
            "artifacts_project_id_id_uidx",
            "artifact_relations_project_subject_fk",
        ):
            self.assertIn(required, source)

    def test_persistence_repo_has_artifact_repository_and_rejects_provider_authority(self) -> None:
        source = PERSISTENCE_REPO.read_text(encoding="utf-8")
        for required in (
            "class ArtifactRepository",
            "createArtifact",
            "getArtifactById",
            "listArtifactsForProject",
            "createArtifactRelation",
            "getArtifactRelationById",
            "listArtifactRelationsForProject",
            "rejectProviderAuthority",
            "CrossProjectArtifactRelationError",
            "DuplicateArtifactRelationError",
        ):
            self.assertIn(required, source)

    def test_authorization_registers_artifact_and_resolves_canonical_tenant(self) -> None:
        types_src = AUTHZ_TYPES.read_text(encoding="utf-8")
        service_src = AUTHZ_SERVICE.read_text(encoding="utf-8")
        self.assertIn('"artifact"', types_src)
        self.assertIn('"artifact_relation"', types_src)
        self.assertIn("getArtifactById", service_src)
        self.assertIn("getArtifactRelationById", service_src)
        self.assertIn("authorizeArtifactResource", service_src)
        self.assertIn("authorizeArtifactRelationResource", service_src)
        self.assertIn("artifact.projectId", service_src)
        self.assertIn("relation.projectId", service_src)
        self.assertIn("no_membership", service_src)
        self.assertIn("unknown_resource", service_src)

    def test_artifact_service_is_server_authoritative_and_tenant_safe(self) -> None:
        source = PROJECT_SERVICE.read_text(encoding="utf-8")
        lowered = source.lower()
        for required in (
            "ArtifactService",
            "createArtifact",
            "getArtifact",
            "listArtifacts",
            "createArtifactRelation",
            "getArtifactRelation",
            "listArtifactRelations",
            "TenantAuthorizationService",
            "ArtifactRepository",
        ):
            self.assertIn(required, source)
        for required in (
            "fails closed",
            "cross-tenant",
            "same canonical project",
            "server-generated",
        ):
            self.assertIn(required, lowered)
        # relation derives scope from canonical endpoints, never a client project claim
        self.assertIn("subject.projectId !== object.projectId", source)
        self.assertNotIn("providerId", source)

    def test_audit_service_scopes_artifact_and_relation_authorization(self) -> None:
        source = AUDIT_SERVICE.read_text(encoding="utf-8")
        self.assertIn('resource.type === "artifact"', source)
        self.assertIn('resource.type === "artifact_relation"', source)
        self.assertIn("FROM artifacts a JOIN projects p", source)
        self.assertIn("FROM artifact_relations r JOIN projects p", source)

    def test_live_suites_require_database_in_ci_and_cover_negatives(self) -> None:
        for path, label in (
            (PERSISTENCE_LIVE, "persistence"),
            (AUTHZ_LIVE, "authorization"),
            (PROJECT_LIVE, "service"),
            (AUDIT_SCOPE_LIVE, "audit"),
        ):
            source = path.read_text(encoding="utf-8")
            self.assertIn('process.env["CI"] === "true"', source, f"{label} live must require DATABASE_URL in CI")
            lowered = source.lower()
            if label == "persistence":
                for required in ("cross-project", "duplicate", "self-edge", "composite fk", "provider"):
                    self.assertIn(required, lowered, f"{label} live must cover {required}")
            elif label == "authorization":
                for required in ("cross-tenant", "unknown_resource", "revoked", "no_membership"):
                    self.assertIn(required, lowered, f"{label} live must cover {required}")
            elif label == "service":
                for required in ("cross-project", "cross-tenant", "same organization", "revoked", "forged"):
                    self.assertIn(required, lowered, f"{label} live must cover {required}")
            else:  # audit
                for required in ("audit_unavailable", "outcome = 'allowed'"):
                    self.assertIn(required, lowered, f"{label} live must cover {required}")

    def test_root_check_wires_m013_contract_and_integration(self) -> None:
        manifest = json.loads(ROOT_PACKAGE.read_text(encoding="utf-8"))
        check = manifest["scripts"]["check"]
        self.assertIn("test_m013_artifact.py", check)
        self.assertIn("run-m013-artifact-integration.py", check)


if __name__ == "__main__":
    unittest.main()
