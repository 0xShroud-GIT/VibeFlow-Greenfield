#!/usr/bin/env python3
"""Deterministic mutation suite for M-007 local development environment gates.

Proves failure for every required adversarial mutation and includes positive
passes for both the active M-007 snapshot and a synthetic later-mission
durable extension, so the retained validator is demonstrably
forward-compatible.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/validate-m007-local-dev.py"
MASTER_VALIDATOR = REPO_ROOT / "scripts/validate-master-contracts.py"
M006_VALIDATOR = REPO_ROOT / "scripts/validate-m006-security-gates.py"
IGNORE = shutil.ignore_patterns(
    ".git", "node_modules", "dist", ".turbo", ".cache", ".vite",
    "__pycache__", ".pytest_cache", ".next", ".expo",
)
DAG = "master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml"
REGISTER = "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv"
SUMS = "master-build-system/SHA256SUMS.txt"
LEDGER_CSV = "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv"
LEDGER_YAML = "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml"
DEVCONTAINER = ".devcontainer/devcontainer.json"
POLICY = "infrastructure/dev/dev-environment-policy.json"

FEATURE_REF = "ghcr.io/devcontainers/features/python@sha256:fbcad6955caeecc5ad3f7886baf652e25cba5225a6c4c2287c536de2e5607511"
BASE_IMAGE = "docker.io/library/node:24.19.0-trixie-slim@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d"
DOCKERFILE = ".devcontainer/Dockerfile"
GIT_FEATURE_REF = "ghcr.io/devcontainers/features/git@sha256:fd75977de13a9979000e0e78baf949adb0ca71d2398995fa22e0a36d7e7e7fe2"
NODE_FEATURE_REF = "ghcr.io/devcontainers/features/node@sha256:586c9a6f7dd40bd3ba2cd41e7f2f88dcc31fbe5d1442afcbf07ffbc66b686857"
NODE_MODULES_VOLUME = "source=vibeflow-node-modules,target=${containerWorkspaceFolder}/node_modules,type=volume"
NODE_MODULES_INIT = (
    "docker run --rm -u 0 -v vibeflow-node-modules:/data "
    "docker.io/library/node:24.19.0-trixie-slim@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d "
    "chown $(id -u):$(id -g) /data"
)


def run(script: Path, root: Path, *extra: str) -> subprocess.CompletedProcess[str]:
    argv = [sys.executable, str(script), "--root", str(root), *extra]
    return subprocess.run(
        argv, capture_output=True, text=True, timeout=240, check=False
    )


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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

    def resync_hash(self, rel: str) -> None:
        """Refresh the SHA256SUMS.txt line for a changed master-build-system file."""
        relative = rel[len("master-build-system/"):]
        sums = self.read(SUMS)
        lines = sums.splitlines(keepends=True)
        digest = sha256_of(self.path(rel))
        found = False
        for index, line in enumerate(lines):
            if line.rstrip("\n").endswith("  " + relative):
                lines[index] = f"{digest}  {relative}\n"
                found = True
                break
        if not found:
            raise AssertionError(f"no SHA256SUMS entry for {relative}")
        self.write(SUMS, "".join(lines))

    def set_status(self, mission: str, status: str, *, register: bool = True) -> None:
        text = self.read(DAG)
        pattern = rf"(?ms)(^- mission_id: {mission}\n.*?^  status: )[A-Z_]+"
        text, count = re.subn(pattern, rf"\g<1>{status}", text, count=1)
        if count != 1:
            raise AssertionError(f"mission missing: {mission}")
        self.write(DAG, text)
        if register:
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
        self.resync_hash(DAG)
        self.resync_hash(REGISTER)

    def set_capability_status(self, vf_id: str, status: str) -> None:
        with self.path(LEDGER_CSV).open(newline="", encoding="utf-8") as handle:
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
        self.write(LEDGER_CSV, output.getvalue())

        text = self.read(LEDGER_YAML)
        pattern = rf"(?ms)(^- vf_id: {re.escape(vf_id)}\n.*?^  status: )[A-Z_]+"
        text, count = re.subn(pattern, rf"\g<1>{status}", text, count=1)
        if count != 1:
            raise AssertionError(f"capability missing: {vf_id}")
        self.write(LEDGER_YAML, text)
        self.resync_hash(LEDGER_CSV)
        self.resync_hash(LEDGER_YAML)

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

    def set_devcontainer(self, **overrides: object) -> None:
        config = json.loads(self.read(DEVCONTAINER))
        for key, value in overrides.items():
            config[key] = value
        self.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")


class M007Tests(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.temp = Path(self._tmp.name)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def box(self) -> Sandbox:
        """Historical M-007 REVIEW snapshot. Live repo may already be durable."""
        sandbox = Sandbox(self.temp)
        sandbox.set_status("M-007", "REVIEW")
        sandbox.set_status("M-008", "LOCKED")
        sandbox.point_to("M-007", "REVIEW")
        return sandbox

    def assert_rejected(self, box: Sandbox, needle: str, *, mode: str | None = None) -> None:
        extra = (f"--mode", mode) if mode else ()
        result = run(VALIDATOR, box.root, *extra)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(needle, result.stdout + result.stderr)

    def assert_accepted(self, box: Sandbox, *, mode: str | None = None) -> None:
        extra = (f"--mode", mode) if mode else ()
        result = run(VALIDATOR, box.root, *extra)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    # ---------- positive: real repository (active M-007 snapshot) ----------
    def test_real_repository_passes_durable_mode(self) -> None:
        result = run(VALIDATOR, REPO_ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mode: durable", result.stdout)
        self.assertIn("capabilities: 405", result.stdout)
        self.assertIn("devcontainer_features: 2", result.stdout)

    def test_historical_m007_review_snapshot_passes_active_mode(self) -> None:
        box = self.box()
        self.assert_accepted(box, mode="active")
        result = run(VALIDATOR, box.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("mode: active", result.stdout)

    # ---------- image provenance (official digest-pinned slim image, no Dockerfile) ----------
    def test_floating_image_reference_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(image="docker.io/library/node:24.19.0-trixie-slim")
        self.assert_rejected(box, "image must be a digest-pinned reference")

    def test_malformed_digest_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(image="docker.io/library/node:24.19.0-trixie-slim@sha256:zzz")
        self.assert_rejected(box, "image must be a digest-pinned reference")

    def test_image_digest_lock_mismatch_fails(self) -> None:
        box = self.box()
        other = "sha256:" + "0" * 64
        box.set_devcontainer(image=f"docker.io/library/node:24.19.0-trixie-slim@{other}")
        self.assert_rejected(box, "image digest")

    def test_image_coordinate_differs_from_locked_provenance_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(image="docker.io/library/node:24.19.0-trixie@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d")
        self.assert_rejected(box, "image semantic coordinate")

    def test_active_forbids_dockerfile(self) -> None:
        box = self.box()
        box.write(DOCKERFILE, "FROM docker.io/library/node:24.19.0-trixie-slim@sha256:0711b541c1c33a8a530ac4f0d391baa9a15b3d804695b1b24a47daa5fb60e74d\n")
        self.assert_rejected(box, "active M-007 forbids a .devcontainer/Dockerfile")

    def test_dockerfile_key_forbidden_in_active(self) -> None:
        box = self.box()
        box.set_devcontainer(dockerFile="Dockerfile")
        self.assert_rejected(box, "active M-007 uses the image key, not dockerFile/compose")

    # ---------- git feature registration / exactness (Round 5) ----------
    def test_floating_git_feature_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"]["ghcr.io/devcontainers/features/git:1"] = {"version": "os-provided", "ppa": False}
        del config["features"][GIT_FEATURE_REF]
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "must be digest-pinned")

    def test_wrong_git_feature_digest_fails(self) -> None:
        box = self.box()
        wrong = "ghcr.io/devcontainers/features/git@sha256:" + "a" * 64
        config = json.loads(box.read(DEVCONTAINER))
        config["features"][wrong] = {"version": "os-provided", "ppa": False}
        del config["features"][GIT_FEATURE_REF]
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "is not registered in the dev-environment policy lock")

    def test_unregistered_git_feature_fails(self) -> None:
        box = self.box()
        policy = json.loads(box.read(POLICY))
        policy["features"] = [f for f in policy["features"] if f.get("digest_reference") != GIT_FEATURE_REF]
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "policy lock must register both python and git features")

    def test_changed_git_feature_options_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"][GIT_FEATURE_REF] = {"version": "os-provided", "ppa": True}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "options must exactly equal the locked registration")

    def test_removed_required_git_feature_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        del config["features"][GIT_FEATURE_REF]
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "active feature set must be exactly python+git")

    def test_unauthorized_additional_feature_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"][NODE_FEATURE_REF] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "active feature set must be exactly python+git")

    def test_real_repo_has_python_and_git_features(self) -> None:
        config = json.loads(Path(REPO_ROOT, DEVCONTAINER).read_text(encoding="utf-8"))
        self.assertIn(GIT_FEATURE_REF, config["features"])
        self.assertIn(FEATURE_REF, config["features"])

    def test_policy_lock_digest_drift_fails(self) -> None:
        box = self.box()
        policy = json.loads(box.read(POLICY))
        policy["base_image"]["digest"] = "sha256:" + "1" * 64
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "policy base image digest")

    def test_missing_devcontainer_fails(self) -> None:
        box = self.box()
        (box.path(DEVCONTAINER)).unlink()
        self.assert_rejected(box, "missing .devcontainer/devcontainer.json")

    def test_missing_policy_lock_fails(self) -> None:
        box = self.box()
        (box.path(POLICY)).unlink()
        self.assert_rejected(box, "missing infrastructure/dev/dev-environment-policy.json")

    # ---------- toolchain parity ----------
    def test_wrong_node_version_fails(self) -> None:
        box = self.box()
        box.write(".nvmrc", "24.19.1\n")
        self.assert_rejected(box, ".nvmrc must pin 24.19.0")

    def test_wrong_pnpm_version_fails(self) -> None:
        box = self.box()
        package = json.loads(box.read("package.json"))
        package["packageManager"] = "pnpm@11.3.0"
        box.write("package.json", json.dumps(package, indent=2) + "\n")
        self.assert_rejected(box, "packageManager must remain pnpm@11.4.0")

    def test_policy_toolchain_drift_fails(self) -> None:
        box = self.box()
        policy = json.loads(box.read(POLICY))
        policy["toolchain"]["node"] = "24.18.0"
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "policy toolchain node must be 24.19.0")

    # ---------- frozen-lockfile bootstrap ----------
    def test_missing_frozen_lockfile_bootstrap_fails(self) -> None:
        box = self.box()
        text = box.read("scripts/dev-bootstrap.py").replace("--frozen-lockfile", "")
        box.write("scripts/dev-bootstrap.py", text)
        self.assert_rejected(box, "must run pnpm install --frozen-lockfile")

    def test_lockfile_bypass_bootstrap_fails(self) -> None:
        box = self.box()
        text = box.read("scripts/dev-bootstrap.py").replace("--frozen-lockfile", "--no-frozen-lockfile")
        box.write("scripts/dev-bootstrap.py", text)
        self.assert_rejected(box, "must not bypass the lockfile")

    def test_shell_true_subprocess_fails(self) -> None:
        box = self.box()
        text = box.read("scripts/dev-bootstrap.py") + "\nsubprocess.run('pnpm install', shell=True)\n"
        box.write("scripts/dev-bootstrap.py", text)
        self.assert_rejected(box, "must not use subprocess shell=True")

    # ---------- security posture ----------
    def test_root_dev_user_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(remoteUser="root")
        self.assert_rejected(box, "active M-007 requires remoteUser == 'node'")

    def test_root_container_user_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(containerUser="root")
        self.assert_rejected(box, "active M-007 requires containerUser == 'node'")

    def test_missing_remote_user_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        del config["remoteUser"]
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "active M-007 requires remoteUser == 'node'")

    def test_missing_container_user_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        del config["containerUser"]
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "active M-007 requires containerUser == 'node'")

    def test_wrong_non_root_user_fails_active(self) -> None:
        box = self.box()
        box.set_devcontainer(remoteUser="node-dev")
        self.assert_rejected(box, "active M-007 requires remoteUser == 'node'")

    def test_privileged_true_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(privileged=True)
        self.assert_rejected(box, "privileged: true is permanently forbidden")

    def test_host_network_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(runArgs=["--network=host"])
        self.assert_rejected(box, "host/network override")

    def test_docker_socket_mount_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(mounts=["source=/var/run/docker.sock,target=/var/run/docker.sock,type=bind"])
        self.assert_rejected(box, "docker socket mount")

    def test_docker_in_docker_unregistered_feature_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"]["ghcr.io/devcontainers/features/docker-in-docker@sha256:" + "a" * 64] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "not registered in the dev-environment policy lock")

    def test_feature_without_digest_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"]["ghcr.io/devcontainers/features/python:1"] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "must be digest-pinned")

    def test_raw_secret_in_container_env_fails(self) -> None:
        box = self.box()
        raw = "sk-" + ("A1b2" * 10)
        box.set_devcontainer(containerEnv={"API_KEY": raw})
        self.assert_rejected(box, "raw secret material")

    def test_raw_secret_in_committed_env_example_fails(self) -> None:
        box = self.box()
        raw = "ghp_" + ("Ab12" * 9)
        box.write(".env.example", f"GITHUB_TOKEN={raw}\n")
        self.assert_rejected(box, "committed env example")

    def test_forwarded_port_in_active_snapshot_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(forwardPorts=[8080])
        self.assert_rejected(box, "forbids forwarded ports")

    def test_product_service_compose_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(dockerComposeFile="docker-compose.yml")
        box.write(".devcontainer/docker-compose.yml", "services:\n  postgres:\n    image: postgres:16\n")
        self.assert_rejected(box, "forbids dockerComposeFile")

    def test_host_credential_mount_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(mounts=["source=${localEnv:HOME}/.ssh,target=/home/node/.ssh,type=bind"])
        self.assert_rejected(box, "host credential mounts")

    # ---------- mission / ledger synchronization ----------
    def test_m006_not_done_fails(self) -> None:
        box = self.box()
        box.set_status("M-006", "REVIEW")
        self.assert_rejected(box, "M-006 must be DONE")

    def test_m007_self_marked_done_fails_active(self) -> None:
        box = self.box()
        box.set_status("M-007", "DONE")
        self.assert_rejected(box, "M-007 must be READY/IN_PROGRESS/REVIEW in active mode", mode="active")

    def test_m007_self_marked_done_without_successor_fails_durable(self) -> None:
        box = self.box()
        box.set_status("M-007", "DONE")
        self.assert_rejected(box, "accepted M-007 requires one active later mission")

    def test_m008_unlocked_early_fails(self) -> None:
        box = self.box()
        box.set_status("M-008", "REVIEW")
        self.assert_rejected(box, "M-008 must remain LOCKED")
        master = run(MASTER_VALIDATOR, box.root)
        self.assertNotEqual(master.returncode, 0, master.stdout + master.stderr)

    def test_dag_register_desync_fails(self) -> None:
        box = self.box()
        box.set_status("M-007", "DONE", register=False)
        self.assert_rejected(box, "status disagrees between DAG and register")

    def test_master_hash_drift_fails(self) -> None:
        box = self.box()
        box.write(DAG, box.read(DAG) + "\n# drift\n")
        self.assert_rejected(box, "master pack hash drift")

    # ---------- capability ledger ----------
    def test_vf_env_005_overclaimed_implemented_fails(self) -> None:
        box = self.box()
        box.set_capability_status("VF-ENV-005", "IMPLEMENTED")
        self.assert_rejected(box, "active M-007 requires VF-ENV-005=IN_PROGRESS")

    def test_vf_env_005_overclaimed_verified_fails(self) -> None:
        box = self.box()
        box.set_capability_status("VF-ENV-005", "VERIFIED")
        self.assert_rejected(box, "active M-007 requires VF-ENV-005=IN_PROGRESS")

    def test_unrelated_env_capability_mutation_fails(self) -> None:
        box = self.box()
        box.set_capability_status("VF-ENV-001", "IN_PROGRESS")
        self.assert_rejected(box, "active M-007 requires VF-ENV-001=NOT_STARTED")

    def test_unrelated_rel_capability_mutation_fails(self) -> None:
        box = self.box()
        box.set_capability_status("VF-REL-007", "IN_PROGRESS")
        self.assert_rejected(box, "active M-007 requires VF-REL-007=NOT_STARTED")

    def test_unrelated_product_capability_mutation_fails(self) -> None:
        box = self.box()
        box.set_capability_status("VF-DEP-001", "IN_PROGRESS")
        self.assert_rejected(box, "active M-007 requires VF-DEP-001=NOT_STARTED")

    # ---------- positive: synthetic later-mission durable extension ----------
    def future_later_mission(self) -> Sandbox:
        box = self.box()
        box.set_status("M-007", "DONE")
        box.set_status("M-008", "REVIEW")
        box.point_to("M-008", "REVIEW")
        return box

    def test_durable_extension_passes_durable_mode(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(forwardPorts=[8080], containerEnv={"VIBEFLOW_DEV_MODE": "integration"})
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-008",
                "rationale": "Synthetic later-mission extension proof for M-007 durable mode.",
                "declared": {
                    "forwarded_ports": [8080],
                    "containerEnv": {"VIBEFLOW_DEV_MODE": "integration"},
                },
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_accepted(box)
        # The retained M-006 validator also accepts the synthetic progression.
        result = run(M006_VALIDATOR, box.root)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_active_snapshot_rejects_durable_extensions(self) -> None:
        box = self.box()
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-008",
                "rationale": "Extensions must not exist while M-007 is active.",
                "declared": {"forwarded_ports": [8080]},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "active M-007 snapshot requires zero durable extensions")

    def test_durable_extension_rejected_by_active_snapshot(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(forwardPorts=[8080])
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-008",
                "rationale": "Synthetic extension must still fail the active snapshot.",
                "declared": {"forwarded_ports": [8080]},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "active M-007 forbids forwarded ports", mode="active")

    def test_durable_undeclared_extension_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(forwardPorts=[8080])
        self.assert_rejected(box, "durable forwarded ports require a declaration owned by the active later mission")

    def test_durable_extension_owned_by_other_mission_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(forwardPorts=[8080])
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-009",
                "rationale": "Wrong owner: must not authorize the change.",
                "declared": {"forwarded_ports": [8080]},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "durable forwarded ports require a declaration owned by the active later mission")

    def test_durable_user_change_requires_owning_declaration(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(remoteUser="node-dev")
        self.assert_rejected(box, "requires a declaration owned by the active later mission")

    def test_durable_user_change_owned_declaration_passes(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(remoteUser="node-dev")
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-008",
                "rationale": "Owning later mission changes the dev user to another non-root user.",
                "declared": {"users": {"remoteUser": "node-dev", "containerUser": "node"}},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_accepted(box)

    def test_durable_docker_socket_declared_still_banned(self) -> None:
        box = self.future_later_mission()
        mount = "source=/var/run/docker.sock,target=/var/run/docker.sock,type=bind"
        box.set_devcontainer(mounts=[mount])
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {"mission_id": "M-008", "rationale": "Malicious: must still fail.", "declared": {"mounts": [mount]}}
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "docker socket mount is permanently forbidden")

    def test_durable_privileged_still_permanently_banned(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(privileged=True)
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {"mission_id": "M-008", "rationale": "Malicious: must still fail.", "declared": {"privileged": True}}
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "privileged: true is permanently forbidden")

    def test_durable_rel_baseline_regression_fails(self) -> None:
        box = self.future_later_mission()
        box.set_capability_status("VF-REL-002", "IN_PROGRESS")
        self.assert_rejected(box, "regressed below M-006 baseline")

    def test_durable_env_005_regression_fails(self) -> None:
        box = self.future_later_mission()
        box.set_capability_status("VF-ENV-005", "NOT_STARTED")
        self.assert_rejected(box, "VF-ENV-005 regressed below IN_PROGRESS")

    def test_durable_later_env_progression_allowed(self) -> None:
        box = self.future_later_mission()
        box.set_capability_status("VF-ENV-001", "IN_PROGRESS")
        self.assert_accepted(box)

    # ---------- Blocker 1: canonical node_modules volume (CI bootstrap) ----------
    def test_active_requires_exact_node_modules_volume(self) -> None:
        box = self.box()
        box.set_devcontainer(mounts=[])
        self.assert_rejected(box, "active M-007 requires exactly the node_modules volume")

    def test_active_extra_mount_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(mounts=[NODE_MODULES_VOLUME, "source=/tmp/x,target=/tmp/x,type=bind"])
        self.assert_rejected(box, "active M-007 requires exactly the node_modules volume")

    def test_real_repo_has_canonical_node_modules_volume(self) -> None:
        config = json.loads(Path(REPO_ROOT, DEVCONTAINER).read_text(encoding="utf-8"))
        self.assertEqual(config["mounts"], [NODE_MODULES_VOLUME])

    # ---------- Blocker 2: wrappers executable ----------
    def test_wrapper_not_executable_fails(self) -> None:
        box = self.box()
        for rel in ("scripts/security/scan-dev-image.sh", "scripts/security/generate-dev-image-sbom.sh"):
            box.path(rel).chmod(0o644)
        self.assert_rejected(box, "must be executable")

    def test_wrappers_executable_on_real_repo(self) -> None:
        for rel in ("scripts/security/scan-dev-image.sh", "scripts/security/generate-dev-image-sbom.sh"):
            self.assertTrue(os.access(Path(REPO_ROOT, rel), os.X_OK), rel)

    # ---------- Blocker 3: durable feature extensions ----------
    def test_active_snapshot_extra_feature_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"][NODE_FEATURE_REF] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "active feature set must be exactly python+git")

    def test_durable_extra_feature_no_declaration_fails(self) -> None:
        box = self.future_later_mission()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"][NODE_FEATURE_REF] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        policy = json.loads(box.read(POLICY))
        policy["features"].append(
            {
                "id": "node",
                "version": "2.1.0",
                "digest_reference": NODE_FEATURE_REF,
                "upstream_source": "https://github.com/devcontainers/features/tree/main/src/node",
                "project_license": "MIT",
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "requires an owning extension from the active or a completed later mission")

    def test_durable_extra_feature_wrong_mission_fails(self) -> None:
        box = self.future_later_mission()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"][NODE_FEATURE_REF] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        policy = json.loads(box.read(POLICY))
        policy["features"].append(
            {
                "id": "node",
                "version": "2.1.0",
                "digest_reference": NODE_FEATURE_REF,
                "upstream_source": "https://github.com/devcontainers/features/tree/main/src/node",
                "project_license": "MIT",
            }
        )
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-009",
                "rationale": "Wrong owner: must not authorize the active mission's new feature.",
                "declared": {"features": [NODE_FEATURE_REF]},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "requires an owning extension from the active or a completed later mission")

    def test_durable_floating_feature_fails(self) -> None:
        box = self.future_later_mission()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"]["ghcr.io/devcontainers/features/node:2"] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "must be digest-pinned")

    def test_durable_feature_not_registered_fails(self) -> None:
        box = self.future_later_mission()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"][NODE_FEATURE_REF] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "is not registered in the dev-environment policy lock")

    def test_durable_extra_feature_owned_passes(self) -> None:
        box = self.future_later_mission()
        config = json.loads(box.read(DEVCONTAINER))
        config["features"][NODE_FEATURE_REF] = {}
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        policy = json.loads(box.read(POLICY))
        policy["features"].append(
            {
                "id": "node",
                "version": "2.1.0",
                "digest_reference": NODE_FEATURE_REF,
                "upstream_source": "https://github.com/devcontainers/features/tree/main/src/node",
                "project_license": "MIT",
            }
        )
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-008",
                "rationale": "Owning later mission adds the node feature for repository tooling.",
                "declared": {"features": [NODE_FEATURE_REF]},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_accepted(box)

    # ---------- Blocker 4: durable runArgs require owning declaration ----------
    def test_durable_undeclared_runargs_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(runArgs=["--env", "FOO=bar"])
        self.assert_rejected(box, "durable runArgs require a declaration owned by the active later mission")

    def test_durable_runargs_wrong_mission_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(runArgs=["--env", "FOO=bar"])
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-009",
                "rationale": "Wrong owner: must not authorize the runArgs.",
                "declared": {"run_args": ["--env", "FOO=bar"]},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "durable runArgs require a declaration owned by the active later mission")

    def test_durable_safe_runargs_owned_passes(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(runArgs=["--env", "FOO=bar"])
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-008",
                "rationale": "Owning later mission sets a benign environment runArg.",
                "declared": {"run_args": ["--env", "FOO=bar"]},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_accepted(box)

    def test_durable_declared_privileged_runargs_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(runArgs=["--privileged"])
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {"mission_id": "M-008", "rationale": "Malicious: must still fail.", "declared": {"run_args": ["--privileged"]}}
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "runArgs --privileged is permanently forbidden")

    def test_durable_declared_host_network_runargs_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(runArgs=["--network=host"])
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {"mission_id": "M-008", "rationale": "Malicious: must still fail.", "declared": {"run_args": ["--network=host"]}}
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "host/network override")

    def test_durable_declared_docker_socket_runargs_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(runArgs=["-v", "/var/run/docker.sock:/var/run/docker.sock"])
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-008",
                "rationale": "Malicious: must still fail.",
                "declared": {"run_args": ["-v", "/var/run/docker.sock:/var/run/docker.sock"]},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "must not mount docker socket")

    # ---------- Blocker 5: durable user fields explicit + non-root ----------
    def test_durable_missing_remote_user_fails(self) -> None:
        box = self.future_later_mission()
        config = json.loads(box.read(DEVCONTAINER))
        del config["remoteUser"]
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "durable remoteUser must be explicitly present and non-root")

    def test_durable_missing_container_user_fails(self) -> None:
        box = self.future_later_mission()
        config = json.loads(box.read(DEVCONTAINER))
        del config["containerUser"]
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "durable containerUser must be explicitly present and non-root")

    def test_durable_null_user_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(remoteUser=None)
        self.assert_rejected(box, "durable remoteUser must be explicitly present and non-root")

    def test_durable_empty_user_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(remoteUser="")
        self.assert_rejected(box, "durable remoteUser must be explicitly present and non-root")

    def test_durable_root_user_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(remoteUser="root")
        self.assert_rejected(box, "durable remoteUser must be explicitly present and non-root")

    def test_durable_uid_zero_user_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(remoteUser="0")
        self.assert_rejected(box, "durable remoteUser must be explicitly present and non-root")

    def test_durable_user_change_wrong_mission_fails(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(remoteUser="node-dev")
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-009",
                "rationale": "Wrong owner: must not authorize the user change.",
                "declared": {"users": {"remoteUser": "node-dev", "containerUser": "node"}},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_rejected(box, "change from 'node' requires a declaration owned by the active later mission")

    def test_durable_both_users_owned_change_passes(self) -> None:
        box = self.future_later_mission()
        box.set_devcontainer(remoteUser="node-dev", containerUser="node-dev")
        policy = json.loads(box.read(POLICY))
        policy["durable_extension_policy"]["extensions"].append(
            {
                "mission_id": "M-008",
                "rationale": "Owning later mission changes both user fields to an explicit non-root user.",
                "declared": {"users": {"remoteUser": "node-dev", "containerUser": "node-dev"}},
            }
        )
        box.write(POLICY, json.dumps(policy, indent=2) + "\n")
        self.assert_accepted(box)


    # ---------- Blocker 1 (continued): canonical initializeCommand ----------
    def test_active_missing_initialize_command_fails(self) -> None:
        box = self.box()
        config = json.loads(box.read(DEVCONTAINER))
        del config["initializeCommand"]
        box.write(DEVCONTAINER, json.dumps(config, indent=2) + "\n")
        self.assert_rejected(box, "active M-007 requires exactly the node_modules initializeCommand")

    def test_active_wrong_initialize_command_fails(self) -> None:
        box = self.box()
        box.set_devcontainer(initializeCommand="echo hi")
        self.assert_rejected(box, "active M-007 requires exactly the node_modules initializeCommand")

    def test_real_repo_has_canonical_initialize_command(self) -> None:
        config = json.loads(Path(REPO_ROOT, DEVCONTAINER).read_text(encoding="utf-8"))
        self.assertEqual(config["initializeCommand"], NODE_MODULES_INIT)



if __name__ == "__main__":
    unittest.main(verbosity=2)
