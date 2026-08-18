#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
bin=${TRIVY_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/trivy}
[[ -x "$bin" ]] || { printf 'trivy binary not executable: %s\n' "$bin" >&2; exit 2; }
export TRIVY_CACHE_DIR=${TRIVY_CACHE_DIR:-${RUNNER_TEMP:-/tmp}/vibeflow-trivy-cache}

cd "$root"
# HIGH/CRITICAL findings with an available remediation are actionable and fail.
# The filesystem target also activates supported Dockerfile/IaC config checks
# whenever those files appear. There is no product image in M-006.
exec "$bin" filesystem \
  --scanners vuln,misconfig \
  --include-dev-deps \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --exit-code 1 \
  --no-progress \
  .
