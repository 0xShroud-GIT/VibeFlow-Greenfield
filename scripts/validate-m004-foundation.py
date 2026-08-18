#!/usr/bin/env python3
"""M-004 repository-foundation contract validator (stdlib only).

This validator checks the ratified M-004 toolchain, workspace shape, dependency
policy, mission progression, and the existence/content of foundation CI.

The toolchain/dependency/workspace rules are *permanent* foundation invariants:
they stay fully enforced for every later mission.

Mission-state logic is deliberately **progression-aware** rather than a frozen
M-004 snapshot, so a legitimate successor branch is not rejected:

    historical M-004 state : M-001..M-003 DONE, M-004 REVIEW, M-005+ LOCKED
    accepted M-004 state   : M-001..M-004 DONE, a later mission may be active

While M-004 is still REVIEW (not yet accepted) every later mission must remain
LOCKED. Once M-004 is DONE this validator stops asserting the status of later
missions: serial mission progression is owned by validate-master-contracts.py.
What this validator keeps enforcing is that M-004 never regresses below the
acceptance state that later work depends on.

The root `check` script is validated by parsing its `&&` stages instead of
matching one frozen literal command, so additional legitimate gates may be added
without allowing a required foundation stage to disappear.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_ROOT = Path(__file__).resolve().parents[1]

NODE_PIN = "24.19.0"
PNPM_PIN = "11.4.0"
APPROVED_ROOT_DEV = {
    "typescript": "6.0.3",
    "turbo": "2.10.6",
    "vitest": "4.1.7",
}
TYPEBOX_PIN = "1.3.6"
EXPECTED_GLOBS = [
    "apps/*",
    "services/*",
    "workers/*",
    "packages/*",
    "adapters/*",
]
EXPECTED_PACKAGES = {
    "core": "@vibeflow/core",
    "contracts": "@vibeflow/contracts",
    "remote": "@vibeflow/remote",
    "bridge": "@vibeflow/bridge",
    "provider-sdk": "@vibeflow/provider-sdk",
    "verification": "@vibeflow/verification",
    "ui": "@vibeflow/ui",
}
STRICT_FLAGS = {
    "strict": True,
    "noUncheckedIndexedAccess": True,
    "exactOptionalPropertyTypes": True,
    "noImplicitOverride": True,
    "noFallthroughCasesInSwitch": True,
    "useUnknownInCatchVariables": True,
    "forceConsistentCasingInFileNames": True,
}
FORBIDDEN_LIFECYCLE = {"preinstall", "install", "postinstall", "prepare"}
# Permanent required stages of the root `check` pipeline, in order. Additional
# legitimate gates may be interleaved, but none of these may disappear and the
# foundation validator must remain the first gate.
REQUIRED_CHECK_STAGES = (
    "python3 scripts/validate-m004-foundation.py",
    "pnpm run typecheck",
    "pnpm run test",
    "pnpm run build",
)
IGNORED_WALK_PARTS = {
    ".git", "node_modules", "dist", ".turbo", ".cache", ".vite",
    "__pycache__", ".pytest_cache", ".next", ".expo",
}
PNPM_PROJECT_SETTINGS = {
    "minimumReleaseAge",
    "minimumReleaseAgeStrict",
    "minimumReleaseAgeIgnoreMissingTime",
    "blockExoticSubdeps",
    "strictDepBuilds",
    "trustLockfile",
    "dangerouslyAllowAllBuilds",
    "allowBuilds",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    return parser.parse_args()


def read_json(path: Path, errors: list[str], label: str) -> dict[str, Any]:
    if not path.is_file():
        errors.append(f"{label}: missing {path}")
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"{label}: invalid JSON in {path}: {exc}")
        return {}
    if not isinstance(data, dict):
        errors.append(f"{label}: expected JSON object in {path}")
        return {}
    return data


def parse_scalar(value: str) -> Any:
    value = value.strip().strip("'\"")
    lower = value.lower()
    if lower == "true":
        return True
    if lower == "false":
        return False
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_workspace(path: Path, errors: list[str]) -> tuple[list[str], dict[str, Any], dict[str, Any]]:
    """Parse the tiny YAML subset M-004 intentionally uses."""
    if not path.is_file():
        errors.append("I: missing pnpm-workspace.yaml")
        return [], {}, {}
    packages: list[str] = []
    settings: dict[str, Any] = {}
    allow_builds: dict[str, Any] = {}
    section: str | None = None

    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        stripped = raw.strip()

        if indent == 0:
            section = None
            if stripped.endswith(":"):
                key = stripped[:-1]
                if key in {"packages", "allowBuilds"}:
                    section = key
                    continue
            if ":" not in stripped:
                errors.append(f"I: malformed pnpm-workspace.yaml line: {raw}")
                continue
            key, value = stripped.split(":", 1)
            settings[key.strip()] = parse_scalar(value)
            continue

        if section == "packages":
            if stripped.startswith("- "):
                packages.append(stripped[2:].strip().strip("'\""))
            else:
                errors.append(f"I: malformed packages entry: {raw}")
        elif section == "allowBuilds":
            if ":" not in stripped:
                errors.append(f"Q: malformed allowBuilds entry: {raw}")
            else:
                key, value = stripped.split(":", 1)
                allow_builds[key.strip().strip("'\"")] = parse_scalar(value)
        else:
            errors.append(f"I: unexpected nested pnpm-workspace.yaml entry: {raw}")

    return packages, settings, allow_builds


def dependency_fields(pkg: dict[str, Any]) -> dict[str, str]:
    merged: dict[str, str] = {}
    for field in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        value = pkg.get(field) or {}
        if isinstance(value, dict):
            for name, spec in value.items():
                merged[str(name)] = str(spec)
    return merged


def has_range_or_exotic(spec: str) -> tuple[bool, bool]:
    lowered = spec.lower()
    ranged = (
        spec.startswith(("^", "~", ">", "<", "="))
        or spec in {"latest", "*"}
        or " || " in spec
        or re.search(r"(^|[.\s])x($|[.\s])", spec, re.I) is not None
    )
    exotic = lowered.startswith(
        ("git+", "git://", "github:", "gitlab:", "bitbucket:",
         "http://", "https://", "file:", "link:")
    )
    return ranged, exotic


def active_path(path: Path, root: Path) -> bool:
    try:
        rel = path.relative_to(root)
    except ValueError:
        return False
    return not any(part in IGNORED_WALK_PARTS for part in rel.parts)


def parse_dag_statuses(path: Path, errors: list[str]) -> dict[str, str]:
    if not path.is_file():
        errors.append("U: missing MISSION_DAG.yaml")
        return {}
    statuses: dict[str, str] = {}
    current: str | None = None
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"\s*-\s*mission_id:\s*(M-\d{3})\s*$", line)
        if match:
            current = match.group(1)
            continue
        if current:
            match = re.match(r"\s*status:\s*([A-Z_]+)\s*$", line)
            if match:
                statuses[current] = match.group(1)
                current = None
    return statuses


def parse_register_statuses(path: Path, errors: list[str]) -> dict[str, str]:
    if not path.is_file():
        errors.append("U: missing MISSION_REGISTER.csv")
        return {}
    try:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
    except Exception as exc:
        errors.append(f"U: failed to parse MISSION_REGISTER.csv: {exc}")
        return {}
    statuses: dict[str, str] = {}
    for row in rows:
        mid = (row.get("mission_id") or "").strip()
        status = (row.get("status") or "").strip()
        if mid:
            statuses[mid] = status
    return statuses


def main() -> int:
    root = parse_args().root.resolve()
    errors: list[str] = []

    root_pkg = read_json(root / "package.json", errors, "A")
    nvmrc = root / ".nvmrc"
    if not nvmrc.is_file() or nvmrc.read_text(encoding="utf-8").strip() != NODE_PIN:
        errors.append(f"A: .nvmrc must pin {NODE_PIN}")
    engines = root_pkg.get("engines") or {}
    if engines.get("node") != "24.x":
        errors.append(f"A: engines.node must be '24.x', got {engines.get('node')!r}")
    if engines.get("pnpm") != PNPM_PIN:
        errors.append(f"A: engines.pnpm must be '{PNPM_PIN}', got {engines.get('pnpm')!r}")
    if root_pkg.get("packageManager") != f"pnpm@{PNPM_PIN}":
        errors.append(f"B: packageManager must be pnpm@{PNPM_PIN}")
    if root_pkg.get("private") is not True or root_pkg.get("type") != "module":
        errors.append("B: root package must be private and ESM")

    root_dev = root_pkg.get("devDependencies") or {}
    root_runtime = root_pkg.get("dependencies") or {}
    if root_runtime:
        errors.append("F: root dependencies must be empty at M-004")
    if root_dev != APPROVED_ROOT_DEV:
        errors.append(f"C/F: root devDependencies must equal {APPROVED_ROOT_DEV}, got {root_dev}")

    root_scripts = root_pkg.get("scripts") or {}
    required_root_scripts = {
        "build": "turbo run build",
        "typecheck": "turbo run typecheck",
        "test": "turbo run test",
        "foundation:validate": "python3 scripts/validate-m004-foundation.py",
    }
    for name, command in required_root_scripts.items():
        if root_scripts.get(name) != command:
            errors.append(f"B: root script {name!r} must be {command!r}")

    # Root `check` is a pipeline, not a frozen literal. Parse its && stages and
    # require every permanent foundation stage to remain present, in order.
    check_script = root_scripts.get("check")
    if not isinstance(check_script, str) or not check_script.strip():
        errors.append("B: root script 'check' is required")
    else:
        stages = [stage.strip() for stage in check_script.split("&&")]
        stages = [stage for stage in stages if stage]
        position = -1
        for required in REQUIRED_CHECK_STAGES:
            try:
                index = stages.index(required, position + 1)
            except ValueError:
                if required in stages:
                    errors.append(
                        f"B: root 'check' stage {required!r} is out of order; required order is "
                        f"{' && '.join(REQUIRED_CHECK_STAGES)}"
                    )
                else:
                    errors.append(
                        f"B: root 'check' must include stage {required!r} (got {check_script!r})"
                    )
                position = len(stages)
                continue
            position = index
        if stages and stages[0] != REQUIRED_CHECK_STAGES[0]:
            errors.append(
                f"B: root 'check' must begin with {REQUIRED_CHECK_STAGES[0]!r}, got {stages[0]!r}"
            )
    for name in FORBIDDEN_LIFECYCLE:
        if name in root_scripts:
            errors.append(f"P: forbidden root lifecycle script {name!r}")

    packages_root = root / "packages"
    found_manifests = {
        p.parent.name: p for p in packages_root.glob("*/package.json")
        if p.is_file() and active_path(p, root)
    }
    if set(found_manifests) != set(EXPECTED_PACKAGES):
        errors.append(
            f"K: expected exactly seven manifests {sorted(EXPECTED_PACKAGES)}, "
            f"got {sorted(found_manifests)}"
        )

    all_specs: list[tuple[str, str, str]] = []
    workspace_graph: dict[str, list[str]] = {}

    for dirname, expected_name in EXPECTED_PACKAGES.items():
        manifest = root / "packages" / dirname / "package.json"
        pkg = read_json(manifest, errors, "K")
        if not pkg:
            continue
        if pkg.get("name") != expected_name:
            errors.append(f"L: packages/{dirname} must be named {expected_name}")
        if pkg.get("private") is not True or pkg.get("version") != "0.0.0" or pkg.get("type") != "module":
            errors.append(f"M: packages/{dirname} must be private, version 0.0.0, and ESM")
        scripts = pkg.get("scripts") or {}
        expected_scripts = {
            "build": "tsc -p tsconfig.json",
            "typecheck": "tsc --noEmit",
            "test": "vitest run --passWithNoTests",
        }
        if scripts != expected_scripts:
            errors.append(f"M: packages/{dirname} scripts must be cross-platform foundation scripts only")
        for name in FORBIDDEN_LIFECYCLE:
            if name in scripts:
                errors.append(f"P: forbidden lifecycle script {name!r} in packages/{dirname}")

        deps = dependency_fields(pkg)
        for dep, spec in deps.items():
            all_specs.append((f"packages/{dirname}", dep, spec))
            if spec.startswith("workspace:"):
                workspace_graph.setdefault(expected_name, []).append(dep)

        if dirname == "contracts":
            if (pkg.get("dependencies") or {}) != {"typebox": TYPEBOX_PIN}:
                errors.append(f"C/N: contracts must depend only on typebox@{TYPEBOX_PIN}")
            if "@sinclair/typebox" in deps:
                errors.append("N: @sinclair/typebox is forbidden; use typebox 1.x")
        elif deps:
            errors.append(f"F: packages/{dirname} must have no dependencies at M-004")

        for required in ("tsconfig.json", "src/index.ts"):
            if not (root / "packages" / dirname / required).is_file():
                errors.append(f"K: missing packages/{dirname}/{required}")

    if not (root / "packages/contracts/src/typebox-smoke.test.ts").is_file():
        errors.append("N: missing TypeBox compatibility smoke test")

    for dep, spec in {**root_runtime, **root_dev}.items():
        all_specs.append(("root", dep, str(spec)))
    for location, dep, spec in all_specs:
        ranged, exotic = has_range_or_exotic(spec)
        if ranged:
            errors.append(f"D: dependency range/dist-tag forbidden: {location} {dep}={spec}")
        if exotic:
            errors.append(f"E: exotic dependency source forbidden: {location} {dep}={spec}")
        if dep == "@sinclair/typebox":
            errors.append(f"N: forbidden TypeBox 0.x package in {location}")

    pnpm_locks = [p for p in root.rglob("pnpm-lock.yaml") if active_path(p, root)]
    if set(pnpm_locks) != {root / "pnpm-lock.yaml"}:
        errors.append(
            "G: exactly one root pnpm-lock.yaml required, got "
            f"{[str(p.relative_to(root)) for p in pnpm_locks]}"
        )
    for name in ("package-lock.json", "yarn.lock", "bun.lock", "bun.lockb"):
        found = [p for p in root.rglob(name) if active_path(p, root)]
        if found:
            errors.append(f"H: forbidden lockfile(s): {[str(p.relative_to(root)) for p in found]}")

    workspace_globs, pnpm_settings, allow_builds = parse_workspace(root / "pnpm-workspace.yaml", errors)
    if workspace_globs != EXPECTED_GLOBS:
        errors.append(f"I: workspace globs must exactly equal {EXPECTED_GLOBS}, got {workspace_globs}")

    required_settings = {
        "minimumReleaseAge": 1440,
        "minimumReleaseAgeStrict": True,
        "minimumReleaseAgeIgnoreMissingTime": False,
        "blockExoticSubdeps": True,
        "strictDepBuilds": True,
        "trustLockfile": False,
    }
    for key, expected in required_settings.items():
        if pnpm_settings.get(key) != expected:
            errors.append(f"R/S: pnpm-workspace.yaml {key} must be {expected!r}, got {pnpm_settings.get(key)!r}")
    if pnpm_settings.get("dangerouslyAllowAllBuilds") is True:
        errors.append("Q: dangerouslyAllowAllBuilds must not be enabled")
    if allow_builds:
        errors.append(f"Q: M-004 expects no allowBuilds approvals, got {allow_builds}")

    npmrc = root / ".npmrc"
    if npmrc.is_file():
        for line in npmrc.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("#", ";")):
                continue
            key = re.split(r"[:=]", stripped, maxsplit=1)[0].strip()
            if key in PNPM_PROJECT_SETTINGS or key in {"engine-strict", "save-exact"}:
                errors.append(f"R: project pnpm setting {key!r} must be in pnpm-workspace.yaml, not .npmrc")

    for prefix in ("apps", "services", "workers", "adapters"):
        base = root / prefix
        if base.is_dir():
            found = [p for p in base.rglob("package.json") if active_path(p, root)]
            if found:
                errors.append(f"J: package.json forbidden under {prefix}: {[str(p.relative_to(root)) for p in found]}")

    tsconfig = read_json(root / "tsconfig.base.json", errors, "O")
    opts = tsconfig.get("compilerOptions") or {}
    for flag, expected in STRICT_FLAGS.items():
        if opts.get(flag) != expected:
            errors.append(f"O: {flag} must be {expected!r}")
    if opts.get("module") != "NodeNext" or opts.get("moduleResolution") != "NodeNext":
        errors.append("O: TypeScript module and moduleResolution must both be NodeNext")

    for dirname in EXPECTED_PACKAGES:
        config = read_json(root / "packages" / dirname / "tsconfig.json", errors, "O")
        if "tsconfig.base.json" not in str(config.get("extends", "")):
            errors.append(f"O: packages/{dirname}/tsconfig.json must extend tsconfig.base.json")

    def visit(node: str, visiting: set[str], visited: set[str]) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for neighbor in workspace_graph.get(node, []):
            if visit(neighbor, visiting, visited):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    if workspace_graph:
        visited: set[str] = set()
        if any(visit(node, set(), visited) for node in workspace_graph):
            errors.append(f"T: workspace dependency cycle detected: {workspace_graph}")
        errors.append(f"T: M-004 shared package shells must not depend on each other yet: {workspace_graph}")

    dag = parse_dag_statuses(root / "master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml", errors)
    register = parse_register_statuses(root / "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv", errors)

    # --- Progression-aware mission state -----------------------------------
    #
    # Phase 0 must stay accepted; M-004 must be REVIEW (its own mission) or DONE
    # (accepted). Nothing later than M-004 may be unlocked until M-004 is DONE.
    # Once M-004 is DONE, later-mission progression belongs to
    # validate-master-contracts.py and is not re-asserted here.

    for mid in ("M-001", "M-002", "M-003"):
        if dag.get(mid) != "DONE":
            errors.append(f"U: DAG {mid} must be DONE, got {dag.get(mid)!r}")
        if register.get(mid) != "DONE":
            errors.append(f"U: register {mid} must be DONE, got {register.get(mid)!r}")

    m004_dag = dag.get("M-004")
    m004_register = register.get("M-004")
    accepted_states = {"REVIEW", "DONE"}
    if m004_dag not in accepted_states:
        errors.append(
            f"U: DAG M-004 must be REVIEW (its own mission) or DONE (accepted), got {m004_dag!r}"
        )
    if m004_register not in accepted_states:
        errors.append(
            f"U: register M-004 must be REVIEW (its own mission) or DONE (accepted), "
            f"got {m004_register!r}"
        )
    if m004_dag != m004_register:
        errors.append(
            f"U: M-004 status disagrees between DAG ({m004_dag!r}) and register ({m004_register!r})"
        )

    later_ids = [f"M-{index:03d}" for index in range(5, 152)]
    if m004_dag == "REVIEW" or m004_register == "REVIEW":
        # M-004 is not yet accepted: no successor mission may be unlocked.
        for mid in later_ids:
            if dag.get(mid) != "LOCKED":
                errors.append(
                    f"V: DAG {mid} must remain LOCKED while M-004 is REVIEW, got {dag.get(mid)!r}"
                )
            if register.get(mid) != "LOCKED":
                errors.append(
                    f"V: register {mid} must remain LOCKED while M-004 is REVIEW, "
                    f"got {register.get(mid)!r}"
                )
    else:
        # M-004 is accepted. Successor progression is owned by
        # validate-master-contracts.py; only DAG/register agreement is enforced.
        for mid in later_ids:
            if dag.get(mid) != register.get(mid):
                errors.append(
                    f"V: {mid} status disagrees between DAG ({dag.get(mid)!r}) and "
                    f"register ({register.get(mid)!r})"
                )

    workflow = root / ".github/workflows/repository-foundation.yml"
    if not workflow.is_file():
        errors.append("W: missing .github/workflows/repository-foundation.yml")
    else:
        text = workflow.read_text(encoding="utf-8")
        for snippet in (
            "node-version: 24.19.0",
            "corepack enable",
            'test "$(node --version)" = "v24.19.0"',
            'test "$(pnpm --version)" = "11.4.0"',
            "pnpm install --frozen-lockfile",
            "pnpm run check",
        ):
            if snippet not in text:
                errors.append(f"W: repository-foundation workflow missing {snippet!r}")

    integrity = root / ".github/workflows/master-build-system-integrity.yml"
    if not integrity.is_file():
        errors.append("W: missing master-build-system-integrity workflow")
    else:
        text = integrity.read_text(encoding="utf-8")
        for snippet in (
            "python3 scripts/validate-m004-foundation.py",
            "python3 tests/contract/test_m004_foundation.py",
        ):
            if snippet not in text:
                errors.append(f"W: integrity workflow missing {snippet!r}")

    turbo = read_json(root / "turbo.json", errors, "W")
    tasks = turbo.get("tasks") or {}
    if set(tasks) != {"build", "typecheck", "test"}:
        errors.append(f"W: turbo tasks must be build/typecheck/test only, got {sorted(tasks)}")

    if errors:
        print("M-004 foundation validation FAILED")
        for error in errors:
            print(f"  ERROR: {error}")
        print(f"Total errors: {len(errors)}")
        return 1

    print("M-004 foundation validation PASSED")
    print(f"  packages=7 lockfiles=1 mission=M-004:{m004_dag}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
