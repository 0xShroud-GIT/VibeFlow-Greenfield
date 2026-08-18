#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
bin=${OSV_SCANNER_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/osv-scanner}
[[ -x "$bin" ]] || { printf 'osv-scanner binary not executable: %s\n' "$bin" >&2; exit 2; }

cd "$root"
# Source mode recursively discovers package manifests and scans their resolved
# lockfiles. No waiver/ignore file is supplied.
exec "$bin" scan source --recursive .
