#!/usr/bin/env python3
"""Run M-011 PostgreSQL audit verification without treating a skip as evidence."""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    database_url = os.environ.get("VIBEFLOW_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        if os.environ.get("CI") == "true":
            print("M-011 PostgreSQL audit is required in CI but DATABASE_URL is absent.", file=sys.stderr)
            return 1
        print(
            "M-011 PostgreSQL audit NOT EXECUTED: DATABASE_URL is absent. "
            "This local skip is not verification evidence."
        )
        return 0
    return subprocess.run(
        ["pnpm", "--filter", "@vibeflow/audit", "exec", "vitest", "run", "src/audit.live.test.ts"],
        check=False,
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
