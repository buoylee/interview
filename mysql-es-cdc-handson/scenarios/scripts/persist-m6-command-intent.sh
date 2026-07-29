#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
scenario_id="${1:?scenario required}"
owner_token="${2:?owner token required}"
output="${3:?output required}"
cd "$root"
count="$(jq --arg id "$scenario_id" '[.scenarios[]|select(.scenario_id==$id)]|length' scenarios/command-intents.json)"
test "$count" -eq 1 || { echo 'scenario command intent must occur exactly once' >&2; exit 64; }
case_file="$(jq -er --arg id "$scenario_id" '.scenarios[]|select(.scenario_id==$id)|[(.design_case|tostring|if length==1 then "0"+. else . end),.scenario_id]|join("-")+".sh"' scenarios/catalog.json)"
fixture_path="scenarios/scripts/cases/$case_file"
test -f "$fixture_path" && test ! -L "$fixture_path"
fixture_sha256="$(shasum -a 256 "$fixture_path" | awk '{print $1}')"
tmp="$(mktemp "$(dirname "$output")/.command-intent.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
jq -e --arg id "$scenario_id" --arg fixture "$fixture_path" '
  [.scenarios[]|select(.scenario_id==$id)] as $rows |
  ($rows|length)==1 and
  [$rows[0].commands[].sequence]==[1,2,3] and
  [$rows[0].commands[].intent_phase]==["business-mutation","fault","recovery"] and
  all($rows[0].commands[];.fixture_path==$fixture)
' scenarios/command-intents.json >/dev/null
jq -n --arg scenario "$scenario_id" --arg token "$owner_token" --arg sha "$fixture_sha256" \
  --argjson commands "$(jq -c --arg id "$scenario_id" '.scenarios[]|select(.scenario_id==$id)|.commands' scenarios/command-intents.json)" \
  '{schema_version:1,scenario_id:$scenario,owner_token:$token,state:"INTENDED",commands:($commands|map(.+{fixture_sha256:$sha})),executions:[]}' >"$tmp"
mv "$tmp" "$output"
trap - EXIT
