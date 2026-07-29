#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
scenario_id="${1:?scenario ID required}";run_dir="${2:?private run directory required}";token="${3:?ownership token required}"
test "$(cat "$run_dir/owner-token")" = "$token" || { echo 'fault ownership mismatch' >&2;exit 73; }
intent="$run_dir/cleanup-intent.json"
jq -e --arg scenario "$scenario_id" --arg token "$token" '
  .scenario_id==$scenario and .owner_token==$token and .registered==true
' "$intent" >/dev/null || { echo 'fault cleanup intent missing or mismatched' >&2;exit 73; }
command_intent="$run_dir/command-intent.json"
jq -e --arg scenario "$scenario_id" --arg token "$token" '
  .scenario_id==$scenario and .owner_token==$token and .state=="INTENDED" and
  [.commands[].intent_phase]==["business-mutation","fault","recovery"] and
  .executions==[] and all(.commands[];has("started_at")|not)
' "$command_intent" >/dev/null 2>&1 || { echo 'pre-dispatch command intent missing or mismatched' >&2;exit 73; }
while IFS=$'\t' read -r fixture_path fixture_sha256; do
  test -f "$root/$fixture_path" && test ! -L "$root/$fixture_path"
  test "$(shasum -a 256 "$root/$fixture_path" | awk '{print $1}')" = "$fixture_sha256"
done < <(jq -r '.commands[]|[.fixture_path,.fixture_sha256]|@tsv' "$command_intent")
if test -n "${M6_RUNNER_FIXTURE:-}";then
  jq -n --arg scenario "$scenario_id" --arg token "$token" \
    '{scenario_id:$scenario,owner_token:$token,resource:"fixture-fault",active:true}' >"$run_dir/fault-status.json"
  jq -n --arg scenario "$scenario_id" --arg token "$token" \
    '{scenario_id:$scenario,owner_token:$token,dispatched:true,cleanup_required:true}'
  test "${M6_RUNNER_FAULT_MODE:-}" != partial-fail || exit 73
  exit 0
fi
test "${M6_RUNNER_EXECUTION_MODE:-}" = real || { echo "real executor mode required" >&2; exit 69; }
jq -n --arg scenario "$scenario_id" --arg token "$token" \
  '{scenario_id:$scenario,owner_token:$token,resource:"m6-real-fault",active:true,state:"DISPATCHING"}' >"$run_dir/fault-status.json"
bash "$root/scenarios/scripts/execute-case.sh" "$scenario_id" mutate "$run_dir" "$token"
jq '.state="DISPATCHED"' "$run_dir/fault-status.json" >"$run_dir/fault-status.next"
mv "$run_dir/fault-status.next" "$run_dir/fault-status.json"
jq -n --arg scenario "$scenario_id" --arg token "$token" \
  '{scenario_id:$scenario,owner_token:$token,dispatched:true,cleanup_required:true}'
