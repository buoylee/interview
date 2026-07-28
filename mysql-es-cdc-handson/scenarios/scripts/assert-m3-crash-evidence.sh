#!/usr/bin/env bash
set -euo pipefail

dir="${1:?evidence directory required}"
definition="$dir/definition.json"
test -s "$definition" && jq -e . "$definition" >/dev/null || { echo "missing/invalid definition" >&2; exit 1; }
jq -e '(.required_files|type)=="array" and (.required_files|length)>0' "$definition" >/dev/null
jq -e '(.required_text_files|type)=="array" and (.required_text_files|length)>0' "$definition" >/dev/null

scenario="$(jq -r .scenario "$definition")"
case "$scenario" in
  m3-after-es-before-offset)
    jq -e '.failpoint=="AFTER_ES_BULK_SUCCESS" and .hits==1' "$definition" >/dev/null ;;
  m3-after-dlq-before-offset)
    jq -e '.failpoint=="AFTER_DLQ_PUBLISH" and .hits==1' "$definition" >/dev/null ;;
  *) echo "unknown scenario: $scenario" >&2; exit 1 ;;
esac

while IFS= read -r file; do
  test -s "$dir/$file" || { echo "missing evidence: $file" >&2; exit 1; }
  jq -e . "$dir/$file" >/dev/null || { echo "invalid JSON evidence: $file" >&2; exit 1; }
done < <(jq -r '.required_files[]' "$definition")
while IFS= read -r file; do
  test -s "$dir/$file" || { echo "missing text evidence: $file" >&2; exit 1; }
done < <(jq -r '.required_text_files[]' "$definition")

while IFS= read -r attempts; do
  while IFS= read -r observation; do
    jq -e . <<<"$observation" >/dev/null || { echo "invalid readiness attempt: $attempts" >&2; exit 1; }
  done <"$dir/$attempts"
done < <(jq -r '.required_text_files[] | select(endswith("-attempts.jsonl"))' "$definition")

rfc3339_epoch() {
  local value="$1" seconds
  [[ "$value" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,9})?Z$ ]] || return 1
  seconds="$(printf '%s' "$value" | sed -E 's/\.[0-9]+Z$/Z/')"
  date -j -u -f '%Y-%m-%dT%H:%M:%SZ' "$seconds" '+%s' 2>/dev/null \
    || date -u -d "$seconds" '+%s' 2>/dev/null
}

before_id="$(jq -r .id "$dir/process-before.json")"
crash_id="$(jq -r .id "$dir/process-crashed.json")"
restart_id="$(jq -r .id "$dir/process-restarted.json")"
[[ "$before_id" =~ ^[0-9a-f]{64}$ && "$before_id" == "$crash_id" && "$before_id" == "$restart_id" ]]
before_start="$(jq -r .started_at "$dir/process-before.json")"
crash_start="$(jq -r .started_at "$dir/process-crashed.json")"
crash_finish="$(jq -r .finished_at "$dir/process-crashed.json")"
restart_start="$(jq -r .started_at "$dir/process-restarted.json")"
test "$before_start" = "$crash_start"
before_epoch="$(rfc3339_epoch "$before_start")"
finish_epoch="$(rfc3339_epoch "$crash_finish")"
restart_epoch="$(rfc3339_epoch "$restart_start")"
(( finish_epoch > before_epoch && restart_epoch > finish_epoch ))
jq -e '.running==true and .exit_code==0' "$dir/process-before.json" >/dev/null
jq -e '.running==false and .exit_code==86' "$dir/process-crashed.json" >/dev/null
jq -e '.running==true and .exit_code==0' "$dir/process-restarted.json" >/dev/null

assert_ready() {
  local file="$1"
  jq -e '.transport_exit==0 and .http_status==200 and .json_valid==true
    and (.raw_body|fromjson)=={"groups":["liveness","readiness"],"status":"UP"}
    and (.consumer_container_id|test("^[0-9a-f]{64}$"))
    and (.container_started_at|type)=="string"
    and (.observed_at|type)=="string"' "$file" >/dev/null
  local started observed
  started="$(rfc3339_epoch "$(jq -r .container_started_at "$file")")"
  observed="$(rfc3339_epoch "$(jq -r .observed_at "$file")")"
  (( observed >= started ))
}
assert_ready "$dir/consumer-ready.json"

product_id="$(jq -r .product_id "$definition")"
initial_revision="$(jq -r .initial_revision "$definition")"
mutation_revision="$(jq -r .mutation_revision "$definition")"
failpoint="$(jq -r .failpoint "$definition")"
hits="$(jq -r .hits "$definition")"
(( product_id > 0 && initial_revision == 1 && mutation_revision == 2 && hits == 1 ))
jq -e --argjson id "$product_id" --argjson revision "$initial_revision" '.productId==$id and .revision==$revision' "$dir/source-create-response.json" >/dev/null
jq -e --argjson id "$product_id" --argjson revision "$mutation_revision" '.productId==$id and .revision==$revision' "$dir/source-mutation-response.json" >/dev/null
jq -e '.transport_exit==0 and .http_status==201 and .json_valid==true and ((.raw_body|fromjson).revision)==1' "$dir/source-create-response-http.json" >/dev/null
jq -e '.transport_exit==0 and .http_status==200 and .json_valid==true and ((.raw_body|fromjson).revision)==2' "$dir/source-mutation-response-http.json" >/dev/null
jq -e --argjson id "$product_id" --argjson revision "$mutation_revision" '.product_id==$id and .revision==$revision and .active==1' "$dir/source-after-mutation.json" >/dev/null
jq -e --arg point "$failpoint" --argjson hits "$hits" '.[$point]==$hits' "$dir/armed.json" >/dev/null
jq -e --arg point "$failpoint" 'to_entries | all(.[]; .key==$point or .value==0)' "$dir/armed.json" >/dev/null

jq -e --argjson id "$product_id" --argjson revision "$mutation_revision" \
  '.partition>=0 and .offset>=.baseline_end and .payload.database=="product_catalog"
   and .payload.table=="product_search_revision" and .payload.isDdl==false
   and (.payload.id|type)=="number" and .payload.id>0
   and (.payload.type=="UPDATE" or .payload.type=="INSERT") and (.payload.data|length)==1
   and (.payload.data[0].product_id|tonumber)==$id and (.payload.data[0].revision|tonumber)==$revision
   and .payload.data[0].active=="1"' "$dir/record.json" >/dev/null

record_partition="$(jq -r .partition "$dir/record.json")"
record_offset="$(jq -r .offset "$dir/record.json")"
raw_match_count="$(awk -v prefix="Partition:${record_partition}\tOffset:${record_offset}\t" 'index($0,prefix)==1{count++}END{print count+0}' "$dir/topic-records.txt")"
test "$raw_match_count" -eq 1
raw_payload="$(awk -v prefix="Partition:${record_partition}\tOffset:${record_offset}\t" 'index($0,prefix)==1{sub(prefix,"");print}' "$dir/topic-records.txt")"
jq -e . <<<"$raw_payload" >/dev/null
test "$(jq -S -c . <<<"$raw_payload")" = "$(jq -S -c .payload "$dir/record.json")"

jq -e --slurpfile r "$dir/record.json" '($r[0]) as $record
  | map(select(.partition==$record.partition)) | length==1
  and .[0].end>$record.offset and .[0].committed<=$record.offset and .[0].lag==(. [0].end-. [0].committed)' "$dir/group-after-crash.json" >/dev/null
jq -e --slurpfile r "$dir/record.json" '($r[0]) as $record
  | map(select(.partition==$record.partition)) | length==1 and .[0].end==$record.baseline_end' "$dir/baseline-group.json" >/dev/null

jq -e --slurpfile d "$definition" '.scenario==$d[0].scenario and .failpoint==$d[0].failpoint and .hits==$d[0].hits and .exit_code==$d[0].exit_code' "$dir/result.json" >/dev/null

assert_ready "$dir/consumer-restarted-ready.json"
test "$(jq -r .consumer_container_id "$dir/consumer-ready.json")" = "$before_id"
test "$(jq -r .consumer_container_id "$dir/consumer-restarted-ready.json")" = "$restart_id"
restart_ready_epoch="$(rfc3339_epoch "$(jq -r .observed_at "$dir/consumer-restarted-ready.json")")"
test "$(jq -r .container_started_at "$dir/consumer-restarted-ready.json")" = "$restart_start"
(( restart_ready_epoch >= restart_epoch ))

case "$scenario" in
  m3-after-es-before-offset)
    expected_result="$(mktemp)"
    jq -e --argjson id "$product_id" --argjson revision "$mutation_revision" \
      '.found==true and (._id|tonumber)==$id and ._source.product_id==$id and ._source.source_revision==$revision and ._source.price_cents==200' "$dir/es-before-restart.json" >/dev/null
    jq -e --argjson id "$product_id" --argjson revision "$mutation_revision" \
      '.found==true and (._id|tonumber)==$id and ._source.product_id==$id and ._source.source_revision==$revision and ._source.price_cents==200' "$dir/es-final.json" >/dev/null
    jq -e --slurpfile before "$dir/es-before-restart.json" '._seq_no==$before[0]._seq_no and ._source==$before[0]._source' "$dir/es-final.json" >/dev/null
    jq -e 'type=="array" and length==0' "$dir/dlq-final.json" >/dev/null
    jq -e --slurpfile r "$dir/record.json" '($r[0]) as $record | map(select(.partition==$record.partition)) | length==1 and .[0].committed>$record.offset and .[0].end==.[0].committed and .[0].lag==0' "$dir/final-group.json" >/dev/null
    jq -n --slurpfile d "$definition" --slurpfile record "$dir/record.json" \
      --slurpfile before_process "$dir/process-before.json" --slurpfile crash "$dir/process-crashed.json" \
      --slurpfile restarted "$dir/process-restarted.json" --slurpfile crash_group "$dir/group-after-crash.json" \
      --slurpfile final_group "$dir/final-group.json" --slurpfile before "$dir/es-before-restart.json" \
      --slurpfile after "$dir/es-final.json" --slurpfile dlq "$dir/dlq-final.json" \
      '($record[0]) as $r | ($crash_group[0][]|select(.partition==$r.partition)) as $cg |
       ($final_group[0][]|select(.partition==$r.partition)) as $fg |
       {scenario:$d[0].scenario,failpoint:$d[0].failpoint,hits:$d[0].hits,exit_code:$crash[0].exit_code,
        product_id:$d[0].product_id,revision:$d[0].mutation_revision,
        record_partition:$r.partition,record_offset:$r.offset,record_baseline_end:$r.baseline_end,
        crash_committed:$cg.committed,crash_end:$cg.end,crash_lag:$cg.lag,
        final_committed:$fg.committed,final_end:$fg.end,final_lag:$fg.lag,
        before_container_id:$before_process[0].id,crashed_container_id:$crash[0].id,restarted_container_id:$restarted[0].id,
        before_started_at:$before_process[0].started_at,crashed_finished_at:$crash[0].finished_at,restarted_started_at:$restarted[0].started_at,
        es_before_found:$before[0].found,es_before_id:$before[0]._id,es_before_price_cents:$before[0]._source.price_cents,
        durable_revision_before_restart:$before[0]._source.source_revision,before_restart_seq_no:$before[0]._seq_no,
        es_final_found:$after[0].found,es_final_id:$after[0]._id,es_final_price_cents:$after[0]._source.price_cents,
        final_seq_no:$after[0]._seq_no,final_revision:$after[0]._source.source_revision,
        dlq_rows:($dlq[0]|length),replay_outcome:"STALE",final_consistency_claim:true}' >"$expected_result"
    jq -e --slurpfile expected "$expected_result" '.==$expected[0]' "$dir/result.json" >/dev/null
    rm "$expected_result"
    ;;
  m3-after-dlq-before-offset)
    expected_result="$(mktemp)"
    assert_ready "$dir/consumer-bad-mapping-ready.json"
    test "$(jq -r .consumer_container_id "$dir/consumer-bad-mapping-ready.json")" = "$before_id"
    bad_ready_epoch="$(rfc3339_epoch "$(jq -r .observed_at "$dir/consumer-bad-mapping-ready.json")")"
    test "$(jq -r .container_started_at "$dir/consumer-bad-mapping-ready.json")" = "$before_start"
    (( bad_ready_epoch >= before_epoch && bad_ready_epoch < finish_epoch ))
    jq -e '.products_v2.mappings.properties.price_cents.type=="byte"' "$dir/mapping-bad.json" >/dev/null
    jq -e '.products_v2.mappings.properties.price_cents.type=="long"' "$dir/mapping-restored.json" >/dev/null
    expected_id="product-search-revisions:$(jq -r .partition "$dir/record.json"):$(jq -r .offset "$dir/record.json"):${product_id}"
    for spec in 'dlq-after-crash.json:1' 'dlq-after-restart.json:2' 'dlq-after-mapping-restore.json:2'; do
      file="${spec%:*}"; attempts="${spec#*:}"
      jq -e --arg event "$expected_id" --argjson id "$product_id" --argjson revision "$mutation_revision" --argjson attempts "$attempts" --slurpfile r "$dir/record.json" \
        'type=="array" and length==1 and .[0].event_id==$event and .[0].topic=="product-search-revisions"
         and .[0].partition==$r[0].partition and .[0].offset==$r[0].offset and .[0].product_id==$id
         and .[0].revision==$revision and .[0].status=="PENDING" and .[0].attempts==$attempts' "$dir/$file" >/dev/null
    done
    jq -e --slurpfile r "$dir/record.json" '($r[0]) as $record | map(select(.partition==$record.partition)) | length==1 and .[0].committed>$record.offset and .[0].end==.[0].committed and .[0].lag==0' "$dir/group-after-restart.json" >/dev/null
    jq -n --slurpfile d "$definition" --slurpfile record "$dir/record.json" \
      --slurpfile before_process "$dir/process-before.json" --slurpfile crash "$dir/process-crashed.json" \
      --slurpfile restarted "$dir/process-restarted.json" --slurpfile crash_group "$dir/group-after-crash.json" \
      --slurpfile restart_group "$dir/group-after-restart.json" --slurpfile first "$dir/dlq-after-crash.json" \
      --slurpfile second "$dir/dlq-after-restart.json" --slurpfile restored "$dir/dlq-after-mapping-restore.json" \
      '($record[0]) as $r | ($crash_group[0][]|select(.partition==$r.partition)) as $cg |
       ($restart_group[0][]|select(.partition==$r.partition)) as $rg |
       {scenario:$d[0].scenario,failpoint:$d[0].failpoint,hits:$d[0].hits,exit_code:$crash[0].exit_code,
        product_id:$d[0].product_id,revision:$d[0].mutation_revision,
        record_partition:$r.partition,record_offset:$r.offset,record_baseline_end:$r.baseline_end,
        crash_committed:$cg.committed,crash_end:$cg.end,crash_lag:$cg.lag,
        restart_committed:$rg.committed,restart_end:$rg.end,restart_lag:$rg.lag,
        before_container_id:$before_process[0].id,crashed_container_id:$crash[0].id,restarted_container_id:$restarted[0].id,
        before_started_at:$before_process[0].started_at,crashed_finished_at:$crash[0].finished_at,restarted_started_at:$restarted[0].started_at,
        event_id:$first[0][0].event_id,
        crash_pending_rows:($first[0]|length),attempts_after_crash:$first[0][0].attempts,status_after_crash:$first[0][0].status,
        restart_pending_rows:($second[0]|length),attempts_after_restart:$second[0][0].attempts,status_after_restart:$second[0][0].status,
        mapping_restore_pending_rows:($restored[0]|length),attempts_after_mapping_restore:$restored[0][0].attempts,
        status_after_mapping_restore:$restored[0][0].status,
        terminal_boundary:"RECOVERY_DEFERRED_TO_TASK7",final_consistency_claim:false}' >"$expected_result"
    jq -e --slurpfile expected "$expected_result" '.==$expected[0]' "$dir/result.json" >/dev/null
    rm "$expected_result"
    ;;
esac
