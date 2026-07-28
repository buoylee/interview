#!/usr/bin/env bash
set -euo pipefail
source scenarios/scripts/lib-m3-crash.sh

evidence="${M3_EVIDENCE_DIR:-evidence/m3/m3-after-dlq-before-offset}"
mkdir -p "$evidence"
cp scenarios/definitions/m3-after-dlq-before-offset.json "$evidence/definition.json"
reset_stack
wait_consumer_ready "$evidence/consumer-ready.json"
create_product 2302 "$evidence/source-create-response.json"
"${compose[@]}" stop search-sync-consumer >/dev/null
install_bad_mapping
curl -fsS http://127.0.0.1:9200/products_v2/_mapping >"$evidence/mapping-bad.json"
"${compose[@]}" start search-sync-consumer >/dev/null
wait_consumer_ready "$evidence/consumer-bad-mapping-ready.json"
wait_group_zero
group_json >"$evidence/baseline-group.json"
group_raw >"$evidence/baseline-group.txt"
container_state >"$evidence/process-before.json"
arm_failpoint AFTER_DLQ_PUBLISH
curl -fsS http://127.0.0.1:8082/internal/failpoints >"$evidence/armed.json"
change_price 2302 1000 "$evidence/source-mutation-response.json"
source_state 2302 >"$evidence/source-after-mutation.json"
wait_exit_86
container_state >"$evidence/process-crashed.json"
capture_matching_record 2302 2 "$evidence/baseline-group.json" "$evidence/record.json" "$evidence/topic-records.txt"
group_json >"$evidence/group-after-crash.json"
group_raw >"$evidence/group-after-crash.txt"
assert_offset_uncommitted "$evidence/group-after-crash.json" "$evidence/record.json"
dlq_row 2302 >"$evidence/dlq-after-crash.json"
start_consumer
wait_consumer_ready "$evidence/consumer-restarted-ready.json"
wait_group_zero
container_state >"$evidence/process-restarted.json"
group_json >"$evidence/group-after-restart.json"
group_raw >"$evidence/group-after-restart.txt"
dlq_row 2302 >"$evidence/dlq-after-restart.json"
"${compose[@]}" stop search-sync-consumer >/dev/null
restore_mapping_without_resolution
curl -fsS http://127.0.0.1:9200/products_v2/_mapping >"$evidence/mapping-restored.json"
dlq_row 2302 >"$evidence/dlq-after-mapping-restore.json"
jq -n --slurpfile d "$evidence/definition.json" --slurpfile record "$evidence/record.json" \
  --slurpfile before_process "$evidence/process-before.json" --slurpfile crash "$evidence/process-crashed.json" \
  --slurpfile restarted "$evidence/process-restarted.json" --slurpfile crash_group "$evidence/group-after-crash.json" \
  --slurpfile restart_group "$evidence/group-after-restart.json" \
  --slurpfile first "$evidence/dlq-after-crash.json" --slurpfile second "$evidence/dlq-after-restart.json" \
  --slurpfile restored "$evidence/dlq-after-mapping-restore.json" \
  '($record[0]) as $r | ($crash_group[0][]|select(.partition==$r.partition)) as $cg |
   ($restart_group[0][]|select(.partition==$r.partition)) as $rg |
   {scenario:$d[0].scenario,failpoint:$d[0].failpoint,hits:$d[0].hits,exit_code:$crash[0].exit_code,
    product_id:$d[0].product_id,revision:$d[0].mutation_revision,
    record_partition:$r.partition,record_offset:$r.offset,record_baseline_end:$r.baseline_end,
    crash_committed:$cg.committed,crash_end:$cg.end,crash_lag:$cg.lag,
    restart_committed:$rg.committed,restart_end:$rg.end,restart_lag:$rg.lag,
    before_container_id:$before_process[0].id,crashed_container_id:$crash[0].id,
    restarted_container_id:$restarted[0].id,before_started_at:$before_process[0].started_at,
    crashed_finished_at:$crash[0].finished_at,restarted_started_at:$restarted[0].started_at,
    event_id:$first[0][0].event_id,
    crash_pending_rows:($first[0]|length),attempts_after_crash:$first[0][0].attempts,status_after_crash:$first[0][0].status,
    restart_pending_rows:($second[0]|length),attempts_after_restart:$second[0][0].attempts,status_after_restart:$second[0][0].status,
    mapping_restore_pending_rows:($restored[0]|length),attempts_after_mapping_restore:$restored[0][0].attempts,
    status_after_mapping_restore:$restored[0][0].status,
    terminal_boundary:"RECOVERY_DEFERRED_TO_TASK7",final_consistency_claim:false}' >"$evidence/result.json"
bash scenarios/scripts/assert-m3-crash-evidence.sh "$evidence"
