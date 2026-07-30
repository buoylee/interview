#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

for script in m6-collectors-retention.sh m6-retention-gap.sh; do
  output=$(mktemp "${TMPDIR:-/tmp}/m6-live-prerequisite.XXXXXX")
  set +e
  env -u MYSQL_PWD bash "tests/contracts/$script" >"$output" 2>&1
  rc=$?
  set -e
  if test "$rc" -ne 64; then
    echo "$script did not fail closed without MYSQL_PWD: exit $rc" >&2
    rm -f "$output"
    exit 1
  fi
  grep -Fq 'MYSQL_PWD required' "$output"
  rm -f "$output"
done

echo 'M6 live contract prerequisite failures are explicit'
