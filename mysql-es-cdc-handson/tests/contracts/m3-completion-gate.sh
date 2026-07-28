#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
for target in bootstrap-index scenario-m3 verify-m3 gate-m2-m3; do
  grep -Eq "^${target}:" "$root/Makefile" || { echo "missing target $target" >&2; exit 1; }
done
matrix="$root/scenarios/scripts/run-m3-matrix.sh"
test -f "$matrix"
for scenario in m3-consumer-restart m3-after-es-before-offset m3-bulk-partial \
  m3-duplicate-record m3-late-old-revision m3-mapping-conflict \
  m3-record-parse-dlq m3-after-dlq-before-offset m3-delete-then-old-replay; do
  grep -Fq "$scenario" "$matrix" || { echo "missing matrix scenario $scenario" >&2; exit 1; }
done
grep -Fq 'git status --porcelain --untracked-files=no' "$root/Makefile"
grep -Fq 'cdc_product_dlq_unresolved' "$root/Makefile"
grep -Fq 'cdc_record_dlq_unresolved' "$root/Makefile"
for doc in docs/02-reliable-pipeline.md docs/03-failure-model.md; do test -s "$root/$doc"; done
