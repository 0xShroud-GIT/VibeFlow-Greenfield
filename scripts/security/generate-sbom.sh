#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 1 ]]; then
  printf 'usage: %s OUTPUT.cdx.json\n' "$0" >&2
  exit 2
fi
root=$(git rev-parse --show-toplevel)
bin=${TRIVY_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/trivy}
[[ -x "$bin" ]] || { printf 'trivy binary not executable: %s\n' "$bin" >&2; exit 2; }
export TRIVY_CACHE_DIR=${TRIVY_CACHE_DIR:-${RUNNER_TEMP:-/tmp}/vibeflow-trivy-cache}
output=$1
mkdir -p "$(dirname "$output")"

cd "$root"
"$bin" filesystem --scanners vuln --format cyclonedx --output "$output" --no-progress .
sha256sum "$output" | tee "${output}.sha256"
