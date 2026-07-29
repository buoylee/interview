#!/usr/bin/env bash
set -euo pipefail
scenario_id="${1:?scenario ID required}";run_dir="${2:?private run directory required}";token="${3:?ownership token required}"
test "$(cat "$run_dir/owner-token")" = "$token" || { echo 'recovery ownership mismatch' >&2;exit 73; }
intent="$run_dir/cleanup-intent.json"
jq -e --arg scenario "$scenario_id" --arg token "$token" '
  .scenario_id==$scenario and .owner_token==$token and .registered==true
' "$intent" >/dev/null || { echo 'recovery cleanup intent missing or mismatched' >&2;exit 73; }
command_intent="$run_dir/command-intent.json"
jq -e --arg scenario "$scenario_id" --arg token "$token" '
  .scenario_id==$scenario and .owner_token==$token and (.state=="INTENDED" or .state=="EXECUTING") and
  ([.executions[]|select(.execution=="recovery")]|length)==0
' "$command_intent" >/dev/null 2>&1 || { echo 'recovery command intent missing or mismatched' >&2;exit 73; }
jq -e --arg scenario "$scenario_id" --arg token "$token" '
  .scenario_id==$scenario and .owner_token==$token and .active==true and
  (.resource=="fixture-fault" or .resource=="m6-real-fault")
' "$run_dir/fault-status.json" >/dev/null 2>&1 || { echo 'owned active fault dispatch receipt missing' >&2;exit 73; }
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
  bash "$(dirname "$0")/complete-m6-command-intent.sh" "$command_intent" recovery "$started_at" "$finished_at" "$exit_code"
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
test "${M6_RUNNER_EXECUTION_MODE:-}" = real || { echo "real recovery mode required" >&2; exit 69; }
started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
success=true;exit_code=0
if bash "$(dirname "$0")/execute-case.sh" "$scenario_id" recover "$run_dir" "$token"; then
  rm -f "$run_dir/fault-status.json"
else
  exit_code=$?;success=false
fi
finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
bash "$(dirname "$0")/complete-m6-command-intent.sh" "$command_intent" recovery "$started_at" "$finished_at" "$exit_code"
status_clear=false;test ! -e "$run_dir/fault-status.json" && status_clear=true
jq -n --arg scenario "$scenario_id" --arg token "$token" --arg started "$started_at" --arg finished "$finished_at" \
  --argjson success "$success" --argjson status_clear "$status_clear" --argjson exit_code "$exit_code" '{
    scenario_id:$scenario,owner_token:$token,recovery_action_observed:$status_clear,
    external_status:{resource:"m6-real-fault",active:($status_clear|not),observed:$status_clear},
    cleanup_actions:[{name:"dispatch-owned-m6-real-fault",success:$success,finished_at:$finished}],
    commands:[{sequence:1,kind:"CONTROL",target:"m6-real-fault",method:"DELETE",path:("/scenario/"+$scenario+"/fault"),started_at:$started,finished_at:$finished,exit_code:$exit_code}]
  }'
exit "$exit_code"
