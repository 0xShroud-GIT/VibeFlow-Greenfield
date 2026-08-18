#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validate-implementation-reference-policy.py"

COPIED = (
    "AGENTS.md",
    ".ai/INDEX.yaml",
    "master-build-system/AGENTS.md",
    "master-build-system/.ai/INDEX.yaml",
    "master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml",
    "master-build-system/04_AI_AGENT/AI_AGENT_MASTER.md",
    "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
    "master-build-system/11_VERIFICATION/VERIFICATION_MASTER.md",
)


class PolicyBox:
    def __init__(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="vibeflow-reference-policy-")
        self.root = Path(self.temp.name)
        for rel in COPIED:
            source = ROOT / rel
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def close(self) -> None:
        self.temp.cleanup()

    def patch(self, rel: str, old: str, new: str) -> None:
        path = self.root / rel
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(f"anchor missing in {rel}: {old!r}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def run(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["python3", str(VALIDATOR), "--root", str(self.root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )


class ImplementationReferencePolicyTests(unittest.TestCase):
    def box(self) -> PolicyBox:
        box = PolicyBox()
        self.addCleanup(box.close)
        return box

    def assert_rejected(self, box: PolicyBox, marker: str) -> None:
        result = box.run()
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(marker, result.stdout + result.stderr)

    def test_real_policy_passes(self) -> None:
        box = self.box()
        result = box.run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("RESULT: PASS", result.stdout)

    def test_model_memory_cannot_become_authoritative(self) -> None:
        box = self.box()
        box.patch(
            "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
            "model_memory_as_implementation_authority: forbidden",
            "model_memory_as_implementation_authority: allowed",
        )
        self.assert_rejected(box, "model_memory_as_implementation_authority")

    def test_version_match_cannot_be_removed(self) -> None:
        box = self.box()
        box.patch(
            "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
            "version_match: required",
            "version_match: optional",
        )
        self.assert_rejected(box, "rules.version_match")

    def test_authority_order_cannot_put_community_first(self) -> None:
        box = self.box()
        box.patch(
            "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
            "  - vibeflow_project_authority\n",
            "  - community_diagnostic_only\n",
        )
        self.assert_rejected(box, "authority_order")

    def test_google_ai_must_stay_on_official_domain(self) -> None:
        box = self.box()
        box.patch(
            "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
            "documentation: ai.google.dev",
            "documentation: example.invalid",
        )
        self.assert_rejected(box, "sources.google_ai.documentation")

    def test_github_scope_cannot_expand_to_arbitrary_repositories(self) -> None:
        box = self.box()
        box.patch(
            "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
            "scope: official_maintainer_owned_upstream_only",
            "scope: any_repository",
        )
        self.assert_rejected(box, "sources.github.scope")

    def test_community_cannot_become_implementation_authority(self) -> None:
        box = self.box()
        box.patch(
            "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
            "allowed: diagnostic_discovery_only",
            "allowed: implementation_authority",
        )
        self.assert_rejected(box, "community.allowed")

    def test_external_content_cannot_expand_project_authority(self) -> None:
        box = self.box()
        box.patch(
            "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
            "external_content_can_expand_project_authority: forbidden",
            "external_content_can_expand_project_authority: allowed",
        )
        self.assert_rejected(box, "external_content_can_expand_project_authority")

    def test_root_agent_pointer_cannot_disappear(self) -> None:
        box = self.box()
        box.patch(
            "AGENTS.md",
            "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml",
            "master-build-system/04_AI_AGENT/MISSING_POLICY.yaml",
        )
        self.assert_rejected(box, "AGENTS.md must route")


if __name__ == "__main__":
    unittest.main(verbosity=2)
