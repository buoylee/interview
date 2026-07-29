#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
scanner="$project_root/tests/contracts/no-evidence-secrets.sh"
fixtures="$project_root/tests/fixtures/m6/secrets"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

test -x "$scanner" || { echo 'missing evidence secret scanner' >&2; exit 1; }
for fixture in "$fixtures"/reject-*; do
  diagnostic="$tmp/$(basename "$fixture").txt"
  if bash "$scanner" "$fixture" >"$diagnostic" 2>&1; then
    echo "secret fixture accepted: $(basename "$fixture")" >&2
    exit 1
  fi
  grep -F "$(basename "$fixture")" "$diagnostic" >/dev/null
  test "$(wc -c <"$diagnostic" | tr -d ' ')" -le 512 || { echo 'secret diagnostic is unbounded' >&2; exit 1; }
  if grep -F 'value-do-not-echo' "$diagnostic" >/dev/null; then
    echo 'secret value leaked into diagnostic' >&2
    exit 1
  fi
done
for fixture in "$fixtures"/allow-*; do bash "$scanner" "$fixture" >/dev/null; done

printf 'M6 evidence secret tamper negatives passed\n'
