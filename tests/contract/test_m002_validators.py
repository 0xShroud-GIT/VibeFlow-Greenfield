#!/usr/bin/env python3
"""M-002 deterministic validator tests (stdlib unittest, no third-party deps).

Proves the generalized mission-progression validator and the dependency/harvest
registry validator fail deterministically for:
  - duplicate H-ID / duplicate mission ID;
  - missing required registry field;
  - invalid or non-official/missing source;
  - unsupported decision or integration classification;
  - missing/unresolved license classification;
  - fake GitHub-repository provenance (generic github.com is not proof);
  - missing use/ownership/upgrade-policy/replacement-strategy data;
  - mission dependency progression violations (unlocked dependent, unlocked
    mission without DONE dependencies, multiple active missions, DONE mission
    after the active one, zero active missions, missing dependency, dependency
    cycle, forward dependency reference, DAG/register desync, stale
    ACTIVE_MISSION pointer);
  - multiline rule continuations staying inside the parsed rule value (final-review
    blocker regression coverage for H-008/H-015/H-016/H-025/H-030).

Each scenario runs against a throwaway temp copy of the repository; the real
repository is never mutated.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MASTER = REPO_ROOT / "scripts" / "validate-master-contracts.py"
HARVEST = REPO_ROOT / "scripts" / "validate-harvest-registry.py"

IGNORE = shutil.ignore_patterns(".git")


def run_script(script: Path, root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=120,
    )


class RepoSandbox:
    """Copy of the repository for mutation testing."""

    def __init__(self, tmp: Path) -> None:
        self.root = tmp / "repo"
        shutil.copytree(REPO_ROOT, self.root, ignore=IGNORE)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def patch(self, rel: str, old: str, new: str) -> None:
        p = self.path(rel)
        text = p.read_text(encoding="utf-8")
        assert old in text, f"anchor not found in {rel}: {old[:60]!r}"
        p.write_text(text.replace(old, new, 1), encoding="utf-8")


class TempDirMixin:
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)


class HarvestRegistryTests(TempDirMixin, unittest.TestCase):
    def test_real_repository_passes(self) -> None:
        result = run_script(HARVEST, REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_duplicate_h_id_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "- id: H-035\n",
            "- id: H-034\n",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Duplicate H-ID", result.stdout)

    def test_missing_required_field_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "- id: H-001\n  capability: runtime\n",
            "- id: H-001\n",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field 'capability'", result.stdout)

    def test_non_official_source_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  source: https://nodejs.org/en/about/previous-releases",
            "  source: https://some-random-blog.example.com/nodejs",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejected official-identity check", result.stdout)

    def test_missing_source_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  source: https://nodejs.org/en/about/previous-releases",
            "  source: ''",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field 'source'", result.stdout)

    def test_unsupported_decision_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: ADOPT",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: INVENT_FROM_SCRATCH",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported decision 'INVENT_FROM_SCRATCH'", result.stdout)

    def test_unsupported_integration_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: ADOPT\n  integration: DEPEND",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: ADOPT\n  integration: VENDOR_EVERYTHING",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unsupported integration classification 'VENDOR_EVERYTHING'", result.stdout)

    def test_missing_license_classification_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: ADOPT\n  integration: DEPEND\n  license: MIT",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: ADOPT\n  integration: DEPEND\n  license: ''",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing license classification", result.stdout)

    def test_unresolved_license_classification_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: ADOPT\n  integration: DEPEND\n  license: MIT",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: ADOPT\n  integration: DEPEND\n  license: See upstream",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unresolved license classification", result.stdout)

    def test_fake_github_repository_fails(self) -> None:
        """Generic github.com is not provenance: a look-alike repo must fail."""
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  source: https://github.com/microsoft/TypeScript",
            "  source: https://github.com/attacker/TypeScript-mirror",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejected official-identity check", result.stdout)
        self.assertIn("microsoft/TypeScript", result.stdout)

    def test_same_slug_wrong_owner_github_repo_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  source: https://github.com/vercel/turborepo",
            "  source: https://github.com/vercel-mirror/turborepo",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("rejected official-identity check", result.stdout)

    def test_missing_ownership_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        registry = box.path("master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        text = registry.read_text(encoding="utf-8")
        first = text.index("  ownership: ")
        line_end = text.index("\n", first)
        registry.write_text(text[:first] + "  ownership: ''" + text[line_end:], encoding="utf-8")
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field 'ownership'", result.stdout)

    def test_missing_upgrade_policy_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        registry = box.path("master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        text = registry.read_text(encoding="utf-8")
        first = text.index("  upgrade_policy: ")
        line_end = text.index("\n", first)
        registry.write_text(text[:first] + "  upgrade_policy: ''" + text[line_end:], encoding="utf-8")
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field 'upgrade_policy'", result.stdout)

    def test_missing_replacement_strategy_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        registry = box.path("master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        text = registry.read_text(encoding="utf-8")
        first = text.index("  replacement_strategy: ")
        line_end = text.index("\n", first)
        registry.write_text(text[:first] + "  replacement_strategy: ''" + text[line_end:], encoding="utf-8")
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field 'replacement_strategy'", result.stdout)

    def test_missing_use_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        registry = box.path("master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        text = registry.read_text(encoding="utf-8")
        first = text.index("  use: ")
        line_end = text.index("\n", first)
        registry.write_text(text[:first] + "  use: ''" + text[line_end:], encoding="utf-8")
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field 'use'", result.stdout)

    def test_entry_count_change_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        registry = box.path("master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        text = registry.read_text(encoding="utf-8")
        head = text.index("- id: H-035")
        registry.write_text(text[:head], encoding="utf-8")
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Expected exactly 35 registry entries", result.stdout)

    def test_build_without_adr_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: ADOPT",
            "  name: Monaco Editor\n  version: 0.56.x\n  decision: BUILD",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("BUILD decision requires explicit ADR justification", result.stdout)


    # --- M-006 extension of the same authoritative harvest policy ----------

    def test_current_npm_coordinate_mapping_passes(self) -> None:
        result = run_script(HARVEST, REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("package coordinates: 4", result.stdout)
        self.assertIn("install/build-script approvals: 0", result.stdout)

    def test_package_coordinate_unknown_harvest_id_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "harvest_id: H-002\n    approved_usage: development",
            "harvest_id: H-999\n    approved_usage: development",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unknown harvest ID", result.stdout)

    def test_duplicate_package_coordinate_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  source: https://github.com/vercel/turborepo\n  package_coordinates:",
            "  source: https://github.com/vercel/turborepo\n  package_coordinates:\n"
            "  - ecosystem: npm\n    name: typescript\n    harvest_id: H-004\n"
            "    approved_usage: development",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Duplicate package coordinate", result.stdout)

    def test_build_script_policy_must_default_deny(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "install_build_script_policy:\n  default: deny",
            "install_build_script_policy:\n  default: allow",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("default must be 'deny'", result.stdout)

    def test_build_script_approval_requires_exact_version_binding(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  approvals: []",
            "  approvals:\n  - ecosystem: npm\n    package: typebox\n    harvest_id: H-025\n"
            "    pnpm_matcher: typebox\n    version: ^1.3.6\n"
            "    approved: true\n    rationale: Synthetic stale-range fixture.",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must be one exact package version", result.stdout)

    def test_build_script_approval_requires_rationale(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml",
            "  approvals: []",
            "  approvals:\n  - ecosystem: npm\n    package: typebox\n    harvest_id: H-025\n    pnpm_matcher: typebox\n    version: 1.3.6\n"
            "    approved: true\n    rationale: ''",
        )
        result = run_script(HARVEST, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing required field 'rationale'", result.stdout)


def load_registry_entries(root: Path) -> dict[str, dict]:
    """Parse the registry with the repository's own stdlib YAML-subset loader."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "validate_master_contracts", root / "scripts" / "validate-master-contracts.py"
    )
    vmc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vmc)
    doc = vmc.load_yaml_file(root / "master-build-system" / "06_HARVEST" / "OSS_HARVEST_REGISTRY.yaml")
    return {str(e.get("id")): e for e in (doc.get("entries") or [])}


# Multiline rule: continuation clauses that MUST remain part of the parsed
# `rule` value (final-review blocker: revision-2 field insertion had moved
# them into replacement_strategy). Keys: H-ID -> (first-line anchor, clause).
MULTILINE_RULE_CLAUSES = {
    "H-008": (
        "  rule: VibeFlow owns TerminalSession authority and transport, not terminal emulation. Use the official @xterm/*\n",
        "scoped npm packages (legacy xterm/xterm-* names are deprecated upstream).",
    ),
    "H-015": (
        "  rule: Default BYOA-compatible adapter/reference, never core authority. MIT applies to the SDK repo; the OpenHands\n",
        "application's enterprise/ directory is separately licensed source-available code that VibeFlow must not incorporate.",
    ),
    "H-016": (
        "  rule: Primary BYOW candidate; adapter must pass VibeFlow workspace certification. Certification (Phase 11) must\n",
        "validate the operated Daytona service, since the open-source repository no longer receives updates.",
    ),
    # H-025 was reconciled at M-005 to record the TypeBox 1.x / 1.3.6 selection
    # that M-004 actually made. Its rule now folds two continuation lines, so
    # both must stay inside the parsed `rule` value.
    "H-025": (
        "  rule: Contracts are JSON Schema first; generated TypeScript types are derived. TypeBox 1.x (repo `typebox`,\n",
        "ESM) is the VibeFlow selected line, chosen by M-004 and pinned exactly at 1.3.6; `@sinclair/typebox` 0.x "
        "remains upstream LTS for CJS but is not the VibeFlow selected line.",
    ),
    "H-030": (
        "  rule: Container/dependency/misconfiguration scan. Verify release provenance/checksums when adopting CI binaries\n",
        "(upstream disclosed a malicious v0.69.4 release incident, March 2026, since remediated).",
    ),
}


def multiline_rules_intact(root: Path) -> list[str]:
    """Return H-IDs whose continuation clause left the parsed rule value."""
    entries = load_registry_entries(root)
    problems = []
    for hid, (_anchor_line, clause) in MULTILINE_RULE_CLAUSES.items():
        rule = str((entries.get(hid) or {}).get("rule") or "")
        replacement = str((entries.get(hid) or {}).get("replacement_strategy") or "")
        if clause not in rule:
            problems.append(f"{hid}: clause missing from rule")
        if clause in replacement:
            problems.append(f"{hid}: clause leaked into replacement_strategy")
    return problems



class RegistryMultilineRuleRegressionTests(TempDirMixin, unittest.TestCase):
    def test_real_registry_multiline_rules_intact(self) -> None:
        problems = multiline_rules_intact(REPO_ROOT)
        self.assertEqual(problems, [])

    def test_moved_continuation_is_detected(self) -> None:
        """Simulate the final-review defect: a continuation moved after
        replacement_strategy must be caught by the regression check."""
        box = RepoSandbox(self.tmp)
        registry = box.path("master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml")
        text = registry.read_text(encoding="utf-8")
        anchor, clause = MULTILINE_RULE_CLAUSES["H-008"]
        cont_line = "    " + clause + "\n"
        assert anchor in text and cont_line in text
        # Move the continuation to the end of the entry (after replacement_strategy).
        text = text.replace(cont_line, "", 1)
        marker = "  replacement_strategy: Alternative terminal emulator behind the TerminalTransport interface.\n"
        assert marker in text
        text = text.replace(marker, marker + cont_line, 1)
        registry.write_text(text, encoding="utf-8")
        problems = multiline_rules_intact(box.root)
        self.assertTrue(
            any("H-008" in p for p in problems),
            f"regression check failed to detect moved continuation: {problems}",
        )


class MissionProgressionTests(TempDirMixin, unittest.TestCase):
    DAG = "master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml"
    REG = "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv"
    ACTIVE = ".ai/ACTIVE_MISSION.md"
    # M-005 extended mission-pointer coherence beyond ACTIVE_MISSION.md. A
    # synthetic serial state must therefore move every pointer, exactly as a
    # real mission transition does.
    README = "README.md"
    BOOTSTRAP = "docs/WORKSPACE_BOOTSTRAP_STATUS.md"

    def test_real_repository_passes(self) -> None:
        result = run_script(MASTER, REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_m001_bootstrap_state_still_passes(self) -> None:
        """Historical proof: the original M-001 READY-only state remains valid."""
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-001", "READY")
        result = run_script(MASTER, box.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_unlocked_m003_while_m002_review_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        self._set_status(box, "M-003", "READY")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("M-003 is unlocked but dependencies are not DONE", result.stdout)

    def test_m002_review_with_m001_not_done_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        self._set_status(box, "M-001", "REVIEW")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("M-002 is unlocked but dependencies are not DONE", result.stdout)

    def test_two_active_missions_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        self._set_status(box, "M-001", "READY")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Exactly one mission may be active", result.stdout)

    def test_done_mission_after_active_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        self._set_status(box, "M-003", "DONE")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DONE missions may not follow the active mission", result.stdout)

    def test_zero_active_missions_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        self._set_status(box, "M-002", "LOCKED")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Exactly one mission may be active", result.stdout)

    def test_missing_dependency_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        box.patch(self.DAG, "  depends_on: M-001\n  capability_selector: ALL", "  depends_on: M-999\n  capability_selector: ALL")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("depends on missing mission M-999", result.stdout)

    def test_dependency_cycle_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        box.patch(self.DAG, "  depends_on: M-001\n  capability_selector: ALL", "  depends_on: M-003\n  capability_selector: ALL")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue("Mission DAG cycle" in result.stdout or "forward" in result.stdout, result.stdout)

    def test_forward_dependency_reference_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        box.patch(self.DAG, "  depends_on: M-001\n  capability_selector: ALL", "  depends_on: M-005\n  capability_selector: ALL")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("same/later missions", result.stdout)

    def test_duplicate_mission_id_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        text = box.path(self.DAG).read_text(encoding="utf-8")
        m2 = text.index("- mission_id: M-002")
        m3 = text.index("- mission_id: M-003")
        block = text[m2:m3].replace("mission_id: M-002", "mission_id: M-001", 1)
        box.path(self.DAG).write_text(text[:m3] + block + text[m3:], encoding="utf-8")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Duplicate mission IDs", result.stdout)

    def test_register_dag_status_desync_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        self._set_status(box, "M-002", "LOCKED", update_register=False)
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("!= DAG status", result.stdout)

    def test_register_dag_order_desync_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        lines = [
            line
            for line in box.path(self.REG).read_text(encoding="utf-8").splitlines(keepends=True)
            if not line.startswith("M-004,")
        ]
        box.path(self.REG).write_text("".join(lines), encoding="utf-8")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("MISSION_REGISTER.csv mission_id order/set does not match", result.stdout)

    def test_stale_active_mission_pointer_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-002", "REVIEW")
        box.path(self.ACTIVE).write_text(
            "# Active Mission\n\n**Mission:** M-003 — Ratify threat model and trust boundaries\n\n**Status:** REVIEW\n",
            encoding="utf-8",
        )
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("but the active mission is M-002", result.stdout)

    def test_future_state_m003_review_passes(self) -> None:
        """Generalization proof: after M-002 acceptance, M-003 REVIEW is valid."""
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-003", "REVIEW")
        result = run_script(MASTER, box.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # --- M-005 audit remediation 3B: mission-pointer coherence -------------
    #
    # ACTIVE_MISSION.md was previously the only checked pointer, so README.md
    # and docs/WORKSPACE_BOOTSTRAP_STATUS.md silently went stale. All three are
    # now checked; these tests prove each stale pointer is rejected.

    def test_stale_readme_active_mission_pointer_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-003", "REVIEW")
        box.path(self.README).write_text(
            "# VibeFlow\n\n## Current state\n\n"
            "The active constitution mission is `M-002` (ratify dependency/harvest registry).\n",
            encoding="utf-8",
        )
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("README.md", result.stdout)
        self.assertIn("M-003", result.stdout)

    def test_readme_naming_no_mission_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-003", "REVIEW")
        box.path(self.README).write_text("# VibeFlow\n\nNo mission pointer here.\n", encoding="utf-8")
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("README.md names no mission", result.stdout)

    def test_stale_bootstrap_status_active_mission_pointer_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-003", "REVIEW")
        box.path(self.BOOTSTRAP).write_text(
            "# Workspace Bootstrap Status\n\n- Active mission: M-002 — stale pointer\n",
            encoding="utf-8",
        )
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("docs/WORKSPACE_BOOTSTRAP_STATUS.md", result.stdout)

    def test_missing_readme_pointer_file_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        self._set_serial_state(box, "M-003", "REVIEW")
        box.path(self.README).unlink()
        result = run_script(MASTER, box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Mission pointer file missing: README.md", result.stdout)

    def _set_serial_state(self, box: RepoSandbox, active_id: str, active_status: str) -> None:
        """Build a complete serial state without inheriting the repository's current mission."""
        import csv
        import io
        import re

        active_num = int(active_id.split("-")[1])

        def status_for(mid: str) -> str:
            number = int(mid.split("-")[1])
            if number < active_num:
                return "DONE"
            if number == active_num:
                return active_status
            return "LOCKED"

        dag_path = box.path(self.DAG)
        text = dag_path.read_text(encoding="utf-8")
        pattern = re.compile(r"(?ms)^- mission_id: (M-\d{3})\n.*?(?=^- mission_id: |\Z)")

        def replace_block(match: re.Match) -> str:
            mid = match.group(1)
            block, count = re.subn(
                r"(?m)^  status: [A-Z_]+$",
                f"  status: {status_for(mid)}",
                match.group(0),
                count=1,
            )
            assert count == 1, mid
            return block

        text, count = pattern.subn(replace_block, text)
        assert count == 151, count
        dag_path.write_text(text, encoding="utf-8")

        with box.path(self.REG).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        assert len(rows) == 151
        for row in rows:
            row["status"] = status_for(row["mission_id"])
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        box.path(self.REG).write_text(out.getvalue(), encoding="utf-8")
        box.path(self.ACTIVE).write_text(
            f"# Active Mission\n\n**Mission:** {active_id} — Synthetic historical test state\n\n**Status:** {active_status}\n",
            encoding="utf-8",
        )
        box.path(self.README).write_text(
            "# VibeFlow\n\n## Current state\n\n"
            f"Synthetic historical test state. The active mission is `{active_id}` "
            f"({active_status}).\n",
            encoding="utf-8",
        )
        box.path(self.BOOTSTRAP).write_text(
            "# Workspace Bootstrap Status\n\n"
            f"- Active mission: {active_id} — synthetic historical test state ({active_status})\n",
            encoding="utf-8",
        )

    def _set_status(self, box: RepoSandbox, mid: str, status: str, *, update_register: bool = True) -> None:
        import csv
        import io
        import re

        text = box.path(self.DAG).read_text(encoding="utf-8")
        start = text.index(f"mission_id: {mid}")
        nxt = text.find("- mission_id:", start + 10)
        if nxt == -1:
            nxt = len(text)
        block, count = re.subn(r"  status: [A-Z_]+", f"  status: {status}", text[start:nxt], count=1)
        assert count == 1
        box.path(self.DAG).write_text(text[:start] + block + text[nxt:], encoding="utf-8")
        if not update_register:
            return
        with box.path(self.REG).open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            if row["mission_id"] == mid:
                row["status"] = status
        out = io.StringIO()
        writer = csv.DictWriter(out, fieldnames=rows[0].keys(), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        box.path(self.REG).write_text(out.getvalue(), encoding="utf-8")


if __name__ == "__main__":
    unittest.main(verbosity=2)
