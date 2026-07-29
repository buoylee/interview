#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
comparator=tests/contracts/normalized-evidence.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
left="$tmp/left"
right="$tmp/right"
mkdir -p "$left" "$right"
cp evidence/index.json "$left/index.json"
cp evidence/index.json "$right/index.json"

while IFS=$'\t' read -r design_case scenario; do
  cp -R "evidence/$scenario" "$left/$scenario"
  cp -R "evidence/$scenario" "$right/$scenario"
  runner_id="$(printf '10000000-0000-4000-8000-%012d' "$design_case")"
  verifier_id="$(printf '20000000-0000-4000-8000-%012d' "$design_case")"
  jq --arg runner_id "$runner_id" --arg verifier_id "$verifier_id" '
    .runner_run_id=$runner_id |
    .verification.run_id=$verifier_id |
    .watermark_run_id=$verifier_id |
    .started_at="2026-07-30T00:00:00Z" |
    .finished_at="2026-07-30T00:01:00Z" |
    .cleanup_actions[].finished_at="2026-07-30T00:00:59Z" |
    .consistency_preconditions[].observed_at="2026-07-30T00:00:01Z" |
    .verification.observed_at="2026-07-30T00:00:58Z" |
    .source_watermark+=1000 |
    .target_watermarks.mysql_revision+=1000 |
    .target_watermarks.elasticsearch_revision+=1000 |
    .applied_offsets|=with_entries(.value+=1000) |
    .dependency_versions.image_digests={mysql:"sha256:fresh"} |
    if .canal_position_recovery == null then . else
      .canal_position_recovery.reset_anchor_run_id=$runner_id |
      .canal_position_recovery.normal_sentinel_run_id=$verifier_id |
      .canal_position_recovery.reset_anchor_next_offsets|=with_entries(.value+=1000) |
      .canal_position_recovery.reset_restart_offsets_before|=with_entries(.value+=1000) |
      .canal_position_recovery.normal_restart_offsets_after|=with_entries(.value+=1000) |
      .canal_position_recovery.normal_sentinel_next_offsets|=with_entries(.value+=1000) |
      .canal_position_recovery.reset_anchor_events[] |=
        (.run_id=$runner_id | .event_id=$runner_id | .offset+=1000 | .next_offset+=1000 | .record_value_sha256=("a"*64)) |
      .canal_position_recovery.normal_sentinel_events[] |=
        (.run_id=$verifier_id | .event_id=$verifier_id | .offset+=1000 | .next_offset+=1000 | .record_value_sha256=("b"*64))
    end
  ' "$right/$scenario/result.json" >"$right/$scenario/result.tmp"
  mv "$right/$scenario/result.tmp" "$right/$scenario/result.json"
done < <(jq -r '.scenarios[]|[.design_case,.scenario_id]|@tsv' scenarios/catalog.json)

bash "$comparator" "$left" "$right" >/dev/null

expect_rejected() {
  local name="$1" scenario="$2" filter="$3" candidate
  candidate="$tmp/rejected-$name"
  cp -R "$right" "$candidate"
  jq "$filter" "$candidate/$scenario/result.json" >"$candidate/$scenario/result.tmp"
  mv "$candidate/$scenario/result.tmp" "$candidate/$scenario/result.json"
  if bash "$comparator" "$left" "$candidate" >"$tmp/$name.out" 2>&1; then
    echo "normalized comparison accepted semantic tamper: $name" >&2
    exit 1
  fi
}

scenario=duplicate-event
expect_rejected result "$scenario" '.result="FAIL"'
expect_rejected scenario-id "$scenario" '.scenario_id="late-old-revision"'
expect_rejected expected-state "$scenario" '.expected_pipeline_state="DEGRADED"'
expect_rejected observed-state "$scenario" '.observed_pipeline_state="DEGRADED"'
expect_rejected recovery "$scenario" '.recovery_action="skip recovery"'
expect_rejected count "$scenario" '.exact_diff_count=1'
expect_rejected precondition-name "$scenario" '.consistency_preconditions[0].name="invented"'
expect_rejected precondition-result "$scenario" '.consistency_preconditions[0].satisfied=false'
expect_rejected dependency-version "$scenario" '.dependency_versions.mysql="invented"'
expect_rejected target-watermark-result "$scenario" '.target_watermark_passed=false'
expect_rejected tombstone-count "$scenario" '.tombstone_mismatch_count=1'

same_ids="$tmp/same-ids"
cp -R "$left" "$same_ids"
if bash "$comparator" "$left" "$same_ids" >"$tmp/same-ids.out" 2>&1; then
  echo 'normalized comparison accepted reused run identities' >&2
  exit 1
fi

printf 'Normalized evidence tamper contract passed\n'
