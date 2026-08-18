#!/usr/bin/env python3
"""VibeFlow dev-environment doctor (M-007).

Fast, network-free precondition check for the repository development
environment. Reports version/precondition failures without modifying the
environment (no corepack enable, no installs).

Exact toolchain authority (M-004 / H-001..H-004, H-025, H-028):
    Node.js 24.19.0, pnpm 11.4.0, TypeScript 6.0.3, Turborepo 2.10.6,
    Vitest 4.1.7, TypeBox 1.3.6.
Environment additions (M-007): python3 and git are required, corepack must be
available (pnpm is provided through the corepack path).
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_EXACT = "v24.19.0"
PNPM_EXACT = "11.4.0"


def run_tool(argv: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            argv,
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
    except FileNotFoundError:
        return 127, ""
    return completed.returncode, (completed.stdout or "").strip()


def node_version() -> str | None:
    code, out = run_tool(["node", "--version"])
    return out if code == 0 else None


def pnpm_version() -> str | None:
    code, out = run_tool(["pnpm", "--version"])
    if code == 0:
        return out
    # The corepack path provides pnpm without writing shims: `corepack pnpm`.
    code, out = run_tool(["corepack", "pnpm", "--version"])
    return out if code == 0 else None


def corepack_version() -> str | None:
    code, out = run_tool(["corepack", "--version"])
    return out if code == 0 else None


def python3_version() -> str | None:
    code, out = run_tool(["python3", "--version"])
    return out if code == 0 else None


def git_version() -> str | None:
    code, out = run_tool(["git", "--version"])
    return out if code == 0 else None


def declared_package_manager() -> str | None:
    try:
        package = json.loads((REPO_ROOT / "package.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return str(package.get("packageManager") or "").strip() or None


def main() -> int:
    failures: list[str] = []
    notes: list[str] = []

    node = node_version()
    if node == NODE_EXACT:
        notes.append(f"node {node}")
    else:
        failures.append(f"node --version must be {NODE_EXACT}, got {node!r}")

    pnpm = pnpm_version()
    if pnpm == PNPM_EXACT:
        notes.append(f"pnpm {pnpm}")
    else:
        corepack = corepack_version()
        declared = declared_package_manager()
        if corepack is None:
            failures.append("pnpm is unavailable and corepack is not on PATH")
        else:
            failures.append(
                f"pnpm --version must be {PNPM_EXACT}, got {pnpm!r} "
                f"(corepack {corepack} present; enable it with scripts/dev-bootstrap.py)"
            )
            if declared is None:
                failures.append("package.json packageManager must declare pnpm@11.4.0")

    python3 = python3_version()
    if python3:
        notes.append(f"python3 {python3}")
    else:
        failures.append("python3 is required (repository stdlib validators/tests)")

    git = git_version()
    if git:
        notes.append(f"git {git}")
    else:
        failures.append("git is required")

    print("VibeFlow dev-environment doctor (network-free)")
    for note in notes:
        print(f"  ok: {note}")
    for failure in failures:
        print(f"  FAIL: {failure}")
    if failures:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
