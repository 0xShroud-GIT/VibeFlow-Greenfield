#!/usr/bin/env python3
"""Validate the complete static M-006 CI/security/dependency policy.

Stdlib-only and network-free. Runtime scanners are separate deterministic
wrappers so `pnpm run check` never downloads a scanner or vulnerability DB.
The gate is retained after M-006 and therefore supports both the historical
M-006 active state and accepted M-006 with a later serial mission active.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[1]
DEPENDENCY_FIELDS = (
    "dependencies",
    "devDependencies",
    "optionalDependencies",
    "peerDependencies",
)
PRODUCTION_FIELDS = {"dependencies", "optionalDependencies", "peerDependencies"}
EXPECTED_TOOLS = {
    "gitleaks": ("H-029", "8.30.1"),
    "trivy": ("H-030", "0.72.0"),
    "osv-scanner": ("H-031", "2.4.0"),
    "semgrep": ("H-032", "1.172.0"),
}
EXPECTED_ACTIONS = {
    "actions/checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",  # v7.0.1
    "actions/setup-node": "820762786026740c76f36085b0efc47a31fe5020",  # v7.0.0
    "actions/upload-artifact": "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a",  # v7.0.1
}
REQUIRED_WORKFLOW_JOBS = (
    "dependency-policy",
    "secrets",
    "vulnerabilities",
    "sast",
    "sbom",
    "security-gate",
)
REQUIRED_SEMGREP_RULES = {
    "vibeflow.python.dynamic-eval",
    "vibeflow.python.dynamic-exec",
    "vibeflow.python.os-system",
    "vibeflow.python.subprocess-shell-true",
    "vibeflow.javascript.dynamic-eval",
    "vibeflow.javascript.child-process-exec",
}
CAPABILITY_EXPECTED = {
    "VF-REL-002": "IMPLEMENTED",
    "VF-REL-003": "IMPLEMENTED",
    "VF-REL-004": "IMPLEMENTED",
    "VF-REL-005": "IN_PROGRESS",
}
IGNORED_PARTS = {
    ".git", "node_modules", "dist", "build", "out", ".turbo", ".cache",
    ".vite", ".next", ".venv", "venv", "__pycache__",
}


def load_module(path: Path, name: str) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Validator:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.errors: list[str] = []
        self.counts: dict[str, int] = {}
        self.master = load_module(root / "scripts/validate-master-contracts.py", "m006_master")
        self.harvest = load_module(root / "scripts/validate-harvest-registry.py", "m006_harvest")
        self.m006_active = True

    def err(self, area: str, message: str) -> None:
        self.errors.append(f"{area}: {message}")

    def read(self, rel: str, area: str) -> str | None:
        path = self.root / rel
        if not path.is_file():
            self.err(area, f"missing {rel}")
            return None
        return path.read_text(encoding="utf-8")

    def read_json(self, rel: str, area: str) -> dict[str, Any] | None:
        text = self.read(rel, area)
        if text is None:
            return None
        try:
            value = json.loads(text)
        except json.JSONDecodeError as exc:
            self.err(area, f"invalid JSON in {rel}: {exc}")
            return None
        if not isinstance(value, dict):
            self.err(area, f"{rel} must contain a JSON object")
            return None
        return value

    def parse_statuses(self) -> tuple[dict[str, str], dict[str, str]]:
        dag_text = self.read("master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml", "mission") or ""
        dag: dict[str, str] = {}
        current: str | None = None
        for line in dag_text.splitlines():
            match = re.match(r"^- mission_id: (M-\d{3})$", line)
            if match:
                current = match.group(1)
            elif current and (match := re.match(r"^  status: ([A-Z_]+)$", line)):
                dag[current] = match.group(1)
                current = None
        register: dict[str, str] = {}
        path = self.root / "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv"
        if path.is_file():
            with path.open(newline="", encoding="utf-8") as handle:
                register = {
                    row["mission_id"]: row["status"] for row in csv.DictReader(handle)
                }
        else:
            self.err("mission", "missing MISSION_REGISTER.csv")
        return dag, register

    def check_mission_progression(self) -> None:
        dag, register = self.parse_statuses()
        for mid in sorted(set(dag) | set(register)):
            if dag.get(mid) != register.get(mid):
                self.err(
                    "mission",
                    f"{mid} status disagrees between DAG ({dag.get(mid)!r}) and register ({register.get(mid)!r})",
                )
        for index in range(1, 6):
            mid = f"M-{index:03d}"
            if dag.get(mid) != "DONE" or register.get(mid) != "DONE":
                self.err("mission", f"{mid} must be DONE before M-006 is active")

        status = dag.get("M-006")
        if status not in {"IN_PROGRESS", "REVIEW", "DONE"}:
            self.err("mission", f"M-006 must be IN_PROGRESS/REVIEW or accepted DONE, got {status!r}")
        self.m006_active = status in {"IN_PROGRESS", "REVIEW"}
        if self.m006_active:
            for index in range(7, 152):
                mid = f"M-{index:03d}"
                if dag.get(mid) != "LOCKED" or register.get(mid) != "LOCKED":
                    self.err("mission", f"{mid} must remain LOCKED while M-006 is {status}")
        else:
            # Durable mode permits serial successor progression but never a
            # regression/desynchronization of the accepted mission itself.
            active_later = [
                mid for mid, value in dag.items()
                if int(mid.split("-")[1]) >= 7
                and value in {"READY", "IN_PROGRESS", "REVIEW", "BLOCKED"}
            ]
            if len(active_later) != 1:
                self.err("mission", f"accepted M-006 requires one active later mission, got {active_later}")

        expected_active = "M-006" if self.m006_active else None
        if not self.m006_active:
            active = [mid for mid, value in dag.items() if value in {"READY", "IN_PROGRESS", "REVIEW", "BLOCKED"}]
            expected_active = active[0] if len(active) == 1 else None
        for rel in (".ai/ACTIVE_MISSION.md", "README.md", "docs/WORKSPACE_BOOTSTRAP_STATUS.md"):
            text = self.read(rel, "mission")
            if text is not None and expected_active and expected_active not in text:
                self.err("mission", f"{rel} does not name active mission {expected_active}")

    def check_dependency_policy(self) -> None:
        harvest_result = self.harvest.validate(self.root)
        for error in harvest_result.get("errors", []):
            self.err("harvest", error)
        coordinates = {
            (item["ecosystem"], item["name"].lower()): item
            for item in harvest_result.get("package_coordinates", [])
        }
        approvals = {
            (item["ecosystem"], item["package"].lower()): item
            for item in harvest_result.get("install_build_script_approvals", [])
        }

        manifests: list[Path] = []
        for path in sorted(self.root.rglob("package.json")):
            rel = path.relative_to(self.root)
            if any(part in IGNORED_PARTS for part in rel.parts):
                continue
            # The root and direct members of declared workspace directories are
            # authoritative; nested package manifests are rejected by M-004.
            if len(rel.parts) == 1 or (len(rel.parts) == 3 and rel.parts[0] in {"apps", "services", "workers", "packages", "adapters"}):
                manifests.append(path)
        packages: dict[str, tuple[Path, dict[str, Any]]] = {}
        for manifest in manifests:
            try:
                package = json.loads(manifest.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                self.err("dependency", f"invalid {manifest.relative_to(self.root)}: {exc}")
                continue
            name = str(package.get("name") or "")
            if not name:
                self.err("dependency", f"{manifest.relative_to(self.root)} has no package name")
            elif name in packages:
                self.err("dependency", f"duplicate workspace package name {name!r}")
            else:
                packages[name] = (manifest, package)

        direct_external = 0
        internal_edges = 0
        for owner, (manifest, package) in packages.items():
            seen_in_fields: set[str] = set()
            for field in DEPENDENCY_FIELDS:
                deps = package.get(field) or {}
                if not isinstance(deps, dict):
                    self.err("dependency", f"{manifest.relative_to(self.root)} {field} must be an object")
                    continue
                for name, raw_spec in deps.items():
                    name = str(name)
                    spec = str(raw_spec)
                    if name in seen_in_fields:
                        self.err("dependency", f"{owner} declares {name!r} in multiple dependency fields")
                    seen_in_fields.add(name)
                    if name.startswith("@vibeflow/"):
                        internal_edges += 1
                        if name not in packages:
                            self.err("dependency", f"{owner} has unknown internal workspace dependency {name!r}")
                        if not spec.startswith("workspace:"):
                            self.err("dependency", f"internal dependency {owner} -> {name} must use workspace: protocol")
                        if name == owner:
                            self.err("dependency", f"workspace package {owner} cannot depend on itself")
                        continue

                    direct_external += 1
                    coordinate = coordinates.get(("npm", name.lower()))
                    if coordinate is None:
                        self.err("dependency", f"unregistered external direct dependency {name!r} in {owner}")
                        continue
                    usage = coordinate["approved_usage"]
                    required_usage = "production" if field in PRODUCTION_FIELDS else "development"
                    if usage not in {required_usage, "both"}:
                        self.err(
                            "dependency",
                            f"{name!r} is approved for {usage}, not {required_usage} use in {owner}.{field}",
                        )
                    if field in PRODUCTION_FIELDS and coordinate["license_class"] != "GREEN":
                        self.err(
                            "dependency",
                            f"review-required license for {name!r} cannot silently become a production dependency",
                        )

        workspace_text = self.read("pnpm-workspace.yaml", "build-policy")
        if workspace_text is not None:
            try:
                workspace = self.master.load_simple_yaml(workspace_text)
            except Exception as exc:  # noqa: BLE001
                self.err("build-policy", f"cannot parse pnpm-workspace.yaml: {exc}")
                workspace = {}
            if "dangerouslyAllowAllBuilds" in workspace:
                self.err("build-policy", "dangerouslyAllowAllBuilds is permanently forbidden")
            if "allowBuilds" in workspace:
                allowed = workspace.get("allowBuilds")
                if not isinstance(allowed, dict) or not allowed:
                    self.err("build-policy", "allowBuilds must be a non-empty per-package mapping")
                else:
                    for package, approved in allowed.items():
                        key = ("npm", str(package).lower())
                        if approved is not True:
                            self.err("build-policy", f"allowBuilds[{package!r}] must be boolean true")
                        if key not in coordinates:
                            self.err("build-policy", f"allowBuilds package {package!r} is not a ratified coordinate")
                        if key not in approvals:
                            self.err(
                                "build-policy",
                                f"allowBuilds package {package!r} lacks explicit harvest-side approval and rationale",
                            )
        self.counts["workspace_manifests"] = len(manifests)
        self.counts["external_direct_dependencies"] = direct_external
        self.counts["internal_workspace_edges"] = internal_edges
        self.counts["build_script_approvals"] = len(approvals)

    @staticmethod
    def workflow_jobs(text: str) -> dict[str, str]:
        jobs_match = re.search(r"(?m)^jobs:\s*$", text)
        if not jobs_match:
            return {}
        body = text[jobs_match.end():]
        starts = list(re.finditer(r"(?m)^  ([a-zA-Z0-9_-]+):\s*$", body))
        jobs: dict[str, str] = {}
        for index, match in enumerate(starts):
            end = starts[index + 1].start() if index + 1 < len(starts) else len(body)
            jobs[match.group(1)] = body[match.end():end]
        return jobs

    def check_workflows(self) -> None:
        workflow_dir = self.root / ".github/workflows"
        paths = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))
        if not paths:
            self.err("workflow", "no GitHub Actions workflows found")
            return
        action_uses = 0
        for path in paths:
            rel = path.relative_to(self.root).as_posix()
            text = path.read_text(encoding="utf-8")
            if re.search(r"(?m)^\s*pull_request_target\s*:", text):
                self.err("workflow", f"{rel} uses forbidden pull_request_target")
            if re.search(r"(?m)^\s*paths(?:-ignore)?\s*:", text):
                self.err("workflow", f"{rel} must not use path filters")
            if not re.search(r"(?m)^\s*pull_request\s*:\s*$", text):
                self.err("workflow", f"{rel} must run on every pull_request")
            if not re.search(r"(?ms)^\s*push\s*:\s*\n\s*branches:\s*\[?main\]?", text):
                self.err("workflow", f"{rel} must run on pushes to main")
            if not re.search(r"(?m)^permissions:\s*\n\s{2}contents:\s*read\s*$", text):
                self.err("workflow", f"{rel} top-level permissions must be contents: read only")
            if re.search(r"(?m)^\s+[A-Za-z_-]+:\s*write\s*$", text):
                self.err("workflow", f"{rel} requests a write permission")
            if "${{ secrets." in text:
                self.err("workflow", f"{rel} references an unnecessary secret")
            if re.search(r"(?m)^\s*continue-on-error:\s*true\s*$", text):
                self.err("workflow", f"{rel} contains fail-open continue-on-error")
            if re.search(r"(?m)^\s*(?:git\s+push|gh\s+pr|gh\s+api).*", text):
                self.err("workflow", f"{rel} contains a repository-writing command")

            jobs = self.workflow_jobs(text)
            if not jobs:
                self.err("workflow", f"{rel} has no parseable jobs")
            for job, block in jobs.items():
                if not re.search(r"(?m)^    timeout-minutes:\s*[1-9][0-9]*\s*$", block):
                    self.err("workflow", f"{rel} job {job!r} lacks finite timeout-minutes")

            for match in re.finditer(r"(?m)^\s*-\s+uses:\s*([^\s#]+)(?:\s+#\s*(.*))?$", text):
                action_uses += 1
                reference = match.group(1)
                comment = match.group(2) or ""
                if "@" not in reference:
                    self.err("workflow", f"{rel} malformed uses reference {reference!r}")
                    continue
                action, pin = reference.rsplit("@", 1)
                if action not in EXPECTED_ACTIONS:
                    self.err("workflow", f"{rel} uses unapproved third-party or unnecessary Action {action!r}")
                    continue
                if not re.fullmatch(r"[0-9a-f]{40}", pin):
                    self.err("workflow", f"{rel} Action {action} must use a full 40-hex commit SHA")
                elif pin != EXPECTED_ACTIONS[action]:
                    self.err("workflow", f"{rel} Action {action} uses unapproved commit {pin}")
                if not re.search(r"v\d+\.\d+\.\d+", comment):
                    self.err("workflow", f"{rel} Action {action} pin needs a human-readable release comment")

                # Inspect the complete YAML step for action-specific hardening.
                step_start = match.start()
                next_step = re.search(r"(?m)^\s*-\s+(?:name|uses|run):", text[match.end():])
                step_end = match.end() + next_step.start() if next_step else len(text)
                step = text[step_start:step_end]
                if action == "actions/checkout" and not re.search(r"persist-credentials:\s*false", step):
                    self.err("workflow", f"{rel} checkout must set persist-credentials: false")
                if action == "actions/setup-node" and not re.search(r"package-manager-cache:\s*false", step):
                    self.err("workflow", f"{rel} setup-node must explicitly disable package-manager caching")

        security_rel = ".github/workflows/security-and-dependency-gates.yml"
        security_text = self.read(security_rel, "workflow")
        if security_text is not None:
            jobs = self.workflow_jobs(security_text)
            missing = sorted(set(REQUIRED_WORKFLOW_JOBS) - set(jobs))
            if missing:
                self.err("workflow", f"security workflow missing required scanner job(s): {missing}")
            extras = sorted(set(jobs) - set(REQUIRED_WORKFLOW_JOBS))
            if extras:
                self.err("workflow", f"security workflow has unexpected jobs: {extras}")
            gate = jobs.get("security-gate", "")
            if "if: always()" not in gate:
                self.err("workflow", "security-gate must use if: always()")
            for upstream in REQUIRED_WORKFLOW_JOBS[:-1]:
                if f"needs.{upstream}.result" not in gate or "success" not in gate:
                    self.err("workflow", f"security-gate does not fail closed on {upstream}")
            needed = set(REQUIRED_WORKFLOW_JOBS[:-1])
            needs_match = re.search(r"needs:\s*\[([^]]+)\]", gate)
            actual_needs = set()
            if needs_match:
                actual_needs = {part.strip() for part in needs_match.group(1).split(",")}
            if actual_needs != needed:
                self.err("workflow", f"security-gate needs must be {sorted(needed)}, got {sorted(actual_needs)}")
            required_commands = {
                "dependency-policy": "pnpm run security:validate",
                "secrets": "scripts/security/run-gitleaks.sh",
                "vulnerabilities": "scripts/security/run-osv-scanner.sh",
                "sast": "scripts/security/run-semgrep.sh",
                "sbom": "scripts/security/generate-sbom.sh",
            }
            for job, command in required_commands.items():
                if command not in jobs.get(job, ""):
                    self.err("workflow", f"security workflow job {job!r} missing {command!r}")
        self.counts["workflows"] = len(paths)
        self.counts["action_uses"] = action_uses

    def check_toolchain(self) -> None:
        lock = self.read_json("security/ci-toolchain.lock.json", "toolchain")
        if lock is None:
            return
        if lock.get("schema_version") != 1 or lock.get("platform") != "linux-amd64":
            self.err("toolchain", "lock schema/platform must be schema 1, linux-amd64")
        tools = lock.get("tools")
        if not isinstance(tools, dict) or set(tools) != set(EXPECTED_TOOLS):
            self.err("toolchain", f"tool set must be exactly {sorted(EXPECTED_TOOLS)}")
            return
        registry = self.master.load_yaml_file(
            self.root / "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml"
        )
        harvest_versions = {
            str(entry.get("id")): str(entry.get("version"))
            for entry in registry.get("entries") or []
        }
        for name, (harvest_id, version) in EXPECTED_TOOLS.items():
            item = tools.get(name, {})
            if item.get("harvest_id") != harvest_id:
                self.err("toolchain", f"{name} must map to {harvest_id}")
            if item.get("version") != version or harvest_versions.get(harvest_id) != version:
                self.err("toolchain", f"{name} version must be exactly {version} in lock and harvest registry")
            source = str(item.get("official_upstream_source") or "")
            coordinate = str(item.get("distribution_coordinate") or "")
            if not source.startswith("https://github.com/"):
                self.err("toolchain", f"{name} official upstream source is not GitHub HTTPS")
            if re.search(r"(?:^|[:/@-])latest(?:$|[:/@-])", coordinate, re.I):
                self.err("toolchain", f"{name} distribution coordinate uses a floating latest tag")
            if name == "semgrep":
                digest = str(item.get("immutable_container_digest") or "")
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                    self.err("toolchain", "semgrep immutable container digest is malformed")
                if not coordinate.endswith("@" + digest):
                    self.err("toolchain", "semgrep coordinate must be pinned to its full digest")
            else:
                digest = str(item.get("immutable_sha256") or "")
                if not re.fullmatch(r"[0-9a-f]{64}", digest):
                    self.err("toolchain", f"{name} immutable sha256 is malformed")
                if f"{version}" not in coordinate:
                    self.err("toolchain", f"{name} coordinate does not contain exact version {version}")
        trivy = tools["trivy"]
        for field in ("checksum_manifest_sha256", "sigstore_bundle_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(trivy.get(field) or "")):
                self.err("toolchain", f"Trivy provenance field {field} is malformed")

        required_wrapper_content = {
            "scripts/security/install-ci-tool.py": (
                "distribution checksum mismatch",
                "Trivy official checksum manifest identity mismatch",
                "Trivy Sigstore bundle subject does not match archive checksum",
            ),
            "scripts/security/run-gitleaks.sh": ("--redact=100", '--log-opts="--all"'),
            "scripts/security/run-osv-scanner.sh": ("scan source --recursive .",),
            "scripts/security/run-trivy.sh": (
                "--scanners vuln,misconfig",
                "--severity HIGH,CRITICAL",
                "--ignore-unfixed",
                "--exit-code 1",
            ),
            "scripts/security/generate-sbom.sh": ("--format cyclonedx", "sha256sum"),
            "scripts/security/run-semgrep.sh": ("security/semgrep.yml", "distribution_coordinate"),
        }
        for rel, snippets in required_wrapper_content.items():
            text = self.read(rel, "toolchain") or ""
            for snippet in snippets:
                if snippet not in text:
                    self.err("toolchain", f"{rel} missing required policy argument {snippet!r}")
        self.counts["locked_security_tools"] = len(tools)

    def check_semgrep(self) -> None:
        config = self.read("security/semgrep.yml", "semgrep")
        if config is None:
            return
        # Repository-owned local rules only: no Registry packs or URL configs.
        if re.search(r"(?m)^\s*(?:config|extends):\s*(?:p/|r/|https?://)", config):
            self.err("semgrep", "remote Semgrep config is forbidden")
        ids = set(re.findall(r"(?m)^\s*-\s+id:\s*([\w.-]+)\s*$", config))
        if ids != REQUIRED_SEMGREP_RULES:
            self.err("semgrep", f"local rule IDs differ: expected {sorted(REQUIRED_SEMGREP_RULES)}, got {sorted(ids)}")
        if len(re.findall(r"(?m)^\s+severity:\s*ERROR\s*$", config)) != len(REQUIRED_SEMGREP_RULES):
            self.err("semgrep", "every local rule must use gated severity ERROR")
        for rel in (
            "tests/security/fixtures/semgrep/positive/dangerous.py",
            "tests/security/fixtures/semgrep/positive/dangerous.ts",
            "tests/security/fixtures/semgrep/negative/safe.py",
            "tests/security/fixtures/semgrep/negative/safe.ts",
            "scripts/security/test-semgrep-rules.sh",
        ):
            self.read(rel, "semgrep")
        test_script = self.read("scripts/security/test-semgrep-rules.sh", "semgrep") or ""
        for rule_id in REQUIRED_SEMGREP_RULES:
            if rule_id not in test_script:
                self.err("semgrep", f"fixture test does not assert rule ID {rule_id}")
        if "negative.get(\"results\")" not in test_script:
            self.err("semgrep", "fixture test does not assert zero negative findings")
        for path in (self.root / ".github/workflows").glob("*.y*ml"):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"--config\s+([^\s\\]+)", text):
                value = match.group(1).strip("'\"")
                if value.startswith(("p/", "r/", "http://", "https://")):
                    self.err("semgrep", f"{path.name} uses remote Semgrep config {value!r}")
        self.counts["semgrep_rules"] = len(ids)

    def check_root_scripts(self) -> None:
        package = self.read_json("package.json", "root")
        if package is None:
            return
        scripts = package.get("scripts") or {}
        expected = "python3 scripts/validate-m006-security-gates.py"
        if scripts.get("security:validate") != expected:
            self.err("root", f"security:validate must be {expected!r}")
        stages = [part.strip() for part in str(scripts.get("check") or "").split("&&")]
        if "pnpm run security:validate" not in stages:
            self.err("root", "root check must include the security:validate stage")
        if stages and stages[0] != "python3 scripts/validate-m004-foundation.py":
            self.err("root", "M-004 foundation validator must remain the first check stage")

    def check_capabilities(self) -> None:
        csv_path = self.root / "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv"
        yaml_path = self.root / "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml"
        with csv_path.open(newline="", encoding="utf-8") as handle:
            csv_statuses = {row["vf_id"]: row["status"] for row in csv.DictReader(handle)}
        yaml_doc = self.master.load_yaml_file(yaml_path)
        yaml_statuses = {
            str(item.get("vf_id")): str(item.get("status"))
            for item in yaml_doc.get("capabilities") or []
        }
        for vf_id, expected in CAPABILITY_EXPECTED.items():
            if csv_statuses.get(vf_id) != expected or yaml_statuses.get(vf_id) != expected:
                self.err(
                    "capability",
                    f"{vf_id} must be {expected} coherently in CSV/YAML, got {csv_statuses.get(vf_id)!r}/{yaml_statuses.get(vf_id)!r}",
                )
        for vf_id in yaml_statuses:
            if vf_id.startswith("VF-ENV-") and yaml_statuses[vf_id] != "NOT_STARTED":
                self.err("capability", f"{vf_id} ENV status must remain NOT_STARTED in M-006")

    def run(self) -> dict[str, Any]:
        self.check_mission_progression()
        self.check_dependency_policy()
        self.check_workflows()
        self.check_toolchain()
        self.check_semgrep()
        self.check_root_scripts()
        self.check_capabilities()
        return {
            "result": "FAIL" if self.errors else "PASS",
            "errors": self.errors,
            "counts": self.counts,
            "mode": "m006-active" if self.m006_active else "durable",
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()
    try:
        result = Validator(args.root.resolve()).run()
    except Exception as exc:  # noqa: BLE001 — a malformed policy must fail closed
        result = {"result": "FAIL", "errors": [f"validator exception: {type(exc).__name__}: {exc}"], "counts": {}, "mode": "unknown"}
    print("M-006 CI/security/dependency gate validator")
    print(f"  mode: {result['mode']}")
    for key, value in sorted(result["counts"].items()):
        print(f"  {key}: {value}")
    if result["errors"]:
        print("Errors:")
        for error in result["errors"]:
            print(f"  - {error}")
    print(f"RESULT: {result['result']}")
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return 0 if result["result"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
