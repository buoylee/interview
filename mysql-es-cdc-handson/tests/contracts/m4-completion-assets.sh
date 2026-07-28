#!/usr/bin/env bash
set -euo pipefail

scenario=scenarios/scripts/run-m4-reconciliation.sh
definition=scenarios/definitions/m4-consumer-projection-bug.json
e2e=tests/end-to-end/m4-reconciliation.sh
doc=docs/04-reconciliation.md

for file in "$scenario" "$definition" "$e2e" "$doc"; do
  test -s "$file" || { echo "missing Task 6 asset: $file" >&2; exit 1; }
done

for case_name in \
  m4-missing-document \
  m4-extra-document \
  m4-modified-field-same-revision \
  m4-stale-document \
  m4-tombstone-mismatch \
  m4-source-moves-during-scan \
  m4-consumer-projection-bug; do
  grep -Fq "$case_name" "$scenario" || {
    echo "matrix case absent: $case_name" >&2
    exit 1
  }
done

jq -e '
  .scenario_id == "m4-consumer-projection-bug"
  and .seed == "baseline-v1"
  and .fault == "CATEGORY_NAME_FROM_ID"
  and .expected_difference == {
    "productId":1001,"type":"MODIFIED","field":"category_name"
  }
  and .expected_state_before_repair == "DEGRADED"
  and .expected_state_after_repair == "HEALTHY"
' "$definition" >/dev/null

grep -Eq '^reconcile:' Makefile
grep -Eq '^scenario-m4:' Makefile
grep -Eq '^verify-m4:' Makefile
grep -Fq 'MySQL is the fact source' "$doc"
grep -Fq 'consumer-only mapping defect remains visible' "$doc"
grep -Fq 'external_gte' "$doc"
grep -Fq 'Confirmed log gaps require M5 rebuild' "$doc"

echo "M4 completion assets contract passed"
