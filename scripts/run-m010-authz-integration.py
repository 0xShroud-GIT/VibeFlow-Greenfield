#!/usr/bin/env python3
"""Run M-010 PostgreSQL tenant/resource authorization verification deliberately.

A local developer without PostgreSQL receives an explicit non-verification
notice. CI must supply a database URL or fail; a skipped suite is never treated
as authorization evidence.
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> int:
    database_url = os.environ.get("VIBEFLOW_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        if os.environ.get("CI") == "true":
            print(
                "M-010 PostgreSQL authorization is required in CI but DATABASE_URL is absent.",
                file=sys.stderr,
            )
            return 1
        print(
            "M-010 PostgreSQL authorization NOT EXECUTED: DATABASE_URL is absent. "
            "This local skip is not verification evidence."
        )
        return 0

    completed = subprocess.run(
        [
            "pnpm",
            "--filter",
            "@vibeflow/authorization",
            "exec",
            "vitest",
            "run",
            "src/tenant.live.test.ts",
        ],
        check=False,
    )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
