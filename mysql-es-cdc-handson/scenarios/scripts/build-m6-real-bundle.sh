#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
scenario_id="${1:?scenario required}"
run_id="${2:?run id required}"
started_at="${3:?started timestamp required}"
run_dir="${4:?run directory required}"
observations="${5:?observations required}"
recovery_output="${6:?recovery output required}"
bundle="${7:?bundle required}"
cd "$root"
mkdir -p "$bundle"

jq -n --arg scenario "$scenario_id" --arg run "$run_id" --arg head "$(git rev-parse HEAD)" \
  '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,project_head:$head,execution_mode:"real"}' >"$bundle/manifest.json"
jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" \
  '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,commands:$o[0].commands}' >"$bundle/input-commands.json"
jq -n --arg scenario "$scenario_id" --arg run "$run_id" --argjson fault "$(jq -c --arg id "$scenario_id" '.scenarios[]|select(.scenario_id==$id)|.fault' scenarios/catalog.json)" \
  --slurpfile states "$run_dir/intermediate-states.json" \
  '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,declared_fault:$fault,cleanup_registered_before_fault:true,observed_intermediate_states:$states[0]}' >"$bundle/fault.json"

mysql_id="$(docker compose -f infra/compose.yaml ps -q mysql)"
MYSQL_PWD="$(docker inspect "$mysql_id" | jq -r '.[0].Config.Env[]|select(startswith("MYSQL_ROOT_PASSWORD="))|split("=")[1]')"
export MYSQL_PWD MYSQL_USER=root MYSQL_HOST=127.0.0.1 MYSQL_PORT=3308
bash scenarios/scripts/capture-mysql.sh "$run_dir/mysql-capture.json"
bash scenarios/scripts/capture-elasticsearch.sh "$run_dir/es-capture.json"
bash scenarios/scripts/capture-kafka.sh "$run_dir/kafka-capture.json"
jq --arg scenario "$scenario_id" --arg run "$run_id" '.+{scenario_id:$scenario,runner_run_id:$run}' "$run_dir/mysql-capture.json" >"$bundle/mysql-snapshot.json"
jq --arg scenario "$scenario_id" --arg run "$run_id" '.+{scenario_id:$scenario,runner_run_id:$run}' "$run_dir/es-capture.json" >"$bundle/es-snapshot.json"
if test "$scenario_id" = canal-outage-beyond-binlog-retention; then
  jq --arg scenario "$scenario_id" --arg run "$run_id" \
    --slurpfile anchor "$run_dir/raw/canal-recovery/reset-anchor-events-normalized.json" \
    --slurpfile anchor_offsets "$run_dir/raw/canal-recovery/reset-anchor-offsets.json" \
    --slurpfile sentinel "$run_dir/raw/canal-recovery/normal-sentinel-events-normalized.json" \
    --slurpfile sentinel_offsets "$run_dir/raw/canal-recovery/normal-sentinel-offsets.json" \
    '.+{scenario_id:$scenario,runner_run_id:$run,raw_recovery_observations:{reset_anchor:{events:$anchor[0],next_offsets:$anchor_offsets[0]},normal_sentinel:{events:$sentinel[0],next_offsets:$sentinel_offsets[0]}}}' \
    "$run_dir/kafka-capture.json" >"$bundle/kafka-offsets.json"
else
  jq --arg scenario "$scenario_id" --arg run "$run_id" '.+{scenario_id:$scenario,runner_run_id:$run}' "$run_dir/kafka-capture.json" >"$bundle/kafka-offsets.json"
fi

jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" \
  --slurpfile verification "$run_dir/raw/final-verification.json" \
  '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,observations:$o[0],independent_verification:$verification[0]}' >"$bundle/differences.json"
jq -n --arg scenario "$scenario_id" --arg run "$run_id" --slurpfile o "$observations" --slurpfile recovery "$recovery_output" \
  '{schema_version:1,scenario_id:$scenario,runner_run_id:$run,rebuild_required_observed_before_rebuild:$o[0].rebuild_required_before_rebuild,commands:$recovery[0].commands,cleanup_actions:$recovery[0].cleanup_actions,cleanup_failures:([$recovery[0].cleanup_actions[]|select(.success!=true)]|length)}' >"$bundle/recovery-actions.json"
bash scenarios/scripts/write-result.sh "$scenario_id" "$run_id" "$started_at" "$observations" "$bundle/recovery-actions.json" "$bundle/result.json"
