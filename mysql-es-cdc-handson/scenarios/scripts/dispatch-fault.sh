#!/usr/bin/env bash
set -euo pipefail
scenario_id="${1:?scenario ID required}";run_dir="${2:?private run directory required}";token="${3:?ownership token required}"
test "$(cat "$run_dir/owner-token")" = "$token" || { echo 'fault ownership mismatch' >&2;exit 73; }
intent="$run_dir/cleanup-intent.json"
jq -e --arg scenario "$scenario_id" --arg token "$token" '
  .scenario_id==$scenario and .owner_token==$token and .registered==true
' "$intent" >/dev/null || { echo 'fault cleanup intent missing or mismatched' >&2;exit 73; }
if test -n "${M6_RUNNER_FIXTURE:-}";then
  jq -n --arg scenario "$scenario_id" --arg token "$token" \
    '{scenario_id:$scenario,owner_token:$token,resource:"fixture-fault",active:true}' >"$run_dir/fault-status.json"
  jq -n --arg scenario "$scenario_id" --arg token "$token" \
    '{scenario_id:$scenario,owner_token:$token,dispatched:true,cleanup_required:true}'
  test "${M6_RUNNER_FAULT_MODE:-}" != partial-fail || exit 73
  exit 0
fi
echo "Task 3 has no real executor for $scenario_id" >&2;exit 69
