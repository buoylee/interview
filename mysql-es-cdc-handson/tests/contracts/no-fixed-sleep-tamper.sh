#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
scanner="$project_root/tests/contracts/no-fixed-sleep.sh"
fixtures="$project_root/tests/fixtures/m6/fixed-sleep"

test -x "$scanner" || { echo 'missing fixed-sleep scanner' >&2; exit 1; }
for fixture in "$fixtures"/reject-*; do
  if bash "$scanner" "$fixture" >/dev/null 2>&1; then
    echo "fixed-sleep fixture accepted: $(basename "$fixture")" >&2
    exit 1
  fi
done
for fixture in "$fixtures"/allow-* "$fixtures"/allowed/wait-condition.sh; do
  bash "$scanner" "$fixture" >/dev/null
done

printf 'M6 fixed-sleep tamper negatives passed\n'
