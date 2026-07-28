#!/usr/bin/env bash
set -euo pipefail

fixture="$(mktemp -d)"
trap 'rm -rf "$fixture"' EXIT
printf '{"unresolved":1}\n' >"$fixture/first-bad.json"
printf '{"unresolved":0}\n' >"$fixture/second-good.json"

if bash tests/contracts/assert-m4-dlq.sh "$fixture/first-bad.json" "$fixture/second-good.json"; then
  echo "DLQ assertion accepted a bad first input" >&2
  exit 1
fi
bash tests/contracts/assert-m4-dlq.sh "$fixture/second-good.json" "$fixture/second-good.json"
echo "M4 DLQ tamper contract passed"
