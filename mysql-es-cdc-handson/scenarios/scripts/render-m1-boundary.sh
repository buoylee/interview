#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
evidence_root="${M1_EVIDENCE_ROOT:-evidence/m1}"
output="${M1_BOUNDARY_OUTPUT:-docs/01-canal-boundary.md}"

bash scenarios/scripts/assert-m1-evidence.sh "$evidence_root/m1-basic"
bash scenarios/scripts/assert-m1-restart-evidence.sh "$evidence_root/m1-restart"
bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$evidence_root/m1-hard-delete"
bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh \
  "$evidence_root/m1-bulk-partial"

basic="$evidence_root/m1-basic/result.json"
restart="$evidence_root/m1-restart/result.json"
hard_delete="$evidence_root/m1-hard-delete/result.json"
partial="$evidence_root/m1-bulk-partial/result.json"

sha() {
  sha256sum "$1" | awk '{print $1}'
}

basic_result=$(jq -r '.result' "$basic")
basic_gap=$(jq -r '.updated_at_matches_source' "$basic")
restart_result=$(jq -r '.result' "$restart")
hard_delete_result=$(jq -r '.result' "$hard_delete")
bulk_failure=$(jq -r '.bulk_partial_failure_observed' "$partial")
error_proven=$(jq -r '.current_run_error_proven' "$partial")
valid=$(jq -r '.valid_item_applied' "$partial")
invalid=$(jq -r '.invalid_item_applied_before_mapping_fix' "$partial")
value_preserved=$(jq -r '.invalid_source_value_preserved_before_fix' "$partial")
source_price=$(jq -r '.captured_values.invalid_source_price_cents' "$partial")
target_price=$(jq -r '.captured_values.invalid_target_price_before_fix' "$partial")
later=$(jq -r '.later_batch_applied_before_mapping_fix' "$partial")
retried=$(jq -r '.invalid_item_retried_after_mapping_fix' "$partial")
etl_required=$(jq -r '.etl_required' "$partial")
etl_invoked=$(jq -r '.etl_invoked' "$partial")
etl_succeeded=$(jq -r '.etl_repair_succeeded' "$partial")

temporary=$(mktemp "${output}.tmp.XXXXXX")
trap 'rm -f "$temporary"' EXIT
{
  printf '%s\n' '# Canal and Adapter evidence boundary'
  printf '%s\n' '' '## Verdict'
  printf '%s\n' \
    'Canal captures and parses committed MySQL binlog changes and delivers incremental row-change data. It is a CDC/incremental-subscription component, not an end-to-end final-consistency solution.'
  printf '%s\n' \
    'This pinned official Canal Adapter 1.1.8 run did **not** produce the intended Bulk partial failure: the byte-mapped source value `1000` was observed in Elasticsearch as `-24`. This is an observed coercion boundary, not a successful poison-item experiment and not a guarantee.'

  printf '%s\n' '' '## Pinned observed results'
  printf -- '- `m1-basic.result`: `%s`; `updated_at_matches_source`: `%s`; result SHA-256: `%s`.\n' \
    "$basic_result" "$basic_gap" "$(sha "$basic")"
  printf -- '- `m1-restart.result`: `%s`; result SHA-256: `%s`.\n' \
    "$restart_result" "$(sha "$restart")"
  printf -- '- `m1-hard-delete.result`: `%s`; result SHA-256: `%s`.\n' \
    "$hard_delete_result" "$(sha "$hard_delete")"
  printf -- '- `m1-bulk-partial.bulk_partial_failure_observed`: `%s`; `current_run_error_proven`: `%s`; result SHA-256: `%s`.\n' \
    "$bulk_failure" "$error_proven" "$(sha "$partial")"

  printf '%s\n' '' 'The baseline computed-field gap is explicit: the locked `DATE_FORMAT(...) AS updated_at` expression produced a non-null MySQL value but `null` in the Adapter incremental target, so `updated_at_matches_source` is `false`.'

  printf '%s\n' '' '## Byte-mapping and repair observation'
  printf -- '- `valid_item_applied`: `%s`.\n' "$valid"
  printf -- '- `invalid_item_applied_before_mapping_fix`: `%s`.\n' "$invalid"
  printf -- '- `invalid_source_value_preserved_before_fix`: `%s` (source `%s`, target `%s`).\n' \
    "$value_preserved" "$source_price" "$target_price"
  printf -- '- `later_batch_applied_before_mapping_fix`: `%s`.\n' "$later"
  printf -- '- `invalid_item_retried_after_mapping_fix`: `%s`.\n' "$retried"
  printf -- '- `etl_required`: `%s`; `etl_invoked`: `%s`; `etl_repair_succeeded`: `%s`.\n' \
    "$etl_required" "$etl_invoked" "$etl_succeeded"
  printf '%s\n' \
    'The runner verified the official launcher annotation before invoking `POST /etl/es8/products.yml?params=1401`; it did not write directly to Elasticsearch or move the Canal cursor.'

  printf '%s\n' '' '## Missing end-to-end capabilities'
  printf '%s\n' \
    'M1 has no final multi-table projection, revision fencing, per-Bulk-item settlement contract, durable DLQ, independent reconciliation/repair loop, binlog-gap classification, or rebuild/cutover workflow. `products_adapter_v1` is disposable comparison state, not the serving index.'

  printf '%s\n' '' '## Evidence lifecycle'
  printf '%s\n' \
    'Runtime evidence under `evidence/m1/` is generated locally and intentionally ignored by Git. Regenerate and verify the evidence and this rendered document with:'
  printf '%s\n' '' '```bash' 'make scenario-m1' 'make verify-m1' '```'
  printf '%s\n' '' \
    'The links are meaningful in a generated workspace only; a clean checkout does not ship observed runtime JSON. No M1 result claims exactly-once processing or MySQL-to-Elasticsearch final consistency.'
} >"$temporary"
mv "$temporary" "$output"
trap - EXIT
