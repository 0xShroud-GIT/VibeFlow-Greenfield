#!/usr/bin/env python3
"""M-015 project lifecycle E2E live integration runner (PostgreSQL 18.4).

Runs the M-015 live suites against a real PostgreSQL instance:

  * packages/project      src/profile.live.test.ts
  * packages/project      src/capability-profile.live.test.ts
  * packages/project      src/overview.live.test.ts

In CI (CI=true) a database is mandatory.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

SUITES: tuple[tuple[str, str], ...] = (
    ("@vibeflow/project", "src/profile.live.test.ts"),
    ("@vibeflow/project", "src/capability-profile.live.test.ts"),
    ("@vibeflow/project", "src/overview.live.test.ts"),
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
        if in_ci:
            print(
                "M-015 PostgreSQL project lifecycle E2E tests require DATABASE_URL in CI",
                file=sys.stderr,
            )
            return 1
        print(
            "M-015 PostgreSQL lifecycle E2E NOT EXECUTED: DATABASE_URL is absent. "
            "This local skip is not verification evidence."
        )
        return 0

    pnpm = shutil.which("pnpm")
    if pnpm is None:
        print("FAIL: pnpm is not on PATH", file=sys.stderr)
        return 1

    failures: list[str] = []
    for package, suite in SUITES:
        print(f"\n=== M-015 live: {package} {suite} ===", flush=True)
        result = subprocess.run(
            [pnpm, "--filter", package, "exec", "vitest", "run", suite],
            cwd=ROOT,
            check=False,
        )
        if result.returncode != 0:
            failures.append(f"{package} {suite}")

    if failures:
        print("\nFAIL: M-015 live suites failed:", file=sys.stderr)
        for failure in failures:
            print(f"  - {failure}", file=sys.stderr)
        return 1

    print("\nPASS: M-015 live project lifecycle E2E suites green.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
