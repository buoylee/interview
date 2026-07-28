#!/usr/bin/env bash
set -euo pipefail
source scenarios/scripts/lib-m3-crash.sh

evidence="${M3_EVIDENCE_DIR:-evidence/m3/m3-after-dlq-before-offset}"
mkdir -p "$evidence"
cp scenarios/definitions/m3-after-dlq-before-offset.json "$evidence/definition.json"
reset_stack
create_product 2302 "$evidence/source-create-response.json"
"${compose[@]}" stop search-sync-consumer >/dev/null
install_bad_mapping
curl -fsS http://127.0.0.1:9200/products_v2/_mapping >"$evidence/mapping-bad.json"
"${compose[@]}" start search-sync-consumer >/dev/null
poll "consumer after bad mapping" 120 "curl -fsS http://127.0.0.1:8082/actuator/health >/dev/null"
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
line="$(find_record 2302 "$evidence/topic-records.txt")"
record_coordinates "$line" >"$evidence/record.json"
group_json >"$evidence/group-after-crash.json"
group_raw >"$evidence/group-after-crash.txt"
assert_offset_uncommitted "$evidence/group-after-crash.json" "$evidence/record.json"
dlq_row 2302 >"$evidence/dlq-after-crash.json"
start_consumer
wait_group_zero
container_state >"$evidence/process-restarted.json"
group_json >"$evidence/group-after-restart.json"
group_raw >"$evidence/group-after-restart.txt"
dlq_row 2302 >"$evidence/dlq-after-restart.json"
"${compose[@]}" stop search-sync-consumer >/dev/null
restore_mapping_without_resolution
curl -fsS http://127.0.0.1:9200/products_v2/_mapping >"$evidence/mapping-restored.json"
dlq_row 2302 >"$evidence/dlq-after-mapping-restore.json"
jq -n --slurpfile d "$evidence/definition.json" --slurpfile crash "$evidence/process-crashed.json" \
  --slurpfile first "$evidence/dlq-after-crash.json" --slurpfile second "$evidence/dlq-after-restart.json" \
  --slurpfile restored "$evidence/dlq-after-mapping-restore.json" \
  '{scenario:$d[0].scenario,failpoint:$d[0].failpoint,exit_code:$crash[0].exit_code,
    crash_pending_rows:($first|length),attempts_after_crash:$first[0].attempts,
    restart_pending_rows:($second|length),attempts_after_restart:$second[0].attempts,
    status_after_mapping_restore:$restored[0].status,
    terminal_boundary:"RECOVERY_DEFERRED_TO_TASK7",final_consistency_claim:false}' >"$evidence/result.json"
bash scenarios/scripts/assert-m3-crash-evidence.sh "$evidence"
