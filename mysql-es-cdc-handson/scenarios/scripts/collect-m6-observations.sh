#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
scenario_id="${1:?scenario required}"
run_id="${2:?run id required}"
run_dir="${3:?run directory required}"
output="${4:?output required}"
cd "$root"
compose=(docker compose -f infra/compose.yaml)
waiter=scenarios/scripts/wait-condition.sh
raw="$run_dir/raw"

"$waiter" 'consumer HTTP after recovery' 180 0.2 curl -fsS http://127.0.0.1:8082/actuator/health/liveness >/dev/null
"$waiter" 'verifier HTTP after recovery' 180 0.2 curl -fsS http://127.0.0.1:8083/actuator/health >/dev/null
"$waiter" 'three consumer partitions lag zero after recovery' 300 0.2 bash -c '
  docker compose -f "$1" exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:9092 --group product-search-sync-v1 --describe 2>/dev/null |
    awk '\''$2=="product-search-revisions"&&$3~/^[0-9]+$/{seen++;lag=$6;if($4=="-"&&$5==0&&lag=="-")lag=0;if(lag!~/^[0-9]+$/||lag!=0)bad=1}END{exit !(seen==3&&!bad)}'\''
' _ "$root/infra/compose.yaml" >/dev/null

curl -fsS -X POST http://127.0.0.1:9200/products_write/_refresh >"$raw/final-refresh.json"
verification_body='{"target":"products_write","pageSize":200}'
verification_started="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
curl -fsS -X POST http://127.0.0.1:8083/internal/reconciliation/runs -H 'Content-Type: application/json' -d "$verification_body" >"$raw/final-verification.json"
verification_finished="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -e '.status=="PASS" and .differenceCount==0' "$raw/final-verification.json" >/dev/null
curl -fsS http://127.0.0.1:8083/internal/pipeline/status >"$raw/final-pipeline-status.json"
jq -e '.state=="HEALTHY" and (.activeConditions|length)==0 and .kafkaLag==0 and .unresolvedDlq==0 and .latestDifferenceCount==0' "$raw/final-pipeline-status.json" >/dev/null
curl -fsS http://127.0.0.1:8082/internal/dlq/count >"$raw/final-product-dlq.json"
curl -fsS http://127.0.0.1:8082/internal/record-dlq/count >"$raw/final-record-dlq.json"

source_watermark="$("${compose[@]}" exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e 'SELECT COALESCE(MAX(revision),0) FROM product_search_revision')"
es_watermark="$(curl -fsS -H 'Content-Type: application/json' http://127.0.0.1:9200/products_write/_search -d '{"size":0,"aggs":{"max_revision":{"max":{"field":"source_revision"}}}}'|jq -r '.aggregations.max_revision.value//0|floor')"
offsets="$("${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:9092 --group product-search-sync-v1 --describe 2>/dev/null|awk 'BEGIN{printf "{"}$2=="product-search-revisions"&&$3~/^[0-9]+$/{offset=$4;if(offset=="-"&&$5==0)offset=0;printf "%s\"%s\":%s",s,$3,offset;s=","}END{print "}"}'|jq -S .)"
intermediate="$(cat "$run_dir/intermediate-states.json")"
product_dlq="$(jq -r .unresolved "$raw/final-product-dlq.json")"
record_dlq="$(jq -r .unresolved "$raw/final-record-dlq.json")"
rebuild=false; test -f "$run_dir/rebuild-required-before-rebuild" && rebuild=true

canal_recovery=null
if test "$scenario_id" = canal-outage-beyond-binlog-retention; then
  completion="$raw/canal-recovery/canal-recovery-completion.json"
  enrich_events() {
    local source="$1" destination="$2" partition next offset event_id run_id line key payload hash tmp
    tmp="$destination.next"; printf '{}\n' >"$tmp"
    while IFS=$'\t' read -r partition next event_id run_id; do
      offset=$((next-1))
      line="$("${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh \
        --bootstrap-server kafka:9092 --topic product-search-revisions --partition "$partition" \
        --offset "$offset" --max-messages 1 --timeout-ms 10000 \
        --property print.key=true --property print.value=true </dev/null 2>/dev/null)"
      key="${line%%$'\t'*}"; payload="${line#*$'\t'}"
      test "$key" = null
      jq -e --arg token "$partition" '.database=="product_catalog" and .table=="cdc_barrier" and .isDdl==false and (.data|length)==1 and .data[0].partition_token==$token' <<<"$payload" >/dev/null
      hash="$(printf '%s' "$payload" | shasum -a 256 | awk '{print $1}')"
      jq --arg key "$partition" --arg event "$event_id" --arg run "$run_id" --arg token "$partition" --arg hash "$hash" \
        --argjson partition "$partition" --argjson offset "$offset" --argjson next "$next" \
        '.[$key]={event_id:$event,topic:"product-search-revisions",partition:$partition,offset:$offset,next_offset:$next,run_id:$run,partition_token:$token,key_is_null:true,record_value_sha256:$hash}' \
        "$tmp" >"$tmp.row"; mv "$tmp.row" "$tmp"
    done < <(jq -r '.[]|[.partition,.nextOffset,.eventId,.runId]|@tsv' "$source")
    mv "$tmp" "$destination"
  }
  enrich_events "$raw/canal-recovery/reset-anchor-events.json" "$raw/canal-recovery/reset-anchor-events-normalized.json"
  enrich_events "$raw/canal-recovery/normal-sentinel-events.json" "$raw/canal-recovery/normal-sentinel-events-normalized.json"
  canal_recovery="$(jq '{
    old_cursor_sha256:.oldCursorSha256,old_missing_journal:.oldJournalName,old_missing_position:.oldPosition,
    retained_binlog_files:(.retainedManifest|sort_by(.fileIndex)|map(.journal)),
    reset_lower_bound_journal:.resetLowerBoundJournal,reset_lower_bound_file_index:.resetLowerBoundFileIndex,reset_lower_bound_position:.resetLowerBoundPosition,
    reset_cursor_sha256:.resetCursorSha256,reset_journal:.resetJournalName,reset_file_index:.resetFileIndex,reset_position:.resetPosition,
    reset_anchor_run_id:.resetAnchorRunId,reset_anchor_next_offsets:.resetAnchorOffsets,
    reset_restart_offsets_before:.resetRestartOffsetsBefore,normal_restart_cursor_sha256:.normalRestartCursorSha256,
    normal_restart_journal:.normalRestartJournalName,normal_restart_file_index:.normalRestartFileIndex,normal_restart_position:.normalRestartPosition,
    normal_restart_offsets_after:.normalRestartOffsetsAfter,normal_restart_preserved:true,
    normal_sentinel_run_id:.normalSentinelRunId,normal_sentinel_next_offsets:.normalSentinelOffsets
  }' "$completion" | jq --slurpfile anchors "$raw/canal-recovery/reset-anchor-events-normalized.json" \
    --slurpfile sentinels "$raw/canal-recovery/normal-sentinel-events-normalized.json" \
    '.+{reset_anchor_events:$anchors[0],normal_sentinel_events:$sentinels[0]}')"
fi

now="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
jq -n --slurpfile setup "$run_dir/setup-observation.json" --slurpfile verifier "$raw/final-verification.json" \
  --arg run "$run_id" --arg now "$now" --arg command_started "$verification_started" --arg command_finished "$verification_finished" \
  --arg body_sha256 "$(printf '%s' "$verification_body" | shasum -a 256 | awk '{print $1}')" \
  --arg collector_sha256 "$(shasum -a 256 scenarios/scripts/collect-m6-observations.sh | awk '{print $1}')" \
  --argjson source "$source_watermark" --argjson es "$es_watermark" --argjson offsets "$offsets" \
  --argjson intermediate "$intermediate" --argjson product_dlq "$product_dlq" --argjson record_dlq "$record_dlq" \
  --argjson rebuild "$rebuild" --argjson canal "$canal_recovery" '{
    consistency_preconditions:$setup[0].consistency_preconditions,
    source_watermark:$source,
    target_watermarks:{mysql_revision:$source,elasticsearch_revision:$es,passed:($es >= $source)},
    watermark_run_id:$verifier[0].runId,applied_offsets:$offsets,scenario_lag_satisfied:true,
    product_unresolved_dlq_count:$product_dlq,record_unresolved_dlq_count:$record_dlq,
    verification:{run_id:$verifier[0].runId,status:$verifier[0].status,
      conclusive:($verifier[0].status != "INCONCLUSIVE"),
      stable:($verifier[0].sourceWatermarkStart == $verifier[0].sourceWatermarkEnd),
      exact_managed_field_diff_count:$verifier[0].differenceCount,
      version_metadata_diff_count:($verifier[0].counts.VERSION_METADATA_MISMATCH // 0),observed_at:$now},
    exact_diff_count:$verifier[0].differenceCount,
    tombstone_mismatch_count:($verifier[0].counts.TOMBSTONE_MISMATCH // 0),canal_position_recovery:$canal,
    observed_intermediate_states:$intermediate,observed_pipeline_state:"HEALTHY",
    recovery_action_observed:true,rebuild_required_before_rebuild:$rebuild,
    commands:[{sequence:3,execution:"verification",intent_phases:["verification"],kind:"HTTP",target:"consistency-verifier",method:"POST",
      path:"/internal/reconciliation/runs",body_sha256:$body_sha256,
      fixture_path:"scenarios/scripts/collect-m6-observations.sh",
      fixture_sha256:$collector_sha256,
      started_at:$command_started,finished_at:$command_finished,exit_code:0}],
    recovery_commands:[],cleanup_actions:[],runner_failures:[]
  }' >"$output"
