#!/usr/bin/env python3
from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/classify-verification-scope.py"

spec = importlib.util.spec_from_file_location("vibeflow_scope", SCRIPT)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)


class ScopeClassifierTests(unittest.TestCase):
    def assert_scope(self, path: str, *, full: bool, dev: bool) -> None:
        result = module.classify_paths([path])
        self.assertEqual(result.full_mutations, full, path)
        self.assertEqual(result.dev_image, dev, path)

    def test_ordinary_product_code_is_fast(self) -> None:
        self.assert_scope("apps/web/src/page.tsx", full=False, dev=False)
        self.assert_scope("packages/ui/src/button.tsx", full=False, dev=False)
        self.assert_scope("services/api/src/index.ts", full=False, dev=False)

    def test_routine_mission_progression_is_fast(self) -> None:
        self.assert_scope("master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml", full=False, dev=False)
        self.assert_scope("master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv", full=False, dev=False)
        self.assert_scope("master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml", full=False, dev=False)
        self.assert_scope(".ai/ACTIVE_MISSION.md", full=False, dev=False)

    def test_future_mission_validator_does_not_replay_old_history(self) -> None:
        self.assert_scope("scripts/validate-m008-example.py", full=False, dev=False)
        self.assert_scope("tests/contract/test_m008_example.py", full=False, dev=False)

    def test_workflow_and_devcontainer_changes_take_deepest_path(self) -> None:
        self.assert_scope(".github/workflows/repo-sanitation.yml", full=True, dev=True)
        self.assert_scope(".devcontainer/devcontainer.json", full=True, dev=True)
        self.assert_scope("package.json", full=True, dev=True)
        self.assert_scope("scripts/ci/classify-verification-scope.py", full=True, dev=True)

    def test_governance_contract_and_security_boundaries_replay_mutations(self) -> None:
        self.assert_scope("master-build-system/02_ARCHITECTURE/TRUST_BOUNDARIES.md", full=True, dev=False)
        self.assert_scope("master-build-system/05_INTEROP/NATIVE_WEB_BRIDGE.md", full=True, dev=False)
        self.assert_scope("master-build-system/09_CONTRACTS/FRONTEND_BACKEND_MATRIX.yaml", full=True, dev=False)
        self.assert_scope("scripts/repo-sanitize.sh", full=True, dev=False)
        self.assert_scope("tests/security/fixtures/semgrep/positive/dangerous.ts", full=True, dev=False)
        self.assert_scope("packages/contracts/generated/catalog.schema.json", full=True, dev=False)

    def test_native_platform_configuration_is_risk_triggered(self) -> None:
        self.assert_scope("apps/mobile/android/app/build.gradle", full=True, dev=False)
        self.assert_scope("apps/mobile/ios/Podfile", full=True, dev=False)
        self.assert_scope("apps/mobile/app.json", full=True, dev=False)

    def test_unknown_path_fails_closed(self) -> None:
        self.assert_scope("mystery/new-control.cfg", full=True, dev=True)

    def test_missing_base_fails_closed(self) -> None:
        result = subprocess.run(
            ["python3", str(SCRIPT), "--json"],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('"full_mutations": true', result.stdout)
        self.assertIn('"dev_image": true', result.stdout)

    def test_rename_exposes_old_sensitive_path(self) -> None:
        with tempfile.TemporaryDirectory(prefix="vibeflow-scope-git-") as tmp:
            repo = Path(tmp)
            subprocess.run(["git", "init", "-q", str(repo)], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.name", "VibeFlow Test"], check=True)
            subprocess.run(["git", "-C", str(repo), "config", "user.email", "test@example.invalid"], check=True)
            old = repo / "master-build-system/08_SECURITY/SECURITY_MASTER.md"
            old.parent.mkdir(parents=True)
            old.write_text("security\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qm", "base"], check=True)
            base = subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip()
            target = repo / "docs/moved.md"
            target.parent.mkdir(parents=True)
            subprocess.run(["git", "-C", str(repo), "mv", str(old.relative_to(repo)), str(target.relative_to(repo))], check=True)
            subprocess.run(["git", "-C", str(repo), "commit", "-qam", "rename"], check=True)
            changed = module.git_changed_paths(base, "HEAD", repo)
            self.assertIn("master-build-system/08_SECURITY/SECURITY_MASTER.md", changed)
            self.assertIn("docs/moved.md", changed)
            classified = module.classify_paths(changed)
            self.assertTrue(classified.full_mutations)


if __name__ == "__main__":
    unittest.main(verbosity=2)
