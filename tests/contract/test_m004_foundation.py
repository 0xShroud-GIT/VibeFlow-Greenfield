#!/usr/bin/env python3
"""M-004 deterministic foundation validator tests (stdlib unittest, no third-party deps).

Proves the M-004 foundation validator fails deterministically for:
  - wrong Node pin
  - wrong pnpm packageManager pin
  - semver range dependency
  - unapproved external dependency
  - git URL dependency
  - nested/extra lockfile
  - npm/yarn/bun lockfile
  - package.json introduced under apps/*/services/*/workers/*/adapters/*
  - missing workspace glob
  - TypeBox 0.x/@sinclair package
  - missing strict TS flag
  - lifecycle install script
  - dangerouslyAllowAllBuilds enabled
  - release-age protection disabled
  - trustLockfile true
  - malformed/missing shared package
  - M-005 unlocked while M-004 is REVIEW

Each scenario runs against a throwaway temp copy; the real repo is never mutated.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts" / "validate-m004-foundation.py"

IGNORE = shutil.ignore_patterns(".git")

def run_validator(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(root / "scripts" / "validate-m004-foundation.py"), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
    )

# Also support running the validator from original location with --root
def run_validator_original(root: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
    )

class RepoSandbox:
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

    def write(self, rel: str, content: str) -> None:
        p = self.path(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def delete(self, rel: str) -> None:
        p = self.path(rel)
        if p.is_file():
            p.unlink()
        elif p.is_dir():
            shutil.rmtree(p)

class TempDirMixin:
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

class M004FoundationTests(TempDirMixin, unittest.TestCase):
    def test_real_repository_passes(self) -> None:
        result = run_validator_original(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wrong_node_pin_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(".nvmrc", "24.19.0", "22.22.3")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("A: Wrong Node pin", result.stdout)

    def test_wrong_pnpm_pin_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch("package.json", '"packageManager": "pnpm@11.4.0"', '"packageManager": "pnpm@11.3.0"')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("B: Wrong packageManager", result.stdout)

    def test_semver_range_dependency_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        # Change exact pin to range
        box.patch("package.json", '"typescript": "6.0.3"', '"typescript": "^6.0.3"')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("D: Dependency range forbidden", result.stdout)

    def test_unapproved_external_dependency_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        # Add unapproved dep express
        box.patch("package.json", '"vitest": "4.1.7"', '"vitest": "4.1.7",\n    "express": "4.18.0"')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("F: Unapproved external dependency", result.stdout)

    def test_git_url_dependency_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch("package.json", '"vitest": "4.1.7"', '"vitest": "4.1.7",\n    "left-pad": "git+https://github.com/stevemao/left-pad.git"')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("E: Git URL dependency", result.stdout)

    def test_nested_lockfile_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.write("packages/core/pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("G: Nested pnpm-lock.yaml", result.stdout)

    def test_npm_lockfile_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.write("package-lock.json", "{}")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("H: Forbidden lockfile", result.stdout)

    def test_yarn_lockfile_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.write("yarn.lock", "")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("H: Forbidden lockfile", result.stdout)

    def test_bun_lockfile_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.write("bun.lockb", "")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("H: Forbidden lockfile", result.stdout)

    def test_package_json_under_apps_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.write("apps/web/package.json", '{"name":"evil","version":"1.0.0"}')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("J: Forbidden package.json under apps", result.stdout)

    def test_package_json_under_services_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.write("services/gateway/package.json", '{"name":"evil","version":"1.0.0"}')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("J: Forbidden package.json under services", result.stdout)

    def test_package_json_under_workers_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.write("workers/execution/package.json", '{"name":"evil","version":"1.0.0"}')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("J: Forbidden package.json under workers", result.stdout)

    def test_package_json_under_adapters_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.write("adapters/agents/package.json", '{"name":"evil","version":"1.0.0"}')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("J: Forbidden package.json under adapters", result.stdout)

    def test_missing_workspace_glob_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        # Remove one glob entirely
        orig = box.path("pnpm-workspace.yaml").read_text(encoding="utf-8")
        new_text = orig.replace("  - adapters/*\n", "")
        assert "adapters/*" not in new_text or new_text.count("adapters/*") == 0, "failed to remove"
        box.path("pnpm-workspace.yaml").write_text(new_text, encoding="utf-8")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("I: Missing required workspace glob", result.stdout)

    def test_typebox_0x_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        # Replace typebox with @sinclair/typebox
        box.patch("packages/contracts/package.json", '"typebox": "1.3.6"', '"@sinclair/typebox": "0.34.0"')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("N: Forbidden TypeBox 0.x", result.stdout)

    def test_missing_strict_flag_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        # Remove one strict flag
        box.patch("tsconfig.base.json", '"strict": true,', '')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("O: Missing or wrong TypeScript strict flag", result.stdout)

    def test_lifecycle_script_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        # Add preinstall script to one package
        box.patch("packages/core/package.json", '"clean": "rm -rf dist"', '"clean": "rm -rf dist",\n    "postinstall": "echo evil"')
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("P: Forbidden lifecycle script", result.stdout)

    def test_dangerously_allow_builds_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        # Append dangerous flag
        orig = box.path(".npmrc").read_text(encoding="utf-8")
        box.path(".npmrc").write_text(orig + "\ndangerouslyAllowAllBuilds=true\n", encoding="utf-8")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Q: 'dangerouslyAllowAllBuilds'", result.stdout)

    def test_release_age_disabled_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(".npmrc", "minimumReleaseAgeStrict=true", "minimumReleaseAgeStrict=false")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("R: 'minimumReleaseAgeStrict'", result.stdout)

    def test_trustlockfile_true_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.patch(".npmrc", "trustLockfile=false", "trustLockfile=true")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("S: 'trustLockfile' must not be true", result.stdout)

    def test_malformed_missing_shared_package_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        box.delete("packages/core/package.json")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("K: Missing shared package manifest", result.stdout)

    def test_m005_unlocked_fails(self) -> None:
        box = RepoSandbox(self.tmp)
        # Change M-005 status from LOCKED to REVIEW in DAG
        dag = box.path("master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml").read_text(encoding="utf-8")
        # Replace first occurrence of M-005 LOCKED with REVIEW - but our DAG has M-005 LOCKED, we need to patch precisely
        # We'll replace the status line after M-005
        # Simpler: replace the exact block snippet
        old = "- mission_id: M-005\n  phase: 1\n  phase_name: Repository Foundation\n  title: Establish schema/codegen pipeline\n  scope: 'Repository Foundation: Establish schema/codegen pipeline.'\n  depends_on: M-004\n  capability_selector: REL,ENV\n  required_master_context: MASTER_OF_MASTERS + relevant master(s) + exact contracts + harvest entries + acceptance gates\n  agent_context_budget: 'small: target <= 12k tokens unless mission explicitly requires more'\n  deliverables: code/tests/evidence + ledger update + ADR only if architecture decision changed\n  exit_gate: all mission acceptance tests pass; no invariant violation; CI green\n  status: LOCKED"
        new = old.replace("status: LOCKED", "status: REVIEW")
        assert old in dag, "M-005 block not found"
        box.path("master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml").write_text(dag.replace(old, new, 1), encoding="utf-8")
        # Also need to update REGISTER
        reg = box.path("master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv").read_text(encoding="utf-8")
        reg = reg.replace("M-005,1,Repository Foundation,Establish schema/codegen pipeline,Repository Foundation: Establish schema/codegen pipeline.,M-004,\"REL,ENV\"", "M-005,1,Repository Foundation,Establish schema/codegen pipeline,Repository Foundation: Establish schema/codegen pipeline.,M-004,\"REL,ENV\"")
        # Actually the status is at end, replace ,LOCKED with ,REVIEW for M-005 line
        # Find line starting with M-005,
        lines = reg.splitlines()
        for i, line in enumerate(lines):
            if line.startswith("M-005,"):
                lines[i] = line.replace(",LOCKED", ",REVIEW")
        box.path("master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv").write_text("\n".join(lines)+"\n", encoding="utf-8")
        result = run_validator_original(box.root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("V: M-005 must remain LOCKED", result.stdout)

if __name__ == "__main__":
    unittest.main()
