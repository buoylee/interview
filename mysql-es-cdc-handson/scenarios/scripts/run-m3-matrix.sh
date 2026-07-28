#!/usr/bin/env bash
set -euo pipefail

scenarios=(
  m3-consumer-restart
  m3-after-es-before-offset
  m3-bulk-partial
  m3-duplicate-record
  m3-late-old-revision
  m3-mapping-conflict
  m3-record-parse-dlq
  m3-after-dlq-before-offset
  m3-delete-then-old-replay
)

for scenario in "${scenarios[@]}"; do
  script="scenarios/scripts/run-${scenario}.sh"
  test -x "$script" || { echo "missing executable scenario: $script" >&2; exit 1; }
  echo "==> $scenario"
  "$script"
done
