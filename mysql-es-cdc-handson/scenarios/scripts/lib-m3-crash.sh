#!/usr/bin/env bash

set -euo pipefail

compose=(docker compose -f infra/compose.yaml)
topic=product-search-revisions
group=product-search-sync-v1

die() { echo "ERROR: $*" >&2; exit 1; }

poll() {
  local description="$1" timeout="$2" command="$3" start=$SECONDS
  until eval "$command"; do
    (( SECONDS - start < timeout )) || die "timeout waiting for ${description}"
    sleep 1
  done
}

reset_stack() {
  "${compose[@]}" --profile m0-tools down --volumes --remove-orphans
  make up
  bash infra/elasticsearch/bootstrap-products-v2.sh
  "${compose[@]}" --profile m0-tools up -d --build search-sync-consumer
}

observe_http_json() {
  local url="$1" output="$2" body status rc valid=false
  body="$(mktemp)"
  set +e
  status="$(curl -sS -o "$body" -w '%{http_code}' "$url")"; rc=$?
  set -e
  if jq -e . "$body" >/dev/null 2>&1; then valid=true; fi
  jq -n --argjson transport_exit "$rc" --argjson http_status "${status:-0}" \
    --argjson json_valid "$valid" --rawfile raw_body "$body" \
    '{transport_exit:$transport_exit,http_status:$http_status,json_valid:$json_valid,raw_body:$raw_body}' >"$output"
  rm -f "$body"
}

wait_consumer_ready() {
  local final="$1" attempts start=$SECONDS observation
  attempts="${final%.json}-attempts.jsonl"
  : >"$attempts"
  while true; do
    observation="$(mktemp)"
    observe_http_json http://127.0.0.1:8082/actuator/health "$observation"
    jq -c . "$observation" >>"$attempts"
    if jq -e '.transport_exit==0 and .http_status==200 and .json_valid==true and (.raw_body|fromjson|.status)=="UP"' "$observation" >/dev/null; then
      mv "$observation" "$final"; return
    fi
    if ! jq -e '(.transport_exit!=0 and .http_status==0) or (.transport_exit==0 and .http_status==503 and .json_valid==true)' "$observation" >/dev/null; then
      cat "$observation" >&2; rm -f "$observation"; die "terminal consumer health response"
    fi
    rm -f "$observation"
    (( SECONDS - start < 120 )) || die "timeout waiting for consumer HTTP"
    sleep 1
  done
}

create_product() {
  local id="$1" output="${2:-/dev/null}" observation body status rc valid=false
  observation="${output%.json}-http.json"
  body="$(mktemp)"
  set +e
  status="$(curl -sS -o "$body" -w '%{http_code}' -X POST http://127.0.0.1:8081/api/products \
    -H 'Content-Type: application/json' \
    -d "{\"id\":${id},\"sku\":\"LAB-${id}\",\"name\":\"Crash ${id}\",\"description\":\"fixture\",\"categoryId\":10,\"priceCents\":100}")"; rc=$?
  set -e
  jq -e . "$body" >/dev/null 2>&1 && valid=true
  jq -n --argjson transport_exit "$rc" --argjson http_status "${status:-0}" --argjson json_valid "$valid" --rawfile raw_body "$body" '{transport_exit:$transport_exit,http_status:$http_status,json_valid:$json_valid,raw_body:$raw_body}' >"$observation"
  (( rc==0 && status==201 )) && [[ "$valid" == true ]] || die "create product HTTP failure"
  cp "$body" "$output"; rm -f "$body"
  jq -e --argjson id "$id" '.productId == $id and .revision == 1' "$output" >/dev/null
  wait_es_revision "$id" 1
  wait_group_zero
}

change_price() {
  local id="$1" price="$2" output="${3:-/dev/null}" observation body status rc valid=false
  observation="${output%.json}-http.json"
  body="$(mktemp)"
  set +e
  status="$(curl -sS -o "$body" -w '%{http_code}' -X PUT "http://127.0.0.1:8081/api/products/${id}/price" -H 'Content-Type: application/json' -d "{\"priceCents\":${price}}")"; rc=$?
  set -e
  jq -e . "$body" >/dev/null 2>&1 && valid=true
  jq -n --argjson transport_exit "$rc" --argjson http_status "${status:-0}" --argjson json_valid "$valid" --rawfile raw_body "$body" '{transport_exit:$transport_exit,http_status:$http_status,json_valid:$json_valid,raw_body:$raw_body}' >"$observation"
  (( rc==0 && status==200 )) && [[ "$valid" == true ]] || die "change price HTTP failure"
  cp "$body" "$output"; rm -f "$body"
  jq -e --argjson id "$id" '.productId == $id and .revision == 2' "$output" >/dev/null
}

source_state() {
  local id="$1"
  "${compose[@]}" exec -T mysql mysql -N -B -uproduct -pproductpass product_catalog \
    -e "SELECT JSON_OBJECT('product_id',p.id,'price_cents',p.price_cents,'revision',r.revision,'active',r.active) FROM products p JOIN product_search_revision r ON r.product_id=p.id WHERE p.id=${id};" \
    | jq -c .
}

wait_es_revision() {
  local id="$1" revision="$2" final="${3:-/tmp/m3-es-observation.json}" attempts start=$SECONDS observation
  attempts="${final%.json}-attempts.jsonl"
  : >"$attempts"
  while true; do
    observation="$(mktemp)"
    observe_http_json "http://127.0.0.1:9200/products_write/_doc/${id}" "$observation"
    jq -c . "$observation" >>"$attempts"
    if jq -e --argjson id "$id" --argjson revision "$revision" \
      '.transport_exit==0 and .http_status==200 and .json_valid==true and ((.raw_body|fromjson) | .found==true and (._id|tonumber)==$id and ._source.source_revision==$revision)' "$observation" >/dev/null; then
      mv "$observation" "$final"; return
    fi
    if ! jq -e '.transport_exit==0 and .json_valid==true and
      (.http_status==404 or (.http_status==503 and ((.raw_body|fromjson).error.root_cause|length)>0
        and all((.raw_body|fromjson).error.root_cause[];.type=="no_shard_available_action_exception")))' "$observation" >/dev/null; then
      cat "$observation" >&2; rm -f "$observation"; die "terminal Elasticsearch observation"
    fi
    rm -f "$observation"
    (( SECONDS - start < 120 )) || die "timeout waiting for ES revision"
    sleep 1
  done
}

group_json() {
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 --group "$group" --describe 2>/dev/null \
    | awk -v topic="$topic" '
      BEGIN { printf "[" }
      $2 == topic && $3 ~ /^[0-9]+$/ {
        committed=$4; lag=$6
        if (committed == "-" && $5 == 0 && lag == "-") { committed=0; lag=0 }
        if (committed !~ /^[0-9]+$/ || $5 !~ /^[0-9]+$/ || lag !~ /^[0-9]+$/) exit 42
        printf "%s{\"partition\":%s,\"committed\":%s,\"end\":%s,\"lag\":%s}", sep,$3,committed,$5,lag; sep="," }
      END { printf "]\n" }' | jq 'sort_by(.partition)'
}

group_raw() {
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh \
    --bootstrap-server kafka:9092 --group "$group" --describe 2>/dev/null
}

wait_group_zero() {
  poll "consumer group lag zero" 120 \
    "group_json | jq -e 'length == 3 and all(.[]; .lag == 0)' >/dev/null"
}

capture_matching_record() {
  local id="$1" revision="$2" baseline="$3" output="$4" records="$5" line prefix payload partition offset baseline_end
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 --topic "$topic" --from-beginning --timeout-ms 10000 \
    --property print.partition=true --property print.offset=true --property print.value=true \
    >"$records" 2>/dev/null || true
  line="$(awk -v id="\"product_id\":\"${id}\"" -v rev="\"revision\":\"${revision}\"" 'index($0,id)&&index($0,rev){print}' "$records" | tail -1)"
  test -n "$line" || die "matching revision record absent"
  prefix="${line%%\{*}"; payload="{${line#*\{}"
  partition="$(printf '%s' "$prefix" | sed -E 's/^Partition:([0-9]+).*/\1/')"
  offset="$(printf '%s' "$prefix" | sed -E 's/^.*Offset:([0-9]+).*/\1/')"
  jq -e --argjson id "$id" --argjson revision "$revision" \
    '.database=="product_catalog" and .table=="product_search_revision" and .isDdl==false
     and (.id|type)=="number" and .id>0 and (.type=="UPDATE" or .type=="INSERT")
     and (.data|length)==1 and (.data[0].product_id|tonumber)==$id
     and (.data[0].revision|tonumber)==$revision and (.data[0].active=="1")' <<<"$payload" >/dev/null
  baseline_end="$(jq -r --argjson partition "$partition" '.[]|select(.partition==$partition)|.end' "$baseline")"
  test -n "$baseline_end" && (( offset >= baseline_end )) || die "record predates baseline"
  jq -n --argjson partition "$partition" --argjson offset "$offset" --argjson baseline_end "$baseline_end" \
    --argjson payload "$payload" '{partition:$partition,offset:$offset,baseline_end:$baseline_end,payload:$payload}' >"$output"
}

container_state() {
  local id
  id="$("${compose[@]}" ps -a -q search-sync-consumer)"
  test -n "$id" || die "consumer container absent"
  docker inspect "$id" | jq -c '.[0] | {id:.Id,started_at:.State.StartedAt,running:.State.Running,exit_code:.State.ExitCode,finished_at:.State.FinishedAt}'
}

wait_exit_86() {
  poll "consumer exit code 86" 120 \
    "container_state | jq -e '.running == false and .exit_code == 86' >/dev/null"
}

assert_offset_uncommitted() {
  local group_file="$1" coordinates_file="$2"
  jq -e --slurpfile c "$coordinates_file" \
    '($c[0]) as $record | map(select(.partition == $record.partition)) | length == 1
     and .[0].committed <= $record.offset and .[0].end > $record.offset' "$group_file" >/dev/null
}

start_consumer() {
  "${compose[@]}" start search-sync-consumer >/dev/null
}

arm_failpoint() {
  local name="$1"
  curl -fsS -X DELETE http://127.0.0.1:8082/internal/failpoints >/dev/null
  curl -fsS -X POST "http://127.0.0.1:8082/internal/failpoints/${name}/arm?hits=1" \
    | jq -e --arg name "$name" '.[$name] == 1' >/dev/null
}

dlq_row() {
  local id="$1"
  "${compose[@]}" exec -T mysql mysql -N -B -uproduct -pproductpass product_catalog \
    -e "SELECT JSON_OBJECT('event_id',event_id,'topic',topic_name,'partition',partition_no,'offset',offset_no,'product_id',product_id,'revision',source_revision,'status',status,'attempts',attempts) FROM sync_dlq_record WHERE product_id=${id};" \
    | jq -s .
}

install_bad_mapping() {
  curl -fsS -X DELETE http://127.0.0.1:9200/products_v2 >/dev/null
  local bad_mapping
  bad_mapping="$(mktemp)"
  jq '.template.mappings.properties.price_cents.type="byte" | {mappings:(.template.mappings + {"_meta":{"schema_version":1,"deletion_mode":"tombstone","generation":"products_v2"}})}' \
    infra/elasticsearch/index-template.json >"$bad_mapping"
  curl -fsS -X PUT http://127.0.0.1:9200/products_v2 -H 'Content-Type: application/json' --data-binary @"$bad_mapping" >/dev/null
  rm -f "$bad_mapping"
  curl -fsS -X POST http://127.0.0.1:9200/_aliases -H 'Content-Type: application/json' \
    -d '{"actions":[{"add":{"index":"products_v2","alias":"products_write","is_write_index":true}},{"add":{"index":"products_v2","alias":"products_search","filter":{"term":{"searchable":true}}}}]}' >/dev/null
}

restore_mapping_without_resolution() {
  curl -fsS -X DELETE http://127.0.0.1:9200/products_v2 >/dev/null
  bash infra/elasticsearch/bootstrap-products-v2.sh
}
