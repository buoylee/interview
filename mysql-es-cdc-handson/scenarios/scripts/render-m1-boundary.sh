#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
evidence_root="${M1_EVIDENCE_DIR:-${M1_EVIDENCE_ROOT:-evidence/m1}}"
output="${M1_BOUNDARY_OUT:-${M1_BOUNDARY_OUTPUT:-docs/01-canal-boundary.md}}"

bash scenarios/scripts/assert-m1-evidence.sh "$evidence_root/m1-basic"
bash scenarios/scripts/assert-m1-restart-evidence.sh "$evidence_root/m1-restart"
bash scenarios/scripts/assert-m1-hard-delete-evidence.sh "$evidence_root/m1-hard-delete"
bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh \
  "$evidence_root/m1-bulk-partial"

basic="$evidence_root/m1-basic/result.json"
restart="$evidence_root/m1-restart/result.json"
hard_delete="$evidence_root/m1-hard-delete/result.json"
partial="$evidence_root/m1-bulk-partial/result.json"

claim_manifest="$evidence_root/claim-manifest.json"
claim_manifest_tmp=$(mktemp "${TMPDIR:-/tmp}/m1-claim-manifest.XXXXXX")
bash scenarios/scripts/build-m1-claim-manifest.sh "$evidence_root" \
  >"$claim_manifest_tmp"
mv "$claim_manifest_tmp" "$claim_manifest"
claim_digest=$(sha256sum "$claim_manifest" | awk '{print $1}')

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

branch=
if jq -e '
  .bulk_partial_failure_observed == false and
  .current_run_error_proven == false and
  .valid_item_applied == true and
  .invalid_item_applied_before_mapping_fix == true and
  .invalid_source_value_preserved_before_fix == false and
  .captured_values.invalid_source_price_cents == 1000 and
  .captured_values.invalid_target_price_before_fix == -24 and
  .later_batch_applied_before_mapping_fix == true
' "$partial" >/dev/null; then
  branch=coercion
elif jq -e '
  .bulk_partial_failure_observed == true and
  .current_run_error_proven == true and
  (.valid_item_applied | type) == "boolean" and
  .invalid_item_applied_before_mapping_fix == false and
  .invalid_source_value_preserved_before_fix == false and
  .captured_values.invalid_source_price_cents == 1000 and
  .captured_values.invalid_target_price_before_fix == null and
  (.later_batch_applied_before_mapping_fix | type) == "boolean"
' "$partial" >/dev/null; then
  branch=genuine-bulk
else
  echo "Unsupported or contradictory M1 Bulk observation combination" >&2
  exit 1
fi

temporary=$(mktemp "${output}.tmp.XXXXXX")
trap 'rm -f "$temporary"' EXIT
{
  printf '%s\n' '# Canal and Adapter evidence boundary'
  printf '%s\n' '' '## Verdict'
  printf '%s\n' \
    'Canal captures and parses committed MySQL binlog changes and delivers incremental row-change data. It is a CDC/incremental-subscription component, not an end-to-end final-consistency solution.'
  if test "$branch" = coercion; then
    printf '%s\n' \
      'This pinned official Canal Adapter 1.1.8 run did **not** produce the intended Bulk partial failure: the byte-mapped source value `1000` was observed in Elasticsearch as `-24`. This is an observed coercion boundary, not a successful poison-item experiment and not a guarantee.'
  else
    printf '%s\n' \
      'This pinned official Canal Adapter 1.1.8 run did produce a genuine Bulk partial failure: the invalid byte-mapped source value `1000` was absent before repair and the current-run mapping error was proven. This is one observed run, not a delivery or recovery guarantee.'
  fi

  printf '%s\n' '' '## Pinned observed results'
  printf -- '- `m1-basic.result`: `%s`; `updated_at_matches_source`: `%s`.\n' \
    "$basic_result" "$basic_gap"
  printf -- '- `m1-restart.result`: `%s`.\n' "$restart_result"
  printf -- '- `m1-hard-delete.result`: `%s`.\n' "$hard_delete_result"
  printf -- '- `m1-bulk-partial.bulk_partial_failure_observed`: `%s`; `current_run_error_proven`: `%s`.\n' \
    "$bulk_failure" "$error_proven"
  printf -- '- Stable claim manifest SHA-256: `%s`.\n' "$claim_digest"

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
  if test "$etl_invoked" = true; then
    printf '%s\n' \
      'The runner verified the official launcher annotation before invoking `POST /etl/es8/products.yml?params=1401`; it did not write directly to Elasticsearch or move the Canal cursor.'
  else
    printf '%s\n' \
      'The runner verified the official launcher annotation. The ETL endpoint was verified but not invoked because the invalid item automatically reappeared with `price_cents=1000` after the same-container restart; no direct Elasticsearch write or Canal cursor move was used.'
  fi

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
