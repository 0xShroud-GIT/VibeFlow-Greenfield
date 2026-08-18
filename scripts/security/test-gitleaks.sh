#!/usr/bin/env bash
set -euo pipefail

bin=${GITLEAKS_BIN:-${RUNNER_TEMP:-/tmp}/vibeflow-security-tools/gitleaks}
[[ -x "$bin" ]] || { printf 'gitleaks binary not executable: %s\n' "$bin" >&2; exit 2; }
lock=$(git rev-parse --show-toplevel)/security/ci-toolchain.lock.json
expected_version=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["tools"]["gitleaks"]["version"])' "$lock")
actual_version=$($bin version)
[[ "$actual_version" == *"$expected_version"* ]] || {
  printf 'gitleaks version mismatch: expected %s, got %s\n' "$expected_version" "$actual_version" >&2
  exit 1
}

temp=$(mktemp -d "${RUNNER_TEMP:-/tmp}/vibeflow-gitleaks-fixtures.XXXXXX")
trap 'rm -rf "$temp"' EXIT
init_repo() {
  local repo=$1
  git init -q "$repo"
  git -C "$repo" config user.name 'VibeFlow Security Fixture'
  git -C "$repo" config user.email 'security-fixture@example.invalid'
}

negative="$temp/negative"
init_repo "$negative"
printf '%s\n' 'github_token=not-a-token' 'access_key=AKIA_NOT_REAL' > "$negative/config.txt"
git -C "$negative" add config.txt
git -C "$negative" commit -q -m 'negative fixture'
"$bin" git --no-banner --redact=100 --exit-code 1 --log-opts="--all" "$negative" \
  > "$temp/negative.log" 2>&1

positive="$temp/positive"
init_repo "$positive"
prefix=$(printf '%s%s' 'g' 'hp_')
payload=$(printf '%s%s' 'A1b2C3d4E5f6G7h8' 'I9j0K1l2M3n4O5p6Q7r8')
token="${prefix}${payload}"
printf 'github_token=%s\n' "$token" > "$positive/config.txt"
git -C "$positive" add config.txt
git -C "$positive" commit -q -m 'positive fixture'
set +e
"$bin" git --no-banner --redact=100 --exit-code 1 --log-opts="--all" "$positive" \
  > "$temp/positive.log" 2>&1
positive_rc=$?
set -e
[[ $positive_rc -eq 1 ]] || {
  printf 'positive Gitleaks fixture expected finding exit 1, got %s\n' "$positive_rc" >&2
  cat "$temp/positive.log" >&2
  exit 1
}
if grep -Fq "$token" "$temp/positive.log"; then
  printf 'positive Gitleaks fixture leaked the generated token into logs\n' >&2
  exit 1
fi
printf 'Gitleaks fixtures passed: exact version %s; negative clean; positive detected and redacted.\n' "$expected_version"
