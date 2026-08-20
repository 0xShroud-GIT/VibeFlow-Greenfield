#!/usr/bin/env python3
"""M-014 import/clone live integration runner (PostgreSQL 18.4).

Runs the M-014 live suites against a real PostgreSQL instance:

  * packages/persistence  src/lifecycle.live.test.ts   (DB-level authority backstops)
  * packages/project      src/import.live.test.ts      (archive import command path)
  * packages/project      src/clone.live.test.ts       (clone plan command path)

In CI (CI=true) a database is mandatory: a missing DATABASE_URL is a hard
failure, because a skipped live suite is not verification evidence. Locally the
runner reports the skip loudly and exits non-zero unless
VIBEFLOW_ALLOW_SKIPPED_LIVE=1 is set explicitly.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SUITES: tuple[tuple[str, str], ...] = (
    ("@vibeflow/persistence", "src/lifecycle.live.test.ts"),
    ("@vibeflow/project", "src/import.live.test.ts"),
    ("@vibeflow/project", "src/clone.live.test.ts"),
)


def resolve_database_url() -> str | None:
    for key in ("VIBEFLOW_DATABASE_URL", "DATABASE_URL"):
        value = os.environ.get(key)
        if value:
            return value
    return None


def main() -> int:
    database_url = resolve_database_url()
    in_ci = os.environ.get("CI") == "true"

    if not database_url:
        message = (
            "M-014 live integration requires DATABASE_URL (or VIBEFLOW_DATABASE_URL) "
            "pointing at PostgreSQL 18.4; a skipped live suite is not verification evidence."
        )
        if in_ci:
            print(f"FAIL: {message}", file=sys.stderr)
            return 1
        if os.environ.get("VIBEFLOW_ALLOW_SKIPPED_LIVE") == "1":
            print(f"SKIP (explicitly allowed locally): {message}")
            return 0
        print(f"FAIL: {message}", file=sys.stderr)
        print(
            "      set VIBEFLOW_ALLOW_SKIPPED_LIVE=1 to acknowledge a local skip.",
            file=sys.stderr,
        )
        return 1

    pnpm = shutil.which("pnpm")
    if pnpm is None:
        print("FAIL: pnpm is not on PATH", file=sys.stderr)
        return 1

    failures: list[str] = []
    for package, suite in SUITES:
        print(f"\n=== M-014 live: {package} {suite} ===", flush=True)
        result = subprocess.run(
            [pnpm, "--filter", package, "exec", "vitest", "run", suite],
            cwd=ROOT,
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"{package} {suite}")

    if failures:
        print("\nFAIL: M-014 live suites failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nPASS: M-014 live import/clone integration suites green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
