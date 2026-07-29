#!/usr/bin/env bash
set -euo pipefail
scenario_id="${1:?scenario ID required}";run_dir="${2:?private run directory required}";token="${3:?ownership token required}"
test "$(cat "$run_dir/owner-token")" = "$token" || { echo 'recovery ownership mismatch' >&2;exit 73; }
intent="$run_dir/cleanup-intent.json"
jq -e --arg scenario "$scenario_id" --arg token "$token" '
  .scenario_id==$scenario and .owner_token==$token and .registered==true
' "$intent" >/dev/null || { echo 'recovery cleanup intent missing or mismatched' >&2;exit 73; }
if test -n "${M6_RUNNER_FIXTURE:-}";then
  started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  success=true
  exit_code=0
  if test "${M6_RUNNER_RECOVERY_MODE:-}" = fail; then
    success=false
    exit_code=73
  else
    rm -f "$run_dir/fault-status.json"
  fi
  status_clear=false
  test ! -e "$run_dir/fault-status.json" && status_clear=true
  finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  jq -n \
    --arg scenario "$scenario_id" \
    --arg token "$token" \
    --arg started "$started_at" \
    --arg finished "$finished_at" \
    --argjson success "$success" \
    --argjson status_clear "$status_clear" \
    --argjson exit_code "$exit_code" \
    '{
      scenario_id:$scenario,
      owner_token:$token,
      recovery_action_observed:$status_clear,
      external_status:{resource:"fixture-fault",active:false,observed:$status_clear},
      cleanup_actions:[{name:"dispatch-owned-fixture-fault",success:$success,finished_at:$finished}],
      commands:[{
        sequence:1,kind:"CONTROL",target:"fixture-fault-status",method:"DELETE",
        path:"/owned/fixture-fault",started_at:$started,finished_at:$finished,exit_code:$exit_code
      }]
    }'
  exit "$exit_code"
fi
echo "Task 3 has no real recovery executor for $scenario_id" >&2;exit 69
