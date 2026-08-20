#!/usr/bin/env python3
"""M-014 imports/templates lifecycle contract tests.

These assert the M-014 authority contract as source-level invariants: what the
migration/schema must enforce, what the services must order, and — critically —
what M-014 must NOT invent (canonical Import/Template resources, new event
families, new public state machines, or provider adapters).
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

MIGRATION = ROOT / "migrations/0006_project_import_clone.sql"
PERSISTENCE_SCHEMA = ROOT / "packages/persistence/src/schema.ts"
LIFECYCLE_REPO = ROOT / "packages/persistence/src/lifecycle-repository.ts"
LIFECYCLE_LIVE = ROOT / "packages/persistence/src/lifecycle.live.test.ts"
PERSISTENCE_INDEX = ROOT / "packages/persistence/src/index.ts"

SCANNER = ROOT / "packages/project/src/archive/scanner.ts"
SCANNER_TEST = ROOT / "packages/project/src/archive/scanner.test.ts"
PATH_POLICY = ROOT / "packages/project/src/archive/path-policy.ts"
LIMITS = ROOT / "packages/project/src/archive/limits.ts"
ARCHIVE_ERRORS = ROOT / "packages/project/src/archive/errors.ts"
STAGING = ROOT / "packages/project/src/archive/staging.ts"
ZIP_READER = ROOT / "packages/project/src/archive/zip.ts"
TAR_READER = ROOT / "packages/project/src/archive/tar.ts"

IMPORT_SERVICE = ROOT / "packages/project/src/import-service.ts"
CLONE_SERVICE = ROOT / "packages/project/src/clone-service.ts"
IMPORT_LIVE = ROOT / "packages/project/src/import.live.test.ts"
CLONE_LIVE = ROOT / "packages/project/src/clone.live.test.ts"
PROJECT_INDEX = ROOT / "packages/project/src/index.ts"
PROJECT_EXPORTS_TEST = ROOT / "packages/project/src/exports.test.ts"

CANONICAL_RESOURCES = ROOT / "master-build-system/02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml"
EVENT_CATALOG = ROOT / "master-build-system/03_BACKEND/EVENT_CATALOG.yaml"
STATE_MACHINES = ROOT / "master-build-system/03_BACKEND/STATE_MACHINES.yaml"
CAPABILITY_CSV = ROOT / "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv"
CAPABILITY_YAML = ROOT / "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml"
CONTRACT_TRACE = ROOT / "master-build-system/09_CONTRACTS/CAPABILITY_CONTRACT_TRACE.csv"
AUTHZ_TYPES = ROOT / "packages/authorization/src/types.ts"
ROOT_PACKAGE = ROOT / "package.json"
EVIDENCE_JSON = ROOT / "evidence/missions/M-014/IMPORT_CLONE_LIFECYCLE.json"
EVIDENCE_MD = ROOT / "evidence/missions/M-014/IMPORT_CLONE_LIFECYCLE.md"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def flatten(text: str) -> str:
    """Collapse comment wrapping so prose assertions survive line breaks."""
    return re.sub(r"\s+", " ", text.replace("*", " "))


def strip_comments(text: str) -> str:
    """Remove TS comments so 'must not implement' checks see code, not prose.

    Documenting deferred scope (e.g. naming RepositoryBinding as a non-goal) is
    required by M-014; implementing it is forbidden. Only code is checked.
    """
    without_block = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"^\s*//.*$", "", without_block, flags=re.MULTILINE)



class M014MigrationTests(unittest.TestCase):
    def test_migration_defines_internal_lifecycle_records(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        for required in (
            "CREATE TABLE project_archive_imports",
            "CREATE TABLE project_archive_import_entries",
            "CREATE TABLE project_clone_plans",
            "CREATE TABLE project_clone_artifact_map",
            "id uuid PRIMARY KEY",
            "organization_id uuid NOT NULL REFERENCES organizations (id)",
            "actor_account_id uuid NOT NULL REFERENCES accounts (id)",
            "created_at timestamptz NOT NULL DEFAULT now()",
        ):
            self.assertIn(required, sql)

    def test_migration_restricts_formats_and_source_kind(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        # Exactly the formats the ledger proves for VF-PRJ-004.
        self.assertIn("archive_format IN ('zip', 'tar')", sql)
        self.assertIn("source_kind = 'archive'", sql)
        # No provider adapter may be smuggled into the accepted source kinds.
        for provider in ("github", "bitbucket", "figma", "vercel", "bolt", "lovable"):
            self.assertNotIn(f"'{provider}'", sql.lower())

    def test_migration_enforces_server_derived_hashes(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("archive_sha256 ~ '^[0-9a-f]{64}$'", sql)
        self.assertIn("manifest_sha256 ~ '^[0-9a-f]{64}$'", sql)

    def test_migration_never_stores_archive_bytes(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8").lower()
        for forbidden in (
            "archive_bytes",
            "content bytea",
            "payload bytea",
            "file_content",
            "blob bytea",
        ):
            self.assertNotIn(forbidden, sql)

    def test_migration_backstops_unsafe_manifest_paths(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("project_archive_import_entries_path_relative", sql)
        self.assertIn("normalized_path !~ '^/'", sql)
        self.assertIn(r"normalized_path !~ '(^|/)\.\.(/|$)'", sql)
        self.assertIn("normalized_path !~ '^[A-Za-z]:'", sql)
        # duplicate normalized path rejection
        self.assertIn("project_archive_import_entries_path_uidx", sql)

    def test_migration_enforces_same_organization_clone_policy(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        # Both endpoints pinned to the plan's single canonical Organization.
        self.assertIn("project_clone_plans_org_source_fk", sql)
        self.assertIn("project_clone_plans_org_target_fk", sql)
        self.assertIn("REFERENCES projects (organization_id, id)", sql)
        self.assertIn("projects_organization_id_id_uidx", sql)
        self.assertIn("project_clone_plans_distinct_projects", sql)

    def test_migration_enforces_command_idempotency(self) -> None:
        sql = MIGRATION.read_text(encoding="utf-8")
        self.assertIn("project_archive_imports_idempotency_uidx", sql)
        self.assertIn("project_clone_plans_idempotency_uidx", sql)
        self.assertIn("UNIQUE (organization_id, actor_account_id, idempotency_key)", sql)


class M014NoInventedAuthorityTests(unittest.TestCase):
    """M-014 must not invent canonical resources, events, or state machines."""

    def test_canonical_resource_model_has_no_import_or_template_resource(self) -> None:
        text = CANONICAL_RESOURCES.read_text(encoding="utf-8")
        resources = re.findall(r"^- resource: (.+)$", text, re.MULTILINE)
        for invented in (
            "Import",
            "ProjectImport",
            "Template",
            "ProjectTemplate",
            "ArchiveImport",
            "Clone",
            "ProjectClonePlan",
        ):
            self.assertNotIn(invented, resources, f"{invented} must not be canonical")

    def test_event_catalog_has_no_invented_import_template_clone_events(self) -> None:
        text = EVENT_CATALOG.read_text(encoding="utf-8")
        names = re.findall(r"^  name: (.+)$", text, re.MULTILINE)
        for name in names:
            self.assertFalse(
                name.startswith(("import.", "project.import.", "template.", "clone.")),
                f"invented event family: {name}",
            )
        # The canonical Project events remain the contract.
        self.assertIn("project.created", names)

    def test_state_machines_have_no_invented_import_template_clone_states(self) -> None:
        text = STATE_MACHINES.read_text(encoding="utf-8")
        machines = re.findall(r"^  (\w+):$", text, re.MULTILINE)
        for invented in ("Import", "Template", "Clone", "ProjectImport", "ClonePlan"):
            self.assertNotIn(invented, machines)

    def test_authorization_registers_no_public_import_or_template_resource(self) -> None:
        text = AUTHZ_TYPES.read_text(encoding="utf-8")
        block = text.split("RESOURCE_TYPES")[1].split("]")[0]
        for invented in ('"import"', '"template"', '"clone"', '"archive"'):
            self.assertNotIn(invented, block)
        # The canonical resources remain the authorization vocabulary.
        for canonical in ('"organization"', '"project"', '"artifact"', '"artifact_relation"'):
            self.assertIn(canonical, block)

    def test_services_authorize_against_canonical_resources_only(self) -> None:
        for path in (IMPORT_SERVICE, CLONE_SERVICE):
            source = path.read_text(encoding="utf-8")
            used = set(re.findall(r'resource:\s*\{\s*type:\s*"(\w+)"', source))
            self.assertTrue(used, f"{path.name} must authorize something")
            self.assertTrue(
                used <= {"organization", "project", "artifact", "artifact_relation"},
                f"{path.name} authorizes a non-canonical resource type: {used}",
            )

    def test_no_provider_adapter_scope_is_implemented(self) -> None:
        """VF-PRJ-008..012 and binding/provider work stay out of M-014."""
        forbidden = (
            "RepositoryBinding",
            "WorkspaceBinding",
            "octokit",
            "bitbucket",
            "figma",
            "vercel",
            "git clone",
            "gitclone",
            "provisionWorkspace",
        )
        for path in (
            IMPORT_SERVICE,
            CLONE_SERVICE,
            SCANNER,
            LIFECYCLE_REPO,
            STAGING,
            ZIP_READER,
            TAR_READER,
        ):
            # Comments are stripped: documenting deferred scope is required,
            # implementing it is forbidden.
            code = strip_comments(read(path)).lower()
            for token in forbidden:
                self.assertNotIn(
                    token.lower(),
                    code,
                    f"{path.name} must not implement deferred provider scope: {token}",
                )


class M014ArchiveScannerTests(unittest.TestCase):
    def test_scanner_documents_structural_not_malware_scope(self) -> None:
        source = SCANNER.read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertIn("structural", lowered)
        # M-014 must not claim malware scanning.
        self.assertIn("not a malware scanner", lowered)
        self.assertNotIn("malware detected", lowered)
        self.assertNotIn("virus", lowered)

    def test_scanner_never_extracts_or_executes(self) -> None:
        for path in (SCANNER, ZIP_READER, TAR_READER, PATH_POLICY):
            source = path.read_text(encoding="utf-8")
            for forbidden in (
                "child_process",
                "execSync",
                "spawnSync",
                "eval(",
                "new Function(",
                "writeFileSync",
                "mkdirSync",
                "createWriteStream",
            ):
                self.assertNotIn(
                    forbidden,
                    source,
                    f"{path.name} must never extract or execute archive content",
                )

    def test_rejection_vocabulary_covers_required_hostile_shapes(self) -> None:
        source = ARCHIVE_ERRORS.read_text(encoding="utf-8")
        for code in (
            "malformed_archive",
            "path_absolute",
            "path_traversal",
            "path_windows_drive",
            "path_unc",
            "path_backslash",
            "path_invalid_characters",
            "symlink_entry",
            "hardlink_entry",
            "special_entry",
            "duplicate_path",
            "path_collision",
            "too_many_entries",
            "entry_too_large",
            "total_size_exceeded",
            "path_too_deep",
            "compression_ratio_exceeded",
            "content_size_mismatch",
        ):
            self.assertIn(f'"{code}"', source)

    def test_limits_are_documented_as_implementation_constants(self) -> None:
        source = LIMITS.read_text(encoding="utf-8")
        prose = flatten(source).lower()
        # The master defines no numeric thresholds; the code must say so.
        self.assertIn("does not define numeric thresholds", prose)
        self.assertIn("implementation safety limit", prose)
        for limit in (
            "maxArchiveBytes",
            "maxEntryCount",
            "maxEntryBytes",
            "maxTotalUncompressedBytes",
            "maxPathDepth",
            "maxPathLength",
            "maxCompressionRatio",
        ):
            self.assertIn(limit, source)

    def test_manifest_is_deterministic_and_server_derived(self) -> None:
        source = SCANNER.read_text(encoding="utf-8")
        self.assertIn("createHash(\"sha256\")", source)
        self.assertIn("ARCHIVE_MANIFEST_VERSION", source)
        lowered = source.lower()
        self.assertIn("deterministic", lowered)
        self.assertIn("server-derived", lowered)
        # Sorted ordering makes the fingerprint reproducible.
        self.assertIn(".sort(", source)

    def test_path_policy_rejects_rather_than_silently_repairs(self) -> None:
        source = PATH_POLICY.read_text(encoding="utf-8")
        for code in (
            "path_absolute",
            "path_traversal",
            "path_windows_drive",
            "path_unc",
            "path_backslash",
            "path_invalid_characters",
            "path_too_deep",
            "path_too_long",
        ):
            self.assertIn(code, source)

    def test_scanner_tests_cover_every_required_negative(self) -> None:
        source = SCANNER_TEST.read_text(encoding="utf-8").lower()
        for scenario in (
            "malformed",
            "absolute",
            "traversal",
            "windows drive",
            "unc",
            "backslash",
            "nul",
            "symlink",
            "hardlink",
            "device",
            "duplicate",
            "collision",
            "too many entries",
            "expansion ratio",
            "declared size lies",
        ):
            self.assertIn(scenario, source, f"missing scanner negative: {scenario}")

    def test_zip_reader_reconciles_local_and_central_metadata(self) -> None:
        """A ZIP stores entry metadata twice; disagreement must be rejected.

        Trusting only the central directory lets a hostile archive show a safe
        name to the scanner and a traversal-shaped name to a later extractor.
        """
        source = ZIP_READER.read_text(encoding="utf-8")

        # Raw filename BYTES, never normalized strings.
        self.assertIn("localNameBytes.equals(entry.rawPathBytes)", source)
        self.assertIn("rawPathBytes", source)

        # Method, flags, CRC and both sizes are reconciled.
        self.assertIn("localMethod !== entry.compressionMethod", source)
        self.assertIn("localSignificant !== centralSignificant", source)
        self.assertIn("localCrc !== entry.crc32", source)
        self.assertIn("localCompressedSize !== entry.compressedSize", source)
        self.assertIn("localDeclaredSize !== entry.declaredSize", source)

        # Data descriptors are handled explicitly, not silently trusted.
        self.assertIn("FLAG_DATA_DESCRIPTOR", source)
        prose = flatten(source).lower()
        self.assertIn("data descriptor", prose)

    def test_zip_reader_verifies_payload_crc(self) -> None:
        source = ZIP_READER.read_text(encoding="utf-8")
        self.assertIn("computeCrc32(content)", source)
        self.assertIn("actualCrc !== entry.crc32", source)
        self.assertIn("content_checksum_mismatch", source)

        # CRC supplements SHA-256 manifest hashing, it does not replace it.
        self.assertIn("createHash(\"sha256\")", SCANNER.read_text(encoding="utf-8"))

    def test_zip_reader_preserves_bounded_decompression(self) -> None:
        source = ZIP_READER.read_text(encoding="utf-8")
        # The ceiling stays enforced BY the decompressor.
        self.assertIn("maxOutputLength: limits.maxEntryBytes", source)
        self.assertIn("entry_too_large", source)
        # No allocation sized from a hostile declared size.
        self.assertNotIn("Buffer.alloc(entry.declaredSize", source)
        self.assertNotIn("Buffer.allocUnsafe(entry.declaredSize", source)

    def test_scanner_tests_cover_zip_ambiguity_negatives(self) -> None:
        source = SCANNER_TEST.read_text(encoding="utf-8").lower()
        for scenario in (
            "traversal local name",
            "absolute local name",
            "differ without any traversal",
            "raw filename bytes rather than normalized",
            "compression-method mismatch",
            "general-purpose flag mismatch",
            "local-header crc that disagrees",
            "compressed size that disagrees",
            "uncompressed size that disagrees",
            "zeroed local-header values",
            "data-descriptor form",
            "content crc does not match",
            "tampered with after the crc",
            "still accepts valid zips",
        ):
            self.assertIn(scenario, source, f"missing ZIP ambiguity negative: {scenario}")


class M014StagingBoundaryTests(unittest.TestCase):
    def test_staging_is_not_a_canonical_object_storage_binding(self) -> None:
        prose = flatten(read(STAGING)).lower()
        # The boundary must be documented, not merely implied.
        self.assertIn("content-addressed", prose)
        self.assertIn("not", prose)
        self.assertIn("objectstoragebinding", prose.replace(" ", "").replace("`", ""))
        self.assertIn("credential surface", prose)

        # ...and must not actually be a provider/credential surface.
        code = strip_comments(read(STAGING)).lower()
        for forbidden in ("credential", "accesskey", "secretkey", "s3client", "bucket"):
            self.assertNotIn(forbidden, code)

    def test_staging_ref_is_server_derived_content_address(self) -> None:
        source = STAGING.read_text(encoding="utf-8")
        self.assertIn("sha256", source)
        self.assertIn("stagedArchiveRefFor", source)


class M014ImportServiceTests(unittest.TestCase):
    def test_import_service_documents_and_follows_authority_sequence(self) -> None:
        source = IMPORT_SERVICE.read_text(encoding="utf-8")
        lowered = source.lower()
        for phrase in (
            "server-generated",
            "fail-closed",
            "idempotency",
            "never executed",
        ):
            self.assertIn(phrase, lowered)

        # Authorization must precede scanning, which must precede persistence.
        authorize_at = source.index("action: \"create\"")
        scan_at = source.index("scanArchive({")
        apply_at = source.index("applyArchiveImport({")
        self.assertLess(authorize_at, scan_at, "authorization must precede archive scanning")
        self.assertLess(scan_at, apply_at, "scanning must precede durable persistence")

    def test_import_service_rejects_authority_shaped_fields(self) -> None:
        source = IMPORT_SERVICE.read_text(encoding="utf-8")
        self.assertIn("FORBIDDEN_AUTHORITY_KEYS", source)
        for key in (
            '"providerId"',
            '"externalId"',
            '"repositoryId"',
            '"workspaceId"',
            '"projectId"',
            '"manifestSha256"',
            '"archiveSha256"',
            '"actorAccountId"',
        ):
            self.assertIn(key, source)

    def test_import_service_creates_no_artifact_per_file(self) -> None:
        source = IMPORT_SERVICE.read_text(encoding="utf-8")
        # No Artifact creation belongs in the archive import path.
        self.assertNotIn("createArtifact", source)

    def test_import_live_tests_cover_required_negatives(self) -> None:
        source = IMPORT_LIVE.read_text(encoding="utf-8").lower()
        for scenario in (
            "valid zip",
            "valid tar",
            "malformed archive",
            "traversal path",
            "absolute path",
            "windows drive",
            "unc path",
            "symlink entry",
            "hardlink entry",
            "device/special entry",
            "duplicate normalized path",
            "forged",
            "cross tenant",
            "revoked",
            "random",
            "authority-shaped",
            "idempotency key",
            "rolls back",
            "fails closed",
        ):
            self.assertIn(scenario, source, f"missing import negative: {scenario}")


class M014CloneServiceTests(unittest.TestCase):
    def test_clone_service_orders_authorization_fail_closed(self) -> None:
        source = CLONE_SERVICE.read_text(encoding="utf-8")

        source_authz = source.index('action: "read"')
        canonical_load = source.index("getProjectById(sourceProjectId)")
        derive_org = source.index("sourceProject.organizationId")
        create_authz = source.index('action: "create"')
        materialize = source.index("applyClonePlan({")

        # 2 -> 3 -> 4 -> 5 -> 7 from the M-014 required ordering.
        self.assertLess(source_authz, canonical_load, "source authz must precede canonical load")
        self.assertLess(canonical_load, derive_org, "load must precede organization derivation")
        self.assertLess(derive_org, create_authz, "org must be derived before create authz")
        self.assertLess(create_authz, materialize, "create authz must precede materialization")

    def test_clone_service_derives_org_from_persistence_not_client(self) -> None:
        source = CLONE_SERVICE.read_text(encoding="utf-8")
        self.assertIn("canonicalOrganizationId = sourceProject.organizationId", source)
        # The caller's destination claim is only ever compared, never trusted.
        self.assertIn("assertedDestinationOrganizationId !== canonicalOrganizationId", source)
        self.assertIn("organizationId: canonicalOrganizationId", source)

    def test_clone_service_enforces_same_tenant_template_policy(self) -> None:
        source = CLONE_SERVICE.read_text(encoding="utf-8")
        lowered = source.lower()
        self.assertIn("cross-organization", lowered)
        self.assertIn("deferred", lowered)
        self.assertIn("ProjectCloneError", source)

    def test_clone_creates_no_canonical_template_resource(self) -> None:
        prose = flatten(read(CLONE_SERVICE)).lower()
        self.assertIn("no canonical `template` resource", prose)
        self.assertIn("no template catalog", prose)
        code = strip_comments(read(CLONE_SERVICE)).lower()
        for invented in ("templateCatalog", "publishTemplate", "marketplace", "catalog"):
            self.assertNotIn(invented.lower(), code)

    def test_clone_remaps_artifacts_and_relations_in_repository(self) -> None:
        source = LIFECYCLE_REPO.read_text(encoding="utf-8")
        self.assertIn("artifactIdMap", source)
        self.assertIn("projectCloneArtifactMap", source)
        prose = flatten(source).lower()
        # Clone provenance must not become an ArtifactRelation, and cloned
        # artifacts must receive new ids.
        self.assertIn("clone provenance lives here, not in artifactrelation", prose)
        self.assertIn(
            "never creates an artifactrelation between source and target projects", prose
        )
        self.assertIn("new ids", prose)

    def test_clone_live_tests_cover_required_negatives(self) -> None:
        source = CLONE_LIVE.read_text(encoding="utf-8").lower()
        for scenario in (
            "same canonical organization",
            "before loading any canonical source detail",
            "cross-tenant source probe",
            "cross-organization clone",
            "revoked",
            "forged",
            "new server-generated id",
            "new ids and preserved type tokens",
            "remapped target artifact ids",
            "no artifactrelation linking the source and target",
            "composite-fk",
            "duplicate idempotency key",
            "rolls back",
            "fails closed",
        ):
            self.assertIn(scenario, source, f"missing clone negative: {scenario}")


class M014PackageBoundaryTests(unittest.TestCase):
    def test_package_root_exports_intended_public_surface(self) -> None:
        source = PROJECT_INDEX.read_text(encoding="utf-8")
        for expected in (
            "ProjectImportService",
            "ProjectCloneService",
            "ProjectImportError",
            "ProjectCloneError",
            "ArchiveRejectedError",
            "scanArchive",
            "DEFAULT_ARCHIVE_SCAN_LIMITS",
            "ARCHIVE_FORMATS",
            "InMemoryArchiveStaging",
        ):
            self.assertIn(expected, source)

    def test_package_root_does_not_export_persistence_internals(self) -> None:
        # Comments are stripped: the file documents the exclusion by name.
        source = strip_comments(read(PROJECT_INDEX))
        for internal in (
            "ProjectLifecycleRepository",
            "ControlPlaneDatabase",
            "createControlPlanePool",
            "projectArchiveImports",
            "projectClonePlans",
        ):
            self.assertNotIn(internal, source)

    def test_export_regression_test_exists(self) -> None:
        source = PROJECT_EXPORTS_TEST.read_text(encoding="utf-8")
        self.assertIn("M-014", source)
        self.assertIn("does NOT re-export persistence/DB internals", source)
        self.assertIn("does not export an invented Import/Template", source)


class M014CapabilityLedgerTests(unittest.TestCase):
    def test_only_vf_prj_004_and_007_advance(self) -> None:
        csv_text = CAPABILITY_CSV.read_text(encoding="utf-8")
        rows = {
            line.split(",")[0]: line.rsplit(",", 1)[1].strip()
            for line in csv_text.splitlines()[1:]
            if line.strip()
        }
        self.assertEqual(rows["VF-PRJ-004"], "IMPLEMENTED")
        self.assertEqual(rows["VF-PRJ-007"], "IMPLEMENTED")

        # No bulk advancement: everything else in the PRJ import family stays put.
        for vf_id in (
            "VF-PRJ-001",
            "VF-PRJ-002",
            "VF-PRJ-003",
            "VF-PRJ-008",
            "VF-PRJ-009",
            "VF-PRJ-010",
            "VF-PRJ-011",
            "VF-PRJ-012",
            "VF-PRJ-014",
            "VF-PRJ-016",
            "VF-PRJ-017",
        ):
            self.assertEqual(
                rows[vf_id], "NOT_STARTED", f"{vf_id} must not advance in M-014"
            )

    def test_ledger_csv_and_yaml_agree(self) -> None:
        yaml_text = CAPABILITY_YAML.read_text(encoding="utf-8")
        for vf_id in ("VF-PRJ-004", "VF-PRJ-007"):
            block = yaml_text.split(f"vf_id: {vf_id}")[1].split("- vf_id:")[0]
            self.assertIn("status: IMPLEMENTED", block)

    def test_contract_trace_agrees(self) -> None:
        trace = CONTRACT_TRACE.read_text(encoding="utf-8")
        for vf_id in ("VF-PRJ-004", "VF-PRJ-007"):
            row = [l for l in trace.splitlines() if l.startswith(f"{vf_id},")][0]
            self.assertTrue(row.rstrip().endswith("IMPLEMENTED"), row)


class M014VerificationWiringTests(unittest.TestCase):
    def test_root_check_runs_m014_contract_and_integration(self) -> None:
        package = json.loads(ROOT_PACKAGE.read_text(encoding="utf-8"))
        check = package["scripts"]["check"]
        self.assertIn("tests/contract/test_m014_import_clone.py", check)
        self.assertIn("scripts/run-m014-import-clone-integration.py", check)
        # Retained regressions must still run.
        for retained in range(8, 14):
            self.assertIn(f"test_m{retained:03d}_", check)
            if retained >= 9:
                self.assertIn(f"run-m{retained:03d}-", check)

    def test_integration_runner_requires_database_in_ci(self) -> None:
        runner = ROOT / "scripts/run-m014-import-clone-integration.py"
        source = runner.read_text(encoding="utf-8")
        self.assertIn("DATABASE_URL", source)
        self.assertIn('os.environ.get("CI") == "true"', source)
        self.assertIn("not verification evidence", source)
        for suite in (
            "src/lifecycle.live.test.ts",
            "src/import.live.test.ts",
            "src/clone.live.test.ts",
        ):
            self.assertIn(suite, source)


class M014EvidenceTests(unittest.TestCase):
    def test_evidence_records_required_facts(self) -> None:
        record = json.loads(EVIDENCE_JSON.read_text(encoding="utf-8"))
        self.assertEqual(record["mission"], "M-014")
        self.assertEqual(record["mission_status"], "REVIEW")
        for key in (
            "starting_main_sha",
            "mission_start_commit",
            "implementation_commits",
            "migrations",
            "changed_file_scope",
            "archive_import_authority_model",
            "archive_scan_policy",
            "manifest_hash_rules",
            "import_authority_sequence_proof",
            "clone_authority_sequence_proof",
            "clone_plan_model",
            "clone_materialization_model",
            "blob_staging_boundary",
            "transaction_idempotency_semantics",
            "artifact_relation_remapping_proof",
            "cross_tenant_idor_negatives",
            "audit_proof",
            "package_root_exports",
            "testing",
            "postgresql_results",
            "capability_changes",
            "capabilities_deliberately_not_advanced",
            "canonical_gaps_documented_not_invented",
            "deferred_provider_scope",
            "exact_head_ci_policy",
            "overclaim_check",
        ):
            self.assertIn(key, record)

    def test_evidence_never_claims_done(self) -> None:
        record = json.loads(EVIDENCE_JSON.read_text(encoding="utf-8"))
        self.assertNotEqual(record["mission_status"], "DONE")

        overclaim = record["overclaim_check"]
        self.assertEqual(overclaim["capabilities_claimed_verified_or_complete"], [])
        self.assertFalse(overclaim["mission_claimed_done"])
        self.assertFalse(overclaim["malware_scanning_claimed"])
        self.assertFalse(overclaim["provider_integration_claimed"])

        # No capability may be recorded above IMPLEMENTED by M-014.
        for change in record["capability_changes"]:
            self.assertEqual(change["to"], "IMPLEMENTED")

    def test_markdown_parity_exists(self) -> None:
        text = EVIDENCE_MD.read_text(encoding="utf-8")
        self.assertIn("M-014", text)
        self.assertIn("REVIEW", text)


if __name__ == "__main__":
    unittest.main(verbosity=2)
