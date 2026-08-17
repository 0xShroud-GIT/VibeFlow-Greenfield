#!/usr/bin/env bash
set -euo pipefail

fail=0
max_bytes=$((10 * 1024 * 1024))

report_bad_path() {
  printf 'SANITATION ERROR: forbidden tracked path: %s\n' "$1" >&2
  fail=1
}

while IFS= read -r -d '' path; do
  base=${path##*/}

  case "$path" in
    .env|*/.env|.env.*|*/.env.*)
      case "$path" in
        .env.example|*/.env.example|.env.*.example|*/.env.*.example) ;;
        *) report_bad_path "$path" ;;
      esac
      ;;
    *.pem|*.key|*.p8|*.p12|*.pfx|*.jks|*.keystore|*.mobileprovision|*.kdbx)
      report_bad_path "$path"
      ;;
    *.db|*.db-journal|*.db-shm|*.db-wal|*.sqlite|*.sqlite3|*.log|*.apk|*.aab|*.ipa|*.xcarchive|*.pyc)
      report_bad_path "$path"
      ;;
    node_modules/*|*/node_modules/*|dist/*|*/dist/*|build/*|*/build/*|out/*|*/out/*|coverage/*|*/coverage/*|.expo/*|*/.expo/*|.next/*|*/.next/*|.turbo/*|*/.turbo/*|.cache/*|*/.cache/*|.parcel-cache/*|*/.parcel-cache/*|.vite/*|*/.vite/*|storybook-static/*|*/storybook-static/*|.venv/*|*/.venv/*|venv/*|*/venv/*|__pycache__/*|*/__pycache__/*|.pytest_cache/*|*/.pytest_cache/*|.mypy_cache/*|*/.mypy_cache/*|.ruff_cache/*|*/.ruff_cache/*|.gradle/*|*/.gradle/*|.cxx/*|*/.cxx/*|DerivedData/*|*/DerivedData/*|Pods/*|*/Pods/*|logs/*|*/logs/*|tmp/*|*/tmp/*|.tmp/*|*/.tmp/*|pgdata/*|*/pgdata/*|.postgres/*|*/.postgres/*|.idea/*|*/.idea/*|.vscode/*|*/.vscode/*)
      report_bad_path "$path"
      ;;
  esac

  case "$base" in
    .DS_Store|Thumbs.db|npm-debug.log*|yarn-debug.log*|yarn-error.log*|pnpm-debug.log*|*.swp|*.swo|*~)
      report_bad_path "$path"
      ;;
  esac

  if [[ -f "$path" ]]; then
    bytes=$(wc -c < "$path")
    if (( bytes > max_bytes )); then
      printf 'SANITATION ERROR: tracked file exceeds 10 MiB: %s (%s bytes)\n' "$path" "$bytes" >&2
      fail=1
    fi
  fi
done < <(git ls-files -z)

secret_regex='-----BEGIN( [A-Z0-9]+)? PRIVATE KEY-----|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{50,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{35}|sk-(proj-)?[A-Za-z0-9_-]{24,}'

if git grep -IEn "$secret_regex" -- . ':!scripts/repo-sanitize.sh'; then
  printf 'SANITATION ERROR: possible high-confidence credential material detected.\n' >&2
  fail=1
fi

if (( fail != 0 )); then
  exit 1
fi

printf 'Repository sanitation checks passed.\n'
