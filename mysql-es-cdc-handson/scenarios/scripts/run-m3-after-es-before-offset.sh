#!/usr/bin/env bash
set -euo pipefail
source scenarios/scripts/lib-m3-crash.sh

evidence="${M3_EVIDENCE_DIR:-evidence/m3/m3-after-es-before-offset}"
mkdir -p "$evidence"
cp scenarios/definitions/m3-after-es-before-offset.json "$evidence/definition.json"
reset_stack
wait_consumer_ready "$evidence/consumer-ready.json"
create_product 2301 "$evidence/source-create-response.json"
group_json >"$evidence/baseline-group.json"
group_raw >"$evidence/baseline-group.txt"
container_state >"$evidence/process-before.json"
arm_failpoint AFTER_ES_BULK_SUCCESS
curl -fsS http://127.0.0.1:8082/internal/failpoints >"$evidence/armed.json"
change_price 2301 200 "$evidence/source-mutation-response.json"
source_state 2301 >"$evidence/source-after-mutation.json"
wait_exit_86
container_state >"$evidence/process-crashed.json"
curl -fsS http://127.0.0.1:9200/products_write/_doc/2301 >"$evidence/es-before-restart.json"
capture_matching_record 2301 2 "$evidence/baseline-group.json" "$evidence/record.json" "$evidence/topic-records.txt"
group_json >"$evidence/group-after-crash.json"
group_raw >"$evidence/group-after-crash.txt"
assert_offset_uncommitted "$evidence/group-after-crash.json" "$evidence/record.json"
start_consumer
wait_consumer_ready "$evidence/consumer-restarted-ready.json"
container_state >"$evidence/process-restarted.json"
wait_group_zero
group_json >"$evidence/final-group.json"
group_raw >"$evidence/final-group.txt"
curl -fsS http://127.0.0.1:9200/products_write/_doc/2301 >"$evidence/es-final.json"
dlq_row 2301 >"$evidence/dlq-final.json"
jq -n --slurpfile d "$evidence/definition.json" --slurpfile record "$evidence/record.json" \
  --slurpfile before_process "$evidence/process-before.json" --slurpfile crash "$evidence/process-crashed.json" \
  --slurpfile restarted "$evidence/process-restarted.json" --slurpfile crash_group "$evidence/group-after-crash.json" \
  --slurpfile final_group "$evidence/final-group.json" \
  --slurpfile before "$evidence/es-before-restart.json" --slurpfile after "$evidence/es-final.json" \
  --slurpfile dlq "$evidence/dlq-final.json" \
  '($record[0]) as $r | ($crash_group[0][]|select(.partition==$r.partition)) as $cg |
   ($final_group[0][]|select(.partition==$r.partition)) as $fg |
   {scenario:$d[0].scenario,failpoint:$d[0].failpoint,hits:$d[0].hits,exit_code:$crash[0].exit_code,
    product_id:$d[0].product_id,revision:$d[0].mutation_revision,
    record_partition:$r.partition,record_offset:$r.offset,record_baseline_end:$r.baseline_end,
    crash_committed:$cg.committed,crash_end:$cg.end,crash_lag:$cg.lag,
    final_committed:$fg.committed,final_end:$fg.end,final_lag:$fg.lag,
    before_container_id:$before_process[0].id,crashed_container_id:$crash[0].id,
    restarted_container_id:$restarted[0].id,before_started_at:$before_process[0].started_at,
    crashed_finished_at:$crash[0].finished_at,restarted_started_at:$restarted[0].started_at,
    es_before_found:$before[0].found,es_before_id:$before[0]._id,es_before_price_cents:$before[0]._source.price_cents,
    durable_revision_before_restart:$before[0]._source.source_revision,before_restart_seq_no:$before[0]._seq_no,
    es_final_found:$after[0].found,es_final_id:$after[0]._id,es_final_price_cents:$after[0]._source.price_cents,
    final_seq_no:$after[0]._seq_no,final_revision:$after[0]._source.source_revision,
    dlq_rows:($dlq[0]|length),replay_outcome:"STALE",final_consistency_claim:true}' >"$evidence/result.json"
bash scenarios/scripts/assert-m3-crash-evidence.sh "$evidence"
