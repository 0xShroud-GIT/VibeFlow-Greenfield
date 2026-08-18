#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
lock="$root/security/ci-toolchain.lock.json"
image=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tools"]["semgrep"]["distribution_coordinate"])' "$lock")

if [[ -n ${SEMGREP_BIN:-} ]]; then
  exec "$SEMGREP_BIN" scan --config "$root/security/semgrep.yml" --error --severity ERROR \
    --exclude 'tests/security/fixtures/semgrep/positive/**' "$root"
fi

command -v docker >/dev/null || {
  printf 'docker is required for the digest-pinned Semgrep distribution (or set SEMGREP_BIN for local verification)\n' >&2
  exit 2
}
exec docker run --rm --network none \
  -v "$root:/src:ro" -w /src "$image" \
  semgrep scan --config security/semgrep.yml --error --severity ERROR \
  --exclude 'tests/security/fixtures/semgrep/positive/**' .
