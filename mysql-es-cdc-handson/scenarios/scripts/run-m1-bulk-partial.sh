#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-adapter.sh
source scenarios/scripts/lib-m1-log-window.sh
source scenarios/scripts/lib-m1-mapping-proof.sh
source scenarios/scripts/lib-m1-task3.sh

scenario=m1-bulk-partial
out="evidence/m1/$scenario"
archive=infra/canal-adapter/artifacts/canal.adapter-1.1.8.tar.gz
official_sha=e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340
rm -rf "$out"
mkdir -p "$out"
cp "scenarios/definitions/$scenario.json" "$out/input-commands.json"

capture_http_json() {
  local method="$1"
  local url="$2"
  local output="$3"
  local data_file="${4:-}"
  local body status transport_ok=true
  body=$(mktemp "${TMPDIR:-/tmp}/m1-task4-http.XXXXXX")
  if test -n "$data_file"; then
    status=$(curl -sS --connect-timeout 2 --max-time 30 -X "$method" \
      -H 'Content-Type: application/json' --data-binary "@$data_file" \
      -o "$body" -w '%{http_code}' "$url") || transport_ok=false
  else
    status=$(curl -sS --connect-timeout 2 --max-time 30 -X "$method" \
      -o "$body" -w '%{http_code}' "$url") || transport_ok=false
  fi
  if test "$transport_ok" = true && jq -e . "$body" >/dev/null 2>&1; then
    jq -n --arg url "$url" --argjson status "$status" \
      --slurpfile body "$body" '
      {requested_url:$url,transport_ok:true,http_status:$status,body:$body[0]}
    ' >"$output"
  elif test "$transport_ok" = true; then
    jq -n --arg url "$url" --argjson status "$status" --rawfile body "$body" '
      {requested_url:$url,transport_ok:true,http_status:$status,body:$body}
    ' >"$output"
  else
    jq -n --arg url "$url" --rawfile body "$body" '
      {requested_url:$url,transport_ok:false,http_status:null,body:$body}
    ' >"$output"
  fi
  rm -f "$body"
  test "$transport_ok" = true
}

capture_es_get() {
  local id="$1"
  local output="$2"
  capture_http_json GET \
    "http://127.0.0.1:9200/products_adapter_v1/_doc/$id" "$output"
  jq -e --arg id "$id" '
    .transport_ok == true and
    ((.http_status == 200 and .body.found == true and .body._id == $id) or
     (.http_status == 404 and .body == {
       _index:"products_adapter_v1",_id:$id,found:false
     }))
  ' "$output" >/dev/null
}

document_is_present() {
  local id="$1"
  local price="$2"
  curl -fsS --connect-timeout 2 --max-time 4 \
    "http://127.0.0.1:9200/products_adapter_v1/_doc/$id" \
    | jq -e --argjson id "$id" --argjson price "$price" '
      .found == true and ._source.product_id == $id and
      ._source.price_cents == $price
    ' >/dev/null
}

capture_adapter_log() {
  compose_adapter exec -T canal-adapter \
    cat /opt/canal-adapter/logs/adapter/adapter.log
}

partial_error_is_current() {
  local cutoff="$1"
  local log
  log=$(mktemp "${TMPDIR:-/tmp}/m1-task4-log.XXXXXX")
  capture_adapter_log >"$log" || {
    rm -f "$log"
    return 1
  }
  log_pattern_exists_since "$cutoff" "$log" "mapper_parsing_exception" &&
    log_pattern_exists_since "$cutoff" "$log" "1000" &&
    log_pattern_exists_since "$cutoff" "$log" "byte"
  local result=$?
  rm -f "$log"
  return "$result"
}

capture_source_pair() {
  local output="$1"
  local rows
  rows=$(mysql_adapter -e "SELECT JSON_ARRAYAGG(row_value) FROM (
    SELECT JSON_OBJECT(
      'product_id',p.id,'price_cents',p.price_cents,'revision',r.revision,
      'available_quantity',i.available_quantity,
      'reserved_quantity',i.reserved_quantity
    ) AS row_value
    FROM products p
    JOIN product_search_revision r ON r.product_id=p.id
    JOIN inventory i ON i.product_id=p.id
    WHERE p.id IN (1401,1402)
    ORDER BY p.id
  ) ordered_rows")
  jq -n --arg captured "$(m1_task3_utc_millis)" --argjson products "$rows" '
    {captured_at:$captured,products:$products}
  ' >"$output"
}

capture_source_later() {
  local output="$1"
  local row
  row=$(mysql_adapter -e "SELECT JSON_OBJECT(
    'product_id',p.id,'price_cents',p.price_cents,'revision',r.revision,
    'available_quantity',i.available_quantity,
    'reserved_quantity',i.reserved_quantity)
    FROM products p
    JOIN product_search_revision r ON r.product_id=p.id
    JOIN inventory i ON i.product_id=p.id
    WHERE p.id=1403")
  jq -n --arg captured "$(m1_task3_utc_millis)" --argjson row "$row" '
    $row + {captured_at:$captured}
  ' >"$output"
}

poll_until 60 product_api_is_ready
bash tests/contracts/m1-adapter.sh --live >/dev/null
initial_container=$(m1_task3_container_id)
initial_identity=$(m1_task3_adapter_identity)
compose_adapter stop canal-adapter
test "$(m1_task3_container_id)" = "$initial_container"
test "$(m1_task3_container_running "$initial_container")" = false

mysql_adapter <<'SQL'
START TRANSACTION;
DELETE FROM product_search_revision WHERE product_id IN (1401,1402,1403);
DELETE FROM inventory WHERE product_id IN (1401,1402,1403);
DELETE FROM products WHERE id IN (1401,1402,1403);
COMMIT;
SQL
test "$(mysql_adapter -e "SELECT
  (SELECT COUNT(*) FROM products WHERE id IN (1401,1402,1403)) +
  (SELECT COUNT(*) FROM inventory WHERE product_id IN (1401,1402,1403)) +
  (SELECT COUNT(*) FROM product_search_revision WHERE product_id IN (1401,1402,1403))")" = 0

delete_capture=$(mktemp "${TMPDIR:-/tmp}/m1-task4-delete.XXXXXX")
capture_http_json DELETE http://127.0.0.1:9200/products_adapter_v1 "$delete_capture"
jq -e '.http_status == 200 or .http_status == 404' "$delete_capture" >/dev/null
poll_until 30 es_index_is_absent
capture_http_json PUT http://127.0.0.1:9200/products_adapter_v1 \
  "$out/partial-index-create.capture.json" \
  infra/elasticsearch/adapter-index-partial-failure.json
jq -e '.transport_ok == true and .http_status == 200 and
  .body == {acknowledged:true,shards_acknowledged:true,index:"products_adapter_v1"}' \
  "$out/partial-index-create.capture.json" >/dev/null
jq '.body' "$out/partial-index-create.capture.json" >"$out/partial-index-create.json"
rm "$out/partial-index-create.capture.json" "$delete_capture"
capture_http_json GET http://127.0.0.1:9200/products_adapter_v1/_mapping \
  "$out/partial-mapping-proof.json"
jq -e '.http_status == 200 and
  .body.products_adapter_v1.mappings.properties.price_cents.type == "byte"' \
  "$out/partial-mapping-proof.json" >/dev/null

first_sql="START TRANSACTION; INSERT INTO products (id, sku, name, description, category_id, price_cents, status) VALUES (1401, 'M1-1401', 'Partial Valid', 'same transaction valid', 10, 100, 'ACTIVE'), (1402, 'M1-1402', 'Partial Invalid', 'same transaction invalid', 10, 1000, 'ACTIVE'); INSERT INTO inventory (product_id, available_quantity, reserved_quantity) VALUES (1401, 0, 0), (1402, 0, 0); INSERT INTO product_search_revision (product_id, revision, active) VALUES (1401, 1, 1), (1402, 1, 1); COMMIT;"
first_started=$(m1_task3_utc_millis)
first_connection=$(mysql_adapter -e "SELECT CONNECTION_ID(); $first_sql" | head -n 1)
first_committed=$(m1_task3_utc_millis)
case "$first_connection" in ''|*[!0-9]*) exit 1 ;; esac
jq -n --arg transaction "$first_sql" --arg started "$first_started" \
  --arg committed "$first_committed" --argjson connection "$first_connection" '
  {
    transaction:$transaction,started_at:$started,committed_at:$committed,
    mysql_connection_id:$connection,same_mysql_session:true,committed:true
  }
' >"$out/transaction-1401-1402.json"
capture_source_pair "$out/source-1401-1402.json"

compose_adapter start canal-adapter
poll_until 30 m1_task3_adapter_identity >/dev/null
partial_container=$(m1_task3_container_id)
partial_identity=$(m1_task3_adapter_identity)
test "$partial_container" = "$initial_container"
test "$partial_identity" != "$initial_identity"
partial_config_proof="$out/partial-run-mapping-config-proof.json"
M1_MAPPING_PROOF_OUTPUT="$partial_config_proof" \
  bash tests/contracts/m1-adapter.sh --live \
  >"$out/partial-run-topology-proof.txt"
jq '{
  container_id,java_identity,java_cutoff_utc,
  container_mapping_sha256,mapping_load_current:true
}' "$partial_config_proof" >"$out/adapter-partial-run.json"
partial_cutoff=$(jq -r '.java_cutoff_utc' "$out/adapter-partial-run.json")

partial_deadline=false
if ! poll_until 30 partial_error_is_current "$partial_cutoff"; then
  partial_deadline=true
fi
capture_adapter_log >"$out/adapter-partial-error.log"
jq -n --arg container "$(m1_task3_container_id)" \
  --arg identity "$(m1_task3_adapter_identity)" \
  --arg captured "$(m1_task3_utc_millis)" '
  {
    container_id:$container,java_identity:$identity,
    container_running:true,captured_at:$captured
  }
' >"$out/adapter-after-partial-error.json"
capture_es_get 1401 "$out/1401-before-fix.json"
capture_es_get 1402 "$out/1402-before-fix.json"
partial_completed=$(m1_task3_utc_millis)
jq -n --argjson deadline "$partial_deadline" --arg completed "$partial_completed" '
  {
    deadline_seconds:30,deadline_reached:$deadline,
    error_observed:($deadline | not),completed_at:$completed
  }
' >"$out/partial-observation.json"

later_sql="START TRANSACTION; INSERT INTO products (id, sku, name, description, category_id, price_cents, status) VALUES (1403, 'M1-1403', 'Later Valid', 'later transaction', 10, 101, 'ACTIVE'); INSERT INTO inventory (product_id, available_quantity, reserved_quantity) VALUES (1403, 0, 0); INSERT INTO product_search_revision (product_id, revision, active) VALUES (1403, 1, 1); COMMIT;"
later_started=$(m1_task3_utc_millis)
later_connection=$(mysql_adapter -e "SELECT CONNECTION_ID(); $later_sql" | head -n 1)
later_committed=$(m1_task3_utc_millis)
case "$later_connection" in ''|*[!0-9]*) exit 1 ;; esac
test "$later_connection" != "$first_connection"
jq -n --arg transaction "$later_sql" --arg started "$later_started" \
  --arg committed "$later_committed" --argjson connection "$later_connection" '
  {
    transaction:$transaction,started_at:$started,committed_at:$committed,
    mysql_connection_id:$connection,separate_mysql_session:true,committed:true
  }
' >"$out/transaction-1403.json"
capture_source_later "$out/source-1403.json"
later_deadline=false
if ! poll_until 30 document_is_present 1403 101; then
  later_deadline=true
fi
capture_es_get 1403 "$out/1403-before-fix.json"
jq -n --argjson deadline "$later_deadline" \
  --arg completed "$(m1_task3_utc_millis)" '
  {deadline_seconds:30,deadline_reached:$deadline,completed_at:$completed}
' >"$out/later-observation.json"

compose_adapter stop canal-adapter
test "$(m1_task3_container_id)" = "$partial_container"
jq -n --arg container "$partial_container" --arg identity "$partial_identity" \
  --arg captured "$(m1_task3_utc_millis)" '
  {
    container_id:$container,java_identity:$identity,
    container_running:false,captured_at:$captured
  }
' >"$out/adapter-before-repair-start.json"

repair_delete=$(mktemp "${TMPDIR:-/tmp}/m1-task4-repair-delete.XXXXXX")
repair_create=$(mktemp "${TMPDIR:-/tmp}/m1-task4-repair-create.XXXXXX")
capture_http_json DELETE http://127.0.0.1:9200/products_adapter_v1 "$repair_delete"
poll_until 30 es_index_is_absent
capture_http_json PUT http://127.0.0.1:9200/products_adapter_v1 "$repair_create" \
  infra/elasticsearch/adapter-index.json
jq -n --slurpfile delete "$repair_delete" --slurpfile create "$repair_create" '
  {delete:$delete[0],create:$create[0]}
' >"$out/mapping-repair.json"
rm -f "$repair_delete" "$repair_create"
capture_http_json GET http://127.0.0.1:9200/products_adapter_v1/_mapping \
  "$out/normal-mapping-proof.json"
jq -e '.http_status == 200 and
  .body.products_adapter_v1.mappings.properties.price_cents.type == "long"' \
  "$out/normal-mapping-proof.json" >/dev/null

compose_adapter start canal-adapter
poll_until 30 m1_task3_adapter_identity >/dev/null
repair_config_proof="$out/repair-run-mapping-config-proof.json"
M1_MAPPING_PROOF_OUTPUT="$repair_config_proof" \
  bash tests/contracts/m1-adapter.sh --live \
  >"$out/repair-run-topology-proof.txt"
repair_identity=$(m1_task3_adapter_identity)
test "$(m1_task3_container_id)" = "$partial_container"
test "$repair_identity" != "$partial_identity"
jq --arg captured "$(m1_task3_utc_millis)" '
  {
    container_id,java_identity,java_cutoff_utc,container_running:true,
    workspace_mapping_sha256,container_mapping_sha256,
    mapping_load_current:true,captured_at:$captured
  }
' "$repair_config_proof" >"$out/adapter-after-repair-start.json"
capture_adapter_log >"$out/adapter-repair-run.log"

retry_deadline=false
if ! poll_until 30 document_is_present 1402 1000; then
  retry_deadline=true
fi
capture_es_get 1402 "$out/1402-after-restart.json"
jq -n --argjson deadline "$retry_deadline" \
  --arg completed "$(m1_task3_utc_millis)" '
  {deadline_seconds:30,deadline_reached:$deadline,completed_at:$completed}
' >"$out/retry-observation.json"

bash scenarios/scripts/prove-m1-etl-endpoint.sh "$out/etl-endpoint-proof.json"
if test "$retry_deadline" = false; then
  jq -n --arg sha "$official_sha" '
    {
      official_archive_sha256:$sha,
      source_class:"com.alibaba.otter.canal.adapter.launcher.rest.CommonRest",
      method:"POST",endpoint:"/etl/es8/products.yml",params:"1401",
      invoked:false,transport_ok:null,http_status:null,response_body:null
    }
  ' >"$out/etl-action.json"
else
  etl_body=$(mktemp "${TMPDIR:-/tmp}/m1-task4-etl-body.XXXXXX")
  etl_transport=true
  etl_status=$(curl -sS --connect-timeout 2 --max-time 120 -X POST \
    -o "$etl_body" -w '%{http_code}' \
    'http://127.0.0.1:8084/etl/es8/products.yml?params=1401') || etl_transport=false
  if jq -e . "$etl_body" >/dev/null 2>&1; then
    jq -n --arg sha "$official_sha" --argjson transport "$etl_transport" \
      --argjson status "${etl_status:-null}" --slurpfile body "$etl_body" '
      {
        official_archive_sha256:$sha,
        source_class:"com.alibaba.otter.canal.adapter.launcher.rest.CommonRest",
        method:"POST",endpoint:"/etl/es8/products.yml",params:"1401",
        invoked:true,transport_ok:$transport,http_status:$status,
        response_body:$body[0]
      }
    ' >"$out/etl-action.json"
  else
    jq -n --arg sha "$official_sha" --argjson transport "$etl_transport" \
      --argjson status "${etl_status:-null}" --rawfile body "$etl_body" '
      {
        official_archive_sha256:$sha,
        source_class:"com.alibaba.otter.canal.adapter.launcher.rest.CommonRest",
        method:"POST",endpoint:"/etl/es8/products.yml",params:"1401",
        invoked:true,transport_ok:$transport,http_status:$status,
        response_body:$body
      }
    ' >"$out/etl-action.json"
  fi
  rm -f "$etl_body"
  etl_completion_observed=true
  if ! poll_until 60 document_is_present 1402 1000; then
    etl_completion_observed=false
  fi
fi
capture_es_get 1402 "$out/1402-final.json"

bash scenarios/scripts/derive-m1-bulk-partial-result.sh "$out" >"$out/result.json"
bash scenarios/scripts/assert-m1-bulk-partial-evidence.sh "$out"
if test "$retry_deadline" = true; then
  test "$etl_completion_observed" = true
fi
