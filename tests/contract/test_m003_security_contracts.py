#!/usr/bin/env python3
"""M-003 deterministic threat-model/security contract tests (stdlib only)."""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate-threat-model.py"
IGNORE = shutil.ignore_patterns(".git")

_spec = importlib.util.spec_from_file_location("validate_threat_model", VALIDATOR)
_validator = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(_validator)


def validate(root: Path) -> dict:
    return _validator.validate(root)


def errors(result: dict) -> str:
    return "\n".join(result.get("errors") or [])


class RepoSandbox:
    def __init__(self, tmp: Path) -> None:
        self.root = tmp / "repo"
        shutil.copytree(REPO_ROOT, self.root, ignore=IGNORE)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def patch(self, rel: str, old: str, new: str, count: int = 1) -> None:
        path = self.path(rel)
        text = path.read_text(encoding="utf-8")
        assert old in text, f"anchor not found in {rel}: {old[:80]!r}"
        path.write_text(text.replace(old, new, count), encoding="utf-8")


class TempDirMixin:
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)


class M003SecurityContractTests(TempDirMixin, unittest.TestCase):
    THREATS = "master-build-system/08_SECURITY/THREAT_MODEL.md"
    BOUNDARIES = "master-build-system/02_ARCHITECTURE/TRUST_BOUNDARIES.md"
    SECURITY = "master-build-system/08_SECURITY/SECURITY_MASTER.md"
    SECRETS = "master-build-system/08_SECURITY/SECRET_HANDLING.md"
    WORKSPACE = "master-build-system/08_SECURITY/WORKSPACE_ISOLATION.md"

    def test_real_repository_passes(self) -> None:
        result = validate(REPO_ROOT)
        self.assertEqual(result["result"], "PASS", errors(result))
        self.assertEqual(result["counts"]["assets"], 12)
        self.assertEqual(result["counts"]["threats"], 24)
        self.assertEqual(result["counts"]["boundaries"], 13)
        self.assertEqual(result["counts"]["invariants_crosswalked"], 20)

    def test_missing_threat_id_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.THREATS, "### TM-024 —", "### XX-024 —")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("threat IDs must be exactly", errors(result))

    def test_duplicate_threat_id_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.THREATS, "### TM-024 —", "### TM-023 —")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("duplicate threat IDs", errors(result))

    def test_missing_threat_field_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.THREATS, "- **Required controls:** Authenticate session;", "- **Controls removed:** Authenticate session;")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("TM-001: missing required field 'Required controls'", errors(result))

    def test_unknown_boundary_reference_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.THREATS, "- **Boundaries:** TB-001, TB-002", "- **Boundaries:** TB-999, TB-002")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("TM-001: unknown boundary reference TB-999", errors(result))

    def test_unknown_asset_reference_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            self.THREATS,
            "- **Assets:** AS-001, AS-002, AS-004, AS-005, AS-010",
            "- **Assets:** AS-999, AS-002, AS-004, AS-005, AS-010",
        )
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("TM-001: unknown asset reference AS-999", errors(result))

    def test_missing_boundary_id_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.BOUNDARIES, "## TB-013 —", "## TB-014 —")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("boundary IDs must be exactly", errors(result))

    def test_missing_boundary_field_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            self.BOUNDARIES,
            "- **Authentication:** Validate the VibeFlow session/access token",
            "- **Authentication removed:** Validate the VibeFlow session/access token",
        )
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("TB-001: missing required field 'Authentication'", errors(result))

    def test_uncovered_boundary_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        path = box.path(self.THREATS)
        text = path.read_text(encoding="utf-8")
        updated = []
        for line in text.splitlines():
            if line.startswith("- **Boundaries:**"):
                value = line.replace("TB-012, ", "").replace(", TB-012", "").replace("TB-012", "")
                updated.append(value)
            else:
                updated.append(line)
        path.write_text("\n".join(updated) + "\n", encoding="utf-8")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("trust boundaries not covered by any threat: TB-012", errors(result))

    def test_missing_invariant_crosswalk_entry_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        path = box.path(self.THREATS)
        text = path.read_text(encoding="utf-8")
        line = next(x for x in text.splitlines() if x.startswith("- **INV-020:**"))
        path.write_text(text.replace(line + "\n", "", 1), encoding="utf-8")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("invariant crosswalk must contain INV-020 exactly once", errors(result))

    def test_security_master_normative_reference_removal_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.SECURITY, "08_SECURITY/SECRET_HANDLING.md", "08_SECURITY/SECRET_POLICY_REMOVED.md")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("SECURITY_MASTER.md missing normative reference '08_SECURITY/SECRET_HANDLING.md'", errors(result))

    def test_fail_closed_security_principle_removal_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.SECURITY, "fails closed", "continues optimistically")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("missing constitutional marker 'fails closed'", errors(result))

    def test_tool_availability_permission_boundary_removal_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.BOUNDARIES, "Tool availability", "Tool discovery")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("missing anti-authority marker 'Tool availability'", errors(result))

    def test_agent_finish_cannot_become_verified_fails_if_weakened(self) -> None:
        box = RepoSandbox(self.tmp)
        path = box.path(self.THREATS)
        text = path.read_text(encoding="utf-8")
        self.assertGreaterEqual(text.count("Agent finish never VERIFIED"), 2)
        path.write_text(
            text.replace("Agent finish never VERIFIED", "Agent finish may be VERIFIED"),
            encoding="utf-8",
        )
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("missing anti-authority marker 'Agent finish never VERIFIED'", errors(result))

    def test_repository_workspace_reconciliation_marker_removal_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.THREATS, "Repository != workspace", "Repository and workspace are equivalent")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("missing anti-authority marker 'Repository != workspace'", errors(result))

    def test_secret_channel_policy_weakening_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            self.SECRETS,
            "Never place raw secrets in Agent prompts, event payloads, evidence blobs, logs, analytics or the native-web bridge",
            "Raw secrets may be copied into execution context when convenient",
        )
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("SECRET_HANDLING.md missing required policy marker", errors(result))

    def test_workspace_provider_documentation_is_not_evidence_fails_if_removed(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(
            self.WORKSPACE,
            "Provider documentation is not sufficient evidence",
            "Provider documentation is sufficient evidence",
        )
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("WORKSPACE_ISOLATION.md missing required certification marker", errors(result))

    def test_workspace_cross_tenant_certification_marker_removal_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(self.WORKSPACE, "cross-tenant separation", "basic tenant separation")
        result = validate(box.root)
        self.assertEqual(result["result"], "FAIL")
        self.assertIn("WORKSPACE_ISOLATION.md missing required certification marker 'cross-tenant separation'", errors(result))


if __name__ == "__main__":
    unittest.main(verbosity=2)
