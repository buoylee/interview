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
  >"$fixture/current-run-topology-proof.txt"
printf '%s\n' \
  '{"contract":"m1-adapter-baseline-continuity-v1","phase":"pre_behavior","container_id":"229932d46a1e1234567890abcdef1234567890abcdef1234567890abcdef1234","java_identity":"40|123456","java_cutoff_utc":"2026-07-26 13:12:52.700","workspace_mapping_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","container_mapping_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","loader_assertions":{"start_loading_after_cutoff":true,"loaded_after_cutoff":true},"identity_stable_during_precheck":true,"baseline_continuity_verified":false}' \
  >"$fixture/pre-behavior-mapping-proof.json"
printf '%s\n' \
  '{"contract":"m1-adapter-baseline-continuity-v1","phase":"baseline_complete","container_id":"229932d46a1e1234567890abcdef1234567890abcdef1234567890abcdef1234","java_identity":"40|123456","java_cutoff_utc":"2026-07-26 13:12:52.700","workspace_mapping_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","container_mapping_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","loader_assertions":{"start_loading_after_cutoff":true,"loaded_after_cutoff":true},"identity_stable_during_precheck":true,"baseline_continuity_verified":true,"post_behavior":{"container_id":"229932d46a1e1234567890abcdef1234567890abcdef1234567890abcdef1234","java_identity":"40|123456","container_mapping_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","identity_stable_during_postcheck":true}}' \
  >"$fixture/current-run-mapping-proof.json"

jq -n \
  --slurpfile insert_source "$fixture/mysql-insert-snapshot.json" \
  --slurpfile insert_target "$fixture/es-insert-snapshot.json" \
  --slurpfile source "$fixture/mysql-snapshot.json" \
  --slurpfile target "$fixture/es-snapshot.json" '
  {
    scenario_id:"m1-basic",
    result:"OBSERVED_INSERT_UPDATE_WITH_COMPUTED_FIELD_GAP",
    input_commands_match:true,
    mapping_continuity_verified:true,
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
      input:"input-commands.json",
      source:"mysql-snapshot.json",
      target:"es-snapshot.json",
      adapter_log:"adapter.log",
      pre_behavior_mapping_proof:"pre-behavior-mapping-proof.json",
      mapping_proof:"current-run-mapping-proof.json"
    },
    final_consistency_claim:false
  }
' >"$fixture/result.json"

bash scenarios/scripts/assert-m1-evidence.sh "$fixture"

cp "$fixture/mysql-snapshot.json" "$fixture/mysql-snapshot.valid.json"
cp "$fixture/es-snapshot.json" "$fixture/es-snapshot.valid.json"
cp "$fixture/input-commands.json" "$fixture/input-commands.valid.json"
cp "$fixture/result.json" "$fixture/result.valid.json"

jq '.non_computed_fields_match = true | .captured_values.final_source_updated_at = "wrong"' \
  "$fixture/result.json" >"$fixture/result-mutated.json"
mv "$fixture/result-mutated.json" "$fixture/result.json"
if bash scenarios/scripts/assert-m1-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "M1 evidence assertion trusted a hard-coded result over captured snapshots" >&2
  exit 1
fi

cp "$fixture/mysql-snapshot.valid.json" "$fixture/mysql-snapshot.json"
cp "$fixture/es-snapshot.valid.json" "$fixture/es-snapshot.json"
cp "$fixture/input-commands.valid.json" "$fixture/input-commands.json"
jq '.name = "Wrong Keyboard"' "$fixture/mysql-snapshot.json" \
  >"$fixture/mysql-snapshot.mutated.json"
mv "$fixture/mysql-snapshot.mutated.json" "$fixture/mysql-snapshot.json"
jq '._source.name = "Wrong Keyboard"' "$fixture/es-snapshot.json" \
  >"$fixture/es-snapshot.mutated.json"
mv "$fixture/es-snapshot.mutated.json" "$fixture/es-snapshot.json"
bash scenarios/scripts/derive-m1-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "M1 evidence accepted matching MySQL/ES values that disagree with scenario input" >&2
  exit 1
fi

cp "$fixture/mysql-snapshot.valid.json" "$fixture/mysql-snapshot.json"
cp "$fixture/es-snapshot.valid.json" "$fixture/es-snapshot.json"
jq '.source_products[0].name = "Tampered Input"' \
  "$fixture/input-commands.valid.json" >"$fixture/input-commands.json"
bash scenarios/scripts/derive-m1-result.sh "$fixture" >"$fixture/result.json"
if bash scenarios/scripts/assert-m1-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "M1 evidence accepted a tampered scenario input" >&2
  exit 1
fi

cp "$fixture/input-commands.valid.json" "$fixture/input-commands.json"
cp "$fixture/result.valid.json" "$fixture/result.json"
mv "$fixture/input-commands.json" "$fixture/input-commands.missing.json"
if bash scenarios/scripts/assert-m1-evidence.sh "$fixture" >/dev/null 2>&1; then
  echo "M1 evidence accepted a missing scenario input" >&2
  exit 1
fi
