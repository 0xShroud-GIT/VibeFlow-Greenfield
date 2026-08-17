#!/usr/bin/env python3
"""Deterministic mutation tests for the M-004 foundation contract."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/validate-m004-foundation.py"
IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "dist", ".turbo", ".cache", ".vite",
    "__pycache__", ".pytest_cache", ".next", ".expo",
)


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(VALIDATOR), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


class Sandbox:
    def __init__(self, temp_root: Path) -> None:
        self.root = temp_root / "repo"
        shutil.copytree(REPO_ROOT, self.root, ignore=IGNORE)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def patch(self, rel: str, old: str, new: str) -> None:
        path = self.path(rel)
        text = path.read_text(encoding="utf-8")
        if old not in text:
            raise AssertionError(f"anchor missing in {rel}: {old!r}")
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    def write(self, rel: str, content: str) -> None:
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def delete(self, rel: str) -> None:
        path = self.path(rel)
        if path.is_dir():
            shutil.rmtree(path)
        elif path.exists():
            path.unlink()

    def set_dag_status(self, mission_id: str, status: str) -> None:
        path = self.path("master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml")
        lines = path.read_text(encoding="utf-8").splitlines()
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
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    def set_register_status(self, mission_id: str, status: str) -> None:
        path = self.path("master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv")
        with path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fieldnames = reader.fieldnames or []
        changed = False
        for row in rows:
            if row.get("mission_id") == mission_id:
                row["status"] = status
                changed = True
                break
        if not changed:
            raise AssertionError(f"mission not found in register: {mission_id}")
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)


class M004FoundationTests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def assert_rejected(self, box: Sandbox, needle: str) -> None:
        result = run_validator(box.root)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(needle, result.stdout + result.stderr)

    def test_00_real_repository_passes(self) -> None:
        result = run_validator(REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_wrong_node_pin(self) -> None:
        box = Sandbox(self.tmp)
        box.patch(".nvmrc", "24.19.0", "22.22.3")
        self.assert_rejected(box, "A: .nvmrc must pin")

    def test_wrong_pnpm_package_manager(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("package.json", '"packageManager": "pnpm@11.4.0"', '"packageManager": "pnpm@11.3.0"')
        self.assert_rejected(box, "B: packageManager")

    def test_semver_range_dependency(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("package.json", '"typescript": "6.0.3"', '"typescript": "^6.0.3"')
        self.assert_rejected(box, "D: dependency range/dist-tag forbidden")

    def test_unapproved_external_dependency(self) -> None:
        box = Sandbox(self.tmp)
        pkg = json.loads(box.path("package.json").read_text(encoding="utf-8"))
        pkg["devDependencies"]["express"] = "4.18.0"
        box.write("package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "C/F: root devDependencies")

    def test_git_url_dependency(self) -> None:
        box = Sandbox(self.tmp)
        pkg = json.loads(box.path("package.json").read_text(encoding="utf-8"))
        pkg["devDependencies"]["left-pad"] = "git+https://github.com/stevemao/left-pad.git"
        box.write("package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "E: exotic dependency source forbidden")

    def test_nested_pnpm_lockfile(self) -> None:
        box = Sandbox(self.tmp)
        box.write("packages/core/pnpm-lock.yaml", "lockfileVersion: '9.0'\n")
        self.assert_rejected(box, "G: exactly one root pnpm-lock.yaml")

    def test_package_lockfile(self) -> None:
        box = Sandbox(self.tmp)
        box.write("package-lock.json", "{}\n")
        self.assert_rejected(box, "H: forbidden lockfile")

    def test_yarn_lockfile(self) -> None:
        box = Sandbox(self.tmp)
        box.write("yarn.lock", "")
        self.assert_rejected(box, "H: forbidden lockfile")

    def test_bun_lockfile(self) -> None:
        box = Sandbox(self.tmp)
        box.write("bun.lock", "")
        self.assert_rejected(box, "H: forbidden lockfile")

    def test_manifest_under_apps(self) -> None:
        box = Sandbox(self.tmp)
        box.write("apps/web/package.json", '{"name":"forbidden"}\n')
        self.assert_rejected(box, "J: package.json forbidden under apps")

    def test_manifest_under_services(self) -> None:
        box = Sandbox(self.tmp)
        box.write("services/gateway/package.json", '{"name":"forbidden"}\n')
        self.assert_rejected(box, "J: package.json forbidden under services")

    def test_manifest_under_workers(self) -> None:
        box = Sandbox(self.tmp)
        box.write("workers/execution/package.json", '{"name":"forbidden"}\n')
        self.assert_rejected(box, "J: package.json forbidden under workers")

    def test_manifest_under_adapters(self) -> None:
        box = Sandbox(self.tmp)
        box.write("adapters/agents/package.json", '{"name":"forbidden"}\n')
        self.assert_rejected(box, "J: package.json forbidden under adapters")

    def test_missing_workspace_glob(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("pnpm-workspace.yaml", "  - adapters/*\n", "")
        self.assert_rejected(box, "I: workspace globs")

    def test_typebox_zero_x(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("packages/contracts/package.json", '"typebox": "1.3.6"', '"@sinclair/typebox": "0.34.0"')
        self.assert_rejected(box, "C/N: contracts")

    def test_missing_strict_flag(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("tsconfig.base.json", '"strict": true,', '"strict": false,')
        self.assert_rejected(box, "O: strict must be True")

    def test_lifecycle_script(self) -> None:
        box = Sandbox(self.tmp)
        pkg = json.loads(box.path("packages/core/package.json").read_text(encoding="utf-8"))
        pkg["scripts"]["postinstall"] = "echo forbidden"
        box.write("packages/core/package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "P: forbidden lifecycle script")

    def test_dangerously_allow_all_builds(self) -> None:
        box = Sandbox(self.tmp)
        text = box.path("pnpm-workspace.yaml").read_text(encoding="utf-8")
        box.write("pnpm-workspace.yaml", text + "dangerouslyAllowAllBuilds: true\n")
        self.assert_rejected(box, "Q: dangerouslyAllowAllBuilds")

    def test_release_age_value_disabled(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("pnpm-workspace.yaml", "minimumReleaseAge: 1440", "minimumReleaseAge: 0")
        self.assert_rejected(box, "minimumReleaseAge")

    def test_release_age_strict_disabled(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("pnpm-workspace.yaml", "minimumReleaseAgeStrict: true", "minimumReleaseAgeStrict: false")
        self.assert_rejected(box, "minimumReleaseAgeStrict")

    def test_release_age_missing_time_relaxed(self) -> None:
        box = Sandbox(self.tmp)
        box.patch(
            "pnpm-workspace.yaml",
            "minimumReleaseAgeIgnoreMissingTime: false",
            "minimumReleaseAgeIgnoreMissingTime: true",
        )
        self.assert_rejected(box, "minimumReleaseAgeIgnoreMissingTime")

    def test_trust_lockfile_true(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("pnpm-workspace.yaml", "trustLockfile: false", "trustLockfile: true")
        self.assert_rejected(box, "trustLockfile")

    def test_strict_dep_builds_disabled(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("pnpm-workspace.yaml", "strictDepBuilds: true", "strictDepBuilds: false")
        self.assert_rejected(box, "strictDepBuilds")

    def test_security_settings_in_npmrc_do_not_count(self) -> None:
        box = Sandbox(self.tmp)
        box.patch("pnpm-workspace.yaml", "minimumReleaseAgeStrict: true\n", "")
        box.write(".npmrc", "minimumReleaseAgeStrict=true\n")
        self.assert_rejected(box, "must be in pnpm-workspace.yaml, not .npmrc")

    def test_missing_shared_package_manifest(self) -> None:
        box = Sandbox(self.tmp)
        box.delete("packages/core/package.json")
        self.assert_rejected(box, "K: expected exactly seven manifests")

    def test_unix_only_clean_script_rejected(self) -> None:
        box = Sandbox(self.tmp)
        pkg = json.loads(box.path("packages/core/package.json").read_text(encoding="utf-8"))
        pkg["scripts"]["clean"] = "rm -rf dist"
        box.write("packages/core/package.json", json.dumps(pkg, indent=2) + "\n")
        self.assert_rejected(box, "cross-platform foundation scripts only")

    def test_m005_unlocked(self) -> None:
        box = Sandbox(self.tmp)
        box.set_dag_status("M-005", "REVIEW")
        box.set_register_status("M-005", "REVIEW")
        self.assert_rejected(box, "V: DAG M-005 must remain LOCKED")

    def test_missing_foundation_workflow(self) -> None:
        box = Sandbox(self.tmp)
        box.delete(".github/workflows/repository-foundation.yml")
        self.assert_rejected(box, "W: missing .github/workflows/repository-foundation.yml")


if __name__ == "__main__":
    unittest.main()
