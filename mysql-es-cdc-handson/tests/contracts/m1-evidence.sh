#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

fixture=$(mktemp -d "${TMPDIR:-/tmp}/m1-evidence-fixture.XXXXXX")
trap 'rm -rf "$fixture"' EXIT

cp scenarios/definitions/m1-basic.json "$fixture/input-commands.json"
printf '%s\n' '{"acknowledged":true,"shards_acknowledged":true,"index":"products_adapter_v1"}' \
  >"$fixture/index-create.json"
printf '%s\n' '{"productId":1101,"revision":1}' >"$fixture/create-response.json"
printf '%s\n' '{"productId":1101,"revision":2}' >"$fixture/update-response.json"
printf '%s\n' \
  '{"product_id":1101,"sku":"M1-1101","name":"Adapter Keyboard","description":"initial","category_id":10,"price_cents":100,"status":"ACTIVE","updated_at":"2026-07-26T13:13:37.665217Z"}' \
  >"$fixture/mysql-insert-snapshot.json"
printf '%s\n' \
  '{"found":true,"_source":{"product_id":1101,"sku":"M1-1101","name":"Adapter Keyboard","description":"initial","category_id":10,"price_cents":100,"status":"ACTIVE","updated_at":null}}' \
  >"$fixture/es-insert-snapshot.json"
printf '%s\n' \
  '{"product_id":1101,"sku":"M1-1101","name":"Adapter Keyboard","description":"initial","category_id":10,"price_cents":120,"status":"ACTIVE","updated_at":"2026-07-26T13:14:00.123456Z"}' \
  >"$fixture/mysql-snapshot.json"
printf '%s\n' \
  '{"found":true,"_source":{"product_id":1101,"sku":"M1-1101","name":"Adapter Keyboard","description":"initial","category_id":10,"price_cents":120,"status":"ACTIVE","updated_at":null}}' \
  >"$fixture/es-snapshot.json"
printf '%s\n' \
  '2026-07-26 13:12:52.781 INFO ## Start loading es mapping config ...' \
  '2026-07-26 13:12:52.794 INFO ## ES mapping config loaded' \
  >"$fixture/adapter.log"
printf '%s\n' \
  'M1 Adapter topology evidence passed:' \
  '- formal es8 products mapping: exact image file plus current-Java-run load evidence' \
  >"$fixture/current-run-mapping-proof.txt"

jq -n \
  --slurpfile insert_source "$fixture/mysql-insert-snapshot.json" \
  --slurpfile insert_target "$fixture/es-insert-snapshot.json" \
  --slurpfile source "$fixture/mysql-snapshot.json" \
  --slurpfile target "$fixture/es-snapshot.json" '
  {
    scenario_id:"m1-basic",
    result:"OBSERVED_INSERT_UPDATE_WITH_COMPUTED_FIELD_GAP",
    insert_observed:true,
    update_observed:true,
    non_computed_fields_match:true,
    forbidden_fields_absent:true,
    allowed_field_set_exact:true,
    source_updated_at_non_null:true,
    target_updated_at_is_null:true,
    updated_at_matches_source:false,
    captured_values:{
      insert_source_updated_at:$insert_source[0].updated_at,
      insert_target_updated_at:$insert_target[0]._source.updated_at,
      final_source_updated_at:$source[0].updated_at,
      final_target_updated_at:$target[0]._source.updated_at
    },
    evidence_files:{
      source:"mysql-snapshot.json",
      target:"es-snapshot.json",
      adapter_log:"adapter.log",
      mapping_proof:"current-run-mapping-proof.txt"
    },
    final_consistency_claim:false
  }
' >"$fixture/result.json"

bash scenarios/scripts/assert-m1-evidence.sh "$fixture"

jq '.non_computed_fields_match = true | .captured_values.final_source_updated_at = "wrong"' \
  "$fixture/result.json" >"$fixture/result-mutated.json"
mv "$fixture/result-mutated.json" "$fixture/result.json"
if bash scenarios/scripts/assert-m1-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "M1 evidence assertion trusted a hard-coded result over captured snapshots" >&2
  exit 1
fi
