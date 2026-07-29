#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
bundle="${1:?usage: evidence-contract.sh BUNDLE}"
result_schema="$project_root/scenarios/schema/result.schema.json"
validator="$project_root/tests/contracts/validate-json-schema.py"
files=(manifest.json input-commands.json fault.json mysql-snapshot.json es-snapshot.json kafka-offsets.json differences.json recovery-actions.json result.json)

test -f "$result_schema" || { echo 'missing result schema' >&2; exit 1; }
test -d "$bundle" || { echo "missing evidence bundle: $bundle" >&2; exit 1; }
for name in "${files[@]}"; do
  test -f "$bundle/$name" || { echo "missing locked evidence file: $name" >&2; exit 1; }
done
actual_names="$(find -H "$bundle" -maxdepth 1 -type f -exec basename {} \; | LC_ALL=C sort)"
expected_names="$(printf '%s\n' "${files[@]}" | LC_ALL=C sort)"
test "$actual_names" = "$expected_names" || { echo 'evidence bundle JSON names differ from locked nine-file contract' >&2; exit 1; }

schema_args=()
for name in "${files[@]}"; do
  jq -e . "$bundle/$name" >/dev/null
  schema="$project_root/scenarios/schema/${name%.json}.schema.json"
  test -f "$schema" || { echo "missing evidence schema: ${name%.json}.schema.json" >&2; exit 1; }
  schema_args+=("$schema" "$bundle/$name")
done
uv run --quiet --with 'jsonschema[format]==4.25.1' python "$validator" "${schema_args[@]}"

scenario_id="$(jq -er '.scenario_id' "$bundle/result.json")"
for name in "${files[@]}"; do
  test "$(jq -er '.scenario_id' "$bundle/$name")" = "$scenario_id" || { echo "scenario identity mismatch: $name" >&2; exit 1; }
done
runner_run_id="$(jq -er .runner_run_id "$bundle/result.json")"
for name in "${files[@]}"; do
  test "$(jq -er '.runner_run_id' "$bundle/$name")" = "$runner_run_id" || { echo "runner identity mismatch: $name" >&2; exit 1; }
done
catalog_row="$(jq -cer --arg id "$scenario_id" '.scenarios[] | select(.scenario_id==$id)' "$project_root/scenarios/catalog.json")" || { echo 'scenario is absent from locked catalog' >&2; exit 1; }
jq -e --argjson catalog "$catalog_row" '
  .expected_intermediate_states == $catalog.expected_intermediate_states and
  .expected_pipeline_state == $catalog.expected_terminal_state and
  .recovery_action == $catalog.recovery_action and
  .requires_rebuild == $catalog.requires_rebuild
' "$bundle/result.json" >/dev/null || { echo 'catalog/result semantic binding failed' >&2; exit 1; }
jq -e --slurpfile recovery "$bundle/recovery-actions.json" '
  .rebuild_required_before_rebuild == $recovery[0].rebuild_required_observed_before_rebuild
' "$bundle/result.json" >/dev/null || { echo 'recovery/result binding failed' >&2; exit 1; }

jq -e --slurpfile es "$bundle/es-snapshot.json" '
  def expected_source:
    if .active==1 then
      {product_id,sku,name,description,category_id,category_name,price_cents,available_quantity,
       searchable:true,source_revision:.revision,source_updated_at:.updated_at}
    else
      {product_id,searchable:false,source_revision:.revision,source_updated_at:.updated_at}
    end;
  (.documents|map(.product_id)|length)==(.documents|map(.product_id)|unique|length) and
  ($es[0].documents|map(.product_id)|length)==($es[0].documents|map(.product_id)|unique|length) and
  (.documents|map(.product_id)|sort)==($es[0].documents|map(.product_id)|sort) and
  all(.documents[]; . as $mysql |
    [$es[0].documents[]|select(.product_id==$mysql.product_id)] as $matches |
    ($matches|length)==1 and $matches[0].source==($mysql|expected_source))
' "$bundle/mysql-snapshot.json" >/dev/null || { echo 'MySQL/Elasticsearch snapshot binding failed' >&2; exit 1; }

jq -e --slurpfile result "$bundle/result.json" '
  if $result[0].result=="PASS" then
    ([.beginning[].partition]|sort)==[0,1,2] and
    ([.end[].partition]|sort)==[0,1,2] and
    ([.primary[].partition]|sort)==[0,1,2] and
    all(.primary[]; .offset==$result[0].applied_offsets[(.partition|tostring)] and .lag==0) and
    all(.beginning[]; . as $row | .offset <= $result[0].applied_offsets[($row.partition|tostring)]) and
    all(.end[]; . as $row | .offset >= $result[0].applied_offsets[($row.partition|tostring)]) and
    (if $result[0].requires_rebuild then
      (.shadow_and_barrier|length)>0 and
      all(.shadow_and_barrier|group_by([.run_id,.phase,.partition_id])[]; length==1) and
      any(.shadow_and_barrier|group_by(.run_id)[];
        ([.[]|(.phase+":"+(.partition_id|tostring))]|sort)==
        ["BARRIER:0","BARRIER:1","BARRIER:2","SHADOW:0","SHADOW:1","SHADOW:2","START:0","START:1","START:2"])
     else (.shadow_and_barrier|length)==0 end)
  else true end
' "$bundle/kafka-offsets.json" >/dev/null || { echo 'Kafka partition/offset binding failed' >&2; exit 1; }

jq -e --slurpfile manifest "$bundle/manifest.json" --slurpfile commands "$bundle/input-commands.json" \
  --slurpfile differences "$bundle/differences.json" '
  if .result=="PASS" then
    $manifest[0].execution_mode=="real" and
    $manifest[0].git.commit==.dependency_versions.project_head and
    $manifest[0].git.dirty==false and $manifest[0].git.tracked_dirty==false and
    ($manifest[0].checked_in_config_hashes|length)>=6 and
    [$commands[0].intents[].sequence]==[1,2,3] and
    [$commands[0].intents[].intent_phase]==["business-mutation","fault","recovery"] and
    [$commands[0].executions[].sequence]==[1,2,3] and
    [$commands[0].executions[].execution]==["mutate","recovery","verification"] and
    [$commands[0].executions[].intent_phases]==[["business-mutation","fault"],["recovery"],["verification"]] and
    all($commands[0].executions[];
      (.started_at|fromdateiso8601) <= (.finished_at|fromdateiso8601) and .exit_code==0) and
    $differences[0].independent_verification.runId==.verification.run_id and
    $differences[0].independent_verification.status==.verification.status and
    $differences[0].independent_verification.differenceCount==.exact_diff_count and
    $differences[0].observations.verification.run_id==.verification.run_id and
    $differences[0].observations.watermark_run_id==.watermark_run_id and
    (.started_at|fromdateiso8601) <= (.finished_at|fromdateiso8601)
  else true end
' "$bundle/result.json" >/dev/null || { echo 'manifest/commands/differences provenance binding failed' >&2; exit 1; }

if test "$(jq -r .result "$bundle/result.json")" = PASS; then
  while IFS=$'\t' read -r fixture_path fixture_sha256; do
    case "$fixture_path" in /*|*../*) echo "unsafe command fixture path: $fixture_path" >&2; exit 1 ;; esac
    test -f "$project_root/$fixture_path" && test ! -L "$project_root/$fixture_path" || { echo "missing command fixture: $fixture_path" >&2; exit 1; }
    test "$(shasum -a 256 "$project_root/$fixture_path" | awk '{print $1}')" = "$fixture_sha256" || { echo "command fixture hash mismatch: $fixture_path" >&2; exit 1; }
  done < <(jq -r '[.intents[],.executions[]]|.[]|[.fixture_path,.fixture_sha256]|@tsv' "$bundle/input-commands.json")
fi

jq -e '
  if .result == "PASS" then
    .target_watermark_passed == true and
    .target_watermarks.passed == true and
    .target_watermarks.mysql_revision >= .source_watermark and
    .target_watermarks.elasticsearch_revision >= .source_watermark and
    .watermark_run_id == .verification.run_id and
    .scenario_lag_satisfied == true and
    .recovery_action_observed == true and
    .cleanup_failures == 0 and
    (.failed_assertions|length) == 0 and
    all(.cleanup_actions[]; .success == true) and
    all(.consistency_preconditions[]; .satisfied == true) and
    .product_unresolved_dlq_count == 0 and
    .record_unresolved_dlq_count == 0 and
    .unresolved_dlq_count == (.product_unresolved_dlq_count + .record_unresolved_dlq_count) and
    .unresolved_dlq_count == 0 and
    .verification.status == "PASS" and
    .verification.conclusive == true and
    .verification.stable == true and
    .verification.exact_managed_field_diff_count == 0 and
    .verification.version_metadata_diff_count == 0 and
    .exact_diff_count == 0 and
    .tombstone_mismatch_count == 0 and
    .observed_pipeline_state == .expected_pipeline_state and
    ([.expected_intermediate_states[]] - [.observed_intermediate_states[]] | length) == 0 and
    (.requires_rebuild == false or .rebuild_required_before_rebuild == true) and
    all(.applied_offsets | to_entries[]; .value >= 0)
  else true end
' "$bundle/result.json" >/dev/null || { echo 'PASS result terminal semantics failed' >&2; exit 1; }

if test "$scenario_id" = canal-outage-beyond-binlog-retention; then
  jq -e '
    .canal_position_recovery as $r |
    $r != null and $r.normal_restart_preserved == true and
    $r.retained_binlog_files[$r.reset_lower_bound_file_index] == $r.reset_lower_bound_journal and
    $r.retained_binlog_files[$r.reset_file_index] == $r.reset_journal and
    $r.retained_binlog_files[$r.normal_restart_file_index] == $r.normal_restart_journal and
    ($r.reset_journal != $r.old_missing_journal or $r.reset_position != $r.old_missing_position) and
    ($r.reset_file_index > $r.reset_lower_bound_file_index or
      ($r.reset_file_index == $r.reset_lower_bound_file_index and $r.reset_position >= $r.reset_lower_bound_position)) and
    $r.reset_cursor_sha256 == $r.normal_restart_cursor_sha256 and
    $r.reset_journal == $r.normal_restart_journal and
    $r.reset_file_index == $r.normal_restart_file_index and
    $r.reset_position == $r.normal_restart_position and
    $r.reset_anchor_next_offsets == $r.reset_restart_offsets_before and
    $r.reset_restart_offsets_before == $r.normal_restart_offsets_after and
    $r.reset_anchor_run_id != $r.normal_sentinel_run_id and
    all([0,1,2][]; . as $partition | ($partition|tostring) as $key |
      $r.reset_anchor_events[$key].partition == $partition and
      $r.reset_anchor_events[$key].partition_token == $key and
      $r.reset_anchor_events[$key].key_is_null == true and
      $r.reset_anchor_events[$key].offset + 1 == $r.reset_anchor_next_offsets[$key] and
      $r.reset_anchor_events[$key].next_offset == $r.reset_anchor_next_offsets[$key] and
      $r.reset_anchor_events[$key].run_id == $r.reset_anchor_run_id and
      $r.normal_sentinel_events[$key].partition == $partition and
      $r.normal_sentinel_events[$key].partition_token == $key and
      $r.normal_sentinel_events[$key].key_is_null == true and
      $r.normal_sentinel_events[$key].offset + 1 == $r.normal_sentinel_next_offsets[$key] and
      $r.normal_sentinel_events[$key].next_offset == $r.normal_sentinel_next_offsets[$key] and
      $r.normal_sentinel_events[$key].run_id == $r.normal_sentinel_run_id and
      $r.normal_sentinel_next_offsets[$key] == $r.normal_restart_offsets_after[$key] + 1) and
    ([$r.reset_anchor_events[].event_id] | unique | length) == 3 and
    ([$r.normal_sentinel_events[].event_id] | unique | length) == 3
  ' "$bundle/result.json" >/dev/null
  jq -e --slurpfile offsets "$bundle/kafka-offsets.json" '
    .canal_position_recovery.reset_anchor_events == $offsets[0].raw_recovery_observations.reset_anchor.events and
    .canal_position_recovery.reset_anchor_next_offsets == $offsets[0].raw_recovery_observations.reset_anchor.next_offsets and
    .canal_position_recovery.normal_sentinel_events == $offsets[0].raw_recovery_observations.normal_sentinel.events and
    .canal_position_recovery.normal_sentinel_next_offsets == $offsets[0].raw_recovery_observations.normal_sentinel.next_offsets
  ' "$bundle/result.json" >/dev/null
fi

if test "$(jq -r .result "$bundle/result.json")" = PASS; then
  facts_tmp="$(mktemp -d)"; trap 'rm -rf "$facts_tmp"' EXIT
  while IFS=$'\t' read -r path sha kind; do
    case "$path" in /*|*../*) echo "unsafe case fact path: $path" >&2; exit 1 ;; esac
    if test "$kind" = json; then
      jq -cS --arg path "$path" '.case_observations.artifacts[]|select(.path==$path)|.json' "$bundle/fault.json" >"$facts_tmp/value"
    else
      jq -jr --arg path "$path" '.case_observations.artifacts[]|select(.path==$path)|.text' "$bundle/fault.json" >"$facts_tmp/value"
    fi
    test "$(shasum -a 256 "$facts_tmp/value" | awk '{print $1}')" = "$sha" || { echo "case fact hash mismatch: $path" >&2; exit 1; }
  done < <(jq -r '.case_observations.artifacts[]|[.path,.sha256,(if has("json") then "json" else "text" end)]|@tsv' "$bundle/fault.json")

  bash "$project_root/scenarios/scripts/assert-m6-case-semantics.sh" "$bundle/fault.json"
fi

printf 'M6 evidence contract passed: %s\n' "$scenario_id"
