#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

for required in \
  infra/elasticsearch/adapter-index-partial-failure.json \
  scenarios/definitions/m1-bulk-partial.json \
  scenarios/scripts/derive-m1-bulk-partial-result.sh \
  scenarios/scripts/assert-m1-bulk-partial-evidence.sh \
  scenarios/scripts/prove-m1-etl-endpoint.sh \
  scenarios/scripts/run-m1-bulk-partial.sh
do
  test -s "$required"
done

jq -e '
  .mappings.dynamic == "strict" and
  .mappings.properties.price_cents.type == "byte"
' infra/elasticsearch/adapter-index-partial-failure.json >/dev/null

jq -e '
  .scenario_id == "m1-bulk-partial" and
  .same_source_transaction == [
    {product_id:1401,price_cents:100,expected_mapping:"valid"},
    {product_id:1402,price_cents:1000,expected_mapping:"invalid"}
  ] and
  .later_source_transaction.product_id == 1403 and
  .later_source_transaction.price_cents == 101 and
  .partial_observation_deadline_seconds == 30 and
  .later_observation_deadline_seconds == 30 and
  .retry_observation_deadline_seconds == 30 and
  .final_consistency_claim == false
' scenarios/definitions/m1-bulk-partial.json >/dev/null

endpoint_proof=$(mktemp "${TMPDIR:-/tmp}/m1-etl-endpoint-proof.XXXXXX")
bash scenarios/scripts/prove-m1-etl-endpoint.sh "$endpoint_proof"
jq -e '
  .official_archive_sha256 == "e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340" and
  (.launcher_jar_sha256 | test("^[0-9a-f]{64}$")) and
  .source_class == "com.alibaba.otter.canal.adapter.launcher.rest.CommonRest" and
  .post_mapping == "/etl/{type}/{task}" and
  .request_param_name == "params" and
  .instantiated_endpoint == "/etl/es8/products.yml" and
  .request_param_value == "1401"
' "$endpoint_proof" >/dev/null
rm -f "$endpoint_proof"

fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/m1-task4-contract.XXXXXX")
trap 'rm -rf "$fixture_root"' EXIT

write_fixture() {
  local out="$1"
  local after_restart_found="$2"
  local etl_invoked="$3"
  local final_found="$4"

  mkdir -p "$out"
  cp scenarios/definitions/m1-bulk-partial.json "$out/input-commands.json"
  printf '%s\n' \
    '{"acknowledged":true,"shards_acknowledged":true,"index":"products_adapter_v1"}' \
    >"$out/partial-index-create.json"
  printf '%s\n' \
    '{"transport_ok":true,"http_status":200,"body":{"products_adapter_v1":{"mappings":{"dynamic":"strict","properties":{"price_cents":{"type":"byte"}}}}}}' \
    >"$out/partial-mapping-proof.json"
  printf '%s\n' \
    '{"container_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","java_identity":"41|1000","java_cutoff_utc":"2026-07-26 15:00:00.000","container_mapping_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"}' \
    >"$out/adapter-partial-run.json"
  printf '%s\n' \
    '{"transaction":"START TRANSACTION; INSERT INTO products (id, sku, name, description, category_id, price_cents, status) VALUES (1401, '\''M1-1401'\'', '\''Partial Valid'\'', '\''same transaction valid'\'', 10, 100, '\''ACTIVE'\''), (1402, '\''M1-1402'\'', '\''Partial Invalid'\'', '\''same transaction invalid'\'', 10, 1000, '\''ACTIVE'\''); INSERT INTO inventory (product_id, available_quantity, reserved_quantity) VALUES (1401, 0, 0), (1402, 0, 0); INSERT INTO product_search_revision (product_id, revision, active) VALUES (1401, 1, 1), (1402, 1, 1); COMMIT;","started_at":"2026-07-26T15:00:01.000Z","committed_at":"2026-07-26T15:00:01.100Z","mysql_connection_id":77,"same_mysql_session":true,"committed":true}' \
    >"$out/transaction-1401-1402.json"
  printf '%s\n' \
    '{"captured_at":"2026-07-26T15:00:01.200Z","products":[{"product_id":1401,"price_cents":100,"revision":1,"available_quantity":0,"reserved_quantity":0},{"product_id":1402,"price_cents":1000,"revision":1,"available_quantity":0,"reserved_quantity":0}]}' \
    >"$out/source-1401-1402.json"
  printf '%s\n' \
    '2026-07-26 15:00:02.001 ERROR Bulk request failed mapper_parsing_exception value [1000] out of range for byte' \
    >"$out/adapter-partial-error.log"
  printf '%s\n' \
    '{"container_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","java_identity":"41|1000","container_running":true,"captured_at":"2026-07-26T15:00:02.100Z"}' \
    >"$out/adapter-after-partial-error.json"
  printf '%s\n' \
    '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1401","transport_ok":true,"http_status":200,"body":{"_index":"products_adapter_v1","_id":"1401","found":true,"_source":{"product_id":1401,"price_cents":100}}}' \
    >"$out/1401-before-fix.json"
  printf '%s\n' \
    '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1402","transport_ok":true,"http_status":404,"body":{"_index":"products_adapter_v1","_id":"1402","found":false}}' \
    >"$out/1402-before-fix.json"
  printf '%s\n' \
    '{"deadline_seconds":30,"deadline_reached":false,"error_observed":true,"completed_at":"2026-07-26T15:00:02.200Z"}' \
    >"$out/partial-observation.json"
  printf '%s\n' \
    '{"transaction":"START TRANSACTION; INSERT INTO products (id, sku, name, description, category_id, price_cents, status) VALUES (1403, '\''M1-1403'\'', '\''Later Valid'\'', '\''later transaction'\'', 10, 101, '\''ACTIVE'\''); INSERT INTO inventory (product_id, available_quantity, reserved_quantity) VALUES (1403, 0, 0); INSERT INTO product_search_revision (product_id, revision, active) VALUES (1403, 1, 1); COMMIT;","started_at":"2026-07-26T15:00:02.300Z","committed_at":"2026-07-26T15:00:02.400Z","mysql_connection_id":78,"separate_mysql_session":true,"committed":true}' \
    >"$out/transaction-1403.json"
  printf '%s\n' \
    '{"captured_at":"2026-07-26T15:00:02.500Z","product_id":1403,"price_cents":101,"revision":1,"available_quantity":0,"reserved_quantity":0}' \
    >"$out/source-1403.json"
  printf '%s\n' \
    '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1403","transport_ok":true,"http_status":200,"body":{"_index":"products_adapter_v1","_id":"1403","found":true,"_source":{"product_id":1403,"price_cents":101}}}' \
    >"$out/1403-before-fix.json"
  printf '%s\n' \
    '{"deadline_seconds":30,"deadline_reached":false,"completed_at":"2026-07-26T15:00:02.600Z"}' \
    >"$out/later-observation.json"
  printf '%s\n' \
    '{"delete":{"transport_ok":true,"http_status":200,"body":{"acknowledged":true}},"create":{"transport_ok":true,"http_status":200,"body":{"acknowledged":true,"shards_acknowledged":true,"index":"products_adapter_v1"}}}' \
    >"$out/mapping-repair.json"
  printf '%s\n' \
    '{"transport_ok":true,"http_status":200,"body":{"products_adapter_v1":{"mappings":{"dynamic":"strict","properties":{"price_cents":{"type":"long"}}}}}}' \
    >"$out/normal-mapping-proof.json"
  printf '%s\n' \
    '{"container_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","java_identity":"41|1000","container_running":false,"captured_at":"2026-07-26T15:00:03.000Z"}' \
    >"$out/adapter-before-repair-start.json"
  printf '%s\n' \
    '{"container_id":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","java_identity":"42|2000","java_cutoff_utc":"2026-07-26 15:00:03.100","container_running":true,"workspace_mapping_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","container_mapping_sha256":"0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef","mapping_load_current":true,"captured_at":"2026-07-26T15:00:03.200Z"}' \
    >"$out/adapter-after-repair-start.json"
  if test "$after_restart_found" = true; then
    printf '%s\n' \
      '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1402","transport_ok":true,"http_status":200,"body":{"_index":"products_adapter_v1","_id":"1402","found":true,"_source":{"product_id":1402,"price_cents":1000}}}' \
      >"$out/1402-after-restart.json"
    printf '%s\n' \
      '{"deadline_seconds":30,"deadline_reached":false,"completed_at":"2026-07-26T15:00:03.300Z"}' \
      >"$out/retry-observation.json"
  else
    printf '%s\n' \
      '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1402","transport_ok":true,"http_status":404,"body":{"_index":"products_adapter_v1","_id":"1402","found":false}}' \
      >"$out/1402-after-restart.json"
    printf '%s\n' \
      '{"deadline_seconds":30,"deadline_reached":true,"completed_at":"2026-07-26T15:00:33.300Z"}' \
      >"$out/retry-observation.json"
  fi
  jq -n --argjson invoked "$etl_invoked" '
    {
      official_archive_sha256:"e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340",
      source_class:"com.alibaba.otter.canal.adapter.launcher.rest.CommonRest",
      method:"POST",endpoint:"/etl/es8/products.yml",params:"1401",
      invoked:$invoked,
      transport_ok:(if $invoked then true else null end),
      http_status:(if $invoked then 200 else null end),
      response_body:(if $invoked then {succeeded:true,resultMessage:"导入ES 数据：3 条"} else null end)
    }
  ' >"$out/etl-action.json"
  printf '%s\n' \
    '{"official_archive_sha256":"e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340","launcher_jar_sha256":"abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789","source_class":"com.alibaba.otter.canal.adapter.launcher.rest.CommonRest","post_mapping":"/etl/{type}/{task}","request_param_name":"params","instantiated_endpoint":"/etl/es8/products.yml","request_param_value":"1401"}' \
    >"$out/etl-endpoint-proof.json"
  if test "$final_found" = true; then
    printf '%s\n' \
      '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1402","transport_ok":true,"http_status":200,"body":{"_index":"products_adapter_v1","_id":"1402","found":true,"_source":{"product_id":1402,"price_cents":1000}}}' \
      >"$out/1402-final.json"
  else
    printf '%s\n' \
      '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1402","transport_ok":true,"http_status":404,"body":{"_index":"products_adapter_v1","_id":"1402","found":false}}' \
      >"$out/1402-final.json"
  fi
  printf '%s\n' \
    '2026-07-26 15:00:03.101 INFO ## Start loading es mapping config ...' \
    '2026-07-26 15:00:03.102 INFO ## ES mapping config loaded' \
    >"$out/adapter-repair-run.log"
}

auto="$fixture_root/auto"
write_fixture "$auto" true false true
bash scenarios/scripts/derive-m1-bulk-partial-result.sh "$auto" >"$auto/result.json"
bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh "$auto"
jq -e '
  .valid_item_applied == true and
  .invalid_item_applied_before_mapping_fix == false and
  .later_batch_applied_before_mapping_fix == true and
  .invalid_item_retried_after_mapping_fix == true and
  .etl_required == false and .etl_invoked == false and
  .etl_repair_succeeded == false and
  .partial_failure_experiment_valid == true and
  .final_consistency_claim == false
' "$auto/result.json" >/dev/null

etl="$fixture_root/etl"
write_fixture "$etl" false true true
bash scenarios/scripts/derive-m1-bulk-partial-result.sh "$etl" >"$etl/result.json"
bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh "$etl"
jq -e '
  .invalid_item_retried_after_mapping_fix == false and
  .etl_required == true and .etl_invoked == true and
  .etl_repair_succeeded == true and
  .partial_failure_experiment_valid == true and
  .final_consistency_claim == false
' "$etl/result.json" >/dev/null

assert_rejected_etl_completion() {
  local fixture="$1"
  local message="$2"
  if bash scenarios/scripts/derive-m1-bulk-partial-result.sh "$fixture" \
      >"$fixture/result.json" 2>/dev/null; then
    echo "$message" >&2
    exit 1
  fi
}

cp -R "$etl" "$fixture_root/etl-final-missing"
printf '%s\n' \
  '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1402","transport_ok":true,"http_status":404,"body":{"_index":"products_adapter_v1","_id":"1402","found":false}}' \
  >"$fixture_root/etl-final-missing/1402-final.json"
assert_rejected_etl_completion "$fixture_root/etl-final-missing" \
  "ETL HTTP 200/succeeded=true was accepted while final 1402 remained absent"

cp -R "$etl" "$fixture_root/etl-http-error"
jq '.http_status = 503' "$fixture_root/etl-http-error/etl-action.json" \
  >"$fixture_root/etl-http-error/etl-action.json.tmp"
mv "$fixture_root/etl-http-error/etl-action.json.tmp" \
  "$fixture_root/etl-http-error/etl-action.json"
assert_rejected_etl_completion "$fixture_root/etl-http-error" \
  "ETL non-200 response was accepted"

cp -R "$etl" "$fixture_root/etl-body-false"
jq '.response_body.succeeded = false' "$fixture_root/etl-body-false/etl-action.json" \
  >"$fixture_root/etl-body-false/etl-action.json.tmp"
mv "$fixture_root/etl-body-false/etl-action.json.tmp" \
  "$fixture_root/etl-body-false/etl-action.json"
assert_rejected_etl_completion "$fixture_root/etl-body-false" \
  "ETL succeeded=false response was accepted"

cp -R "$etl" "$fixture_root/etl-body-malformed"
jq '.response_body = {message:"not the official success contract"}' \
  "$fixture_root/etl-body-malformed/etl-action.json" \
  >"$fixture_root/etl-body-malformed/etl-action.json.tmp"
mv "$fixture_root/etl-body-malformed/etl-action.json.tmp" \
  "$fixture_root/etl-body-malformed/etl-action.json"
assert_rejected_etl_completion "$fixture_root/etl-body-malformed" \
  "ETL malformed success body was accepted"

cp -R "$etl" "$fixture_root/etl-wrong-final-price"
jq '.body._source.price_cents = 999' \
  "$fixture_root/etl-wrong-final-price/1402-final.json" \
  >"$fixture_root/etl-wrong-final-price/1402-final.json.tmp"
mv "$fixture_root/etl-wrong-final-price/1402-final.json.tmp" \
  "$fixture_root/etl-wrong-final-price/1402-final.json"
assert_rejected_etl_completion "$fixture_root/etl-wrong-final-price" \
  "ETL final document with price other than 1000 was accepted"

# Characterize the pinned 1.1.8 behavior observed live: the ES8 Adapter may
# narrow 1000 to -24 before Bulk, so the intended mapping rejection never
# occurs. This is evidence to render, not a successful partial-failure claim.
coercion="$fixture_root/coercion"
cp -R "$etl" "$coercion"
printf '%s\n' \
  '2026-07-26 15:00:02.001 DEBUG DML: {"data":[{"id":1402,"price_cents":1000}]}' \
  >"$coercion/adapter-partial-error.log"
jq '.error_observed = false | .deadline_reached = true' \
  "$coercion/partial-observation.json" >"$coercion/partial-observation.json.tmp"
mv "$coercion/partial-observation.json.tmp" "$coercion/partial-observation.json"
jq '.http_status = 200 | .body = {
  _index:"products_adapter_v1",_id:"1402",found:true,
  _source:{product_id:1402,price_cents:-24}
}' "$coercion/1402-before-fix.json" >"$coercion/1402-before-fix.json.tmp"
mv "$coercion/1402-before-fix.json.tmp" "$coercion/1402-before-fix.json"
bash scenarios/scripts/derive-m1-bulk-partial-result.sh "$coercion" \
  >"$coercion/result.json"
bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh "$coercion"
jq -e '
  .current_run_error_proven == false and
  .bulk_partial_failure_observed == false and
  .invalid_item_applied_before_mapping_fix == true and
  .invalid_source_value_preserved_before_fix == false and
  .captured_values.invalid_target_price_before_fix == -24 and
  .etl_required == true and .etl_invoked == true and
  .etl_repair_succeeded == true and
  .partial_failure_experiment_valid == true and
  .final_consistency_claim == false
' "$coercion/result.json" >/dev/null

cp -R "$etl" "$fixture_root/transport-failure"
jq '.transport_ok = false | .http_status = null | .body = null' \
  "$fixture_root/transport-failure/1402-before-fix.json" \
  >"$fixture_root/transport-failure/1402-before-fix.json.tmp"
mv "$fixture_root/transport-failure/1402-before-fix.json.tmp" \
  "$fixture_root/transport-failure/1402-before-fix.json"
if bash scenarios/scripts/derive-m1-bulk-partial-result.sh \
    "$fixture_root/transport-failure" >/dev/null 2>&1; then
  echo "transport failure was relabeled as found=false" >&2
  exit 1
fi

cp -R "$etl" "$fixture_root/malformed"
printf '%s\n' '{"requested_url":"bad","transport_ok":true,"http_status":404,"body":{}}' \
  >"$fixture_root/malformed/1402-before-fix.json"
if bash scenarios/scripts/derive-m1-bulk-partial-result.sh \
    "$fixture_root/malformed" >/dev/null 2>&1; then
  echo "malformed HTTP evidence was relabeled as found=false" >&2
  exit 1
fi

cp -R "$etl" "$fixture_root/wrong-transaction"
jq '.same_mysql_session = false' \
  "$fixture_root/wrong-transaction/transaction-1401-1402.json" \
  >"$fixture_root/wrong-transaction/transaction-1401-1402.json.tmp"
mv "$fixture_root/wrong-transaction/transaction-1401-1402.json.tmp" \
  "$fixture_root/wrong-transaction/transaction-1401-1402.json"
if bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh \
    "$fixture_root/wrong-transaction" >/dev/null 2>&1; then
  echo "split first transaction evidence was accepted" >&2
  exit 1
fi

cp -R "$etl" "$fixture_root/old-error-log"
sed 's/2026-07-26 15:00:02.001/2026-07-26 14:59:59.999/' \
  "$fixture_root/old-error-log/adapter-partial-error.log" \
  >"$fixture_root/old-error-log/adapter-partial-error.log.tmp"
mv "$fixture_root/old-error-log/adapter-partial-error.log.tmp" \
  "$fixture_root/old-error-log/adapter-partial-error.log"
if bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh \
    "$fixture_root/old-error-log" >/dev/null 2>&1; then
  echo "pre-current-Java error log was accepted" >&2
  exit 1
fi

cp -R "$etl" "$fixture_root/wrong-etl-proof"
jq '.post_mapping = "/guessed"' \
  "$fixture_root/wrong-etl-proof/etl-endpoint-proof.json" \
  >"$fixture_root/wrong-etl-proof/etl-endpoint-proof.json.tmp"
mv "$fixture_root/wrong-etl-proof/etl-endpoint-proof.json.tmp" \
  "$fixture_root/wrong-etl-proof/etl-endpoint-proof.json"
if bash scenarios/scripts/derive-m1-bulk-partial-result.sh \
    "$fixture_root/wrong-etl-proof" >/dev/null 2>&1; then
  echo "unproven ETL endpoint was accepted" >&2
  exit 1
fi
