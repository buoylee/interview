#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

uv run --quiet --with 'jsonschema[format]==4.25.1' python tests/contracts/validate-json-schema.py \
  scenarios/schema/command-intents.schema.json scenarios/command-intents.json
jq -e --slurpfile catalog scenarios/catalog.json '
  (.scenarios|length)==18 and
  ([.scenarios[].scenario_id]|length)==([.scenarios[].scenario_id]|unique|length) and
  ([.scenarios[].scenario_id]|sort)==([$catalog[0].scenarios[].scenario_id]|sort) and
  all(.scenarios[];
    [.commands[].sequence]==[1,2,3] and
    [.commands[].intent_phase]==["business-mutation","fault","recovery"])
' scenarios/command-intents.json >/dev/null

scenario=duplicate-event
token=11111111-1111-4111-8111-111111111111
printf '%s\n' "$token" >"$tmp/owner-token"
jq -n --arg scenario "$scenario" --arg token "$token" \
  '{scenario_id:$scenario,owner_token:$token,registered:true}' >"$tmp/cleanup-intent.json"

if M6_RUNNER_EXECUTION_MODE=fixture M6_RUNNER_FIXTURE=tests/fixtures/m6/runner-wrong-terminal.json \
  bash scenarios/scripts/dispatch-fault.sh "$scenario" "$tmp" "$token" >/dev/null 2>&1; then
  echo 'fault dispatch accepted a missing pre-dispatch command intent' >&2
  exit 1
fi
test ! -e "$tmp/fault-status.json"

bash scenarios/scripts/persist-m6-command-intent.sh "$scenario" "$token" "$tmp/command-intent.json"
jq -e --arg scenario "$scenario" --arg token "$token" '
  .scenario_id==$scenario and .owner_token==$token and .state=="INTENDED" and
  [.commands[].intent_phase]==["business-mutation","fault","recovery"] and
  .executions==[] and
  all(.commands[];
    (.target|length)>0 and (.method|length)>0 and (.path|startswith("/")) and
    (.fixture_path|startswith("scenarios/scripts/cases/")) and
    (.fixture_sha256|test("^[a-f0-9]{64}$")) and
    (has("started_at")|not) and (has("finished_at")|not) and (has("exit_code")|not))
' "$tmp/command-intent.json" >/dev/null

if M6_RUNNER_FIXTURE=tests/fixtures/m6/runner-wrong-terminal.json \
  bash scenarios/scripts/dispatch-recovery.sh "$scenario" "$tmp" "$token" >"$tmp/pre-dispatch-recovery.json" 2>/dev/null; then
  echo 'recovery dispatched without an owned active fault receipt' >&2
  exit 1
fi
test ! -s "$tmp/pre-dispatch-recovery.json"
jq -e '.state=="INTENDED" and .executions==[]' "$tmp/command-intent.json" >/dev/null

bash scenarios/scripts/complete-m6-command-intent.sh "$tmp/command-intent.json" mutate \
  2026-07-29T20:00:00Z 2026-07-29T20:00:01Z 0
bash scenarios/scripts/complete-m6-command-intent.sh "$tmp/command-intent.json" recovery \
  2026-07-29T20:00:02Z 2026-07-29T20:00:03Z 0
jq -e '
  .state=="COMPLETED" and
  [.executions[].execution]==["mutate","recovery"] and
  [.executions[].intent_phases]==[["business-mutation","fault"],["recovery"]] and
  all(.executions[];
    (.started_at|fromdateiso8601) and
    (.finished_at|fromdateiso8601) and
    (.started_at|fromdateiso8601) <= (.finished_at|fromdateiso8601) and
    .exit_code==0)
' "$tmp/command-intent.json" >/dev/null

echo 'M6 pre-dispatch command intent contract passed'
