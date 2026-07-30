#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd -P)"
first_input="${1:?usage: normalized-evidence.sh FIRST_EVIDENCE SECOND_EVIDENCE}"
second_input="${2:?usage: normalized-evidence.sh FIRST_EVIDENCE SECOND_EVIDENCE}"

test -d "$first_input" && test ! -L "$first_input" || { echo "first evidence root must be a physical directory: $first_input" >&2; exit 1; }
test -d "$second_input" && test ! -L "$second_input" || { echo "second evidence root must be a physical directory: $second_input" >&2; exit 1; }
first="$(cd "$first_input" && pwd -P)"
second="$(cd "$second_input" && pwd -P)"
test "$first" != "$second" || { echo 'evidence roots must be distinct' >&2; exit 1; }

for root in "$first" "$second"; do
  test -f "$root/index.json" && test ! -L "$root/index.json" || { echo "missing physical evidence index: $root/index.json" >&2; exit 1; }
  bash "$project_root/scenarios/scripts/validate-m6-index.sh" "$root/index.json" >/dev/null
done

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
: >"$tmp/first-run-ids"
: >"$tmp/second-run-ids"

normalize() {
  local result="$1" output="$2"
  jq -S '
    del(
      .runner_run_id,
      .started_at,
      .finished_at,
      .source_watermark,
      .target_watermarks.mysql_revision,
      .target_watermarks.elasticsearch_revision,
      .applied_offsets,
      .dependency_versions.image_digests,
      .consistency_preconditions[].observed_at,
      .cleanup_actions[].finished_at,
      .verification.run_id,
      .verification.observed_at,
      .watermark_run_id
    ) |
    if .canal_position_recovery == null then . else
      del(
        .canal_position_recovery.old_cursor_sha256,
        .canal_position_recovery.reset_cursor_sha256,
        .canal_position_recovery.normal_restart_cursor_sha256,
        .canal_position_recovery.reset_anchor_run_id,
        .canal_position_recovery.normal_sentinel_run_id,
        .canal_position_recovery.reset_anchor_next_offsets,
        .canal_position_recovery.reset_restart_offsets_before,
        .canal_position_recovery.normal_restart_offsets_after,
        .canal_position_recovery.normal_sentinel_next_offsets,
        .canal_position_recovery.reset_anchor_events[].event_id,
        .canal_position_recovery.reset_anchor_events[].run_id,
        .canal_position_recovery.reset_anchor_events[].offset,
        .canal_position_recovery.reset_anchor_events[].next_offset,
        .canal_position_recovery.reset_anchor_events[].record_value_sha256,
        .canal_position_recovery.normal_sentinel_events[].event_id,
        .canal_position_recovery.normal_sentinel_events[].run_id,
        .canal_position_recovery.normal_sentinel_events[].offset,
        .canal_position_recovery.normal_sentinel_events[].next_offset,
        .canal_position_recovery.normal_sentinel_events[].record_value_sha256
      )
    end
  ' "$result" >"$output"
}

normalize_decoded_cursors() {
  local fault="$1" output="$2"
  jq -Se '
    [
      .case_observations.artifacts[]
      | select(.path == "old-meta.json"
          or .path == "canal-recovery/canal-meta-before.json"
          or .path == "canal-recovery/reset-anchor-meta-before-publication.json"
          or .path == "canal-recovery/canal-meta-reset.json"
          or .path == "canal-recovery/canal-meta-normal-restart.json")
      | {path, cursor:(.json | del(.timestamp))}
    ] | sort_by(.path)
    | if length == 5 then . else error("exact decoded Canal cursor set required") end
  ' "$fault" >"$output"
}

compared=0
while IFS= read -r scenario; do
  first_result="$first/$scenario/result.json"
  second_result="$second/$scenario/result.json"
  for result in "$first_result" "$second_result"; do
    test -f "$result" && test ! -L "$result" || { echo "missing physical result: $result" >&2; exit 1; }
    test "$(jq -er .scenario_id "$result")" = "$scenario" || { echo "scenario identity mismatch: $result" >&2; exit 1; }
  done

  first_run_id="$(jq -er .runner_run_id "$first_result")"
  second_run_id="$(jq -er .runner_run_id "$second_result")"
  test "$first_run_id" != "$second_run_id" || { echo "reused runner_run_id: $scenario" >&2; exit 1; }
  printf '%s\n' "$first_run_id" >>"$tmp/first-run-ids"
  printf '%s\n' "$second_run_id" >>"$tmp/second-run-ids"

  first_started="$(jq -er .started_at "$first_result")"
  second_started="$(jq -er .started_at "$second_result")"
  first_finished="$(jq -er .finished_at "$first_result")"
  second_finished="$(jq -er .finished_at "$second_result")"
  test "$first_started" != "$second_started" && test "$first_finished" != "$second_finished" || {
    echo "reused run timestamp: $scenario" >&2
    exit 1
  }

  normalize "$first_result" "$tmp/first-$scenario.json"
  normalize "$second_result" "$tmp/second-$scenario.json"
  if ! cmp -s "$tmp/first-$scenario.json" "$tmp/second-$scenario.json"; then
    echo "normalized evidence mismatch: $scenario" >&2
    diff -u "$tmp/first-$scenario.json" "$tmp/second-$scenario.json" >&2 || true
    exit 1
  fi
  if test "$scenario" = canal-outage-beyond-binlog-retention; then
    first_fault="$first/$scenario/fault.json"
    second_fault="$second/$scenario/fault.json"
    normalize_decoded_cursors "$first_fault" "$tmp/first-$scenario-cursors.json"
    normalize_decoded_cursors "$second_fault" "$tmp/second-$scenario-cursors.json"
    if ! cmp -s "$tmp/first-$scenario-cursors.json" "$tmp/second-$scenario-cursors.json"; then
      echo "normalized decoded Canal cursor mismatch: $scenario" >&2
      diff -u "$tmp/first-$scenario-cursors.json" "$tmp/second-$scenario-cursors.json" >&2 || true
      exit 1
    fi
  fi
  compared=$((compared + 1))
done < <(jq -r '.scenarios[].scenario_id' "$project_root/scenarios/catalog.json")

test "$compared" -eq 18 || { echo "normalized evidence compared $compared scenarios, expected 18" >&2; exit 1; }
test "$(LC_ALL=C sort -u "$tmp/first-run-ids" | wc -l | tr -d ' ')" -eq 18 || { echo 'first evidence run IDs are not unique' >&2; exit 1; }
test "$(LC_ALL=C sort -u "$tmp/second-run-ids" | wc -l | tr -d ' ')" -eq 18 || { echo 'second evidence run IDs are not unique' >&2; exit 1; }
test "$(LC_ALL=C sort -u "$tmp/first-run-ids" "$tmp/second-run-ids" | wc -l | tr -d ' ')" -eq 36 || { echo 'evidence rounds reuse a runner run ID' >&2; exit 1; }

printf 'Normalized evidence equal: 18/18 with fresh run identities\n'
