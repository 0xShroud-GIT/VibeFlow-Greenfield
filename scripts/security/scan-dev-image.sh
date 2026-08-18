#!/usr/bin/env bash
set -euo pipefail

# Scan the exact M-007 dev container image with the locked Trivy distribution.
# CI normally supplies DEV_IMAGE_INPUT as a docker-save archive so the scan and
# SBOM consume the same content-addressed bytes. DEV_IMAGE remains a local-only
# fallback for direct invocation.

bin=${TRIVY_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/trivy}
[[ -x "$bin" ]] || { printf 'trivy binary not executable: %s\n' "$bin" >&2; exit 2; }
export TRIVY_CACHE_DIR=${TRIVY_CACHE_DIR:-${RUNNER_TEMP:-/tmp}/vibeflow-trivy-cache}

args=(
  image
  --scanners vuln,misconfig
  --severity HIGH,CRITICAL
  --ignore-unfixed
  --exit-code 1
  --no-progress
)
if [[ -n "${DEV_IMAGE_INPUT:-}" ]]; then
  [[ -f "$DEV_IMAGE_INPUT" ]] || { printf 'dev image archive missing: %s\n' "$DEV_IMAGE_INPUT" >&2; exit 2; }
  args+=(--input "$DEV_IMAGE_INPUT")
else
  args+=("${DEV_IMAGE:-vibeflow-dev:latest}")
fi
exec "$bin" "${args[@]}"
