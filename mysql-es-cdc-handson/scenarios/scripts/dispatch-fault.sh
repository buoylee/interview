#!/usr/bin/env bash
set -euo pipefail
scenario_id="${1:?scenario ID required}";run_dir="${2:?private run directory required}";token="${3:?ownership token required}"
test "$(cat "$run_dir/owner-token")" = "$token" || { echo 'fault ownership mismatch' >&2;exit 73; }
if test -n "${M6_RUNNER_FIXTURE:-}";then jq -n --arg scenario "$scenario_id" --arg token "$token" '{scenario_id:$scenario,owner_token:$token,dispatched:true}';exit 0;fi
echo "Task 3 has no real executor for $scenario_id" >&2;exit 69
