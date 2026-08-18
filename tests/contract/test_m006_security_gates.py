#!/usr/bin/env python3
"""Deterministic mutation suite for M-006 static security/dependency gates."""

from __future__ import annotations

import csv
import io
import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/validate-m006-security-gates.py"
M005_VALIDATOR = REPO_ROOT / "scripts/validate-m005-contract-codegen.py"
MASTER_VALIDATOR = REPO_ROOT / "scripts/validate-master-contracts.py"
IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "dist", ".turbo", ".cache", ".vite",
    "__pycache__", ".pytest_cache", ".next", ".expo",
)
DAG = "master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml"
REGISTER = "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv"
REGISTRY = "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml"
SECURITY_WORKFLOW = ".github/workflows/security-and-dependency-gates.yml"
CHECKOUT_SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"


def run(script: Path, root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(script), "--root", str(root)],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )


class Sandbox:
    def __init__(self, temp: Path) -> None:
        self.root = temp / "repo"
        shutil.copytree(REPO_ROOT, self.root, ignore=IGNORE)

    def path(self, rel: str) -> Path:
        return self.root / rel

    def read(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        path = self.path(rel)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    def patch(self, rel: str, old: str, new: str) -> None:
        text = self.read(rel)
        if old not in text:
            raise AssertionError(f"anchor missing in {rel}: {old[:100]!r}")
        self.write(rel, text.replace(old, new, 1))

    def set_status(self, mission: str, status: str, *, register: bool = True) -> None:
        text = self.read(DAG)
        pattern = rf"(?ms)(^- mission_id: {mission}\n.*?^  status: )[A-Z_]+"
        text, count = re.subn(pattern, rf"\g<1>{status}", text, count=1)
        if count != 1:
            raise AssertionError(f"mission missing: {mission}")
        self.write(DAG, text)
        if not register:
            return
        with self.path(REGISTER).open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fields = reader.fieldnames or []
        for row in rows:
            if row["mission_id"] == mission:
                row["status"] = status
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        self.write(REGISTER, output.getvalue())

    def set_capability_status(self, vf_id: str, status: str) -> None:
        csv_path = self.path("master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv")
        with csv_path.open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle)
            rows = list(reader)
            fields = reader.fieldnames or []
        for row in rows:
            if row["vf_id"] == vf_id:
                row["status"] = status
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
        self.write("master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv", output.getvalue())

        rel = "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml"
        text = self.read(rel)
        pattern = rf"(?ms)(^- vf_id: {re.escape(vf_id)}\n.*?^  status: )[A-Z_]+"
        text, count = re.subn(pattern, rf"\g<1>{status}", text, count=1)
        if count != 1:
            raise AssertionError(f"capability missing: {vf_id}")
        self.write(rel, text)

    def point_to(self, mission: str, status: str) -> None:
        self.write(
            ".ai/ACTIVE_MISSION.md",
            f"# Active Mission\n\n**Mission:** {mission} — synthetic progression\n\n**Status:** {status}\n",
        )
        self.write(
            "README.md",
            f"# VibeFlow\n\n## Current state\n\nThe active mission is `{mission}` ({status}).\n",
        )
        self.write(
            "docs/WORKSPACE_BOOTSTRAP_STATUS.md",
            f"# Workspace Bootstrap Status\n\n- Active mission: {mission} — synthetic ({status})\n",
        )

    def add_approved_allow_build(self) -> None:
        self.patch(
            REGISTRY,
            "  approvals: []",
            "  approvals:\n  - ecosystem: npm\n    package: typebox\n    harvest_id: H-025\n    pnpm_matcher: typebox\n    version: 1.3.6\n    approved: true\n    rationale: TypeBox fixture proves explicit reviewed package build approval.",
        )
        self.write("pnpm-workspace.yaml", self.read("pnpm-workspace.yaml") + "allowBuilds:\n  typebox: true\n")

    def remove_job(self, name: str) -> None:
        text = self.read(SECURITY_WORKFLOW)
        pattern = rf"(?ms)^  {re.escape(name)}:\n.*?(?=^  [a-zA-Z0-9_-]+:\n|\Z)"
        text, count = re.subn(pattern, "", text, count=1)
        if count != 1:
            raise AssertionError(f"job missing: {name}")
        self.write(SECURITY_WORKFLOW, text)


class M006Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.addCleanup(self._temp.cleanup)
        self.temp = Path(self._temp.name)

    def box(self) -> Sandbox:
        return Sandbox(self.temp)

    def assert_rejected(self, box: Sandbox, needle: str, script: Path = VALIDATOR) -> None:
        result = run(script, box.root)
        output = result.stdout + result.stderr
        self.assertNotEqual(result.returncode, 0, output)
        self.assertIn(needle, output)

    def assert_accepted(self, box: Sandbox, script: Path = VALIDATOR) -> None:
        result = run(script, box.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def future_m007(self) -> Sandbox:
        box = self.box()
        box.set_status("M-006", "DONE")
        box.set_status("M-007", "REVIEW")
        box.point_to("M-007", "REVIEW")
        return box

    # Dependency/harvest and build-script reconciliation.

    def test_real_repository_and_direct_approved_coordinates_pass(self) -> None:
        result = run(VALIDATOR, REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("external_direct_dependencies: 4", result.stdout)

    def test_unknown_external_direct_dependency_fails(self) -> None:
        box = self.box()
        package = json.loads(box.read("package.json"))
        package["dependencies"] = {"left-pad": "1.3.0"}
        box.write("package.json", json.dumps(package, indent=2) + "\n")
        self.assert_rejected(box, "unregistered external direct dependency")

    def test_dependency_mapped_to_unknown_harvest_id_fails(self) -> None:
        box = self.box()
        box.patch(REGISTRY, "harvest_id: H-002\n    approved_usage: development", "harvest_id: H-999\n    approved_usage: development")
        self.assert_rejected(box, "unknown harvest ID")

    def test_duplicate_package_coordinate_fails(self) -> None:
        box = self.box()
        box.patch(
            REGISTRY,
            "  source: https://github.com/vercel/turborepo\n  package_coordinates:",
            "  source: https://github.com/vercel/turborepo\n  package_coordinates:\n  - ecosystem: npm\n    name: typescript\n    harvest_id: H-004\n    approved_usage: development",
        )
        self.assert_rejected(box, "Duplicate package coordinate")

    def test_historical_m005_snapshot_rejects_allow_builds(self) -> None:
        box = self.box()
        box.set_status("M-005", "REVIEW")
        box.set_status("M-006", "LOCKED")
        box.point_to("M-005", "REVIEW")
        box.add_approved_allow_build()
        self.assert_rejected(box, "M-005 active snapshot forbids allowBuilds", M005_VALIDATOR)

    def test_durable_approved_allow_builds_passes_both_retained_gates(self) -> None:
        box = self.box()
        box.add_approved_allow_build()
        self.assert_accepted(box)
        self.assert_accepted(box, M005_VALIDATOR)

    def test_dependency_version_drift_invalidates_stale_build_approval(self) -> None:
        box = self.box()
        box.add_approved_allow_build()
        box.patch(
            "packages/contracts/package.json",
            '"typebox": "1.3.6"',
            '"typebox": "1.3.7"',
        )
        self.assert_rejected(box, "stale install/build approval")
        self.assert_rejected(box, "stale approval version", M005_VALIDATOR)

    def test_durable_unapproved_allow_builds_fails(self) -> None:
        box = self.box()
        box.write("pnpm-workspace.yaml", box.read("pnpm-workspace.yaml") + "allowBuilds:\n  typebox: true\n")
        self.assert_rejected(box, "lacks exact harvest-side approval")
        self.assert_rejected(box, "lacks matching harvest-side approval", M005_VALIDATOR)

    def test_dangerously_allow_all_builds_fails(self) -> None:
        box = self.box()
        box.write("pnpm-workspace.yaml", box.read("pnpm-workspace.yaml") + "dangerouslyAllowAllBuilds: true\n")
        self.assert_rejected(box, "dangerouslyAllowAllBuilds is permanently forbidden")
        self.assert_rejected(box, "dangerouslyAllowAllBuilds is permanently forbidden", M005_VALIDATOR)

    # Workflow/action hardening.

    def test_floating_action_tag_fails(self) -> None:
        box = self.box()
        box.patch(SECURITY_WORKFLOW, f"actions/checkout@{CHECKOUT_SHA}", "actions/checkout@v7")
        self.assert_rejected(box, "full 40-hex commit SHA")

    def test_short_action_sha_fails(self) -> None:
        box = self.box()
        box.patch(SECURITY_WORKFLOW, f"actions/checkout@{CHECKOUT_SHA}", "actions/checkout@3d3c42e")
        self.assert_rejected(box, "full 40-hex commit SHA")

    def test_unapproved_third_party_action_fails(self) -> None:
        box = self.box()
        box.patch(SECURITY_WORKFLOW, f"actions/checkout@{CHECKOUT_SHA}", "vendor/scanner@" + "a" * 40)
        self.assert_rejected(box, "absent from the action lock")

    def test_workflow_write_permission_fails(self) -> None:
        box = self.box()
        box.patch(SECURITY_WORKFLOW, "  contents: read", "  contents: write")
        self.assert_rejected(box, "permissions")

    def test_missing_timeout_fails(self) -> None:
        box = self.box()
        box.patch(SECURITY_WORKFLOW, "    timeout-minutes: 10\n    steps:", "    steps:")
        self.assert_rejected(box, "lacks finite timeout-minutes")

    def test_pull_request_target_fails(self) -> None:
        box = self.box()
        box.patch(SECURITY_WORKFLOW, "  pull_request:", "  pull_request_target:")
        self.assert_rejected(box, "pull_request_target")

    def test_security_workflow_missing_gitleaks_fixture_smoke_fails(self) -> None:
        box = self.box()
        box.patch(
            SECURITY_WORKFLOW,
            "      - name: Test exact Gitleaks binary with positive and negative fixtures\n"
            "        shell: bash\n        run: scripts/security/test-gitleaks.sh\n",
            "",
        )
        self.assert_rejected(box, "scripts/security/test-gitleaks.sh")

    def test_security_workflow_missing_scanner_job_fails(self) -> None:
        box = self.box()
        box.remove_job("vulnerabilities")
        self.assert_rejected(box, "missing required scanner job")

    def test_aggregate_gate_missing_fails(self) -> None:
        box = self.box()
        box.remove_job("security-gate")
        self.assert_rejected(box, "missing required scanner job")

    def test_aggregate_gate_fail_open_fails(self) -> None:
        box = self.box()
        box.patch(
            SECURITY_WORKFLOW,
            '          test "${{ needs.secrets.result }}" = "success"\n',
            "",
        )
        self.assert_rejected(box, "does not fail closed on secrets")

    # Tool locks and local SAST configuration.

    def test_trivy_vulnerability_wrapper_requires_dev_dependencies(self) -> None:
        box = self.box()
        box.patch("scripts/security/run-trivy.sh", "--include-dev-deps", "")
        self.assert_rejected(
            box,
            "scripts/security/run-trivy.sh missing required policy argument '--include-dev-deps'",
        )

    def test_cyclonedx_wrapper_requires_dev_dependencies(self) -> None:
        box = self.box()
        box.patch(
            "scripts/security/generate-sbom.sh",
            " --include-dev-deps --format cyclonedx",
            " --format cyclonedx",
        )
        self.assert_rejected(
            box,
            "scripts/security/generate-sbom.sh missing required policy argument '--include-dev-deps'",
        )

    def test_malformed_tool_digest_fails(self) -> None:
        box = self.box()
        lock = json.loads(box.read("security/ci-toolchain.lock.json"))
        lock["tools"]["semgrep"]["immutable_container_digest"] = "sha256:1234"
        box.write("security/ci-toolchain.lock.json", json.dumps(lock, indent=2) + "\n")
        self.assert_rejected(box, "immutable container digest is malformed")

    def test_wrong_scanner_version_fails(self) -> None:
        box = self.box()
        lock = json.loads(box.read("security/ci-toolchain.lock.json"))
        lock["tools"]["gitleaks"]["version"] = "8.30.0"
        box.write("security/ci-toolchain.lock.json", json.dumps(lock, indent=2) + "\n")
        self.assert_rejected(box, "version disagrees with harvest registry")

    def test_active_snapshot_rejects_stale_trivy_0720(self) -> None:
        box = self.box()
        box.patch(
            REGISTRY,
            "  name: Trivy\n  version: 0.74.0",
            "  name: Trivy\n  version: 0.72.0",
        )
        lock = json.loads(box.read("security/ci-toolchain.lock.json"))
        trivy = lock["tools"]["trivy"]
        trivy.update(
            {
                "version": "0.72.0",
                "distribution_coordinate": "https://github.com/aquasecurity/trivy/releases/download/v0.72.0/trivy_0.72.0_Linux-64bit.tar.gz",
                "immutable_sha256": "bbb64b9695866ce4a7a8f5c9592002c5961cab378577fa3f8a040df362b9b2ea",
                "official_checksum_manifest": "https://github.com/aquasecurity/trivy/releases/download/v0.72.0/trivy_0.72.0_checksums.txt",
                "checksum_manifest_sha256": "ebe9d19a774b950e240b1017a038e9b5a002ea068e02023369ff6d241c10c580",
                "sigstore_bundle_coordinate": "https://github.com/aquasecurity/trivy/releases/download/v0.72.0/trivy_0.72.0_Linux-64bit.tar.gz.sigstore.json",
                "sigstore_bundle_sha256": "fccbe7d4877af44f27e205528626dfeb3ff6efac57c22061f1fccb59e8a80007",
            }
        )
        box.write("security/ci-toolchain.lock.json", json.dumps(lock, indent=2) + "\n")
        self.assert_rejected(box, "M-006 active trivy must remain H-030@0.74.0")

    def test_active_trivy_provenance_digest_drift_fails(self) -> None:
        box = self.box()
        lock = json.loads(box.read("security/ci-toolchain.lock.json"))
        lock["tools"]["trivy"]["sigstore_bundle_sha256"] = "a" * 64
        box.write("security/ci-toolchain.lock.json", json.dumps(lock, indent=2) + "\n")
        self.assert_rejected(box, "M-006 active Trivy provenance sigstore_bundle_sha256")

    def test_remote_semgrep_config_fails(self) -> None:
        box = self.box()
        box.write("security/semgrep.yml", "config: p/python\n" + box.read("security/semgrep.yml"))
        self.assert_rejected(box, "remote Semgrep config is forbidden")

    def test_local_semgrep_config_and_fixtures_pass(self) -> None:
        self.assert_accepted(self.box())

    def test_durable_registered_additional_workflow_and_action_pass(self) -> None:
        box = self.future_m007()
        lock = json.loads(box.read("security/ci-toolchain.lock.json"))
        action = "example/security-audit"
        pin = "a" * 40
        lock["github_actions"][action] = {
            "version": "1.2.3",
            "commit_sha": pin,
            "official_upstream_source": f"https://github.com/{action}",
            "rationale": "Synthetic M-007 durable workflow registry fixture.",
        }
        rel = ".github/workflows/future-audit.yml"
        lock["workflow_policy"]["additional_workflows"][rel] = {
            "name": "Future Audit",
            "required_jobs": ["audit"],
            "permissions": {"issues": "read"},
            "allowed_secrets": [],
            "allow_repository_write": False,
            "allow_continue_on_error": False,
            "allow_package_manager_cache": False,
            "rationale": "Synthetic future workflow proves lock-driven durable expansion.",
        }
        box.write("security/ci-toolchain.lock.json", json.dumps(lock, indent=2) + "\n")
        box.write(
            rel,
            "name: Future Audit\n\non:\n  workflow_dispatch:\n\npermissions:\n"
            "  issues: read\n\njobs:\n  audit:\n    runs-on: ubuntu-latest\n"
            "    timeout-minutes: 5\n    steps:\n"
            f"      - uses: {action}@{pin} # v1.2.3\n",
        )
        self.assert_accepted(box)

    def test_durable_unregistered_additional_workflow_fails(self) -> None:
        box = self.future_m007()
        box.write(
            ".github/workflows/unregistered.yml",
            "name: Unregistered\n\non:\n  workflow_dispatch:\npermissions:\n  contents: read\n"
            "jobs:\n  check:\n    runs-on: ubuntu-latest\n    timeout-minutes: 5\n"
            "    steps:\n      - run: echo check\n",
        )
        self.assert_rejected(box, "unregistered")

    def test_durable_scanner_upgrade_is_harvest_lock_driven(self) -> None:
        box = self.future_m007()
        box.patch(
            REGISTRY,
            "  name: Gitleaks\n  version: 8.30.1",
            "  name: Gitleaks\n  version: 8.30.2",
        )
        lock = json.loads(box.read("security/ci-toolchain.lock.json"))
        tool = lock["tools"]["gitleaks"]
        tool["version"] = "8.30.2"
        tool["distribution_coordinate"] = tool["distribution_coordinate"].replace("8.30.1", "8.30.2")
        tool["immutable_sha256"] = "b" * 64
        box.write("security/ci-toolchain.lock.json", json.dumps(lock, indent=2) + "\n")
        self.assert_accepted(box)

    def test_durable_semgrep_rule_expansion_is_lock_driven(self) -> None:
        box = self.future_m007()
        lock = json.loads(box.read("security/ci-toolchain.lock.json"))
        lock["semgrep_policy"]["rules"].append(
            {"id": "vibeflow.python.dynamic-compile-exec", "severity": "ERROR"}
        )
        box.write("security/ci-toolchain.lock.json", json.dumps(lock, indent=2) + "\n")
        box.write(
            "security/semgrep.yml",
            box.read("security/semgrep.yml")
            + "\n  - id: vibeflow.python.dynamic-compile-exec\n"
            "    message: Dynamic compile in exec mode can enable code injection.\n"
            "    severity: ERROR\n    languages: [python]\n"
            "    pattern: compile(..., \"exec\")\n"
            "    metadata:\n      confidence: HIGH\n      category: security\n",
        )
        box.write(
            "tests/security/fixtures/semgrep/positive/dangerous.py",
            box.read("tests/security/fixtures/semgrep/positive/dangerous.py")
            + "compile(user_input, \"fixture\", \"exec\")\n",
        )
        self.assert_accepted(box)

    # Progression-aware retained validator.

    def test_m005_done_m006_review_valid(self) -> None:
        self.assert_accepted(self.box())

    def test_m006_active_while_m005_not_done_fails(self) -> None:
        box = self.box()
        box.set_status("M-005", "REVIEW")
        self.assert_rejected(box, "M-005 must be DONE")

    def test_m006_review_with_m007_active_fails(self) -> None:
        box = self.box()
        box.set_status("M-007", "REVIEW")
        self.assert_rejected(box, "M-007 must remain LOCKED")

    def test_future_accepted_m006_with_m007_active_passes(self) -> None:
        box = self.future_m007()
        self.assert_accepted(box)
        result = run(VALIDATOR, box.root)
        self.assertIn("mode: durable", result.stdout)

    def test_durable_rel_capability_progression_passes(self) -> None:
        box = self.future_m007()
        box.set_capability_status("VF-REL-002", "VERIFIED")
        self.assert_accepted(box)

    def test_durable_rel_capability_regression_fails(self) -> None:
        box = self.future_m007()
        box.set_capability_status("VF-REL-002", "IN_PROGRESS")
        self.assert_rejected(box, "regressed below M-006 baseline")

    def test_real_m007_env_progression_passes_durable_validator(self) -> None:
        box = self.future_m007()
        box.set_capability_status("VF-ENV-001", "IN_PROGRESS")
        self.assert_accepted(box)
        master = run(MASTER_VALIDATOR, box.root)
        self.assertEqual(master.returncode, 0, master.stdout + master.stderr)

    def test_m006_active_snapshot_rejects_env_progression(self) -> None:
        box = self.box()
        box.set_capability_status("VF-ENV-001", "IN_PROGRESS")
        self.assert_rejected(box, "M-006 active snapshot requires VF-ENV-001")

    def test_dag_register_desync_fails(self) -> None:
        box = self.box()
        box.set_status("M-006", "DONE", register=False)
        self.assert_rejected(box, "status disagrees between DAG")

    def test_pointer_desync_fails(self) -> None:
        box = self.box()
        box.write("README.md", "# VibeFlow\n\nThe active mission is M-005.\n")
        self.assert_rejected(box, "does not name active mission M-006")


if __name__ == "__main__":
    unittest.main(verbosity=2)
