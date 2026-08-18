#!/usr/bin/env bash
set -euo pipefail

root=$(git rev-parse --show-toplevel)
lock="$root/security/ci-toolchain.lock.json"
image=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tools"]["semgrep"]["distribution_coordinate"])' "$lock")
temp=${RUNNER_TEMP:-/tmp}/vibeflow-semgrep-fixtures
mkdir -p "$temp"

scan_json() {
  local output=$1
  shift
  if [[ -n ${SEMGREP_BIN:-} ]]; then
    "$SEMGREP_BIN" scan --config "$root/security/semgrep.yml" --severity ERROR --json \
      --quiet --no-git-ignore "$@" > "$output"
  else
    command -v docker >/dev/null || {
      printf 'docker is required for Semgrep rule tests (or set SEMGREP_BIN)\n' >&2
      return 2
    }
    local targets=() target
    for target in "$@"; do
      targets+=("${target#"$root/"}")
    done
    docker run --rm --network none -v "$root:/src:ro" -w /src "$image" \
      semgrep scan --config security/semgrep.yml --severity ERROR --json --quiet --no-git-ignore \
      "${targets[@]}" > "$output"
  fi
}

positive_json="$temp/positive.json"
negative_json="$temp/negative.json"
scan_json "$positive_json" \
  "$root/tests/security/fixtures/semgrep/positive/dangerous.py" \
  "$root/tests/security/fixtures/semgrep/positive/dangerous.ts"
scan_json "$negative_json" \
  "$root/tests/security/fixtures/semgrep/negative/safe.py" \
  "$root/tests/security/fixtures/semgrep/negative/safe.ts"
python3 - "$positive_json" "$negative_json" <<'PY'
import json
import sys

expected = {
    "vibeflow.python.dynamic-eval",
    "vibeflow.python.dynamic-exec",
    "vibeflow.python.os-system",
    "vibeflow.python.subprocess-shell-true",
    "vibeflow.javascript.dynamic-eval",
    "vibeflow.javascript.child-process-exec",
}
positive = json.load(open(sys.argv[1], encoding="utf-8"))
negative = json.load(open(sys.argv[2], encoding="utf-8"))
found = {item["check_id"].removeprefix("security.") for item in positive.get("results", [])}
if found != expected:
    raise SystemExit(f"positive fixture rule IDs differ: expected={sorted(expected)} found={sorted(found)}")
if negative.get("results"):
    raise SystemExit(f"negative fixtures produced findings: {negative['results']}")
print(f"Semgrep fixtures passed: {len(expected)} positive rule IDs; 0 negative findings.")
PY
