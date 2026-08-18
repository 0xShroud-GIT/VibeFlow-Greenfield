#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
bin=${GITLEAKS_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/gitleaks}
[[ -x "$bin" ]] || { printf 'gitleaks binary not executable: %s\n' "$bin" >&2; exit 2; }

cd "$root"
# --all forces every reachable ref/history object into scope; --redact keeps
# detected secret values out of CI logs and evidence.
exec "$bin" git --no-banner --redact=100 --exit-code 1 --log-opts="--all" .
