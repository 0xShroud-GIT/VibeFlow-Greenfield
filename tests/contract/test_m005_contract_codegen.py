#!/usr/bin/env python3
"""Deterministic mutation tests for the M-005 schema/codegen pipeline.

Every scenario runs against a throwaway temporary copy of the repository; the
real repository is never mutated.

Coverage:
  - the real repository passes;
  - manual edits to each generated artifact are rejected;
  - authoritative drift (resource/state/terminal/event added, removed or
    renamed) without regeneration is rejected;
  - source-hash drift is rejected;
  - unexpected / missing generated files are rejected;
  - H-025 reverted to the unresolved "choose at M-004" wording is rejected;
  - TypeBox package or pin changes are rejected;
  - a restored public HealthSchema canary is rejected;
  - removing the contracts:check drift gate is rejected;
  - mission-state regressions (M-004 not DONE, M-006 unlocked) are rejected;
  - stale README / bootstrap-status mission pointers are rejected;
  - the generator is byte-identical across repeated runs.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/validate-m005-contract-codegen.py"
GENERATOR = REPO_ROOT / "scripts/generate-contracts.py"
MASTER = REPO_ROOT / "scripts/validate-master-contracts.py"

GENERATED_TS = "packages/contracts/src/generated/catalog.ts"
GENERATED_SCHEMA = "packages/contracts/generated/catalog.schema.json"
GENERATED_MANIFEST = "packages/contracts/generated/catalog.manifest.json"

DAG = "master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml"
REG = "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv"
REGISTRY = "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml"
RESOURCES = "master-build-system/02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml"
STATES = "master-build-system/03_BACKEND/STATE_MACHINES.yaml"
EVENTS = "master-build-system/03_BACKEND/EVENT_CATALOG.yaml"

IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "dist", ".turbo", ".cache", ".vite",
    "__pycache__", ".pytest_cache", ".next", ".expo",
)


def run_script(script: Path, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--root", str(root), *args],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


class Sandbox:
    """Throwaway copy of the repository for mutation testing."""

    def __init__(self, tmp: Path) -> None:
        self.root = tmp / "repo"
        shutil.copytree(REPO_ROOT, self.root, ignore=IGNORE)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def read(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def write(self, rel: str, content: str) -> None:
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def patch(self, rel: str, old: str, new: str) -> None:
        text = self.read(rel)
        if old not in text:
            raise AssertionError(f"anchor missing in {rel}: {old[:80]!r}")
        self.write(rel, text.replace(old, new, 1))

    def delete(self, rel: str) -> None:
        path = self.path(rel)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    def regenerate(self) -> None:
        """Run the real generator inside the sandbox (used for control cases)."""
        result = run_script(self.root / "scripts/generate-contracts.py", self.root)
        assert result.returncode == 0, result.stdout + result.stderr

    def set_dag_status_only(self, mission_id: str, status: str) -> None:
        """Change the DAG without the register, to simulate desync."""
        lines = self.read(DAG).splitlines()
        current = None
        for index, line in enumerate(lines):
            if line.startswith("- mission_id: "):
                current = line.split(":", 1)[1].strip()
            elif current == mission_id and line.startswith("  status: "):
                lines[index] = f"  status: {status}"
                break
        else:
            raise AssertionError(f"mission not found in DAG: {mission_id}")
        self.write(DAG, "\n".join(lines) + "\n")

    def set_mission_status(self, mission_id: str, status: str) -> None:
        lines = self.read(DAG).splitlines()
        current = None
        changed = False
        for index, line in enumerate(lines):
            if line.startswith("- mission_id: "):
                current = line.split(":", 1)[1].strip()
            elif current == mission_id and line.startswith("  status: "):
                lines[index] = f"  status: {status}"
                changed = True
                break
        if not changed:
            raise AssertionError(f"mission not found in DAG: {mission_id}")
        self.write(DAG, "\n".join(lines) + "\n")

        path = self.path(REG)
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = reader.fieldnames or []
        for row in rows:
            if row.get("mission_id") == mission_id:
                row["status"] = status
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)

    def as_historical_m005(self, status: str = "REVIEW") -> "Sandbox":
        """Reconstruct M-005's accepted historical snapshot from a later repo."""
        self.set_mission_status("M-005", status)
        # Explicitly lock every successor (M-006..M-151) so the historical
        # reconstruction is valid on any successor tree (e.g. after M-007
        # consumes M-006 acceptance and M-007 is REVIEW).
        for index in range(6, 152):
            self.set_mission_status(f"M-{index:03d}", "LOCKED")
        self.write(
            ".ai/ACTIVE_MISSION.md",
            f"# Active Mission\n\n**Mission:** M-005 — historical snapshot\n\n**Status:** {status}\n",
        )
        self.write(
            "README.md",
            f"# VibeFlow\n\n## Current state\n\nThe active mission is `M-005` ({status}).\n",
        )
        self.write(
            "docs/WORKSPACE_BOOTSTRAP_STATUS.md",
            f"# Workspace Bootstrap Status\n\n- Active mission: M-005 — historical ({status})\n",
        )
        seed_packages = {
            "core",
            "contracts",
            "remote",
            "bridge",
            "provider-sdk",
            "verification",
            "ui",
        }
        packages_root = self.path("packages")
        if packages_root.is_dir():
            for child in packages_root.iterdir():
                if child.is_dir() and child.name not in seed_packages:
                    self.delete(f"packages/{child.name}/package.json")
        return self

    def approve_typebox_build(self) -> None:
        self.patch(
            REGISTRY,
            "  approvals: []",
            "  approvals:\n  - ecosystem: npm\n    package: typebox\n    harvest_id: H-025\n    pnpm_matcher: typebox\n    version: 1.3.6\n"
            "    approved: true\n    rationale: Deterministic retained M-005 progression fixture.",
        )
        self.write(
            "pnpm-workspace.yaml",
            self.read("pnpm-workspace.yaml") + "allowBuilds:\n  typebox: true\n",
        )

    def refresh_pack_hash(self, pack_rel: str) -> None:
        """Recompute one SHA256SUMS.txt entry so pack drift is not the failure."""
        sums = self.path("master-build-system/SHA256SUMS.txt")
        digest = hashlib.sha256(self.path(f"master-build-system/{pack_rel}").read_bytes()).hexdigest()
        lines = []
        for line in sums.read_text(encoding="utf-8").splitlines():
            if line.strip().endswith(pack_rel):
                lines.append(f"{digest}  {pack_rel}")
            else:
                lines.append(line)
        sums.write_text("\n".join(lines) + "\n", encoding="utf-8")


class M005TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def box(self) -> Sandbox:
        return Sandbox(self.tmp).as_historical_m005()

    def assert_rejected(self, box: Sandbox, needle: str) -> None:
        result = run_script(VALIDATOR, box.root)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, f"validator unexpectedly passed:\n{output}")
        self.assertIn(needle, output)

    def assert_accepted(self, box: Sandbox) -> None:
        result = run_script(VALIDATOR, box.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class RealRepositoryTests(M005TestCase):
    def test_real_repository_passes_validator(self) -> None:
        result = run_script(VALIDATOR, REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_real_repository_passes_generator_check(self) -> None:
        result = run_script(GENERATOR, REPO_ROOT, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unmutated_sandbox_passes(self) -> None:
        self.assert_accepted(self.box())


class GeneratedArtifactEditTests(M005TestCase):
    def test_manual_catalog_ts_edit_fails(self) -> None:
        box = self.box()
        box.patch(GENERATED_TS, '"Account",', '"Account",\n  "HandEditedResource",')
        self.assert_rejected(box, "stale generated artifact")

    def test_catalog_ts_edit_is_caught_by_generator_check(self) -> None:
        box = self.box()
        box.patch(GENERATED_TS, '"Account",', '"Account",\n  "HandEditedResource",')
        result = run_script(GENERATOR, box.root, "--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("stale generated artifact", result.stdout)

    def test_manual_catalog_schema_edit_fails(self) -> None:
        box = self.box()
        schema = json.loads(box.read(GENERATED_SCHEMA))
        schema["$defs"]["CanonicalResourceName"]["enum"].append("HandEditedResource")
        box.write(GENERATED_SCHEMA, json.dumps(schema, indent=2, ensure_ascii=False) + "\n")
        self.assert_rejected(box, "stale generated artifact")

    def test_manual_manifest_edit_fails(self) -> None:
        box = self.box()
        manifest = json.loads(box.read(GENERATED_MANIFEST))
        manifest["counts"]["canonical_resources"] = 34
        box.write(GENERATED_MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        self.assert_rejected(box, "stale generated artifact")

    def test_manifest_count_drift_is_reported(self) -> None:
        box = self.box()
        manifest = json.loads(box.read(GENERATED_MANIFEST))
        manifest["counts"]["events"] = 36
        box.write(GENERATED_MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        self.assert_rejected(box, "manifest counts.events")

    def test_source_hash_drift_fails(self) -> None:
        box = self.box()
        manifest = json.loads(box.read(GENERATED_MANIFEST))
        manifest["sources"][1]["sha256"] = "0" * 64
        box.write(GENERATED_MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        self.assert_rejected(box, "manifest sha256 for")

    def test_unexpected_generated_file_fails(self) -> None:
        box = self.box()
        box.write("packages/contracts/generated/extra.json", "{}\n")
        self.assert_rejected(box, "unexpected file in generated output tree")

    def test_unexpected_generated_ts_file_fails(self) -> None:
        box = self.box()
        box.write("packages/contracts/src/generated/extra.ts", "export const x = 1;\n")
        self.assert_rejected(box, "unexpected file in generated output tree")

    def test_missing_generated_ts_fails(self) -> None:
        box = self.box()
        box.delete(GENERATED_TS)
        self.assert_rejected(box, "missing generated artifact")

    def test_missing_generated_schema_fails(self) -> None:
        box = self.box()
        box.delete(GENERATED_SCHEMA)
        self.assert_rejected(box, "missing generated artifact")

    def test_missing_generated_manifest_fails(self) -> None:
        box = self.box()
        box.delete(GENERATED_MANIFEST)
        self.assert_rejected(box, "missing generated artifact")


class AuthoritativeDriftTests(M005TestCase):
    """Authority changed but the catalog was not regenerated."""

    def test_resource_added_without_regeneration_fails(self) -> None:
        box = self.box()
        box.patch(
            RESOURCES,
            "- resource: SupportCase",
            "- resource: NewCanonicalThing\n  authority: VibeFlow\n"
            "  purpose: Added by a mutation test.\n  durability: durable\n  notes: test\n"
            "- resource: SupportCase",
        )
        box.refresh_pack_hash("02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml")
        self.assert_rejected(box, "stale generated artifact")

    def test_resource_added_reports_count_mismatch(self) -> None:
        box = self.box()
        box.patch(
            RESOURCES,
            "- resource: SupportCase",
            "- resource: NewCanonicalThing\n  authority: VibeFlow\n"
            "  purpose: Added by a mutation test.\n  durability: durable\n  notes: test\n"
            "- resource: SupportCase",
        )
        box.refresh_pack_hash("02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml")
        self.assert_rejected(box, "expected exactly 35 canonical resources")

    def test_resource_removed_without_regeneration_fails(self) -> None:
        box = self.box()
        box.patch(
            RESOURCES,
            "- resource: SupportCase\n  authority: VibeFlow/Helpdesk binding\n"
            "  purpose: Support workflow with explicitly redacted evidence attachments.\n"
            "  durability: durable metadata\n  notes: no silent secret/log exfiltration\n",
            "",
        )
        box.refresh_pack_hash("02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml")
        self.assert_rejected(box, "expected exactly 35 canonical resources")

    def test_resource_renamed_without_regeneration_fails(self) -> None:
        box = self.box()
        box.patch(RESOURCES, "- resource: SupportCase", "- resource: SupportTicket")
        box.refresh_pack_hash("02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml")
        self.assert_rejected(box, "stale generated artifact")

    def test_state_added_without_regeneration_fails(self) -> None:
        box = self.box()
        box.patch(
            STATES,
            "    - CANDIDATE_COMPLETE\n    - VERIFIED\n    - FAILED\n    - CANCELLED\n    terminal:",
            "    - CANDIDATE_COMPLETE\n    - VERIFIED\n    - FAILED\n    - CANCELLED\n"
            "    - INVENTED_STATE\n    terminal:",
        )
        box.refresh_pack_hash("03_BACKEND/STATE_MACHINES.yaml")
        self.assert_rejected(box, "stale generated artifact")

    def test_state_added_reports_enum_mismatch(self) -> None:
        box = self.box()
        box.patch(
            STATES,
            "    - CANDIDATE_COMPLETE\n    - VERIFIED\n    - FAILED\n    - CANCELLED\n    terminal:",
            "    - CANDIDATE_COMPLETE\n    - VERIFIED\n    - FAILED\n    - CANCELLED\n"
            "    - INVENTED_STATE\n    terminal:",
        )
        box.refresh_pack_hash("03_BACKEND/STATE_MACHINES.yaml")
        self.assert_rejected(box, "generated TaskState enum")

    def test_terminal_state_drift_fails(self) -> None:
        box = self.box()
        box.patch(
            STATES,
            "    terminal:\n    - VERIFIED\n    - FAILED\n    - CANCELLED\n"
            "    rule: Task reaches VERIFIED only through successful Verification.",
            "    terminal:\n    - VERIFIED\n    - FAILED\n"
            "    rule: Task reaches VERIFIED only through successful Verification.",
        )
        box.refresh_pack_hash("03_BACKEND/STATE_MACHINES.yaml")
        self.assert_rejected(box, "generated TaskTerminalState enum")

    def test_terminal_state_not_a_subset_fails(self) -> None:
        """A terminal state absent from `states` must be rejected outright."""
        box = self.box()
        box.patch(
            STATES,
            "    terminal:\n    - VERIFIED\n    - FAILED\n    - CANCELLED\n"
            "    rule: Task reaches VERIFIED only through successful Verification.",
            "    terminal:\n    - VERIFIED\n    - FAILED\n    - CANCELLED\n    - GHOST_STATE\n"
            "    rule: Task reaches VERIFIED only through successful Verification.",
        )
        box.refresh_pack_hash("03_BACKEND/STATE_MACHINES.yaml")
        self.assert_rejected(box, "terminal states are not a subset")

    def test_state_machine_removed_fails(self) -> None:
        box = self.box()
        text = box.read(STATES)
        start = text.index("  RecoveryRecord:")
        box.write(STATES, text[:start])
        box.refresh_pack_hash("03_BACKEND/STATE_MACHINES.yaml")
        self.assert_rejected(box, "expected exactly 7 state machines")

    def test_event_id_change_without_regeneration_fails(self) -> None:
        box = self.box()
        box.patch(EVENTS, "- id: EVT-037", "- id: EVT-999")
        box.refresh_pack_hash("03_BACKEND/EVENT_CATALOG.yaml")
        self.assert_rejected(box, "stale generated artifact")

    def test_event_id_change_reports_catalog_mismatch(self) -> None:
        box = self.box()
        box.patch(EVENTS, "- id: EVT-037", "- id: EVT-999")
        box.refresh_pack_hash("03_BACKEND/EVENT_CATALOG.yaml")
        self.assert_rejected(box, "generated EventId enum")

    def test_event_name_change_without_regeneration_fails(self) -> None:
        box = self.box()
        box.patch(EVENTS, "  name: audit.recorded", "  name: audit.written")
        box.refresh_pack_hash("03_BACKEND/EVENT_CATALOG.yaml")
        self.assert_rejected(box, "generated EventName enum")

    def test_event_reordering_without_regeneration_fails(self) -> None:
        """Canonical order is part of the contract, not an incidental detail."""
        box = self.box()
        text = box.read(EVENTS)
        start = text.index("- id: EVT-036")
        block = text[start:]
        entries = block.split("- id: ")
        first, second = entries[1], entries[2]
        box.write(EVENTS, text[:start] + "- id: " + second + "- id: " + first)
        box.refresh_pack_hash("03_BACKEND/EVENT_CATALOG.yaml")
        self.assert_rejected(box, "canonical order")

    def test_event_removed_fails(self) -> None:
        box = self.box()
        text = box.read(EVENTS)
        start = text.index("- id: EVT-037")
        box.write(EVENTS, text[:start])
        box.refresh_pack_hash("03_BACKEND/EVENT_CATALOG.yaml")
        self.assert_rejected(box, "expected exactly 37 events")

    def test_regenerating_after_authority_change_passes(self) -> None:
        """Control: the pipeline accepts drift once the catalog is regenerated."""
        box = self.box()
        box.patch(EVENTS, "  name: audit.recorded", "  name: audit.written")
        box.refresh_pack_hash("03_BACKEND/EVENT_CATALOG.yaml")
        box.regenerate()
        self.assert_accepted(box)


class AuthorityRoutingTests(M005TestCase):
    def test_rerouted_authority_fails(self) -> None:
        box = self.box()
        box.patch(
            "master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml",
            "events: 03_BACKEND/EVENT_CATALOG.yaml",
            "events: 99_REFERENCE/REPLIT_EVIDENCE_SUMMARY.md",
        )
        box.refresh_pack_hash("00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml")
        self.assert_rejected(box, "SOURCE_OF_TRUTH_INDEX.yaml routes 'events'")


class DependencyPolicyTests(M005TestCase):
    def test_typebox_switched_to_sinclair_fails(self) -> None:
        box = self.box()
        box.patch(
            "packages/contracts/package.json",
            '"typebox": "1.3.6"',
            '"@sinclair/typebox": "0.34.0"',
        )
        self.assert_rejected(box, "@sinclair/typebox")

    def test_typebox_pin_changed_fails(self) -> None:
        box = self.box()
        box.patch("packages/contracts/package.json", '"typebox": "1.3.6"', '"typebox": "1.3.15"')
        self.assert_rejected(box, "packages/contracts dependencies must be exactly")

    def test_new_codegen_dependency_fails(self) -> None:
        box = self.box()
        pkg = json.loads(box.read("package.json"))
        pkg["devDependencies"]["json-schema-to-typescript"] = "15.0.0"
        box.write("package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "M-005 adds no code-generation or schema dependency")

    def test_new_runtime_dependency_fails(self) -> None:
        box = self.box()
        pkg = json.loads(box.read("packages/contracts/package.json"))
        pkg["dependencies"]["ajv"] = "8.17.1"
        box.write("packages/contracts/package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "packages/contracts dependencies must be exactly")

    def test_supply_chain_protection_removed_fails(self) -> None:
        box = self.box()
        box.patch("pnpm-workspace.yaml", "minimumReleaseAgeStrict: true", "minimumReleaseAgeStrict: false")
        self.assert_rejected(box, "minimumReleaseAgeStrict")

    def test_dangerously_allow_all_builds_fails(self) -> None:
        box = self.box()
        box.write("pnpm-workspace.yaml", box.read("pnpm-workspace.yaml") + "dangerouslyAllowAllBuilds: true\n")
        self.assert_rejected(box, "dangerouslyAllowAllBuilds")


class H025ReconciliationTests(M005TestCase):
    def test_h025_reverted_to_unresolved_choice_fails(self) -> None:
        box = self.box()
        box.patch(
            REGISTRY,
            "    ESM) is the VibeFlow selected line, chosen by M-004 and pinned exactly at 1.3.6; "
            "`@sinclair/typebox` 0.x\n    remains upstream LTS for CJS but is not the VibeFlow selected line.",
            "    ESM) is the current line; 0.x (`@sinclair/typebox`) remains upstream LTS for CJS "
            "\u2014 choose one at M-004.",
        )
        box.refresh_pack_hash("06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        self.assert_rejected(box, "H-025")

    def test_h025_losing_exact_pin_fails(self) -> None:
        box = self.box()
        box.patch(
            REGISTRY,
            "  version: 1.x (repo `typebox`, ESM); foundation exact pin 1.3.6",
            "  version: pin current stable during bootstrap",
        )
        box.patch(
            REGISTRY,
            "chosen by M-004 and pinned exactly at 1.3.6;",
            "chosen by M-004;",
        )
        box.patch(
            REGISTRY,
            "  upgrade_policy: Stay on vetted TypeBox 1.x from the M-004 exact pin 1.3.6; "
            "moving off the 1.x line requires an architecture change.",
            "  upgrade_policy: Stay on the selected line.",
        )
        box.refresh_pack_hash("06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        self.assert_rejected(box, "foundation exact pin")

    def test_h025_losing_json_schema_first_fails(self) -> None:
        box = self.box()
        box.patch(
            REGISTRY,
            "  rule: Contracts are JSON Schema first; generated TypeScript types are derived.",
            "  rule: Contracts are whatever TypeBox emits.",
        )
        box.refresh_pack_hash("06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        self.assert_rejected(box, "H-025 rule must record")


class ContractPackageTests(M005TestCase):
    def test_health_schema_canary_restored_fails(self) -> None:
        box = self.box()
        box.write(
            "packages/contracts/src/index.ts",
            'import { Type, type Static } from "typebox";\n\n'
            'export const HealthSchema = Type.Object({ status: Type.Literal("ok") });\n'
            "export type Health = Static<typeof HealthSchema>;\n\n"
            'export * from "./generated/catalog.js";\n',
        )
        self.assert_rejected(box, "HealthSchema")

    def test_index_not_reexporting_catalog_fails(self) -> None:
        box = self.box()
        box.write(
            "packages/contracts/src/index.ts",
            'export const CONTRACTS_PACKAGE = "@vibeflow/contracts" as const;\n',
        )
        self.assert_rejected(box, "must re-export the generated catalog")

    def test_smoke_test_reverted_to_health_schema_fails(self) -> None:
        box = self.box()
        box.write(
            "packages/contracts/src/typebox-smoke.test.ts",
            'import { HealthSchema } from "./index.js";\nconsole.log(HealthSchema);\n',
        )
        self.assert_rejected(box, "typebox-smoke.test.ts must test generated schemas")

    def test_handwritten_union_instead_of_derived_type_fails(self) -> None:
        box = self.box()
        box.patch(
            GENERATED_TS,
            "export type CanonicalResourceName = Static<typeof CanonicalResourceNameSchema>;",
            'export type CanonicalResourceName = "Account" | "Organization" | "Project";',
        )
        self.assert_rejected(box, "not derived from a schema")

    def test_invented_error_code_catalog_fails(self) -> None:
        box = self.box()
        box.write(
            GENERATED_TS,
            box.read(GENERATED_TS)
            + '\nexport const ERROR_CODES = ["VF_UNAUTHORIZED", "VF_NOT_FOUND"] as const;\n',
        )
        self.assert_rejected(box, "must not invent commands")


class BuildScriptProgressionTests(M005TestCase):
    def durable(self) -> Sandbox:
        box = self.box()
        box.set_mission_status("M-005", "DONE")
        box.set_mission_status("M-006", "REVIEW")
        box.write(
            ".ai/ACTIVE_MISSION.md",
            "# Active Mission\n\n**Mission:** M-006 — successor\n\n**Status:** REVIEW\n",
        )
        box.write("README.md", "# VibeFlow\n\nThe active mission is `M-006` (REVIEW).\n")
        box.write(
            "docs/WORKSPACE_BOOTSTRAP_STATUS.md",
            "# Workspace Bootstrap Status\n\n- Active mission: M-006 — successor (REVIEW)\n",
        )
        return box

    def test_historical_m005_snapshot_rejects_allow_builds(self) -> None:
        box = self.box()
        box.approve_typebox_build()
        self.assert_rejected(box, "M-005 active snapshot forbids allowBuilds")

    def test_m005_done_m006_active_accepts_approved_allow_builds(self) -> None:
        box = self.durable()
        box.approve_typebox_build()
        self.assert_accepted(box)

    def test_durable_dependency_version_drift_invalidates_approval(self) -> None:
        box = self.durable()
        box.approve_typebox_build()
        box.patch(
            "packages/contracts/package.json",
            '"typebox": "1.3.6"',
            '"typebox": "1.3.7"',
        )
        self.assert_rejected(box, "stale approval version")

    def test_durable_unapproved_allow_builds_fails(self) -> None:
        box = self.durable()
        box.write(
            "pnpm-workspace.yaml",
            box.read("pnpm-workspace.yaml") + "allowBuilds:\n  typebox: true\n",
        )
        self.assert_rejected(box, "lacks matching harvest-side approval")

    def test_dangerously_allow_all_builds_fails_forever(self) -> None:
        box = self.durable()
        box.write(
            "pnpm-workspace.yaml",
            box.read("pnpm-workspace.yaml") + "dangerouslyAllowAllBuilds: true\n",
        )
        self.assert_rejected(box, "dangerouslyAllowAllBuilds is permanently forbidden")


class RootScriptTests(M005TestCase):
    def test_contracts_check_removed_from_root_check_fails(self) -> None:
        box = self.box()
        pkg = json.loads(box.read("package.json"))
        pkg["scripts"]["check"] = (
            "python3 scripts/validate-m004-foundation.py"
            " && pnpm run typecheck && pnpm run test && pnpm run build"
        )
        box.write("package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "must include the 'pnpm run contracts:check' drift gate")

    def test_contracts_check_script_removed_fails(self) -> None:
        box = self.box()
        pkg = json.loads(box.read("package.json"))
        del pkg["scripts"]["contracts:check"]
        box.write("package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "root script 'contracts:check'")

    def test_contracts_generate_script_removed_fails(self) -> None:
        box = self.box()
        pkg = json.loads(box.read("package.json"))
        del pkg["scripts"]["contracts:generate"]
        box.write("package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "root script 'contracts:generate'")


class MissionStateTests(M005TestCase):
    def test_m004_not_done_fails(self) -> None:
        box = self.box()
        box.set_mission_status("M-004", "REVIEW")
        self.assert_rejected(box, "M-004 must be DONE")

    def test_current_branch_records_m009_accepted_and_m010_active(self) -> None:
        """The retained gate accepts the next consumed mission without inventing one.

        M-009 has accepted exact-head evidence, so M-001..M-009 are DONE,
        M-010 is the sole active mission, and M-011+ remain LOCKED.
        """
        dag = (REPO_ROOT / DAG).read_text(encoding="utf-8")
        m009 = dag.split("- mission_id: M-009", 1)[1].split("- mission_id:", 1)[0]
        m010 = dag.split("- mission_id: M-010", 1)[1].split("- mission_id:", 1)[0]
        self.assertIn("status: DONE", m009)
        self.assertRegex(m010, r"status: (IN_PROGRESS|REVIEW)")

        with (REPO_ROOT / REG).open(newline="", encoding="utf-8") as handle:
            rows = {row["mission_id"]: row["status"] for row in csv.DictReader(handle)}
        for index in range(4, 10):
            self.assertEqual(rows[f"M-{index:03d}"], "DONE")
        self.assertIn(rows["M-010"], {"IN_PROGRESS", "REVIEW"})
        for index in range(11, 152):
            self.assertEqual(rows[f"M-{index:03d}"], "LOCKED")

    def test_m005_dag_register_desync_is_rejected(self) -> None:
        box = self.box()
        box.set_dag_status_only("M-005", "DONE")
        self.assert_rejected(box, "M-005 status disagrees between DAG")

    def test_m005_locked_fails(self) -> None:
        box = self.box()
        box.set_mission_status("M-005", "LOCKED")
        self.assert_rejected(box, "M-005 must be REVIEW")

    def test_m006_unlocked_fails(self) -> None:
        box = self.box()
        box.set_mission_status("M-006", "READY")
        self.assert_rejected(box, "M-006 must remain LOCKED")

    def test_stale_readme_active_mission_fails(self) -> None:
        box = self.box()
        box.write(
            "README.md",
            "# VibeFlow\n\n## Current state\n\nThe active mission is `M-004`.\n",
        )
        self.assert_rejected(box, "README.md")

    def test_stale_bootstrap_status_active_mission_fails(self) -> None:
        box = self.box()
        box.write(
            "docs/WORKSPACE_BOOTSTRAP_STATUS.md",
            "# Workspace Bootstrap Status\n\n- Active mission: M-004 — stale pointer\n",
        )
        self.assert_rejected(box, "docs/WORKSPACE_BOOTSTRAP_STATUS.md")

    def test_stale_active_mission_pointer_fails(self) -> None:
        box = self.box()
        box.write(
            ".ai/ACTIVE_MISSION.md",
            "# Active Mission\n\n**Mission:** M-004 — stale\n\n**Status:** REVIEW\n",
        )
        self.assert_rejected(box, "ACTIVE_MISSION.md names M-004")

    def test_master_contract_validator_still_passes(self) -> None:
        """The M-005 state must satisfy the generic progression validator too."""
        result = run_script(MASTER, REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


class M005ProgressionTests(M005TestCase):
    """The M-005 gate is retained by CI, so it must not be current-state coupled.

    Historical M-005 (REVIEW, successors LOCKED) and accepted M-005 (DONE, a
    successor active) must both pass; regression and desync must fail.
    """

    def accepted(self, active: str = "M-006", status: str = "REVIEW") -> Sandbox:
        """M-005 accepted, with `active` as the current mission and pointers moved."""
        box = self.box()
        box.set_mission_status("M-005", "DONE")
        for index in range(6, int(active.split("-")[1])):
            box.set_mission_status(f"M-{index:03d}", "DONE")
        box.set_mission_status(active, status)
        box.write(
            ".ai/ACTIVE_MISSION.md",
            f"# Active Mission\n\n**Mission:** {active} — successor mission\n\n"
            f"**Status:** {status}\n",
        )
        box.write(
            "README.md",
            f"# VibeFlow\n\n## Current state\n\nThe active mission is `{active}` ({status}).\n",
        )
        box.write(
            "docs/WORKSPACE_BOOTSTRAP_STATUS.md",
            f"# Workspace Bootstrap Status\n\n- Active mission: {active} — successor ({status})\n",
        )
        return box

    # --- both valid states pass ------------------------------------------

    def test_historical_m005_review_state_passes(self) -> None:
        """M-001..M-004 DONE, M-005 REVIEW, M-006+ LOCKED."""
        box = self.box()
        box.set_mission_status("M-005", "REVIEW")
        self.assert_accepted(box)

    def test_historical_m005_in_progress_state_passes(self) -> None:
        box = self.box()
        box.set_mission_status("M-005", "IN_PROGRESS")
        box.write(
            ".ai/ACTIVE_MISSION.md",
            "# Active Mission\n\n**Mission:** M-005 — Establish schema/codegen pipeline\n\n"
            "**Status:** IN_PROGRESS\n",
        )
        self.assert_accepted(box)

    def test_accepted_m005_with_m006_review_passes(self) -> None:
        """A correct M-006 branch must not fail this retained gate."""
        self.assert_accepted(self.accepted("M-006", "REVIEW"))

    def test_accepted_m005_with_m006_in_progress_passes(self) -> None:
        self.assert_accepted(self.accepted("M-006", "IN_PROGRESS"))

    def test_accepted_m005_with_far_future_mission_passes(self) -> None:
        self.assert_accepted(self.accepted("M-008", "IN_PROGRESS"))

    def test_reports_active_and_durable_modes(self) -> None:
        historical = run_script(VALIDATOR, self.box().root)
        self.assertIn("mode=m005-active", historical.stdout)
        current = run_script(VALIDATOR, REPO_ROOT)
        self.assertIn("mode=durable", current.stdout)

    # --- invalid states fail ---------------------------------------------

    def test_m005_review_with_m006_active_fails(self) -> None:
        box = self.box()
        box.set_mission_status("M-005", "REVIEW")
        box.set_mission_status("M-006", "REVIEW")
        self.assert_rejected(box, "M-006 must remain LOCKED while M-005 is REVIEW")

    def test_m005_review_with_m007_active_fails(self) -> None:
        box = self.box()
        box.set_mission_status("M-007", "IN_PROGRESS")
        self.assert_rejected(box, "M-007 must remain LOCKED while M-005 is REVIEW")

    def test_m005_regression_to_locked_fails(self) -> None:
        box = self.box()
        box.set_mission_status("M-005", "LOCKED")
        self.assert_rejected(box, "M-005 must be REVIEW")

    def test_m005_regression_to_locked_after_acceptance_fails(self) -> None:
        box = self.accepted()
        box.set_mission_status("M-005", "LOCKED")
        self.assert_rejected(box, "M-005 must be REVIEW")

    def test_m005_dag_register_desync_fails(self) -> None:
        box = self.box()
        box.set_dag_status_only("M-005", "DONE")
        self.assert_rejected(box, "M-005 status disagrees between DAG")

    def test_m004_regression_after_m005_acceptance_fails(self) -> None:
        box = self.accepted()
        box.set_mission_status("M-004", "REVIEW")
        self.assert_rejected(box, "M-004 must be DONE")

    def test_stale_pointer_after_m005_acceptance_fails(self) -> None:
        box = self.accepted()
        box.write(
            "README.md",
            "# VibeFlow\n\n## Current state\n\nThe active mission is `M-005`.\n",
        )
        self.assert_rejected(box, "does not name the active mission M-006")

    # --- durable rules survive M-005 acceptance ---------------------------

    def test_durable_stale_catalog_still_fails_after_acceptance(self) -> None:
        box = self.accepted()
        box.patch(GENERATED_TS, '"Account",', '"Account",\n  "HandEdited",')
        self.assert_rejected(box, "stale generated artifact")

    def test_durable_typebox_pin_still_enforced_after_acceptance(self) -> None:
        box = self.accepted()
        box.patch("packages/contracts/package.json", '"typebox": "1.3.6"', '"typebox": "1.3.15"')
        self.assert_rejected(box, "must keep the typebox@1.3.6 pin")

    def test_durable_sinclair_typebox_still_forbidden_after_acceptance(self) -> None:
        box = self.accepted()
        box.patch(
            "packages/contracts/package.json",
            '"typebox": "1.3.6"',
            '"typebox": "1.3.6", "@sinclair/typebox": "0.34.0"',
        )
        self.assert_rejected(box, "@sinclair/typebox")

    def test_durable_health_schema_canary_still_forbidden_after_acceptance(self) -> None:
        box = self.accepted()
        box.write(
            "packages/contracts/src/index.ts",
            'export const HealthSchema = {} as const;\nexport * from "./generated/catalog.js";\n',
        )
        self.assert_rejected(box, "HealthSchema")

    def test_durable_supply_chain_still_enforced_after_acceptance(self) -> None:
        box = self.accepted()
        box.patch("pnpm-workspace.yaml", "trustLockfile: false", "trustLockfile: true")
        self.assert_rejected(box, "trustLockfile")

    def test_durable_contracts_check_gate_still_required_after_acceptance(self) -> None:
        box = self.accepted()
        pkg = json.loads(box.read("package.json"))
        pkg["scripts"]["check"] = (
            "python3 scripts/validate-m004-foundation.py"
            " && pnpm run typecheck && pnpm run test && pnpm run build"
        )
        box.write("package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "must include the 'pnpm run contracts:check' drift gate")

    def test_durable_source_hash_drift_still_fails_after_acceptance(self) -> None:
        box = self.accepted()
        manifest = json.loads(box.read(GENERATED_MANIFEST))
        manifest["sources"][1]["sha256"] = "0" * 64
        box.write(GENERATED_MANIFEST, json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
        self.assert_rejected(box, "manifest sha256 for")


class FutureCatalogExpansionTests(M005TestCase):
    """After M-005, a later authoritative mission may extend the catalog.

    The fixed 35/7/37 totals are an M-005 snapshot assertion, not a permanent
    cap. The durable rule is that generated output equals current authority.
    """

    def accepted_with_extra_resource(self) -> Sandbox:
        box = self.box()
        box.set_mission_status("M-005", "DONE")
        box.set_mission_status("M-006", "IN_PROGRESS")
        box.write(
            ".ai/ACTIVE_MISSION.md",
            "# Active Mission\n\n**Mission:** M-006 — successor\n\n**Status:** IN_PROGRESS\n",
        )
        box.write("README.md", "# VibeFlow\n\nThe active mission is `M-006`.\n")
        box.write(
            "docs/WORKSPACE_BOOTSTRAP_STATUS.md",
            "# Workspace Bootstrap Status\n\n- Active mission: M-006 — successor\n",
        )
        box.write(
            RESOURCES,
            box.read(RESOURCES)
            + "- resource: FutureAuthoritativeThing\n  authority: VibeFlow\n"
            "  purpose: Added by a later authoritative mission.\n"
            "  durability: durable\n  notes: test\n",
        )
        box.refresh_pack_hash("02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml")
        return box

    def test_expanded_catalog_passes_after_regeneration(self) -> None:
        box = self.accepted_with_extra_resource()
        box.regenerate()
        self.assert_accepted(box)
        manifest = json.loads(box.read(GENERATED_MANIFEST))
        self.assertEqual(manifest["counts"]["canonical_resources"], 36)

    def test_expanded_catalog_without_regeneration_still_fails(self) -> None:
        box = self.accepted_with_extra_resource()
        self.assert_rejected(box, "stale generated artifact")

    def test_expanded_catalog_is_rejected_while_m005_is_active(self) -> None:
        """The 35/7/37 snapshot is still enforced during M-005 itself."""
        box = self.box()
        box.write(
            RESOURCES,
            box.read(RESOURCES)
            + "- resource: FutureAuthoritativeThing\n  authority: VibeFlow\n"
            "  purpose: Not allowed during M-005.\n  durability: durable\n  notes: test\n",
        )
        box.refresh_pack_hash("02_ARCHITECTURE/CANONICAL_RESOURCE_MODEL.yaml")
        box.regenerate()
        self.assert_rejected(box, "expected exactly 35 canonical resources at M-005")

    def test_future_payload_contracts_allowed_after_acceptance(self) -> None:
        """Scope prohibitions are M-005's own snapshot, not a permanent ban."""
        box = self.box()
        box.set_mission_status("M-005", "DONE")
        box.set_mission_status("M-006", "IN_PROGRESS")
        box.write(
            ".ai/ACTIVE_MISSION.md",
            "# Active Mission\n\n**Mission:** M-006 — successor\n\n**Status:** IN_PROGRESS\n",
        )
        box.write("README.md", "# VibeFlow\n\nThe active mission is `M-006`.\n")
        box.write(
            "docs/WORKSPACE_BOOTSTRAP_STATUS.md",
            "# Workspace Bootstrap Status\n\n- Active mission: M-006 — successor\n",
        )
        # A later mission emits an authoritative error-code vocabulary.
        box.write(
            GENERATED_TS,
            box.read(GENERATED_TS)
            + '\nexport const ErrorCodeSchema = {\n  type: "string",\n'
            '  enum: ["VF_UNAUTHORIZED"]\n} as const;\n'
            "export type ErrorCode = Static<typeof ErrorCodeSchema>;\n",
        )
        result = run_script(VALIDATOR, box.root)
        output = result.stdout + result.stderr
        # It must not be rejected merely for containing the token; only the
        # drift/derivation rules apply, which this hand-edit trips.
        self.assertNotIn("must not invent commands", output)

    def test_payload_contracts_still_prohibited_during_m005(self) -> None:
        box = self.box()
        box.write(
            GENERATED_TS,
            box.read(GENERATED_TS)
            + '\nexport const ERROR_CODES = ["VF_UNAUTHORIZED"] as const;\n',
        )
        self.assert_rejected(box, "must not invent commands")


class ScopeTests(M005TestCase):
    def test_unauthorized_implementation_under_services_fails(self) -> None:
        box = self.box()
        box.write("services/control-plane/server.ts", "export const start = () => {};\n")
        self.assert_rejected(box, "unauthorized implementation files under services/")

    def test_unauthorized_implementation_under_apps_fails(self) -> None:
        box = self.box()
        box.write("apps/web/main.ts", "export const app = 1;\n")
        self.assert_rejected(box, "unauthorized implementation files under apps/")


class DeterminismTests(M005TestCase):
    def test_generator_is_byte_identical_across_runs(self) -> None:
        box = self.box()
        artifacts = (GENERATED_TS, GENERATED_SCHEMA, GENERATED_MANIFEST)

        def digests() -> dict[str, str]:
            return {
                rel: hashlib.sha256(box.path(rel).read_bytes()).hexdigest() for rel in artifacts
            }

        tracked = digests()
        box.regenerate()
        first = digests()
        box.regenerate()
        second = digests()

        self.assertEqual(first, second, "generator output differs between runs")
        self.assertEqual(
            tracked, first, "tracked artifacts differ from a fresh deterministic generation"
        )

    def test_generated_output_contains_no_clock_or_machine_state(self) -> None:
        box = self.box()
        for rel in (GENERATED_TS, GENERATED_SCHEMA, GENERATED_MANIFEST):
            text = box.read(rel)
            self.assertNotIn("generated_at", text)
            self.assertNotIn("timestamp", text)
            self.assertNotIn(str(box.root), text)
            self.assertNotIn("/home/", text)

    def test_check_mode_performs_no_writes(self) -> None:
        box = self.box()
        artifacts = (GENERATED_TS, GENERATED_SCHEMA, GENERATED_MANIFEST)
        before = {rel: box.path(rel).read_bytes() for rel in artifacts}
        stats = {rel: box.path(rel).stat().st_mtime_ns for rel in artifacts}
        result = run_script(GENERATOR, box.root, "--check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for rel in artifacts:
            self.assertEqual(before[rel], box.path(rel).read_bytes())
            self.assertEqual(stats[rel], box.path(rel).stat().st_mtime_ns)

    def test_check_mode_writes_nothing_even_when_stale(self) -> None:
        box = self.box()
        box.patch(EVENTS, "  name: audit.recorded", "  name: audit.written")
        before = box.path(GENERATED_TS).read_bytes()
        result = run_script(GENERATOR, box.root, "--check")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(before, box.path(GENERATED_TS).read_bytes())


if __name__ == "__main__":
    unittest.main(verbosity=1)
