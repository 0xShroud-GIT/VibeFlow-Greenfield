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
    "trivy": ("H-030", "0.74.0"),
    "osv-scanner": ("H-031", "2.4.0"),
    "semgrep": ("H-032", "1.172.0"),
}
EXPECTED_TRIVY_PROVENANCE = {
    "distribution_coordinate": "https://github.com/aquasecurity/trivy/releases/download/v0.74.0/trivy_0.74.0_Linux-64bit.tar.gz",
    "immutable_sha256": "2ae6fe3ee734b7fdf11335663e18c75ea12dccc76062f09f164a3b0f8be4371a",
    "official_checksum_manifest": "https://github.com/aquasecurity/trivy/releases/download/v0.74.0/trivy_0.74.0_checksums.txt",
    "checksum_manifest_sha256": "bc701c3c3ee8b9acbea2c23257e41381e3854888f51281616a6ba5dc96963821",
    "sigstore_bundle_coordinate": "https://github.com/aquasecurity/trivy/releases/download/v0.74.0/trivy_0.74.0_Linux-64bit.tar.gz.sigstore.json",
    "sigstore_bundle_sha256": "da49092f6909bbbe943255ac8ec4c4cee503a05576c5dd20dc2fd9fc49c07779",
}
EXPECTED_ACTIONS = {
    "actions/checkout": ("7.0.1", "3d3c42e5aac5ba805825da76410c181273ba90b1"),
    "actions/setup-node": ("7.0.0", "820762786026740c76f36085b0efc47a31fe5020"),
    "actions/upload-artifact": ("7.0.1", "043fb46d1a93c77aae656e7c1c64a875d1fc6a0a"),
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
CAPABILITY_STATUS_RANK = {
    "NOT_STARTED": 0,
    "IN_PROGRESS": 1,
    "IMPLEMENTED": 2,
    "VERIFIED": 3,
    "COMPLETE": 4,
}
ACTIVE_BASELINE_WORKFLOWS = {
    ".github/workflows/master-build-system-integrity.yml",
    ".github/workflows/repo-sanitation.yml",
    ".github/workflows/repository-foundation.yml",
    ".github/workflows/security-and-dependency-gates.yml",
}
ACTIVE_POSITIVE_FIXTURES = {
    "tests/security/fixtures/semgrep/positive/dangerous.py",
    "tests/security/fixtures/semgrep/positive/dangerous.ts",
}
ACTIVE_NEGATIVE_FIXTURES = {
    "tests/security/fixtures/semgrep/negative/safe.py",
    "tests/security/fixtures/semgrep/negative/safe.ts",
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
            (item["ecosystem"], item["pnpm_matcher"].lower()): item
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
        direct_versions: dict[str, set[str]] = {}
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
                    direct_versions.setdefault(name.lower(), set()).add(spec)
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

        # Resolve package versions from the authoritative pnpm lock packages
        # section. A plain package matcher may only approve one exact resolved
        # version; package@version matchers bind that selector explicitly.
        resolved_versions: dict[str, set[str]] = {}
        lock_text = self.read("pnpm-lock.yaml", "build-policy") or ""
        packages_section = lock_text.split("\npackages:\n", 1)
        if len(packages_section) == 2:
            package_body = packages_section[1].split("\nsnapshots:\n", 1)[0]
            for match in re.finditer(r"(?m)^  (['\"]?)(.+?)\1:\s*(?:\{\})?\s*$", package_body):
                coordinate_key = match.group(2)
                split_at = coordinate_key.rfind("@")
                if split_at <= 0:
                    continue
                package_name = coordinate_key[:split_at].lower()
                version = coordinate_key[split_at + 1 :].split("(", 1)[0]
                if version:
                    resolved_versions.setdefault(package_name, set()).add(version)

        for (_ecosystem, _matcher), approval in approvals.items():
            package_name = approval["package"].lower()
            version = approval["version"]
            matcher = approval["pnpm_matcher"]
            direct = direct_versions.get(package_name, set())
            if direct and direct != {version}:
                self.err(
                    "build-policy",
                    f"stale install/build approval for {approval['package']!r}@{version}: "
                    f"direct dependency version(s) are {sorted(direct)}",
                )
            resolved = resolved_versions.get(package_name, set())
            if matcher == approval["package"]:
                if resolved != {version}:
                    self.err(
                        "build-policy",
                        f"stale install/build approval for matcher {matcher!r}@{version}: "
                        f"resolved lockfile version(s) are {sorted(resolved)}",
                    )
            elif version not in resolved:
                self.err(
                    "build-policy",
                    f"install/build matcher {matcher!r} has no matching {version} in pnpm-lock.yaml",
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
                    for matcher, approved in allowed.items():
                        approval_key = ("npm", str(matcher).lower())
                        approval = approvals.get(approval_key)
                        if approved is not True:
                            self.err("build-policy", f"allowBuilds[{matcher!r}] must be boolean true")
                        if approval is None:
                            self.err(
                                "build-policy",
                                f"allowBuilds matcher {matcher!r} lacks exact harvest-side approval, version and rationale",
                            )
                            continue
                        coordinate_key = ("npm", approval["package"].lower())
                        coordinate = coordinates.get(coordinate_key)
                        if coordinate is None:
                            self.err(
                                "build-policy",
                                f"allowBuilds matcher {matcher!r} references an unratified package coordinate",
                            )
                        elif coordinate["harvest_id"] != approval["harvest_id"]:
                            self.err(
                                "build-policy",
                                f"allowBuilds matcher {matcher!r} harvest mapping disagrees with its coordinate",
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

    @staticmethod
    def top_permissions(text: str) -> dict[str, str] | None:
        match = re.search(r"(?m)^permissions:\s*$", text)
        if not match:
            return None
        permissions: dict[str, str] = {}
        for line in text[match.end():].splitlines():
            if not line.strip():
                continue
            item = re.match(r"^  ([a-zA-Z0-9_-]+):\s*([a-z-]+)\s*$", line)
            if item:
                permissions[item.group(1)] = item.group(2)
                continue
            break
        return permissions

    def check_workflows(self) -> None:
        lock = self.read_json("security/ci-toolchain.lock.json", "workflow") or {}
        action_lock = lock.get("github_actions") or {}
        workflow_lock = lock.get("workflow_policy") or {}
        baseline = workflow_lock.get("baseline_workflows") or {}
        additional = workflow_lock.get("additional_workflows") or {}
        if not isinstance(baseline, dict) or not isinstance(additional, dict):
            self.err("workflow", "workflow_policy baseline/additional entries must be mappings")
            baseline, additional = {}, {}
        if set(baseline) != ACTIVE_BASELINE_WORKFLOWS:
            self.err("workflow", "workflow lock must retain the four M-006 baseline workflows")
        if self.m006_active and additional:
            self.err("workflow", "M-006 active snapshot forbids additional workflow registrations")

        registered: dict[str, Any] = {**baseline, **additional}
        workflow_dir = self.root / ".github/workflows"
        paths = sorted(workflow_dir.glob("*.yml")) + sorted(workflow_dir.glob("*.yaml"))
        actual = {path.relative_to(self.root).as_posix() for path in paths}
        expected = set(registered)
        if actual != expected:
            self.err(
                "workflow",
                f"workflow files must match the policy lock (missing={sorted(expected-actual)}, unregistered={sorted(actual-expected)})",
            )
        if self.m006_active and actual != ACTIVE_BASELINE_WORKFLOWS:
            self.err("workflow", "M-006 active snapshot requires exactly its four baseline workflows")

        action_uses = 0
        for path in paths:
            rel = path.relative_to(self.root).as_posix()
            text = path.read_text(encoding="utf-8")
            policy = registered.get(rel)
            if not isinstance(policy, dict):
                self.err("workflow", f"{rel} has no structured workflow policy registration")
                policy = {}
            rationale = str(policy.get("rationale") or "").strip()
            if not rationale:
                self.err("workflow", f"{rel} policy registration needs a rationale")
            declared_name = re.search(r"(?m)^name:\s*(.+?)\s*$", text)
            if declared_name and policy.get("name") != declared_name.group(1):
                self.err("workflow", f"{rel} name disagrees with workflow policy lock")

            is_baseline = rel in baseline
            if re.search(r"(?m)^\s*pull_request_target\s*:", text):
                self.err("workflow", f"{rel} uses forbidden pull_request_target")
            if is_baseline:
                if re.search(r"(?m)^\s*paths(?:-ignore)?\s*:", text):
                    self.err("workflow", f"baseline workflow {rel} must not use path filters")
                if not re.search(r"(?m)^\s*pull_request\s*:\s*$", text):
                    self.err("workflow", f"baseline workflow {rel} must run on every pull_request")
                if not re.search(r"(?ms)^\s*push\s*:\s*\n\s*branches:\s*\[?main\]?", text):
                    self.err("workflow", f"baseline workflow {rel} must run on pushes to main")

            expected_permissions = policy.get("permissions")
            actual_permissions = self.top_permissions(text)
            if not isinstance(expected_permissions, dict) or not expected_permissions:
                self.err("workflow", f"{rel} policy must declare exact least-privilege permissions")
            elif actual_permissions != expected_permissions:
                self.err(
                    "workflow",
                    f"{rel} permissions {actual_permissions!r} != registered least privilege {expected_permissions!r}",
                )
            has_write = any(value == "write" for value in (actual_permissions or {}).values())
            if has_write and policy.get("allow_repository_write") is not True:
                self.err("workflow", f"{rel} requests unapproved write permission")

            secret_names = set(re.findall(r"\$\{\{\s*secrets\.([A-Za-z0-9_]+)", text))
            allowed_secrets = set(policy.get("allowed_secrets") or [])
            if secret_names - allowed_secrets:
                self.err("workflow", f"{rel} references unapproved secrets {sorted(secret_names-allowed_secrets)}")
            if re.search(r"(?m)^\s*continue-on-error:\s*true\s*$", text) and policy.get("allow_continue_on_error") is not True:
                self.err("workflow", f"{rel} contains unapproved continue-on-error")
            writes_repository = bool(re.search(r"(?m)^\s*(?:git\s+push|gh\s+pr|gh\s+api).*", text))
            if writes_repository and policy.get("allow_repository_write") is not True:
                self.err("workflow", f"{rel} contains an unapproved repository-writing command")

            jobs = self.workflow_jobs(text)
            if not jobs:
                self.err("workflow", f"{rel} has no parseable jobs")
            required_jobs = set(policy.get("required_jobs") or [])
            if not required_jobs or not required_jobs.issubset(jobs):
                self.err("workflow", f"{rel} is missing registered required jobs {sorted(required_jobs-set(jobs))}")
            for job, block in jobs.items():
                if not re.search(r"(?m)^    timeout-minutes:\s*[1-9][0-9]*\s*$", block):
                    self.err("workflow", f"{rel} job {job!r} lacks finite timeout-minutes")

            for match in re.finditer(r"(?m)^\s*-\s+uses:\s*([^\s#]+)(?:\s+#\s*(.*))?$", text):
                reference = match.group(1)
                comment = match.group(2) or ""
                if reference.startswith("./"):
                    continue
                action_uses += 1
                if "@" not in reference:
                    self.err("workflow", f"{rel} malformed external uses reference {reference!r}")
                    continue
                action, pin = reference.rsplit("@", 1)
                locked_action = action_lock.get(action)
                if not isinstance(locked_action, dict):
                    self.err("workflow", f"{rel} uses Action {action!r} absent from the action lock")
                    continue
                locked_pin = str(locked_action.get("commit_sha") or "")
                version = str(locked_action.get("version") or "")
                if not re.fullmatch(r"[0-9a-f]{40}", pin):
                    self.err("workflow", f"{rel} Action {action} must use a full 40-hex commit SHA")
                elif pin != locked_pin:
                    self.err("workflow", f"{rel} Action {action} pin disagrees with action lock")
                if f"v{version}" not in comment:
                    self.err("workflow", f"{rel} Action {action} pin needs locked release comment v{version}")

                step_start = match.start()
                next_step = re.search(r"(?m)^\s*-\s+(?:name|uses|run):", text[match.end():])
                step_end = match.end() + next_step.start() if next_step else len(text)
                step = text[step_start:step_end]
                if action == "actions/checkout" and not re.search(r"persist-credentials:\s*false", step):
                    self.err("workflow", f"{rel} checkout must set persist-credentials: false")
                if (
                    action == "actions/setup-node"
                    and policy.get("allow_package_manager_cache") is not True
                    and not re.search(r"package-manager-cache:\s*false", step)
                ):
                    self.err("workflow", f"{rel} setup-node must explicitly disable package-manager caching")

        security_rel = ".github/workflows/security-and-dependency-gates.yml"
        security_text = self.read(security_rel, "workflow")
        if security_text is not None:
            jobs = self.workflow_jobs(security_text)
            missing = sorted(set(REQUIRED_WORKFLOW_JOBS) - set(jobs))
            if missing:
                self.err("workflow", f"security workflow missing required scanner job(s): {missing}")
            if self.m006_active:
                extras = sorted(set(jobs) - set(REQUIRED_WORKFLOW_JOBS))
                if extras:
                    self.err("workflow", f"M-006 active security workflow has unexpected jobs: {extras}")
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
                "secrets": "scripts/security/test-gitleaks.sh",
                "vulnerabilities": "scripts/security/run-osv-scanner.sh",
                "sast": "scripts/security/run-semgrep.sh",
                "sbom": "scripts/security/generate-sbom.sh",
            }
            for job, command in required_commands.items():
                if command not in jobs.get(job, ""):
                    self.err("workflow", f"security workflow job {job!r} missing {command!r}")
            if "scripts/security/run-gitleaks.sh" not in jobs.get("secrets", ""):
                self.err("workflow", "security workflow secrets job must scan repository history")
        self.counts["workflows"] = len(paths)
        self.counts["action_uses"] = action_uses

    def check_toolchain(self) -> None:
        lock = self.read_json("security/ci-toolchain.lock.json", "toolchain")
        if lock is None:
            return
        if lock.get("schema_version") != 2 or lock.get("platform") != "linux-amd64":
            self.err("toolchain", "lock schema/platform must be schema 2, linux-amd64")
        tools = lock.get("tools")
        if not isinstance(tools, dict):
            self.err("toolchain", "tools lock must be a mapping")
            return
        if self.m006_active and set(tools) != set(EXPECTED_TOOLS):
            self.err("toolchain", f"M-006 active tool set must be exactly {sorted(EXPECTED_TOOLS)}")
        if not set(EXPECTED_TOOLS).issubset(tools):
            self.err("toolchain", f"durable tool lock lost M-006 scanners {sorted(set(EXPECTED_TOOLS)-set(tools))}")

        registry = self.master.load_yaml_file(
            self.root / "master-build-system/06_HARVEST/OSS_HARVEST_REGISTRY.yaml"
        )
        harvest_entries = {
            str(entry.get("id")): entry for entry in registry.get("entries") or []
        }
        for name, item in tools.items():
            if not isinstance(item, dict):
                self.err("toolchain", f"{name} lock entry must be a mapping")
                continue
            harvest_id = str(item.get("harvest_id") or "")
            version = str(item.get("version") or "")
            harvest = harvest_entries.get(harvest_id)
            if harvest is None:
                self.err("toolchain", f"{name} maps to unknown harvest ID {harvest_id!r}")
            else:
                if harvest.get("integration") != "CI_TOOL":
                    self.err("toolchain", f"{name} harvest entry {harvest_id} is not a CI_TOOL")
                if str(harvest.get("version")) != version:
                    self.err("toolchain", f"{name} version disagrees with harvest registry")
                if item.get("official_upstream_source") != harvest.get("source"):
                    self.err("toolchain", f"{name} upstream source disagrees with harvest registry")
            if self.m006_active:
                expected_hid, expected_version = EXPECTED_TOOLS.get(name, (None, None))
                if harvest_id != expected_hid or version != expected_version:
                    self.err(
                        "toolchain",
                        f"M-006 active {name} must remain {expected_hid}@{expected_version}",
                    )

            coordinate = str(item.get("distribution_coordinate") or "")
            if re.search(r"(?:^|[:/@-])latest(?:$|[:/@-])", coordinate, re.I):
                self.err("toolchain", f"{name} distribution coordinate uses floating latest")
            container_digest = item.get("immutable_container_digest")
            archive_digest = item.get("immutable_sha256")
            if container_digest is not None:
                digest = str(container_digest)
                if not re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                    self.err("toolchain", f"{name} immutable container digest is malformed")
                if not coordinate.endswith("@" + digest):
                    self.err("toolchain", f"{name} container coordinate must end in its digest")
            elif archive_digest is not None:
                if not re.fullmatch(r"[0-9a-f]{64}", str(archive_digest)):
                    self.err("toolchain", f"{name} immutable sha256 is malformed")
                if version not in coordinate:
                    self.err("toolchain", f"{name} coordinate omits locked version {version}")
            else:
                self.err("toolchain", f"{name} needs immutable sha256 or container digest")

        trivy = tools.get("trivy", {})
        for field in ("checksum_manifest_sha256", "sigstore_bundle_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", str(trivy.get(field) or "")):
                self.err("toolchain", f"Trivy provenance field {field} is malformed")
        if self.m006_active:
            for field, expected in EXPECTED_TRIVY_PROVENANCE.items():
                if trivy.get(field) != expected:
                    self.err(
                        "toolchain",
                        f"M-006 active Trivy provenance {field} must match the 0.74.0 snapshot",
                    )

        actions = lock.get("github_actions")
        if not isinstance(actions, dict):
            self.err("toolchain", "github_actions lock must be a mapping")
            actions = {}
        if self.m006_active and set(actions) != set(EXPECTED_ACTIONS):
            self.err("toolchain", "M-006 active Action lock must contain exactly the three ratified Actions")
        for action, item in actions.items():
            if not isinstance(item, dict):
                self.err("toolchain", f"Action {action} lock entry must be a mapping")
                continue
            version = str(item.get("version") or "")
            pin = str(item.get("commit_sha") or "")
            if not re.fullmatch(r"\d+\.\d+\.\d+", version):
                self.err("toolchain", f"Action {action} version is malformed")
            if not re.fullmatch(r"[0-9a-f]{40}", pin):
                self.err("toolchain", f"Action {action} commit SHA is malformed")
            if item.get("official_upstream_source") != f"https://github.com/{action}":
                self.err("toolchain", f"Action {action} official source is malformed")
            if not str(item.get("rationale") or "").strip():
                self.err("toolchain", f"Action {action} needs approval rationale")
            if self.m006_active and action in EXPECTED_ACTIONS:
                expected_version, expected_pin = EXPECTED_ACTIONS[action]
                if (version, pin) != (expected_version, expected_pin):
                    self.err("toolchain", f"M-006 active Action {action} lock drifted")

        required_wrapper_content = {
            "scripts/security/install-ci-tool.py": (
                "distribution checksum mismatch",
                "Trivy official checksum manifest identity mismatch",
                "Trivy Sigstore bundle subject does not match archive checksum",
            ),
            "scripts/security/test-gitleaks.sh": (
                "expected_version",
                "negative clean",
                "positive detected and redacted",
            ),
            "scripts/security/run-gitleaks.sh": ("--redact=100", '--log-opts="--all"'),
            "scripts/security/run-osv-scanner.sh": ("scan source --recursive .",),
            "scripts/security/run-trivy.sh": (
                "--scanners vuln,misconfig",
                "--include-dev-deps",
                "--severity HIGH,CRITICAL",
                "--ignore-unfixed",
                "--exit-code 1",
            ),
            "scripts/security/generate-sbom.sh": (
                "--scanners vuln",
                "--include-dev-deps",
                "--format cyclonedx",
                "sha256sum",
            ),
            "scripts/security/run-semgrep.sh": ("security/semgrep.yml", "distribution_coordinate"),
        }
        for rel, snippets in required_wrapper_content.items():
            text = self.read(rel, "toolchain") or ""
            for snippet in snippets:
                if snippet not in text:
                    self.err("toolchain", f"{rel} missing required policy argument {snippet!r}")
        self.counts["locked_security_tools"] = len(tools)
        self.counts["locked_github_actions"] = len(actions)

    def check_semgrep(self) -> None:
        lock = self.read_json("security/ci-toolchain.lock.json", "semgrep") or {}
        policy = lock.get("semgrep_policy")
        if not isinstance(policy, dict):
            self.err("semgrep", "semgrep_policy lock must be a mapping")
            return
        config_rel = str(policy.get("config") or "")
        if (
            not config_rel.startswith("security/")
            or config_rel.startswith("/")
            or ".." in Path(config_rel).parts
            or config_rel.startswith(("p/", "r/", "http://", "https://"))
        ):
            self.err("semgrep", f"Semgrep config must be repository-owned under security/, got {config_rel!r}")
        config = self.read(config_rel, "semgrep")
        if config is None:
            return
        if re.search(r"(?m)^\s*(?:config|extends):\s*(?:p/|r/|https?://)", config):
            self.err("semgrep", "remote Semgrep config is forbidden")

        raw_rules = policy.get("rules")
        if not isinstance(raw_rules, list) or not raw_rules:
            self.err("semgrep", "semgrep_policy.rules must be a non-empty list")
            raw_rules = []
        locked_rules: dict[str, str] = {}
        for index, item in enumerate(raw_rules):
            if not isinstance(item, dict):
                self.err("semgrep", f"semgrep_policy.rules[{index}] must be a mapping")
                continue
            rule_id = str(item.get("id") or "")
            severity = str(item.get("severity") or "")
            if not rule_id or rule_id in locked_rules:
                self.err("semgrep", f"duplicate or empty locked Semgrep rule ID {rule_id!r}")
            locked_rules[rule_id] = severity
        gated = str(policy.get("gated_severity") or "")
        for rule_id, severity in locked_rules.items():
            if severity != gated:
                self.err("semgrep", f"locked rule {rule_id} severity {severity!r} != gated {gated!r}")
        if self.m006_active and set(locked_rules) != REQUIRED_SEMGREP_RULES:
            self.err("semgrep", "M-006 active rule lock must retain the exact six snapshot rules")

        configured_rules: dict[str, str] = {}
        blocks = re.findall(r"(?ms)^  - id:\s*([\w.-]+)\s*$\n(.*?)(?=^  - id:|\Z)", config)
        for rule_id, block in blocks:
            severity_match = re.search(r"(?m)^    severity:\s*([A-Z]+)\s*$", block)
            configured_rules[rule_id] = severity_match.group(1) if severity_match else ""
        if configured_rules != locked_rules:
            self.err(
                "semgrep",
                f"local configured rules {configured_rules!r} != rule lock {locked_rules!r}",
            )

        positive = policy.get("positive_fixtures")
        negative = policy.get("negative_fixtures")
        if not isinstance(positive, list) or not positive:
            self.err("semgrep", "Semgrep positive fixture lock must be a non-empty list")
            positive = []
        if not isinstance(negative, list) or not negative:
            self.err("semgrep", "Semgrep negative fixture lock must be a non-empty list")
            negative = []
        if self.m006_active:
            if set(positive) != ACTIVE_POSITIVE_FIXTURES or set(negative) != ACTIVE_NEGATIVE_FIXTURES:
                self.err("semgrep", "M-006 active fixture lock drifted from snapshot")
        for rel in [*positive, *negative, "scripts/security/test-semgrep-rules.sh"]:
            if not isinstance(rel, str) or rel.startswith("/") or ".." in Path(rel).parts:
                self.err("semgrep", f"invalid repository fixture path {rel!r}")
                continue
            self.read(rel, "semgrep")
        test_script = self.read("scripts/security/test-semgrep-rules.sh", "semgrep") or ""
        for snippet in ("semgrep_policy", "positive_fixtures", "negative_fixtures", 'negative.get("results")'):
            if snippet not in test_script:
                self.err("semgrep", f"fixture test is not lock-driven; missing {snippet!r}")
        for path in (self.root / ".github/workflows").glob("*.y*ml"):
            text = path.read_text(encoding="utf-8")
            for match in re.finditer(r"--config\s+([^\s\\]+)", text):
                value = match.group(1).strip("'\"")
                if value.startswith(("p/", "r/", "http://", "https://")):
                    self.err("semgrep", f"{path.name} uses remote Semgrep config {value!r}")
        self.counts["semgrep_rules"] = len(locked_rules)

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
        for vf_id in sorted(set(csv_statuses) | set(yaml_statuses)):
            csv_status = csv_statuses.get(vf_id)
            yaml_status = yaml_statuses.get(vf_id)
            if csv_status != yaml_status:
                self.err(
                    "capability",
                    f"{vf_id} status disagrees between CSV ({csv_status!r}) and YAML ({yaml_status!r})",
                )
            if csv_status not in CAPABILITY_STATUS_RANK:
                self.err("capability", f"{vf_id} has unknown capability status {csv_status!r}")

        for vf_id, snapshot_status in CAPABILITY_EXPECTED.items():
            actual = csv_statuses.get(vf_id)
            if self.m006_active:
                if actual != snapshot_status:
                    self.err(
                        "capability",
                        f"M-006 active snapshot requires {vf_id}={snapshot_status}, got {actual!r}",
                    )
            elif actual in CAPABILITY_STATUS_RANK and (
                CAPABILITY_STATUS_RANK[actual] < CAPABILITY_STATUS_RANK[snapshot_status]
            ):
                self.err(
                    "capability",
                    f"durable {vf_id} regressed below M-006 baseline {snapshot_status} to {actual}",
                )

        if self.m006_active:
            for vf_id, status in csv_statuses.items():
                if vf_id.startswith("VF-ENV-") and status != "NOT_STARTED":
                    self.err(
                        "capability",
                        f"M-006 active snapshot requires {vf_id} ENV status NOT_STARTED, got {status}",
                    )
        # Durable mode intentionally does not freeze ENV rows. M-007 and later
        # missions may advance their selected capabilities while the accepted
        # M-006 REL baseline remains non-regressing.

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
