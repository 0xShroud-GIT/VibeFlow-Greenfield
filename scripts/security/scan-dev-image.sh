#!/usr/bin/env bash
set -euo pipefail

# Scan the exact M-007 dev container image with the locked Trivy distribution.
# CI-only: requires the built `vibeflow-dev:latest` image (devcontainers/ci
# with imageName `vibeflow-dev` tags the built image `vibeflow-dev:latest`)
# and the checksum-verified trivy binary installed by
# scripts/security/install-ci-tool.py trivy.
# Thresholds intentionally mirror the M-006 repository scan: actionable
# (fixable) HIGH/CRITICAL findings fail. The image is not weakened to pass.

bin=${TRIVY_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/trivy}
[[ -x "$bin" ]] || { printf 'trivy binary not executable: %s\n' "$bin" >&2; exit 2; }
export TRIVY_CACHE_DIR=${TRIVY_CACHE_DIR:-${RUNNER_TEMP:-/tmp}/vibeflow-trivy-cache}
image=${DEV_IMAGE:-vibeflow-dev:latest}

exec "$bin" image \
  --scanners vuln,misconfig \
  --severity HIGH,CRITICAL \
  --ignore-unfixed \
  --exit-code 1 \
  --no-progress \
  "$image"
