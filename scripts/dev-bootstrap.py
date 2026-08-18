#!/usr/bin/env python3
"""VibeFlow repository development-environment bootstrap (M-007).

Single repository-owned bootstrap command that:

1. verifies required local/runtime tools (node, corepack/pnpm, python3, git);
2. enables the existing Corepack path (falling back to a user-writable
   install directory when the system prefix is not writable, e.g. the
   non-root `node` user inside the M-007 dev container);
3. verifies the exact Node.js 24.19.0 and pnpm 11.4.0 versions;
4. executes `pnpm install --frozen-lockfile` (lockfile bypass is a hard
   failure);
5. runs the repository's existing full check path (`pnpm run check`).

Stdlib-only by policy: every subprocess is invoked with an explicit argv list
and never with shell=True / string-shell execution.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
NODE_EXACT = "v24.19.0"
PNPM_EXACT = "11.4.0"


def run(argv: list[str], *, cwd: Path = REPO_ROOT) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        argv,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        timeout=600,
        check=False,
    )


def require_tool(argv: list[str], what: str) -> str:
    completed = run(argv)
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise SystemExit(f"bootstrap: {what} unavailable ({' '.join(argv)}): {detail}")
    return (completed.stdout or "").strip()


def enable_corepack() -> None:
    """Enable the corepack shim path without shell execution."""
    completed = run(["corepack", "enable"])
    if completed.returncode == 0:
        print("  ok: corepack enabled (system path)")
        return
    # Non-root fallback: install shims into a user-writable directory and add
    # it to PATH for the remainder of this process and child processes.
    shim_dir = Path.home() / ".local" / "bin"
    shim_dir.mkdir(parents=True, exist_ok=True)
    completed = run(["corepack", "enable", "--install-directory", str(shim_dir)])
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise SystemExit(f"bootstrap: corepack enable failed: {detail}")
    os.environ["PATH"] = f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
    print(f"  ok: corepack enabled (user path {shim_dir})")


def check_version(tool: str, argv: list[str], expected: str) -> None:
    actual = (run(argv).stdout or "").strip()
    if actual != expected:
        raise SystemExit(
            f"bootstrap: {tool} version mismatch: expected {expected!r}, got {actual!r}"
        )
    print(f"  ok: {tool} {actual}")


def main() -> int:
    print("VibeFlow dev-environment bootstrap")
    print("  step 1: verifying required tools")
    require_tool(["node", "--version"], "node")
    python3 = require_tool(["python3", "--version"], "python3")
    print(f"  ok: python3 {python3}")
    git = require_tool(["git", "--version"], "git")
    print(f"  ok: git {git}")

    print("  step 2: enabling the corepack path")
    enable_corepack()

    print("  step 3: verifying exact Node and pnpm versions")
    check_version("node", ["node", "--version"], NODE_EXACT)
    check_version("pnpm", ["pnpm", "--version"], PNPM_EXACT)

    print("  step 4: pnpm install --frozen-lockfile")
    install = run(["pnpm", "install", "--frozen-lockfile"])
    if install.returncode != 0:
        detail = (install.stderr or install.stdout or "").strip()
        raise SystemExit(f"bootstrap: pnpm install --frozen-lockfile failed: {detail}")
    print("  ok: frozen-lockfile install completed")

    print("  step 5: pnpm run check")
    check = run(["pnpm", "run", "check"])
    if check.returncode != 0:
        detail = (check.stderr or check.stdout or "").strip()
        raise SystemExit(f"bootstrap: pnpm run check failed: {detail}")
    print("RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
