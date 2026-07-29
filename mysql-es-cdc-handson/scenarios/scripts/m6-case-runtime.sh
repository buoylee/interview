#!/usr/bin/env bash

source scenarios/scripts/lib-m3-crash.sh
raw="$M6_CASE_RUN_DIR/raw"
waiter=scenarios/scripts/wait-condition.sh
compose=(docker compose -f infra/compose.yaml)

record_intermediate() {
  local state="$1" tmp="$M6_CASE_RUN_DIR/intermediate.next"
  test -f "$M6_CASE_RUN_DIR/intermediate-states.json" || printf '[]\n' >"$M6_CASE_RUN_DIR/intermediate-states.json"
  jq --arg state "$state" '.+[$state]|unique' "$M6_CASE_RUN_DIR/intermediate-states.json" >"$tmp"
  mv "$tmp" "$M6_CASE_RUN_DIR/intermediate-states.json"
}

mark_recovery() {
  jq -n --arg now "$(date -u +%Y-%m-%dT%H:%M:%SZ)" '{recovery_action_observed:true,finished_at:$now}' >"$M6_CASE_RUN_DIR/recovery-observed.json"
}

end_vector() {
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9092 --topic product-search-revisions --time -1 2>/dev/null |
    awk -F: 'BEGIN{printf "{"}{printf "%s\"%s\":%s",s,$2,$3;s=","}END{print "}"}' | jq -S .
}

copy_meta() { "${compose[@]}" cp canal:/home/admin/canal-data/products/meta.dat "$1" >/dev/null; }
decode_meta() { bash scenarios/scripts/decode-canal-meta.sh "$1"; }
mysql_root() { "${compose[@]}" exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e "$1"; }
pipeline_status() { curl -fsS http://127.0.0.1:8083/internal/pipeline/status; }
alias_index() { curl -fsS http://127.0.0.1:9200/_alias/products_search,products_write | jq -er 'if length==1 then keys[0] else error("split aliases") end'; }
rebuild_status() { curl -fsS "http://127.0.0.1:8083/internal/rebuild/runs/$1"; }
wait_rebuild_phase() {
  local run_id="$1" phase="$2"
  "$waiter" "rebuild $run_id reaches $phase" 240 0.2 bash -c 'curl -fsS "http://127.0.0.1:8083/internal/rebuild/runs/$1"|jq -e --arg phase "$2" ".status==\$phase" >/dev/null' _ "$run_id" "$phase"
}
start_rebuild_async() {
  local run_id="$1" page_size="$2" output="$3"
  curl -sS -X POST http://127.0.0.1:8083/internal/rebuild/runs -H 'Content-Type: application/json' \
    -d "{\"runId\":\"$run_id\",\"reason\":\"NORMAL\",\"topic\":\"product-search-revisions\",\"pageSize\":$page_size}" >"$output" 2>"$output.stderr" &
  printf '%s\n' "$!" >"$output.pid"
}

start_rebuild() {
  local reason="$1" page_size="$2" run_id response="$raw/rebuild-response.json"
  run_id="$(uuidgen | tr '[:upper:]' '[:lower:]')"
  curl -fsS -X POST http://127.0.0.1:8083/internal/rebuild/runs -H 'Content-Type: application/json' \
    -d "{\"runId\":\"$run_id\",\"reason\":\"$reason\",\"topic\":\"product-search-revisions\",\"pageSize\":$page_size}" >"$response"
  jq -e '.status=="COMPLETED" and .aliasState=="NEW"' "$response" >/dev/null
  printf '%s\n' "$run_id" >"$raw/rebuild-run-id"
}

metric_value() {
  curl -fsS http://127.0.0.1:8082/actuator/metrics/cdc_stale_revision_total |
    jq -r '[.measurements[]|select(.statistic=="COUNT" or .statistic=="VALUE")|.value]|first'
}

produce_with_key() {
  local key="$1" payload="$2"
  printf '%s:%s\n' "$key" "$payload" | "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server kafka:9092 --topic product-search-revisions \
    --property parse.key=true --property key.separator=: >/dev/null
}

changed_partition() {
  jq -nr --slurpfile before "$1" --slurpfile after "$2" '
    [$after[0]|to_entries[]|select(.value==$before[0][.key]+1)|(.key|tonumber)] as $changed |
    if ($changed|length)==1 and ([$after[0]|to_entries[]|select(.value!=$before[0][.key] and (.key|tonumber)!=$changed[0])]|length)==0
    then $changed[0] else error("not exactly one appended partition") end'
}

select_same_partition_product() {
  local first="$1" selected_file="$2" id probe_partition record_partition before after baseline payload
  for id in $(seq "$first" $((first+11))); do
    end_vector >"$raw/probe-$id-before.json"
    produce_with_key "$id" '{"database":"m6_probe","table":"ignored","isDdl":false,"data":[]}'
    "$waiter" "key partition probe $id" 60 0.2 bash -c 'before=$(jq "to_entries|map(.value)|add" "$1");after=$(docker compose -f "$2" exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9092 --topic product-search-revisions --time -1 2>/dev/null|awk -F: "{sum+=\$3}END{print sum}");test "$after" -eq $((before+1))' _ "$raw/probe-$id-before.json" "$PWD/infra/compose.yaml"
    end_vector >"$raw/probe-$id-after.json"; probe_partition="$(changed_partition "$raw/probe-$id-before.json" "$raw/probe-$id-after.json")"
    wait_group_zero; group_json >"$raw/candidate-$id-baseline.json"; create_product "$id" "$raw/candidate-$id-create.json"
    capture_matching_record "$id" 1 "$raw/candidate-$id-baseline.json" "$raw/candidate-$id-record.json" "$raw/candidate-$id-topic.txt"
    record_partition="$(jq -r .partition "$raw/candidate-$id-record.json")"
    if test "$probe_partition" -eq "$record_partition"; then
      jq -n --argjson id "$id" --argjson partition "$record_partition" --slurpfile record "$raw/candidate-$id-record.json" \
        '{product_id:$id,partition:$partition,record:$record[0]}' >"$selected_file"
      return 0
    fi
  done
  die 'unable to select a product whose keyed replay uses the original partition'
}

case_1() {
  case "$1" in
    mutate)
      create_product 6101 "$raw/create.json"
      copy_meta "$raw/meta-before.dat"; decode_meta "$raw/meta-before.dat" >"$raw/meta-before.json"
      shasum -a 256 "$raw/meta-before.dat" | awk '{print $1}' >"$raw/meta-before.sha256"
      end_vector >"$raw/end-before.json"
      "${compose[@]}" stop canal >"$raw/canal-stop.log" 2>&1 || true
      "${compose[@]}" start canal >"$raw/canal-start.log"
      "$waiter" 'Canal restarted from persisted cursor' 180 0.2 bash -c 'docker compose -f "$1" exec -T canal sh -lc "grep -F '\''find start position successfully'\'' /home/admin/canal-server/logs/products/products.log" >/dev/null' _ "$PWD/infra/compose.yaml"
      copy_meta "$raw/meta-after-restart.dat"; decode_meta "$raw/meta-after-restart.dat" >"$raw/meta-after-restart.json"
      shasum -a 256 "$raw/meta-after-restart.dat" | awk '{print $1}' >"$raw/meta-after-restart.sha256"
      cmp "$raw/meta-before.dat" "$raw/meta-after-restart.dat"
      end_vector >"$raw/end-after-restart.json"; cmp "$raw/end-before.json" "$raw/end-after-restart.json"
      "${compose[@]}" stop search-sync-consumer >/dev/null
      group_json >"$raw/group-before-mutation.json"
      change_price 6101 61101 "$raw/mutate.json"
      "$waiter" 'one post-restart Kafka record' 120 0.2 bash -c 'before=$(jq '\''to_entries|map(.value)|add'\'' "$1"); after=$(docker compose -f "$2" exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9092 --topic product-search-revisions --time -1 2>/dev/null|awk -F: '\''{sum+=$3}END{print sum}'\''); test "$after" -eq $((before+1))' _ "$raw/end-before.json" "$PWD/infra/compose.yaml"
      group_json >"$raw/group-consumer-stopped.json"; capture_matching_record 6101 2 "$raw/group-before-mutation.json" "$raw/post-restart-record.json" "$raw/topic-records.txt"
      jq -e --slurpfile before "$raw/end-before.json" '.offset==$before[0][(.partition|tostring)]' "$raw/post-restart-record.json" >/dev/null
      ;;
    intermediate)
      jq -e '._source.source_revision==1' <(curl -fsS http://127.0.0.1:9200/products_write/_doc/6101) >/dev/null
      container_state | jq -e '.running==false' >"$raw/consumer-stopped.json"
      record_intermediate CATCHING_UP
      ;;
    recover)
      start_consumer; wait_consumer_ready "$raw/consumer-restarted.json"; wait_es_revision 6101 2 "$raw/es-final.json"; wait_group_zero
      mark_recovery
      ;;
  esac
}

case_2() {
  case "$1" in
    mutate)
      create_product 6201 "$raw/create.json"; copy_meta "$raw/meta-before.dat"; decode_meta "$raw/meta-before.dat" >"$raw/meta-before.json"
      "${compose[@]}" stop canal >"$raw/canal-stop.log" 2>&1 || true
      change_price 6201 62201 "$raw/mutate.json"
      journal="$(jq -r .journal "$raw/meta-before.json")"
      mysql_root 'SHOW BINARY LOGS' >"$raw/binlogs-during-outage.tsv"
      awk '{print $1}' "$raw/binlogs-during-outage.tsv" | grep -Fx "$journal" >/dev/null
      ;;
    intermediate)
      source_state 6201 >"$raw/source-during.json"; curl -fsS http://127.0.0.1:9200/products_write/_doc/6201 >"$raw/es-during.json"
      jq -e '.revision==2' "$raw/source-during.json" >/dev/null; jq -e '._source.source_revision==1' "$raw/es-during.json" >/dev/null
      record_intermediate CATCHING_UP
      ;;
    recover)
      "${compose[@]}" start canal >/dev/null; wait_es_revision 6201 2 "$raw/es-final.json"; wait_group_zero; mark_recovery
      ;;
  esac
}

case_3() {
  case "$1" in
    mutate)
      create_product 6301 "$raw/create.json"; "${compose[@]}" stop canal >"$raw/canal-stop.log" 2>&1 || true
      copy_meta "$raw/old-meta.dat"; decode_meta "$raw/old-meta.dat" >"$raw/old-meta.json"
      old_journal="$(jq -r .journal "$raw/old-meta.json")"; old_position="$(jq -r .position "$raw/old-meta.json")"
      mysql_root 'FLUSH BINARY LOGS;' >/dev/null; current="$(mysql_root 'SHOW BINARY LOG STATUS;'|awk '{print $1}')"
      mysql_root "PURGE BINARY LOGS TO '$current';" >/dev/null
      mysql_root 'SHOW BINARY LOGS' >"$raw/retained-binlogs.tsv"
      retained="$(awk '{print $1}' "$raw/retained-binlogs.tsv"|jq -Rsc 'split("\n")|map(select(length>0))')"
      ! jq -e --arg journal "$old_journal" 'index($journal)!=null' <<<"$retained" >/dev/null
      "${compose[@]}" start canal >/dev/null
      "$waiter" 'Canal reports purged cursor' 120 0.2 bash -c 'docker compose -f "$1" logs --no-color canal 2>&1|grep -E '\''Could not find first log file name in binary log index file|purged|not found'\'' >/dev/null' _ "$PWD/infra/compose.yaml"
      jq -n --arg journal "$old_journal" --argjson position "$old_position" --argjson files "$retained" '{target:"mysql-binlog",journal:$journal,position:$position,retained_files:$files,recorded_present:false,canal_missing_position_observed:true}' >"$raw/gap-proof.json"
      bash scenarios/scripts/assert-gap-precondition.sh mysql-binlog "$raw/gap-proof.json"
      curl -fsS -X PUT http://127.0.0.1:8083/internal/pipeline/conditions/LOG_GAP -H 'Content-Type: application/json' -d "{\"journal\":\"$old_journal\",\"position\":$old_position}" >"$raw/log-gap.json"
      "$waiter" 'REBUILD_REQUIRED after MySQL gap' 120 0.2 bash -c 'curl -fsS http://127.0.0.1:8083/internal/pipeline/status|jq -e '\''.state=="REBUILD_REQUIRED" and (.activeConditions|index("LOG_GAP"))!=null'\'' >/dev/null'
      ;;
    intermediate)
      pipeline_status >"$raw/status-gap.json"; jq -e '.state=="REBUILD_REQUIRED"' "$raw/status-gap.json" >/dev/null
      record_intermediate REBUILD_REQUIRED; printf 'true\n' >"$M6_CASE_RUN_DIR/rebuild-required-before-rebuild"
      ;;
    recover)
      run_id="$(uuidgen | tr '[:upper:]' '[:lower:]')"
      curl -fsS -X POST http://127.0.0.1:8083/internal/rebuild/runs -H 'Content-Type: application/json' -d "{\"runId\":\"$run_id\",\"reason\":\"MYSQL_BINLOG_GAP\",\"topic\":\"product-search-revisions\",\"pageSize\":200}" >"$raw/recovery-required.json"
      curl -fsS -X POST "http://127.0.0.1:8083/internal/rebuild/runs/$run_id/canal-recovery/start" >"$raw/recovery-started.json"
      bash scenarios/scripts/reset-canal-position.sh "$run_id" "$raw/canal-recovery"
      "$waiter" 'MySQL gap rebuild completed' 900 0.2 bash -c 'curl -fsS "http://127.0.0.1:8083/internal/rebuild/runs/$1"|jq -e '\''.status=="COMPLETED" and .aliasState=="NEW"'\'' >/dev/null' _ "$run_id"
      mark_recovery
      ;;
  esac
}

case_4() {
  case "$1" in
    mutate)
      create_product 6401 "$raw/create.json"; end_vector >"$raw/end-before.json"
      SCENARIO_CLEANUP_FILE="$raw/network-cleanup.sh" bash scenarios/scripts/fault-network.sh apply kafka-timeout >"$raw/toxic-applied.json"
      change_price 6401 64401 "$raw/mutate.json"; source_state 6401 >"$raw/source-during.json"; end_vector >"$raw/end-during.json"
      cmp "$raw/end-before.json" "$raw/end-during.json"
      ;;
    intermediate)
      jq -e '.revision==2' "$raw/source-during.json" >/dev/null; jq -e '._source.source_revision==1' <(curl -fsS http://127.0.0.1:9200/products_write/_doc/6401) >/dev/null
      bash scenarios/scripts/fault-network.sh status kafka-timeout | jq -e '.active==true' >"$raw/toxic-status.json"
      record_intermediate CATCHING_UP
      ;;
    recover)
      bash scenarios/scripts/fault-network.sh remove kafka-timeout >"$raw/toxic-removed.json"; wait_es_revision 6401 2 "$raw/es-final.json"; wait_group_zero; mark_recovery
      ;;
  esac
}

case_5() {
  case "$1" in
    mutate)
      # The retention primitive appends product 900001 records to the selected
      # partition. Keep that product real in MySQL so the first retained record
      # rehydrates current source state instead of creating an unrelated DLQ.
      create_product 900001 "$raw/create.json"
      jq -n --arg project "$COMPOSE_PROJECT_NAME" '{purpose:"m6-dedicated-retention",compose_project:$project}' >"$raw/retention-provenance.json"
      SCENARIO_CLEANUP_FILE="$raw/retention-cleanup.sh" SCENARIO_STATE_DIR="$raw/retention-state" SCENARIO_PROVENANCE_FILE="$raw/retention-provenance.json" M6_RETENTION_DESTRUCTIVE_ACK=I_UNDERSTAND_M6_DEDICATED_RETENTION_DESTROYS_LOGS \
        bash scenarios/scripts/fault-retention.sh apply kafka >"$raw/kafka-gap-status.json"
      partition="$(jq -r .selected_partition "$raw/kafka-gap-status.json")"
      jq -n --argjson partition "$partition" --argjson committed "$(jq -r --arg p "$partition" '.captured_committed' "$raw/kafka-gap-status.json")" --argjson beginning "$(jq -r --arg p "$partition" '.beginning[$p]' "$raw/kafka-gap-status.json")" '{target:"kafka",topic:"product-search-revisions",partition:$partition,committed_offset:$committed,beginning_offset:$beginning}' >"$raw/gap-proof.json"
      bash scenarios/scripts/assert-gap-precondition.sh kafka "$raw/gap-proof.json"
      "${compose[@]}" --profile m0-tools start search-sync-consumer >/dev/null
      "$waiter" 'consumer detects expired Kafka offset' 120 0.2 bash -c 'curl -fsS http://127.0.0.1:8083/internal/pipeline/status|jq -e '\''.state=="REBUILD_REQUIRED" and (.activeConditions|index("LOG_GAP"))!=null'\'' >/dev/null'
      wait_consumer_ready "$raw/consumer-after-gap.json"
      ;;
    intermediate)
      pipeline_status >"$raw/status-gap.json"; jq -e '.state=="REBUILD_REQUIRED"' "$raw/status-gap.json" >/dev/null
      record_intermediate REBUILD_REQUIRED; printf 'true\n' >"$M6_CASE_RUN_DIR/rebuild-required-before-rebuild"
      ;;
    recover)
      start_rebuild NORMAL 200; mark_recovery
      ;;
  esac
}

case_6() {
  case "$1" in
    mutate)
      create_product 6601 "$raw/create.json"; group_json >"$raw/group-before.json"
      arm_failpoint BEFORE_ES_BULK; change_price 6601 66101 "$raw/mutate.json"; wait_exit_86
      container_state >"$raw/crashed.json"; capture_matching_record 6601 2 "$raw/group-before.json" "$raw/record.json" "$raw/topic.txt"
      group_json >"$raw/group-crashed.json"; assert_offset_uncommitted "$raw/group-crashed.json" "$raw/record.json"
      ;;
    intermediate)
      jq -e '.running==false and .exit_code==86' "$raw/crashed.json" >/dev/null
      jq -e '._source.source_revision==1' <(curl -fsS http://127.0.0.1:9200/products_write/_doc/6601) >/dev/null
      record_intermediate CATCHING_UP
      ;;
    recover)
      start_consumer; wait_consumer_ready "$raw/restarted.json"; wait_es_revision 6601 2 "$raw/es-final.json"; wait_group_zero; mark_recovery
      ;;
  esac
}

case_7() {
  case "$1" in
    mutate)
      create_product 6701 "$raw/create.json"; group_json >"$raw/group-before.json"
      arm_failpoint AFTER_ES_BULK_SUCCESS; change_price 6701 67101 "$raw/mutate.json"; wait_exit_86
      container_state >"$raw/crashed.json"; capture_matching_record 6701 2 "$raw/group-before.json" "$raw/record.json" "$raw/topic.txt"
      group_json >"$raw/group-crashed.json"; assert_offset_uncommitted "$raw/group-crashed.json" "$raw/record.json"
      curl -fsS http://127.0.0.1:9200/products_write/_doc/6701 >"$raw/es-before-restart.json"
      ;;
    intermediate)
      jq -e '.running==false and .exit_code==86' "$raw/crashed.json" >/dev/null
      jq -e '._source.source_revision==2' "$raw/es-before-restart.json" >/dev/null
      record_intermediate CATCHING_UP
      ;;
    recover)
      start_consumer; wait_consumer_ready "$raw/restarted.json"; wait_group_zero
      curl -fsS http://127.0.0.1:9200/products_write/_doc/6701 >"$raw/es-after-restart.json"
      jq -e --slurpfile before "$raw/es-before-restart.json" '._source.source_revision==2 and ._version==2 and ._seq_no==$before[0]._seq_no' "$raw/es-after-restart.json" >/dev/null
      mark_recovery
      ;;
  esac
}

case_8() {
  case "$1" in
    mutate)
      create_product 6801 "$raw/create-valid.json"; create_product 6804 "$raw/create-invalid.json"
      group_json >"$raw/group-before.json"
      curl -fsS -X PUT 'http://127.0.0.1:8082/internal/lab/projection-fault/PRICE_CENTS_AS_STRING?productId=6804' >"$raw/fault.json"
      mysql_root 'START TRANSACTION; UPDATE products SET price_cents=68010 WHERE id=6801; UPDATE products SET price_cents=68040 WHERE id=6804; UPDATE product_search_revision SET revision=revision+1,updated_at=CURRENT_TIMESTAMP(6) WHERE product_id IN (6801,6804); COMMIT;' >/dev/null
      "$waiter" 'one durable product DLQ' 120 0.2 bash -c 'curl -fsS http://127.0.0.1:8082/internal/dlq/count|jq -e ".unresolved==1" >/dev/null'
      capture_matching_batch_record 6801 6804 2 "$raw/group-before.json" "$raw/batch-record.json" "$raw/topic.txt"
      group_json >"$raw/group-settled.json"; jq -e --slurpfile r "$raw/batch-record.json" 'map(select(.partition==$r[0].partition))[0].committed > $r[0].offset' "$raw/group-settled.json" >/dev/null
      curl -fsS 'http://127.0.0.1:8082/internal/dlq?status=PENDING' >"$raw/dlq-pending.json"
      ;;
    intermediate)
      wait_es_revision 6801 2 "$raw/es-valid.json"; jq -e '._source.source_revision==1' <(curl -fsS http://127.0.0.1:9200/products_write/_doc/6804) >/dev/null
      jq -e --slurpfile r "$raw/batch-record.json" 'length==1 and .[0].productId==6804 and .[0].sourceRevision==2 and .[0].status=="PENDING" and .[0].partition==$r[0].partition and .[0].offset==$r[0].offset' "$raw/dlq-pending.json" >/dev/null
      record_intermediate DEGRADED
      ;;
    recover)
      curl -fsS -X DELETE http://127.0.0.1:8082/internal/lab/projection-fault >"$raw/fault-cleared.json"
      event="$(jq -r '.[0].eventId' "$raw/dlq-pending.json")"; encoded="$(jq -rn --arg v "$event" '$v|@uri')"
      curl -fsS -X POST "http://127.0.0.1:8082/internal/dlq/$encoded/replay" >"$raw/replay.json"
      jq -e '.status=="RESOLVED"' "$raw/replay.json" >/dev/null; wait_es_revision 6804 2 "$raw/es-replayed.json"; mark_recovery
      ;;
  esac
}

case_9() {
  case "$1" in
    mutate)
      select_same_partition_product 6901 "$raw/selected.json"; id="$(jq -r .product_id "$raw/selected.json")"; payload="$(jq -c .record.payload "$raw/selected.json")"
      curl -fsS "http://127.0.0.1:9200/products_write/_doc/$id" >"$raw/es-before.json"; metric_value >"$raw/stale-before"
      end_vector >"$raw/replay-before.json"; produce_with_key "$id" "$payload"
      "$waiter" 'duplicate record settled' 60 0.2 bash -c 'before=$(jq "to_entries|map(.value)|add" "$1");after=$(docker compose -f "$2" exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9092 --topic product-search-revisions --time -1 2>/dev/null|awk -F: "{sum+=\$3}END{print sum}");test "$after" -eq $((before+1))' _ "$raw/replay-before.json" "$PWD/infra/compose.yaml"
      end_vector >"$raw/replay-after.json"; test "$(changed_partition "$raw/replay-before.json" "$raw/replay-after.json")" -eq "$(jq -r .partition "$raw/selected.json")"; wait_group_zero
      ;;
    intermediate)
      id="$(jq -r .product_id "$raw/selected.json")"; curl -fsS "http://127.0.0.1:9200/products_write/_doc/$id" >"$raw/es-after.json"
      cmp <(jq -S '{_version,_source}' "$raw/es-before.json") <(jq -S '{_version,_source}' "$raw/es-after.json")
      after="$(metric_value)"; before="$(cat "$raw/stale-before")"; awk -v a="$after" -v b="$before" 'BEGIN{exit !(a>b)}'
      record_intermediate HEALTHY
      ;;
    recover) mark_recovery ;;
  esac
}

case_10() {
  case "$1" in
    mutate)
      select_same_partition_product 7001 "$raw/selected.json"; id="$(jq -r .product_id "$raw/selected.json")"; payload="$(jq -c .record.payload "$raw/selected.json")"
      change_price "$id" 70020 "$raw/revision-2.json"; wait_es_revision "$id" 2 "$raw/es-revision-2.json"
      curl -fsS -X PUT "http://127.0.0.1:8081/api/products/$id/price" -H 'Content-Type: application/json' -d '{"priceCents":70030}' >"$raw/revision-3.json"
      jq -e '.revision==3' "$raw/revision-3.json" >/dev/null
      wait_es_revision "$id" 3 "$raw/es-before-old-ready.json"
      curl -fsS "http://127.0.0.1:9200/products_write/_doc/$id" >"$raw/es-before-old.json"
      metric_value >"$raw/stale-before"
      end_vector >"$raw/replay-before.json"; produce_with_key "$id" "$payload"
      "$waiter" 'late old signal settled' 60 0.2 bash -c 'before=$(jq "to_entries|map(.value)|add" "$1");after=$(docker compose -f "$2" exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9092 --topic product-search-revisions --time -1 2>/dev/null|awk -F: "{sum+=\$3}END{print sum}");test "$after" -eq $((before+1))' _ "$raw/replay-before.json" "$PWD/infra/compose.yaml"
      end_vector >"$raw/replay-after.json"; test "$(changed_partition "$raw/replay-before.json" "$raw/replay-after.json")" -eq "$(jq -r .partition "$raw/selected.json")"; wait_group_zero
      ;;
    intermediate)
      id="$(jq -r .product_id "$raw/selected.json")"; curl -fsS "http://127.0.0.1:9200/products_write/_doc/$id" >"$raw/es-after-old.json"
      jq -e --slurpfile before "$raw/es-before-old.json" '._source.source_revision==3 and ._source.price_cents==70030 and ._version==3 and ._seq_no==$before[0]._seq_no' "$raw/es-after-old.json" >/dev/null
      after="$(metric_value)"; before="$(cat "$raw/stale-before")"; awk -v a="$after" -v b="$before" 'BEGIN{exit !(a>b)}'; record_intermediate HEALTHY
      ;;
    recover) mark_recovery ;;
  esac
}

case_11() {
  case "$1" in
    mutate)
      create_product 7101 "$raw/create.json"; curl -fsS http://127.0.0.1:9200/_alias/products_write | jq -r 'keys[0]' >"$raw/generation-before"
      curl -fsS -X PUT 'http://127.0.0.1:8082/internal/lab/projection-fault/PRICE_CENTS_AS_STRING?productId=7101' >"$raw/fault.json"
      change_price 7101 71101 "$raw/mutate.json"
      "$waiter" 'mapping conflict DLQ' 120 0.2 bash -c 'curl -fsS http://127.0.0.1:8082/internal/dlq/count|jq -e ".unresolved==1" >/dev/null'
      curl -fsS 'http://127.0.0.1:8082/internal/dlq?status=PENDING' >"$raw/dlq-pending.json"
      ;;
    intermediate)
      pipeline_status >"$raw/status-degraded.json"; jq -e '.state=="DEGRADED" and .unresolvedDlq==1' "$raw/status-degraded.json" >/dev/null
      jq -e 'length==1 and .[0].productId==7101 and .[0].sourceRevision==2 and .[0].status=="PENDING"' "$raw/dlq-pending.json" >/dev/null
      record_intermediate DEGRADED
      ;;
    recover)
      curl -fsS -X DELETE http://127.0.0.1:8082/internal/lab/projection-fault >"$raw/fault-cleared.json"
      event="$(jq -r '.[0].eventId' "$raw/dlq-pending.json")"; encoded="$(jq -rn --arg v "$event" '$v|@uri')"
      curl -fsS -X POST "http://127.0.0.1:8082/internal/dlq/$encoded/replay" >"$raw/replay.json"; jq -e '.status=="RESOLVED"' "$raw/replay.json" >/dev/null
      wait_es_revision 7101 2 "$raw/es-final.json"; curl -fsS http://127.0.0.1:9200/_alias/products_write | jq -r 'keys[0]' >"$raw/generation-after"; cmp "$raw/generation-before" "$raw/generation-after"; mark_recovery
      ;;
  esac
}

case_12() {
  case "$1" in
    mutate)
      create_product 7201 "$raw/create-missing.json"; create_product 7202 "$raw/create-modified.json"
      curl -fsS http://127.0.0.1:9200/products_write/_doc/7202 >"$raw/es-original.json"
      curl -fsS -X DELETE 'http://127.0.0.1:9200/products_write/_doc/7201?version=1&version_type=external_gte' >"$raw/delete-es.json"
      jq -e '.result=="deleted" and ._version==1' "$raw/delete-es.json" >/dev/null
      jq '._source|.name="manual-corruption"' "$raw/es-original.json" | curl -fsS -X PUT 'http://127.0.0.1:9200/products_write/_doc/7202?version=1&version_type=external_gte' -H 'Content-Type: application/json' --data-binary @- >"$raw/corrupt-es.json"
      curl -fsS -X POST http://127.0.0.1:9200/products_write/_refresh >/dev/null
      curl -fsS -X POST http://127.0.0.1:8083/internal/reconciliation/runs -H 'Content-Type: application/json' -d '{"target":"products_write","pageSize":200}' >"$raw/diff-run.json"
      ;;
    intermediate)
      jq -e '.status=="DIFF" and .differenceCount==2 and .counts.MISSING==1 and .counts.MODIFIED==1' "$raw/diff-run.json" >/dev/null
      run="$(jq -r .runId "$raw/diff-run.json")"; mysql_root "SELECT JSON_ARRAYAGG(JSON_OBJECT('product_id',product_id,'type',difference_type,'fields',fields_json)) FROM verification_difference WHERE run_id=UUID_TO_BIN('$run') ORDER BY product_id;" | jq . >"$raw/differences.json"
      jq -e 'length==2 and any(.[];.product_id==7201 and .type=="MISSING") and any(.[];.product_id==7202 and .type=="MODIFIED" and any(.fields[];.field=="name"))' "$raw/differences.json" >/dev/null
      record_intermediate DEGRADED
      ;;
    recover)
      run="$(jq -r .runId "$raw/diff-run.json")"; curl -fsS -X POST "http://127.0.0.1:8083/internal/reconciliation/runs/$run/repair" >"$raw/repair.json"
      jq -e '.repaired==true and .failed==0 and .applied==2' "$raw/repair.json" >/dev/null
      mysql_root "SELECT JSON_ARRAYAGG(JSON_OBJECT('product_id',product_id,'action_type',action_type,'outcome',outcome)) FROM repair_action WHERE run_id=UUID_TO_BIN('$run') ORDER BY product_id;" | jq . >"$raw/repair-actions.json"
      jq -e 'length==2 and all(.[];.action_type=="WRITE_EXTERNAL_GTE" and .outcome=="APPLIED")' "$raw/repair-actions.json" >/dev/null
      curl -fsS -X POST http://127.0.0.1:9200/products_write/_refresh >/dev/null
      curl -fsS -X POST http://127.0.0.1:8083/internal/reconciliation/runs -H 'Content-Type: application/json' -d '{"target":"products_write","pageSize":200}' >"$raw/fresh-pass.json"; jq -e '.status=="PASS" and .differenceCount==0' "$raw/fresh-pass.json" >/dev/null; mark_recovery
      ;;
  esac
}

case_13() {
  case "$1" in
    mutate)
      create_product 7301 "$raw/create-1.json"; create_product 7304 "$raw/create-2.json"; create_product 7307 "$raw/create-3.json"
      group_json >"$raw/group-before.json"; mysql_root 'SELECT JSON_ARRAYAGG(JSON_OBJECT("product_id",product_id,"revision",revision,"updated_at",DATE_FORMAT(updated_at,"%Y-%m-%dT%H:%i:%s.%fZ"))) FROM product_search_revision WHERE product_id IN (7301,7304,7307) ORDER BY product_id;' | jq . >"$raw/source-before.json"
      "${compose[@]}" stop search-sync-consumer >/dev/null
      curl -fsS -X PUT http://127.0.0.1:8081/api/categories/10 -H 'Content-Type: application/json' -d '{"name":"M6 Renamed Category"}' >"$raw/rename.json"
      mysql_root 'SELECT JSON_ARRAYAGG(JSON_OBJECT("product_id",product_id,"revision",revision,"updated_at",DATE_FORMAT(updated_at,"%Y-%m-%dT%H:%i:%s.%fZ"))) FROM product_search_revision WHERE product_id IN (7301,7304,7307) ORDER BY product_id;' | jq . >"$raw/source-after.json"
      ;;
    intermediate)
      jq -e 'length==3 and all(.[];.revision==2) and ([.[].updated_at]|unique|length)==1' "$raw/source-after.json" >/dev/null
      "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic product-search-revisions --from-beginning --timeout-ms 10000 --property print.partition=true --property print.offset=true --property print.value=true >"$raw/topic.txt" 2>/dev/null || true
      line="$(awk 'index($0,"\"product_id\":\"7301\"")&&index($0,"\"product_id\":\"7304\"")&&index($0,"\"product_id\":\"7307\""){print}' "$raw/topic.txt"|tail -1)"; test -n "$line"; payload="{${line#*\{}"
      jq -e '.table=="product_search_revision" and .type=="UPDATE" and (.data|length)==3 and ([.data[].product_id|tonumber]|sort)==[7301,7304,7307] and all(.data[];(.revision|tonumber)==2)' <<<"$payload" >"$raw/three-row-record.json"
      for id in 7301 7304 7307; do curl -fsS "http://127.0.0.1:9200/products_write/_doc/$id" | jq -e '._source.source_revision==1' >/dev/null; done
      container_state | jq -e '.running==false' >"$raw/consumer-stopped.json"
      record_intermediate CATCHING_UP
      ;;
    recover)
      start_consumer; wait_consumer_ready "$raw/consumer-restarted.json"
      "$waiter" 'three category rename revisions in ES' 120 0.2 bash -c 'for id in 7301 7304 7307;do curl -fsS "http://127.0.0.1:9200/products_write/_doc/$id"|jq -e '\''._source.source_revision==2 and ._source.category_name=="M6 Renamed Category"'\'' >/dev/null||exit 1;done'
      wait_group_zero; mark_recovery
      ;;
  esac
}

case_14() {
  case "$1" in
    mutate)
      select_same_partition_product 7401 "$raw/selected.json"; id="$(jq -r .product_id "$raw/selected.json")"; payload="$(jq -c .record.payload "$raw/selected.json")"
      curl -fsS -X DELETE "http://127.0.0.1:8081/api/products/$id" >"$raw/delete.json"; jq -e '.revision==2' "$raw/delete.json" >/dev/null
      wait_es_revision "$id" 2 "$raw/tombstone-before.json"; end_vector >"$raw/replay-before.json"; produce_with_key "$id" "$payload"; wait_group_zero
      ;;
    intermediate)
      id="$(jq -r .product_id "$raw/selected.json")"; curl -fsS "http://127.0.0.1:9200/products_write/_doc/$id" >"$raw/tombstone-after.json"
      jq -e '._version==2 and ._source.source_revision==2 and ._source.searchable==false and (._source|keys|sort)==["product_id","searchable","source_revision","source_updated_at"]' "$raw/tombstone-after.json" >/dev/null
      curl -fsS -X POST http://127.0.0.1:9200/products_search/_search \
        -H 'Content-Type: application/json' -d "{\"query\":{\"ids\":{\"values\":[\"$id\"]}}}" >"$raw/search-alias-result.json"
      jq -e '.hits.total.value==0 and (.hits.hits|length)==0' "$raw/search-alias-result.json" >/dev/null
      record_intermediate HEALTHY
      ;;
    recover) mark_recovery ;;
  esac
}

case_15() {
  case "$1" in
    mutate)
      for id in $(seq 7501 7530); do create_product "$id" "$raw/create-$id.json"; done
      code="$(curl -sS -o "$raw/pre-rebuild-write.json" -w '%{http_code}' -X PUT http://127.0.0.1:8081/api/products/7501/price -H 'Content-Type: application/json' -d '{"priceCents":75100}')"; test "$code" -ge 200 && test "$code" -lt 300
      run_id="$(uuidgen|tr '[:upper:]' '[:lower:]')"; printf '%s\n' "$run_id" >"$raw/rebuild-run-id"; start_rebuild_async "$run_id" 10 "$raw/rebuild-response.json"
      "$waiter" 'one partial ten-row snapshot page' 60 0.2 bash -c 'docker compose -f "$1" exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e "SELECT page_size,source_count,(SELECT COUNT(*) FROM product_search_revision),status FROM rebuild_run WHERE run_id=UUID_TO_BIN('\''$2'\'');"|awk '\''$1==10&&$2>0&&$2<$3&&$4=="SNAPSHOTTING"{ok=1}END{exit !ok}'\''' _ "$PWD/infra/compose.yaml" "$run_id"
      mysql_root "SELECT JSON_OBJECT('page_size',page_size,'source_count',source_count,'total',(SELECT COUNT(*) FROM product_search_revision),'status',status) FROM rebuild_run WHERE run_id=UUID_TO_BIN('$run_id');" | jq . >"$raw/page-progress.json"
      curl -sS -o "$raw/concurrent-rename.json" -w '%{http_code}' -X PUT http://127.0.0.1:8081/api/categories/10 -H 'Content-Type: application/json' -d '{"name":"Concurrent M6"}' >"$raw/concurrent-rename.code" & p1=$!
      curl -sS -o "$raw/concurrent-inventory.json" -w '%{http_code}' -X PUT http://127.0.0.1:8081/api/products/7502/inventory -H 'Content-Type: application/json' -d '{"availableQuantity":77,"reservedQuantity":0}' >"$raw/concurrent-inventory.code" & p2=$!
      curl -sS -o "$raw/concurrent-delete.json" -w '%{http_code}' -X DELETE http://127.0.0.1:8081/api/products/7503 >"$raw/concurrent-delete.code" & p3=$!
      curl -sS -o "$raw/concurrent-create.json" -w '%{http_code}' -X POST http://127.0.0.1:8081/api/products -H 'Content-Type: application/json' -d '{"id":7599,"sku":"LAB-7599","name":"Concurrent Create","description":"during scan","categoryId":10,"priceCents":7599}' >"$raw/concurrent-create.code" & p4=$!
      wait "$p1" "$p2" "$p3" "$p4"; for f in "$raw"/concurrent-*.code; do code="$(cat "$f")"; test "$code" -ge 200 && test "$code" -lt 300; done
      wait_rebuild_phase "$run_id" GATING; rebuild_status "$run_id" >"$raw/status-gating.json"
      code="$(curl -sS -o "$raw/gated-write.json" -w '%{http_code}' -X PUT http://127.0.0.1:8081/api/products/7501/price -H 'Content-Type: application/json' -d '{"priceCents":75101}')"; test "$code" -eq 503
      ;;
    intermediate)
      jq -e '.status=="GATING"' "$raw/status-gating.json" >/dev/null
      jq -e '.page_size==10 and .source_count>0 and .source_count<.total and .status=="SNAPSHOTTING"' "$raw/page-progress.json" >/dev/null
      printf 'true\n' >"$M6_CASE_RUN_DIR/rebuild-required-before-rebuild"
      record_intermediate REBUILDING
      ;;
    recover)
      run_id="$(cat "$raw/rebuild-run-id")"; wait_rebuild_phase "$run_id" COMPLETED; rebuild_status "$run_id" >"$raw/rebuild-completed.json"
      jq -e '.status=="COMPLETED" and .aliasState=="NEW" and (.startOffsets|length)==3 and (.barrierOffsets|length)==3 and (.shadowOffsets|length)==3' "$raw/rebuild-completed.json" >/dev/null
      code="$(curl -sS -o "$raw/post-gate-write.json" -w '%{http_code}' -X PUT http://127.0.0.1:8081/api/products/7501/price -H 'Content-Type: application/json' -d '{"priceCents":75101}')"; test "$code" -ge 200 && test "$code" -lt 300; mark_recovery
      ;;
  esac
}

case_16() {
  case "$1" in
    mutate)
      for id in $(seq 7601 7615); do create_product "$id" "$raw/create-$id.json"; done
      alias_index >"$raw/old-alias"; curl -fsS -X PUT http://127.0.0.1:8083/internal/rebuild/failpoint/BEFORE_ALIAS_SWITCH >"$raw/before-failpoint.json"
      run_id="$(uuidgen|tr '[:upper:]' '[:lower:]')"; printf '%s\n' "$run_id" >"$raw/before-run-id"; start_rebuild_async "$run_id" 200 "$raw/before-response.json"
      "$waiter" 'pipeline exposes rebuilding' 120 0.2 bash -c 'curl -fsS http://127.0.0.1:8083/internal/pipeline/status|jq -e '\''.state=="REBUILDING"'\'' >/dev/null'; pipeline_status >"$raw/status-rebuilding.json"
      wait_rebuild_phase "$run_id" FAILED; rebuild_status "$run_id" >"$raw/before-failed.json"; alias_index >"$raw/alias-after-failure"; cmp "$raw/old-alias" "$raw/alias-after-failure"
      "${compose[@]}" restart consistency-verifier >"$raw/verifier-restart-before.log"; "$waiter" 'verifier after pre-alias crash' 180 0.2 curl -fsS http://127.0.0.1:8083/actuator/health >/dev/null
      alias_index >"$raw/alias-after-restart"; cmp "$raw/old-alias" "$raw/alias-after-restart"; pipeline_status >"$raw/status-failed.json"
      ;;
    intermediate)
      jq -e '.state=="REBUILDING"' "$raw/status-rebuilding.json" >/dev/null; jq -e '.status=="FAILED" and .aliasState=="OLD"' "$raw/before-failed.json" >/dev/null
      printf 'true\n' >"$M6_CASE_RUN_DIR/rebuild-required-before-rebuild"
      record_intermediate REBUILDING; record_intermediate DEGRADED
      ;;
    recover)
      curl -fsS -X DELETE http://127.0.0.1:8083/internal/rebuild/failpoint >"$raw/before-cleared.json"
      rerun="$(uuidgen|tr '[:upper:]' '[:lower:]')"; curl -fsS -X POST http://127.0.0.1:8083/internal/rebuild/runs -H 'Content-Type: application/json' -d "{\"runId\":\"$rerun\",\"reason\":\"NORMAL\",\"topic\":\"product-search-revisions\",\"pageSize\":200}" >"$raw/rerun-response.json"; jq -e '.status=="COMPLETED" and .aliasState=="NEW"' "$raw/rerun-response.json" >/dev/null
      curl -fsS -X PUT http://127.0.0.1:8083/internal/rebuild/failpoint/AFTER_ALIAS_SWITCH_BEFORE_GATE_OPEN >"$raw/after-failpoint.json"
      after_run="$(uuidgen|tr '[:upper:]' '[:lower:]')"; printf '%s\n' "$after_run" >"$raw/after-run-id"; start_rebuild_async "$after_run" 200 "$raw/after-response.json"
      wait_rebuild_phase "$after_run" CUTOVER_COMMITTED; alias_index >"$raw/promoted-before-restart"; rebuild_status "$after_run" >"$raw/after-cutover-status.json"
      "${compose[@]}" restart consistency-verifier >"$raw/verifier-restart-after.log"; "$waiter" 'verifier after post-alias crash' 180 0.2 curl -fsS http://127.0.0.1:8083/actuator/health >/dev/null
      wait_rebuild_phase "$after_run" COMPLETED; alias_index >"$raw/promoted-after-restart"; cmp "$raw/promoted-before-restart" "$raw/promoted-after-restart"; curl -fsS -X DELETE http://127.0.0.1:8083/internal/rebuild/failpoint >"$raw/after-cleared.json"; mark_recovery
      ;;
  esac
}

case_17() {
  case "$1" in
    mutate)
      create_product 7701 "$raw/create.json"; curl -fsS -X PUT http://127.0.0.1:8082/internal/lab/projection-fault/CATEGORY_NAME_FROM_ID >"$raw/fault.json"
      curl -fsS -X PUT http://127.0.0.1:8081/api/categories/10 -H 'Content-Type: application/json' -d '{"name":"Correct Category Name"}' >"$raw/rename.json"
      "$waiter" 'wrong same-revision category projection' 120 0.2 bash -c 'curl -fsS http://127.0.0.1:9200/products_write/_doc/7701|jq -e '\''._version==2 and ._source.source_revision==2 and ._source.category_name=="10"'\'' >/dev/null'
      curl -fsS -X DELETE http://127.0.0.1:8082/internal/lab/projection-fault >"$raw/fault-cleared.json"
      curl -fsS -X POST http://127.0.0.1:9200/products_write/_refresh >/dev/null; curl -fsS -X POST http://127.0.0.1:8083/internal/reconciliation/runs -H 'Content-Type: application/json' -d '{"target":"products_write","pageSize":200}' >"$raw/diff-run.json"
      ;;
    intermediate)
      jq -e '.status=="DIFF" and .differenceCount>=1 and .counts.MODIFIED>=1' "$raw/diff-run.json" >/dev/null
      run="$(jq -r .runId "$raw/diff-run.json")"; mysql_root "SELECT COUNT(*) FROM verification_difference WHERE run_id=UUID_TO_BIN('$run') AND product_id=7701 AND difference_type='MODIFIED' AND JSON_CONTAINS(fields_json,JSON_OBJECT('field','category_name'),'$');" | grep -qx 1
      pipeline_status >"$raw/status-degraded.json"; jq -e '.state=="DEGRADED"' "$raw/status-degraded.json" >/dev/null; record_intermediate DEGRADED
      ;;
    recover)
      run="$(jq -r .runId "$raw/diff-run.json")"; curl -fsS -X POST "http://127.0.0.1:8083/internal/reconciliation/runs/$run/repair" >"$raw/repair.json"; jq -e '.repaired==true and .failed==0' "$raw/repair.json" >/dev/null
      mysql_root "SELECT action_type FROM repair_action WHERE run_id=UUID_TO_BIN('$run') AND product_id=7701;" | grep -qx WRITE_EXTERNAL_GTE
      curl -fsS -X POST http://127.0.0.1:9200/products_write/_refresh >/dev/null; curl -fsS -X POST http://127.0.0.1:8083/internal/reconciliation/runs -H 'Content-Type: application/json' -d '{"target":"products_write","pageSize":200}' >"$raw/fresh-pass.json"; jq -e '.status=="PASS" and .differenceCount==0' "$raw/fresh-pass.json" >/dev/null; mark_recovery
      ;;
  esac
}

case_18() {
  case "$1" in
    mutate)
      create_product 7801 "$raw/create.json"; "${compose[@]}" stop search-sync-consumer >/dev/null; install_bad_mapping; "${compose[@]}" start search-sync-consumer >/dev/null; wait_consumer_ready "$raw/bad-mapping-ready.json"
      change_price 7801 1000 "$raw/mutate.json"; "$waiter" 'mapping poison pending DLQ' 120 0.2 bash -c 'curl -fsS http://127.0.0.1:8082/internal/dlq/count|jq -e ".unresolved==1" >/dev/null'
      curl -fsS 'http://127.0.0.1:8082/internal/dlq?status=PENDING' >"$raw/pending-before.json"; event="$(jq -r '.[0].eventId' "$raw/pending-before.json")"; encoded="$(jq -rn --arg v "$event" '$v|@uri')"
      curl -fsS -X POST "http://127.0.0.1:8082/internal/dlq/$encoded/replay" >"$raw/replay-failed.json"; curl -fsS 'http://127.0.0.1:8082/internal/dlq?status=PENDING' >"$raw/pending-after-failed-replay.json"
      ;;
    intermediate)
      jq -e --slurpfile before "$raw/pending-before.json" 'length==1 and .[0].productId==7801 and .[0].status=="PENDING" and .[0].attempts>$before[0][0].attempts' "$raw/pending-after-failed-replay.json" >/dev/null
      pipeline_status >"$raw/status-degraded.json"; jq -e '.state=="DEGRADED" and .unresolvedDlq==1' "$raw/status-degraded.json" >/dev/null; record_intermediate DEGRADED
      ;;
    recover)
      "${compose[@]}" stop search-sync-consumer >/dev/null; restore_mapping_without_resolution; "${compose[@]}" start search-sync-consumer >/dev/null; wait_consumer_degraded "$raw/correct-mapping-ready.json"
      event="$(jq -r '.[0].eventId' "$raw/pending-after-failed-replay.json")"; encoded="$(jq -rn --arg v "$event" '$v|@uri')"; curl -fsS -X POST "http://127.0.0.1:8082/internal/dlq/$encoded/replay" >"$raw/replay-resolved.json"; jq -e '.status=="RESOLVED"' "$raw/replay-resolved.json" >/dev/null
      wait_es_revision 7801 2 "$raw/es-final.json"; curl -fsS http://127.0.0.1:8082/internal/dlq/count | jq -e '.unresolved==0' >"$raw/dlq-final.json"; mark_recovery
      ;;
  esac
}

m6_case_dispatch() {
  local scenario="$1" phase="$2"
  case "$scenario" in
    canal-normal-restart) case_1 "$phase" ;;
    canal-outage-within-binlog-retention) case_2 "$phase" ;;
    canal-outage-beyond-binlog-retention) case_3 "$phase" ;;
    kafka-temporary-unavailable) case_4 "$phase" ;;
    consumer-offset-beyond-kafka-retention) case_5 "$phase" ;;
    consumer-crash-before-elasticsearch) case_6 "$phase" ;;
    consumer-crash-after-elasticsearch-before-offset) case_7 "$phase" ;;
    elasticsearch-bulk-partial-failure) case_8 "$phase" ;;
    duplicate-event) case_9 "$phase" ;;
    late-old-revision) case_10 "$phase" ;;
    mapping-conflict) case_11 "$phase" ;;
    manual-elasticsearch-drift) case_12 "$phase" ;;
    category-rename-multi-product) case_13 "$phase" ;;
    delete-then-old-event-replay) case_14 "$phase" ;;
    rebuild-with-concurrent-writes) case_15 "$phase" ;;
    rebuild-crash-and-restart) case_16 "$phase" ;;
    consumer-systematic-mapping-bug) case_17 "$phase" ;;
    dlq-replay-fails-then-succeeds) case_18 "$phase" ;;
    *) echo "real M6 executor is not implemented yet: $scenario" >&2; return 69 ;;
  esac
}
