#!/usr/bin/env bash
set -euo pipefail
source scenarios/scripts/lib-m3-crash.sh

evidence="${M3_EVIDENCE_DIR:-evidence/m3/m3-after-es-before-offset}"
mkdir -p "$evidence"
cp scenarios/definitions/m3-after-es-before-offset.json "$evidence/definition.json"
reset_stack
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
line="$(find_record 2301 "$evidence/topic-records.txt")"
record_coordinates "$line" >"$evidence/record.json"
group_json >"$evidence/group-after-crash.json"
group_raw >"$evidence/group-after-crash.txt"
assert_offset_uncommitted "$evidence/group-after-crash.json" "$evidence/record.json"
start_consumer
container_state >"$evidence/process-restarted.json"
wait_group_zero
group_json >"$evidence/final-group.json"
group_raw >"$evidence/final-group.txt"
curl -fsS http://127.0.0.1:9200/products_write/_doc/2301 >"$evidence/es-final.json"
dlq_row 2301 >"$evidence/dlq-final.json"
jq -n --slurpfile d "$evidence/definition.json" --slurpfile crash "$evidence/process-crashed.json" \
  --slurpfile before "$evidence/es-before-restart.json" --slurpfile after "$evidence/es-final.json" \
  --slurpfile dlq "$evidence/dlq-final.json" \
  '{scenario:$d[0].scenario,failpoint:$d[0].failpoint,exit_code:$crash[0].exit_code,
    durable_revision_before_restart:$before[0]._source.source_revision,
    before_restart_seq_no:$before[0]._seq_no,final_seq_no:$after[0]._seq_no,
    final_revision:$after[0]._source.source_revision,dlq_rows:($dlq|length),
    replay_outcome:"STALE",final_consistency_claim:true}' >"$evidence/result.json"
bash scenarios/scripts/assert-m3-crash-evidence.sh "$evidence"
