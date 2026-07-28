#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
document="${1:-docs/01-canal-boundary.md}"
test -s "$document"

grep -Fq 'CDC/incremental-subscription component, not an end-to-end final-consistency solution' "$document"
if jq -e '.bulk_partial_failure_observed == false' \
    evidence/m1/m1-bulk-partial/result.json >/dev/null; then
  grep -Fq 'did **not** produce the intended Bulk partial failure' "$document"
  grep -Fq '`1000` was observed in Elasticsearch as `-24`' "$document"
else
  grep -Fq 'did produce a genuine Bulk partial failure' "$document"
fi
grep -Fq '`updated_at_matches_source` is `false`' "$document"
grep -Fq '`invalid_source_value_preserved_before_fix`' "$document"
grep -Fq '`etl_required`' "$document"
grep -Fq '`etl_invoked`' "$document"
grep -Fq '`etl_repair_succeeded`' "$document"
grep -Fq 'revision fencing' "$document"
grep -Fq 'per-Bulk-item settlement contract' "$document"
grep -Fq 'durable DLQ' "$document"
grep -Fq 'independent reconciliation/repair loop' "$document"
grep -Fq 'binlog-gap classification' "$document"
grep -Fq 'rebuild/cutover workflow' "$document"
grep -Fq 'generated locally and intentionally ignored by Git' "$document"
grep -Fq 'make scenario-m1' "$document"
grep -Fq 'make verify-m1' "$document"
grep -Fq 'No M1 result claims exactly-once processing or MySQL-to-Elasticsearch final consistency' "$document"

manifest=$(mktemp "${TMPDIR:-/tmp}/m1-claim-manifest-assert.XXXXXX")
trap 'rm -f "$manifest"' EXIT
bash scenarios/scripts/build-m1-claim-manifest.sh evidence/m1 >"$manifest"
digest=$(sha256sum "$manifest" | awk '{print $1}')
grep -Fq "$digest" "$document"

for result in \
  evidence/m1/m1-basic/result.json \
  evidence/m1/m1-restart/result.json \
  evidence/m1/m1-hard-delete/result.json \
  evidence/m1/m1-bulk-partial/result.json
do
  digest=$(sha256sum "$result" | awk '{print $1}')
  if grep -Fq "$digest" "$document"; then
    echo "document embeds volatile full-result digest: $result" >&2
    exit 1
  fi
done
