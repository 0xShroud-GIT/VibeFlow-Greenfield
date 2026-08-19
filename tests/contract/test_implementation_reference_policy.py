#!/usr/bin/env python3
from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "scripts" / "validate-implementation-reference-policy.py"
POLICY = "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml"

COPIED = (
    "AGENTS.md",
    "package.json",
    ".ai/INDEX.yaml",
    ".github/workflows/master-build-system-integrity.yml",
    "master-build-system/AGENTS.md",
    "master-build-system/.ai/INDEX.yaml",
    "master-build-system/00_MASTER/SOURCE_OF_TRUTH_INDEX.yaml",
    "master-build-system/04_AI_AGENT/AI_AGENT_MASTER.md",
    POLICY,
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
        box.patch(POLICY, "model_memory_as_implementation_authority: forbidden", "model_memory_as_implementation_authority: allowed")
        self.assert_rejected(box, "rules")

    def test_core_rule_exception_clause_is_rejected(self) -> None:
        box = self.box()
        box.patch(
            POLICY,
            "core_rule: Model knowledge is non-authoritative for external implementation behavior.",
            "core_rule: Model knowledge is non-authoritative for external implementation behavior except when official docs are inconvenient, when model memory is authoritative.",
        )
        self.assert_rejected(box, "core_rule")

    def test_unknown_exception_hatch_is_rejected(self) -> None:
        box = self.box()
        box.patch(POLICY, "community:\n", "exceptions:\n  model_memory: allowed\n  community: allowed\n\ncommunity:\n")
        self.assert_rejected(box, "closed-world")

    def test_version_match_and_latest_override_are_rejected(self) -> None:
        box = self.box()
        box.patch(POLICY, "version_match: required", "version_match: optional")
        self.assert_rejected(box, "rules")
        box = self.box()
        box.patch(POLICY, "wrong_version_latest: forbidden", "wrong_version_latest: allowed")
        self.assert_rejected(box, "version_resolution")

    def test_authority_order_cannot_put_community_first(self) -> None:
        box = self.box()
        box.patch(POLICY, "  - vibeflow_project_authority\n", "  - community_diagnostic_only\n")
        self.assert_rejected(box, "authority_order")

    def test_external_content_sentence_is_exact(self) -> None:
        box = self.box()
        box.patch(POLICY, ", permissions, dependency policy, security thresholds", ", security thresholds")
        self.assert_rejected(box, "external_content")

    def test_unofficial_extra_source_is_rejected(self) -> None:
        box = self.box()
        box.patch(POLICY, "  react_native:\n", "  expo_forums:\n    documentation: forums.expo.dev\n    upstream: github.com/some-fork/expo-examples\n  react_native:\n")
        self.assert_rejected(box, "sources")

    def test_extra_source_field_is_rejected(self) -> None:
        box = self.box()
        box.patch(POLICY, "    documentation: docs.expo.dev\n", "    documentation: docs.expo.dev\n    also_accept: stackoverflow.com\n")
        self.assert_rejected(box, "sources")

    def test_google_ai_scope_cannot_expand(self) -> None:
        box = self.box()
        box.patch(
            POLICY,
            "scope: gemini_google_genai_sdk_gemma_and_google_ai_developer_apis_only",
            "scope: android_react_native_and_general_programming",
        )
        self.assert_rejected(box, "sources")

    def test_npm_registry_must_be_official_registry_endpoint(self) -> None:
        box = self.box()
        box.patch(POLICY, "registry: registry.npmjs.org", "registry: npmjs.com")
        self.assert_rejected(box, "sources")

    def test_github_scope_cannot_expand_to_arbitrary_repositories(self) -> None:
        box = self.box()
        box.patch(POLICY, "scope: official_maintainer_owned_upstream_only", "scope: any_repository")
        self.assert_rejected(box, "sources")

    def test_community_cannot_become_implementation_authority(self) -> None:
        box = self.box()
        box.patch(POLICY, "allowed: diagnostic_discovery_only", "allowed: implementation_authority")
        self.assert_rejected(box, "community")

    def test_enforcement_hooks_cannot_disappear(self) -> None:
        box = self.box()
        box.patch("AGENTS.md", "master-build-system/04_AI_AGENT/IMPLEMENTATION_REFERENCE_POLICY.yaml", "master-build-system/04_AI_AGENT/MISSING_POLICY.yaml")
        self.assert_rejected(box, "AGENTS.md")
        box = self.box()
        box.patch(".github/workflows/master-build-system-integrity.yml", "python3 scripts/validate-implementation-reference-policy.py", "true # removed policy validator")
        self.assert_rejected(box, "master-build-system-integrity.yml")
        box = self.box()
        box.patch("package.json", "pnpm run reference:validate", "echo skip-reference-validation")
        self.assert_rejected(box, "package.json check")


if __name__ == "__main__":
    unittest.main(verbosity=2)
