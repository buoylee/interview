#!/usr/bin/env bash
set -euo pipefail
source scenarios/scripts/lib-m3-crash.sh

scenario="${1:?scenario required}"
evidence="${M3_EVIDENCE_DIR:-evidence/m3/$scenario}"
mkdir -p "$evidence"
cp "scenarios/definitions/${scenario}.json" "$evidence/definition.json"
reset_stack
wait_consumer_ready "$evidence/consumer-ready.json"
group_json >"$evidence/baseline-group.json"

produce_raw() {
  printf '%s\n' "$1" | "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-console-producer.sh \
    --bootstrap-server kafka:9092 --topic "$topic" >/dev/null
}
capture_payload() {
  local id="$1" revision="$2" output="$3"
  capture_matching_record "$id" "$revision" "$evidence/baseline-group.json" "$output" "$evidence/topic-records.txt"
  jq -c '.payload' "$output"
}
assert_clean() {
  curl -fsS http://127.0.0.1:8082/internal/dlq/count >"$evidence/product-dlq-count.json"
  curl -fsS http://127.0.0.1:8082/internal/record-dlq/count >"$evidence/record-dlq-count.json"
  jq -e '.unresolved==0' "$evidence/product-dlq-count.json" "$evidence/record-dlq-count.json" >/dev/null
}

case "$scenario" in
  m3-consumer-restart)
    create_product 2401 "$evidence/create.json"
    "${compose[@]}" restart search-sync-consumer >/dev/null
    wait_consumer_ready "$evidence/restarted-ready.json"
    change_price 2401 201 "$evidence/mutate.json"
    wait_es_revision 2401 2 "$evidence/es-final.json"; wait_group_zero; assert_clean
    jq -n --arg scenario "$scenario" --slurpfile es "$evidence/es-final.json" \
      '{scenario:$scenario,terminal_state:"HEALTHY",raw_es:$es[0],final_consistency_claim:false}' >"$evidence/result.json" ;;
  m3-duplicate-record|m3-late-old-revision)
    id=2404; [[ "$scenario" == m3-late-old-revision ]] && id=2405
    create_product "$id" "$evidence/create.json"
    old="$(capture_payload "$id" 1 "$evidence/original-record.json")"
    if [[ "$scenario" == m3-late-old-revision ]]; then
      change_price "$id" 205 "$evidence/mutate.json"; wait_es_revision "$id" 2 "$evidence/es-before-replay.json"
    fi
    produce_raw "$old"; wait_group_zero
    curl -fsS "http://127.0.0.1:9200/products_write/_doc/$id" >"$evidence/es-final.json"; assert_clean
    jq -e --argjson id "$id" '._id==($id|tostring) and ._source.source_revision==(if $id==2405 then 2 else 1 end)' "$evidence/es-final.json" >/dev/null
    jq -n --arg scenario "$scenario" --slurpfile record "$evidence/original-record.json" --slurpfile es "$evidence/es-final.json" \
      '{scenario:$scenario,terminal_state:"HEALTHY",raw_record:$record[0],raw_es:$es[0],final_consistency_claim:false}' >"$evidence/result.json" ;;
  m3-delete-then-old-replay)
    create_product 2409 "$evidence/create.json"
    old="$(capture_payload 2409 1 "$evidence/original-record.json")"
    curl -fsS -X DELETE http://127.0.0.1:8081/api/products/2409 >"$evidence/delete.json"
    wait_es_revision 2409 2 "$evidence/tombstone-before-replay.json"
    produce_raw "$old"; wait_group_zero
    curl -fsS http://127.0.0.1:9200/products_write/_doc/2409 >"$evidence/es-final.json"
    jq -e '._source.source_revision==2 and ._source.searchable==false' "$evidence/es-final.json" >/dev/null; assert_clean
    jq -n --arg scenario "$scenario" --slurpfile record "$evidence/original-record.json" --slurpfile es "$evidence/es-final.json" \
      '{scenario:$scenario,terminal_state:"HEALTHY",raw_old_record:$record[0],raw_tombstone:$es[0],final_consistency_claim:false}' >"$evidence/result.json" ;;
  m3-mapping-conflict|m3-bulk-partial)
    id=2406; [[ "$scenario" == m3-bulk-partial ]] && id=2403
    create_product "$id" "$evidence/create.json"
    [[ "$scenario" == m3-bulk-partial ]] && create_product 2413 "$evidence/create-second.json"
    "${compose[@]}" stop search-sync-consumer >/dev/null; install_bad_mapping
    "${compose[@]}" start search-sync-consumer >/dev/null; wait_consumer_ready "$evidence/bad-mapping-ready.json"
    if [[ "$scenario" == m3-bulk-partial ]]; then
      "${compose[@]}" exec -T mysql mysql -uproduct -pproductpass product_catalog -e \
        "START TRANSACTION; UPDATE products SET price_cents=1000 WHERE id=2403; UPDATE products SET price_cents=110 WHERE id=2413; UPDATE product_search_revision SET revision=revision+1,updated_at=CURRENT_TIMESTAMP(6) WHERE product_id IN (2403,2413); COMMIT;"
    else change_price "$id" 1000 "$evidence/mutate.json"; fi
    poll "product DLQ" 120 "curl -fsS http://127.0.0.1:8082/internal/dlq/count | jq -e '.unresolved>=1' >/dev/null"
    if [[ "$scenario" == m3-bulk-partial ]]; then
      group_json >"$evidence/bulk-group.json"
      capture_matching_batch_record 2403 2413 2 "$evidence/baseline-group.json" \
        "$evidence/batch-record.json" "$evidence/topic-records.txt"
      wait_es_revision 2413 2 "$evidence/es-valid-before-repair.json"
    fi
    curl -fsS 'http://127.0.0.1:8082/internal/dlq?status=PENDING' >"$evidence/dlq-before.json"
    if [[ "$scenario" == m3-bulk-partial ]]; then
      jq -e --slurpfile record "$evidence/batch-record.json" '
        length==1 and .[0].productId==2403 and .[0].sourceRevision==2 and .[0].status=="PENDING"
        and .[0].topic=="product-search-revisions"
        and .[0].partition==$record[0].partition and .[0].offset==$record[0].offset
        and .[0].eventId==("product-search-revisions:"+($record[0].partition|tostring)+":"+($record[0].offset|tostring)+":2403")' \
        "$evidence/dlq-before.json" >/dev/null
      jq -e '(.raw_body|fromjson) | .found==true and ._id=="2413"
        and ._source.product_id==2413 and ._source.source_revision==2 and ._source.price_cents==110
        and ._source.sku=="LAB-2413" and ._source.name=="Crash 2413" and ._source.searchable==true' \
        "$evidence/es-valid-before-repair.json" >/dev/null
    fi
    "${compose[@]}" stop search-sync-consumer >/dev/null
    if [[ "$scenario" == m3-bulk-partial ]]; then
      restore_mapping_preserving_documents
    else
      restore_mapping_without_resolution
    fi
    "${compose[@]}" start search-sync-consumer >/dev/null; wait_consumer_degraded "$evidence/restored-ready.json"
    jq -r '.[].eventId' "$evidence/dlq-before.json" | while IFS= read -r event; do
      encoded="$(jq -rn --arg v "$event" '$v|@uri')"
      curl -fsS -X POST "http://127.0.0.1:8082/internal/dlq/$encoded/replay" >>"$evidence/replay-results.jsonl"
      printf '\n' >>"$evidence/replay-results.jsonl"
    done
    if [[ "$scenario" == m3-bulk-partial ]]; then wait_es_revision 2413 2 "$evidence/es-second-final.json"; fi
    wait_es_revision "$id" 2 "$evidence/es-final.json"; assert_clean
    if [[ "$scenario" == m3-bulk-partial ]]; then
      jq -n --arg scenario "$scenario" --slurpfile batch "$evidence/batch-record.json" \
        --slurpfile dlq "$evidence/dlq-before.json" --slurpfile before "$evidence/es-valid-before-repair.json" \
        --slurpfile bad "$evidence/es-final.json" --slurpfile valid "$evidence/es-second-final.json" \
        '{scenario:$scenario,terminal_state:"HEALTHY",raw_batch_record:$batch[0],raw_pending:$dlq[0],
          raw_valid_before_repair:$before[0],raw_bad_final:$bad[0],raw_valid_final:$valid[0],
          valid_item_applied_before_repair:true,recovered_by_current_source_replay:true,final_consistency_claim:false}' >"$evidence/result.json"
    else
      jq -n --arg scenario "$scenario" --slurpfile dlq "$evidence/dlq-before.json" --slurpfile es "$evidence/es-final.json" \
        '{scenario:$scenario,terminal_state:"HEALTHY",raw_pending:$dlq[0],raw_es:$es[0],recovered_by_current_source_replay:true,final_consistency_claim:false}' >"$evidence/result.json"
    fi ;;
  m3-record-parse-dlq)
    produce_raw 'not-json'
    poll "record poison DLQ" 120 "curl -fsS http://127.0.0.1:8082/internal/record-dlq/count | jq -e '.unresolved==1' >/dev/null"
    curl -sS http://127.0.0.1:8082/actuator/health >"$evidence/health-degraded.json"
    curl -fsS 'http://127.0.0.1:8082/internal/record-dlq?status=PENDING' >"$evidence/record-dlq-before.json"
    record="$(jq -r '.[0].recordId' "$evidence/record-dlq-before.json")"; encoded="$(jq -rn --arg v "$record" '$v|@uri')"
    curl -fsS -X POST "http://127.0.0.1:8082/internal/record-dlq/$encoded/replay" >"$evidence/replay-result.json"
    curl -fsS 'http://127.0.0.1:8082/internal/record-dlq?status=PENDING' >"$evidence/record-dlq-after.json"
    jq -e '.[0].attempts>=2 and .[0].status=="PENDING"' "$evidence/record-dlq-after.json" >/dev/null
    jq -n --arg scenario "$scenario" --slurpfile before "$evidence/record-dlq-before.json" --slurpfile after "$evidence/record-dlq-after.json" \
      '{scenario:$scenario,terminal_state:"DEGRADED",raw_before:$before[0],raw_after:$after[0],replay_still_pending:true,teardown_is_not_recovery:true,final_recovery_claim:false,final_consistency_claim:false}' >"$evidence/result.json"
    "${compose[@]}" --profile m0-tools down --volumes --remove-orphans ;;
  *) die "unsupported standard scenario: $scenario" ;;
esac
bash scenarios/scripts/assert-m3-standard-evidence.sh "$evidence"
