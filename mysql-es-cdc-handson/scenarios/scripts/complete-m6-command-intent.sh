#!/usr/bin/env bash
set -euo pipefail

intent="${1:?intent required}"
execution="${2:?execution required}"
started="${3:?started timestamp required}"
finished="${4:?finished timestamp required}"
exit_code="${5:?exit code required}"
case "$execution" in mutate|recovery) ;; *) echo 'unknown intent execution' >&2; exit 64 ;; esac
jq -en --arg started "$started" --arg finished "$finished" --argjson exit_code "$exit_code" '
  ($started|fromdateiso8601) <= ($finished|fromdateiso8601) and $exit_code>=0 and $exit_code<=255
' >/dev/null
jq -e --arg execution "$execution" '
  (.executions|type)=="array" and
  ([.executions[]|select(.execution==$execution)]|length)==0
' "$intent" >/dev/null
tmp="$(mktemp "$(dirname "$intent")/.command-intent-complete.XXXXXX")"
trap 'rm -f "$tmp"' EXIT
jq --arg execution "$execution" --arg started "$started" --arg finished "$finished" --argjson exit_code "$exit_code" '
  .scenario_id as $scenario |
  .commands[0].fixture_path as $fixture |
  .commands[0].fixture_sha256 as $sha |
  .executions += [
    if $execution=="mutate" then
      {sequence:1,execution:"mutate",intent_phases:["business-mutation","fault"],kind:"CONTROL",
       target:"m6-case-runner",method:"EXECUTE",path:("/scenario/"+$scenario+"/mutate"),
       fixture_path:$fixture,fixture_sha256:$sha,started_at:$started,finished_at:$finished,exit_code:$exit_code}
    else
      {sequence:2,execution:"recovery",intent_phases:["recovery"],kind:"CONTROL",
       target:"m6-case-runner",method:"EXECUTE",path:("/scenario/"+$scenario+"/recover"),
       fixture_path:$fixture,fixture_sha256:$sha,started_at:$started,finished_at:$finished,exit_code:$exit_code}
    end
  ] |
  .state=(if [.executions[].execution]==["mutate","recovery"] then "COMPLETED" else "EXECUTING" end)
' "$intent" >"$tmp"
mv "$tmp" "$intent"
trap - EXIT
