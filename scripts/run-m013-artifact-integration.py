#!/usr/bin/env python3
"""Run M-013 PostgreSQL Artifact/ArtifactRelation authority verification without treating a skip as evidence."""

from __future__ import annotations

import os
import subprocess
import sys


def run(filter_name: str, test_file: str) -> int:
    print(f"Running {filter_name} {test_file}...")
    result = subprocess.run(
        ["pnpm", "--filter", filter_name, "exec", "vitest", "run", test_file],
        check=False,
    )
    return result.returncode


def main() -> int:
    database_url = os.environ.get("VIBEFLOW_DATABASE_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        if os.environ.get("CI") == "true":
            print(
                "M-013 PostgreSQL Artifact/ArtifactRelation authority is required in CI but DATABASE_URL is absent.",
                file=sys.stderr,
            )
            return 1
        print(
            "M-013 PostgreSQL Artifact/ArtifactRelation authority NOT EXECUTED: DATABASE_URL is absent. "
            "This local skip is not verification evidence."
        )
        return 0

    rc = 0
    rc |= run("@vibeflow/persistence", "src/artifact.live.test.ts")
    if rc != 0:
        return rc
    rc |= run("@vibeflow/authorization", "src/artifact.live.test.ts")
    if rc != 0:
        return rc
    rc |= run("@vibeflow/project", "src/artifact.live.test.ts")
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
