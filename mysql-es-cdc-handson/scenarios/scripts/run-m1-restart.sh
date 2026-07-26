#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-adapter.sh
source scenarios/scripts/lib-m1-log-window.sh
source scenarios/scripts/lib-m1-mapping-proof.sh
source scenarios/scripts/lib-m1-task3.sh

scenario="m1-restart"
product_id=1201
out="evidence/m1/$scenario"
pre_mapping_proof="$out/pre-behavior-mapping-proof.json"
final_mapping_proof="$out/current-run-mapping-proof.json"
rm -rf "$out"
mkdir -p "$out"
cp "scenarios/definitions/$scenario.json" "$out/input-commands.json"

started_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
poll_until 60 product_api_is_ready
bash tests/contracts/m1-adapter.sh --live >/dev/null
m1_task3_reset_fixture_and_index "$product_id" "$out/index-create.json"

curl -fsS --connect-timeout 2 --max-time 10 -X POST \
  http://127.0.0.1:8081/api/products \
  -H 'Content-Type: application/json' \
  -d '{"id":1201,"sku":"M1-1201","name":"Restart Keyboard","description":"restart observation","categoryId":10,"priceCents":100}' \
  | jq -e 'select(. == {"productId":1201,"revision":1})' \
  >"$out/create-response.json"
m1_task3_capture_initial "$product_id" \
  "$out/mysql-initial-snapshot.json" "$out/es-initial-snapshot.json"

container_before=$(m1_task3_container_id)
identity_before=$(m1_task3_adapter_identity)
jq -n --arg container "$container_before" --arg identity "$identity_before" \
  --arg captured "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" '
  {container_id:$container,java_identity:$identity,captured_at:$captured}
' >"$out/adapter-before-stop.json"

compose_adapter stop canal-adapter
stopped_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
container_stopped=$(m1_task3_container_id)
test "$container_stopped" = "$container_before"
m1_task3_adapter_is_stopped "$container_stopped"
jq -n --arg container "$container_stopped" --arg identity "$identity_before" \
  --arg captured "$stopped_at" '
  {
    container_id:$container,stopped_java_identity:$identity,
    java_process_absent:true,captured_at:$captured
  }
' >"$out/adapter-stopped.json"

curl -fsS --connect-timeout 2 --max-time 10 -X PUT \
  http://127.0.0.1:8081/api/products/1201/price \
  -H 'Content-Type: application/json' -d '{"priceCents":200}' \
  | jq -e 'select(. == {"productId":1201,"revision":2})' \
  >"$out/price-response.json"
curl -fsS --connect-timeout 2 --max-time 10 -X PUT \
  http://127.0.0.1:8081/api/products/1201/inventory \
  -H 'Content-Type: application/json' \
  -d '{"availableQuantity":7,"reservedQuantity":2}' \
  | jq -e 'select(. == {"productId":1201,"revision":3})' \
  >"$out/inventory-response.json"
source_mutated_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
m1_task3_snapshot_source "$product_id" "$out/mysql-while-down-snapshot.json"
m1_task3_capture_es "$product_id" "$out/es-while-down-snapshot.json"
m1_task3_es_matches_source_price \
  "$product_id" "$out/mysql-initial-snapshot.json" 100

compose_adapter start canal-adapter
poll_until 30 m1_task3_adapter_identity >/dev/null
restarted_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
container_after=$(m1_task3_container_id)
identity_after=$(m1_task3_adapter_identity)
test "$container_after" = "$container_before"
if process_identity_is_unchanged "$identity_before" "$identity_after"; then
  echo "canal-adapter Java identity did not change across stop/start" >&2
  exit 1
fi
jq -n --arg container "$container_after" --arg identity "$identity_after" \
  --arg captured "$restarted_at" '
  {container_id:$container,java_identity:$identity,captured_at:$captured}
' >"$out/adapter-after-start.json"

M1_MAPPING_PROOF_OUTPUT="$pre_mapping_proof" \
  bash tests/contracts/m1-adapter.sh --live >"$out/current-run-topology-proof.txt"
jq -e --arg container "$container_after" --arg identity "$identity_after" '
  .container_id == $container and .java_identity == $identity
' "$pre_mapping_proof" >/dev/null

deadline_reached=false
if ! poll_until 60 m1_task3_es_matches_source_price \
    "$product_id" "$out/mysql-while-down-snapshot.json" 200; then
  deadline_reached=true
fi
completed_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
m1_task3_capture_es "$product_id" "$out/es-snapshot.json"
m1_task3_snapshot_source "$product_id" "$out/mysql-snapshot.json"
jq -n --argjson deadline_reached "$deadline_reached" --arg completed "$completed_at" '
  {
    deadline_seconds:60,deadline_reached:$deadline_reached,
    observation_completed:true,completed_at:$completed
  }
' >"$out/target-observation.json"
jq -n \
  --arg started "$started_at" --arg stopped "$stopped_at" \
  --arg mutated "$source_mutated_at" --arg restarted "$restarted_at" \
  --arg completed "$completed_at" '
  {
    started_at:$started,stopped_at:$stopped,source_mutated_at:$mutated,
    restarted_at:$restarted,completed_at:$completed
  }
' >"$out/timestamps.json"
m1_task3_capture_adapter_log "$out/adapter.log"
scenarios/scripts/verify-m1-topology.sh \
  --mapping-continuity "$pre_mapping_proof" "$final_mapping_proof"

bash scenarios/scripts/derive-m1-restart-result.sh "$out" >"$out/result.json"
bash scenarios/scripts/assert-m1-restart-evidence.sh "$out"
