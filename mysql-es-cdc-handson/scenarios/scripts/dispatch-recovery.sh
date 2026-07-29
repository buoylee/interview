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
  output="$run_dir/recovery-dispatch.json"
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
      external_status:{resource:"fixture-fault",active:($status_clear|not),observed:$status_clear},
      cleanup_actions:[{name:"dispatch-owned-fixture-fault",success:$success,finished_at:$finished}],
      commands:[{
        sequence:1,kind:"CONTROL",target:"fixture-fault-status",method:"DELETE",
        path:"/owned/fixture-fault",started_at:$started,finished_at:$finished,exit_code:$exit_code
      }]
    }' >"$output"
  if test -n "${M6_RUNNER_RECOVERY_OUTPUT_MODE:-}"; then
    test "${M6_RUNNER_INTERNAL_TEST_HOOKS:-}" = fixture-fail-v1 || {
      echo 'recovery output fixture hook is forbidden' >&2
      exit 73
    }
    case "$M6_RUNNER_RECOVERY_OUTPUT_MODE" in
      top-extra) jq '.unexpected=true' "$output" >"$output.next" ;;
      external-extra) jq '.external_status.extra=true' "$output" >"$output.next" ;;
      command-shell) jq '.commands[0].shell="printf forbidden"' "$output" >"$output.next" ;;
      command-auth) jq '.commands[0][("author"+"ization")]="forbidden"' "$output" >"$output.next" ;;
      command-path) jq '.commands[0].path="/../escape"' "$output" >"$output.next" ;;
      success-exit-mismatch) jq '.commands[0].exit_code=73' "$output" >"$output.next" ;;
      status-mismatch) jq '.external_status.observed=false' "$output" >"$output.next" ;;
      cleanup-mismatch) jq '.cleanup_actions[0].success=false' "$output" >"$output.next" ;;
      *) echo 'unknown recovery output fixture mode' >&2;exit 73 ;;
    esac
    mv "$output.next" "$output"
  fi
  cat "$output"
  exit "$exit_code"
fi
echo "Task 3 has no real recovery executor for $scenario_id" >&2;exit 69
