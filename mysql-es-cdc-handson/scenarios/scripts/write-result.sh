#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
source "$(dirname "$0")/lib/common.sh"
scenario_id="${1:?scenario ID required}";run_id="${2:?run ID required}";started_at="${3:?start timestamp required}";observations="${4:?observations required}";recovery="${5:?recovery required}";output="${6:?output required}"
test "$(jq --arg id "$scenario_id" '[.scenarios[]|select(.scenario_id==$id)]|length' "$root/scenarios/catalog.json")" -eq 1
jq -e 'type=="object" and (has("result")|not)' "$observations" >/dev/null
row="$(jq -cer --arg id "$scenario_id" '.scenarios[]|select(.scenario_id==$id)' "$root/scenarios/catalog.json")"
finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)";head="$(git -C "$root" rev-parse HEAD)"
failed="$(jq -cn --argjson row "$row" --slurpfile o "$observations" --slurpfile r "$recovery" --arg run "$run_id" '
  $o[0] as $x | $r[0] as $recovery | [
    (if all($x.consistency_preconditions[]?;.satisfied==true) then empty else "consistency_preconditions" end),
    (if ([$row.expected_intermediate_states[]]-[$x.observed_intermediate_states[]]|length)==0 then empty else "intermediate_states" end),
    (if $x.recovery_action_observed==true then empty else "recovery_action" end),
    (if $x.watermark_run_id==$x.verification.run_id and $x.target_watermarks.passed==true and $x.target_watermarks.mysql_revision >= $x.source_watermark and $x.target_watermarks.elasticsearch_revision >= $x.source_watermark then empty else "target_watermark" end),
    (if $x.scenario_lag_satisfied==true then empty else "scenario_lag" end),
    (if $x.product_unresolved_dlq_count==0 and $x.record_unresolved_dlq_count==0 then empty else "unresolved_dlq" end),
    (if $x.verification.run_id==$x.watermark_run_id and $x.verification.status=="PASS" and $x.verification.conclusive==true and $x.verification.stable==true and $x.verification.exact_managed_field_diff_count==0 and $x.verification.version_metadata_diff_count==0 then empty else "independent_verification" end),
    (if $x.exact_diff_count==0 then empty else "exact_diff" end),
    (if $x.tombstone_mismatch_count==0 then empty else "tombstone_mismatch" end),
    (if $x.observed_pipeline_state==$row.expected_terminal_state then empty else "terminal_pipeline_state" end),
    (if ($recovery.cleanup_failures//1)==0 and all($recovery.cleanup_actions[]?;.success==true) then empty else "cleanup" end),
    (if ($row.requires_rebuild|not) or $x.rebuild_required_before_rebuild==true then empty else "rebuild_required_before_rebuild" end),
    ($x.runner_failures[]?)
  ]|unique')"
result=FAIL;test "$(jq length <<<"$failed")" -ne 0||result=PASS
jq -n --argjson row "$row" --slurpfile o "$observations" --slurpfile recovery "$recovery" --arg run "$run_id" --arg head "$head" --arg result "$result" --arg started "$started_at" --arg finished "$finished_at" --argjson failed "$failed" '
  $o[0] as $x | $recovery[0] as $r | {
    schema_version:1,scenario_id:$row.scenario_id,
    dependency_versions:{mysql:"8.4.8",canal:"1.1.8",kafka:"4.1.2",elasticsearch:"8.17.0",project_head:$head},
    consistency_preconditions:$x.consistency_preconditions,source_watermark:$x.source_watermark,target_watermarks:$x.target_watermarks,
    applied_offsets:$x.applied_offsets,product_unresolved_dlq_count:$x.product_unresolved_dlq_count,record_unresolved_dlq_count:$x.record_unresolved_dlq_count,
    unresolved_dlq_count:($x.product_unresolved_dlq_count+$x.record_unresolved_dlq_count),verification:($x.verification+{run_id:($x.verification.run_id//"00000000-0000-4000-8000-000000000000")}),
    exact_diff_count:$x.exact_diff_count,tombstone_mismatch_count:$x.tombstone_mismatch_count,canal_position_recovery:($x.canal_position_recovery//null),
    expected_intermediate_states:$row.expected_intermediate_states,observed_intermediate_states:$x.observed_intermediate_states,
    expected_pipeline_state:$row.expected_terminal_state,observed_pipeline_state:$x.observed_pipeline_state,recovery_action:$row.recovery_action,
    requires_rebuild:$row.requires_rebuild,rebuild_required_before_rebuild:$x.rebuild_required_before_rebuild,target_watermark_passed:$x.target_watermarks.passed,
    runner_run_id:$run,watermark_run_id:($x.watermark_run_id//"00000000-0000-4000-8000-000000000000"),scenario_lag_satisfied:$x.scenario_lag_satisfied,recovery_action_observed:$x.recovery_action_observed,
    cleanup_failures:$r.cleanup_failures,failed_assertions:$failed,cleanup_actions:$r.cleanup_actions,result:$result,started_at:$started,finished_at:$finished
  }' | atomic_json "$output"
test "$result" = PASS
