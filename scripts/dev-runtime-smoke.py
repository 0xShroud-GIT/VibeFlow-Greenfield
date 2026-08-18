#!/usr/bin/env python3
"""VibeFlow dev-environment runtime smoke (M-007).

Proves the exact dev environment runtime from inside the built dev container:

    node --version  == v24.19.0
    pnpm --version  == 11.4.0   (pnpm on PATH, else the corepack path)
    python3 --version works (>= 3.9)
    git --version works

The script is stdlib-only, invokes subprocesses without shell=True, and can
also run on a host that reproduces the ratified toolchain.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_EXACT = "v24.19.0"
PNPM_EXACT = "11.4.0"
PYTHON_FLOOR = (3, 9)


def run(argv: list[str]) -> tuple[int, str]:
    try:
        completed = subprocess.run(
            argv,
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except FileNotFoundError:
        return 127, ""
    return completed.returncode, (completed.stdout or "").strip()


def pnpm_version() -> str:
    code, out = run(["pnpm", "--version"])
    if code == 0:
        return out
    code, out = run(["corepack", "pnpm", "--version"])
    if code == 0:
        return out
    return ""


def parse_python(triple: str) -> tuple[int, ...]:
    parts = triple.replace("Python ", "").split(".")
    digits: list[int] = []
    for part in parts:
        digits_str = "".join(ch for ch in part if ch.isdigit())
        if not digits_str:
            break
        digits.append(int(digits_str))
    return tuple(digits[:3])


def main() -> int:
    failures: list[str] = []
    results: list[str] = []

    code, node = run(["node", "--version"])
    if code == 0 and node == NODE_EXACT:
        results.append(f"node {node}")
    else:
        failures.append(f"node --version must be {NODE_EXACT}, got {node!r} (rc={code})")

    pnpm = pnpm_version()
    if pnpm == PNPM_EXACT:
        results.append(f"pnpm {pnpm}")
    else:
        failures.append(f"pnpm --version must be {PNPM_EXACT}, got {pnpm!r}")

    code, py = run(["python3", "--version"])
    version = parse_python(py)
    if code == 0 and version and version >= PYTHON_FLOOR:
        results.append(f"python3 {py}")
    else:
        failures.append(f"python3 must work and be >= 3.9, got {py!r} (rc={code})")

    code, git = run(["git", "--version"])
    if code == 0 and git:
        results.append(f"git {git}")
    else:
        failures.append(f"git must work, got {git!r} (rc={code})")

    print("VibeFlow dev-environment runtime smoke")
    for result in results:
        print(f"  ok: {result}")
    for failure in failures:
        print(f"  FAIL: {failure}")
    if failures:
        print("RESULT: FAIL")
        return 1
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
