#!/usr/bin/env bash
set -euo pipefail

# Generate an ephemeral CycloneDX SBOM for the exact M-007 dev container image
# (separate from the repository dependency SBOM) plus its content SHA-256.
# CI-only: requires the built `vibeflow-dev:smoke` image and the checksum-
# verified trivy binary installed by scripts/security/install-ci-tool.py trivy.

if [[ $# -ne 1 ]]; then
  printf 'usage: %s OUTPUT.cdx.json\n' "$0" >&2
  exit 2
fi
bin=${TRIVY_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/trivy}
[[ -x "$bin" ]] || { printf 'trivy binary not executable: %s\n' "$bin" >&2; exit 2; }
export TRIVY_CACHE_DIR=${TRIVY_CACHE_DIR:-${RUNNER_TEMP:-/tmp}/vibeflow-trivy-cache}
output=$1
image=${DEV_IMAGE:-vibeflow-dev:smoke}
mkdir -p "$(dirname "$output")"

"$bin" image \
  --scanners vuln \
  --format cyclonedx \
  --output "$output" \
  --no-progress \
  "$image"
sha256sum "$output" | tee "${output}.sha256"
