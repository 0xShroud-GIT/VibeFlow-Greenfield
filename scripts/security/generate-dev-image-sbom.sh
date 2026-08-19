#!/usr/bin/env bash
set -euo pipefail

# Generate an ephemeral CycloneDX SBOM for the exact M-007 dev container image
# plus its content SHA-256. The checksum-verified binary is installed by
# scripts/security/install-ci-tool.py trivy. CI normally supplies DEV_IMAGE_INPUT
# as the same docker-save archive consumed by the vulnerability scan.

if [[ $# -ne 1 ]]; then
  printf 'usage: %s OUTPUT.cdx.json\n' "$0" >&2
  exit 2
fi
bin=${TRIVY_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/trivy}
[[ -x "$bin" ]] || { printf 'trivy binary not executable: %s\n' "$bin" >&2; exit 2; }
export TRIVY_CACHE_DIR=${TRIVY_CACHE_DIR:-${RUNNER_TEMP:-/tmp}/vibeflow-trivy-cache}
output=$1
mkdir -p "$(dirname "$output")"

args=(
  image
  --scanners vuln
  --format cyclonedx
  --output "$output"
  --no-progress
)
if [[ -n "${DEV_IMAGE_INPUT:-}" ]]; then
  [[ -f "$DEV_IMAGE_INPUT" ]] || { printf 'dev image archive missing: %s\n' "$DEV_IMAGE_INPUT" >&2; exit 2; }
  args+=(--input "$DEV_IMAGE_INPUT")
else
  args+=("${DEV_IMAGE:-vibeflow-dev:latest}")
fi
"$bin" "${args[@]}"
sha256sum "$output" | tee "${output}.sha256"
