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
actual_names="$(find "$bundle" -maxdepth 1 -type f -exec basename {} \; | LC_ALL=C sort)"
expected_names="$(printf '%s\n' "${files[@]}" | LC_ALL=C sort)"
test "$actual_names" = "$expected_names" || { echo 'evidence bundle JSON names differ from locked nine-file contract' >&2; exit 1; }

for name in "${files[@]}"; do jq -e . "$bundle/$name" >/dev/null; done
uv run --quiet --with 'jsonschema[format]==4.25.1' python "$validator" "$result_schema" "$bundle/result.json"

scenario_id="$(jq -er '.scenario_id' "$bundle/result.json")"
for name in "${files[@]}"; do
  test "$(jq -er '.scenario_id' "$bundle/$name")" = "$scenario_id" || { echo "scenario identity mismatch: $name" >&2; exit 1; }
done
catalog_row="$(jq -cer --arg id "$scenario_id" '.scenarios[] | select(.scenario_id==$id)' "$project_root/scenarios/catalog.json")" || { echo 'scenario is absent from locked catalog' >&2; exit 1; }
jq -e --argjson catalog "$catalog_row" '
  .expected_intermediate_states == $catalog.expected_intermediate_states and
  .expected_pipeline_state == $catalog.expected_terminal_state and
  .recovery_action == $catalog.recovery_action and
  .requires_rebuild == $catalog.requires_rebuild
' "$bundle/result.json" >/dev/null
jq -e --slurpfile recovery "$bundle/recovery-actions.json" '
  .rebuild_required_before_rebuild == $recovery[0].rebuild_required_observed_before_rebuild
' "$bundle/result.json" >/dev/null

jq -e '
  if .result == "PASS" then
    .target_watermark_passed == true and
    .target_watermarks.passed == true and
    .target_watermarks.mysql_revision >= .source_watermark and
    .target_watermarks.elasticsearch_revision >= .source_watermark and
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
' "$bundle/result.json" >/dev/null

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

printf 'M6 evidence contract passed: %s\n' "$scenario_id"
