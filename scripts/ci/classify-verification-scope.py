#!/usr/bin/env python3
"""Classify PR verification depth from changed paths.

The classifier is deliberately centralized and fail-closed. Known ordinary
product/evidence/mission-progression paths may take the fast path. Foundational
governance, security, contracts, native/platform, CI, and dev-environment paths
trigger the relevant deeper verification. Any unknown path triggers both deep
historical mutation replay and dev-image verification.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

ROUTINE_PROGRESSION = {
    ".ai/ACTIVE_MISSION.md",
    "README.md",
    "docs/WORKSPACE_BOOTSTRAP_STATUS.md",
    "master-build-system/10_IMPLEMENTATION/MISSION_DAG.yaml",
    "master-build-system/10_IMPLEMENTATION/MISSION_REGISTER.csv",
    "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.yaml",
    "master-build-system/01_PRODUCT/VIBEFLOW_CAPABILITY_LEDGER.csv",
}

FAST_PREFIXES = (
    "apps/",
    "services/",
    "workers/",
    "packages/",
    "adapters/",
    "evidence/",
    "docs/",
)

FOUNDATIONAL_SCRIPT_PATTERNS = (
    r"^scripts/validate-master-contracts\.py$",
    r"^scripts/validate-harvest-registry\.py$",
    r"^scripts/validate-threat-model\.py$",
    r"^scripts/validate-m004-foundation\.py$",
    r"^scripts/validate-m005-contract-codegen\.py$",
    r"^scripts/validate-m006-security-gates\.py$",
    r"^scripts/validate-m007-local-dev\.py$",
    r"^scripts/_validate_m007_core\.py$",
    r"^scripts/generate-contracts\.py$",
    r"^scripts/validate-implementation-reference-policy\.py$",
    r"^scripts/ci/classify-verification-scope\.py$",
)

FOUNDATIONAL_TEST_PATTERNS = (
    r"^tests/contract/test_m002.*\.py$",
    r"^tests/contract/test_m003.*\.py$",
    r"^tests/contract/test_m004.*\.py$",
    r"^tests/contract/test_m005.*\.py$",
    r"^tests/contract/test_m006.*\.py$",
    r"^tests/contract/test_m007.*\.py$",
    r"^tests/contract/test_implementation_reference_policy\.py$",
    r"^tests/contract/test_verification_scope_classifier\.py$",
)

DEV_IMAGE_EXACT = {
    ".nvmrc",
    ".npmrc",
    "package.json",
    "pnpm-lock.yaml",
    "pnpm-workspace.yaml",
    "turbo.json",
    "tsconfig.json",
    "tsconfig.base.json",
}


def _matches_any(path: str, patterns: tuple[str, ...]) -> bool:
    return any(re.match(pattern, path) for pattern in patterns)


def _future_mission_validator(path: str) -> bool:
    match = re.match(r"^scripts/(?:_?validate[_-]?m|validate-m)(\d{3})", path)
    return bool(match and int(match.group(1)) >= 8)


def _future_mission_test(path: str) -> bool:
    match = re.match(r"^tests/contract/test_m(\d{3})", path)
    return bool(match and int(match.group(1)) >= 8)


def _native_or_platform(path: str) -> bool:
    parts = path.split("/")
    if any(part in {"android", "ios"} for part in parts):
        return True
    name = parts[-1]
    return bool(
        name in {"app.json", "eas.json", "gradle.properties", "Podfile", "Podfile.lock"}
        or name.startswith("app.config.")
        or name.startswith("build.gradle")
        or name.startswith("settings.gradle")
    )


def _integrity_sensitive(path: str) -> bool:
    if path in ROUTINE_PROGRESSION:
        return False
    if path.startswith(".github/workflows/"):
        return True
    if path in {"AGENTS.md", ".ai/INDEX.yaml", ".ai/CONTEXT_POLICY.md"}:
        return True
    if path.startswith("master-build-system/"):
        return True
    if path.startswith("security/") or path.startswith("infrastructure/"):
        return True
    if path.startswith("tests/security/"):
        return True
    if _matches_any(path, FOUNDATIONAL_TEST_PATTERNS):
        return True
    if path.startswith("packages/contracts/"):
        return True
    if _native_or_platform(path):
        return True
    if _matches_any(path, FOUNDATIONAL_SCRIPT_PATTERNS):
        return True
    if path.startswith("scripts/security/") or path == "scripts/repo-sanitize.sh":
        return True
    if path in DEV_IMAGE_EXACT or path.startswith("tsconfig."):
        return True
    return False


def _dev_image_sensitive(path: str) -> bool:
    if path.startswith(".devcontainer/") or path.startswith("infrastructure/dev/"):
        return True
    if path.startswith(".github/workflows/"):
        return True
    if path in DEV_IMAGE_EXACT or path.startswith("tsconfig."):
        return True
    if path.startswith("scripts/dev-"):
        return True
    if path in {
        "scripts/validate-m007-local-dev.py",
        "scripts/_validate_m007_core.py",
        "tests/contract/test_m007_local_dev.py",
        "scripts/security/scan-dev-image.sh",
        "scripts/security/generate-dev-image-sbom.sh",
        "scripts/ci/classify-verification-scope.py",
    }:
        return True
    return False


def _known_fast(path: str) -> bool:
    if path in ROUTINE_PROGRESSION:
        return True
    if _future_mission_validator(path) or _future_mission_test(path):
        return True
    if any(path.startswith(prefix) for prefix in FAST_PREFIXES):
        return True
    return False


@dataclass(frozen=True)
class Classification:
    full_mutations: bool
    dev_image: bool
    reasons: tuple[str, ...]


def classify_paths(paths: list[str]) -> Classification:
    full = False
    dev = False
    reasons: list[str] = []
    for raw in paths:
        path = raw.strip().replace("\\", "/")
        if not path:
            continue
        integrity = _integrity_sensitive(path)
        image = _dev_image_sensitive(path)
        known_fast = _known_fast(path)
        if integrity:
            full = True
            reasons.append(f"integrity:{path}")
        if image:
            dev = True
            reasons.append(f"dev-image:{path}")
        if not integrity and not image and not known_fast:
            full = True
            dev = True
            reasons.append(f"unknown-fail-closed:{path}")
    return Classification(full, dev, tuple(sorted(set(reasons))))


def git_changed_paths(base: str, head: str, root: Path = ROOT) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "diff", "--name-only", "--no-renames", f"{base}...{head}"],
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git diff failed")
    return [line for line in result.stdout.splitlines() if line.strip()]


def _emit(result: Classification, github_output: Path | None, as_json: bool) -> None:
    payload = {
        "full_mutations": result.full_mutations,
        "dev_image": result.dev_image,
        "reasons": list(result.reasons),
    }
    if as_json:
        print(json.dumps(payload, sort_keys=True))
    else:
        print(f"full_mutations={'true' if result.full_mutations else 'false'}")
        print(f"dev_image={'true' if result.dev_image else 'false'}")
        print("reasons=" + (";".join(result.reasons) if result.reasons else "ordinary-fast-path"))
    if github_output is not None:
        with github_output.open("a", encoding="utf-8") as handle:
            handle.write(f"full_mutations={'true' if result.full_mutations else 'false'}\n")
            handle.write(f"dev_image={'true' if result.dev_image else 'false'}\n")
            handle.write("reasons=" + (";".join(result.reasons) if result.reasons else "ordinary-fast-path") + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Classify VibeFlow verification scope")
    parser.add_argument("--base")
    parser.add_argument("--head", default="HEAD")
    parser.add_argument("--path", action="append", default=[])
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    if args.path:
        result = classify_paths(args.path)
    elif not args.base:
        result = Classification(True, True, ("missing-base-fail-closed",))
    else:
        try:
            paths = git_changed_paths(args.base, args.head)
        except Exception as exc:
            result = Classification(True, True, (f"classification-failed:{type(exc).__name__}",))
        else:
            result = classify_paths(paths)
    _emit(result, args.github_output, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
