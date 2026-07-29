#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
index="${1:?index path required}"
catalog="$root/scenarios/catalog.json"

jq -e '
  type=="object" and
  (keys|sort==["fail_count","pass_count","scenario_count","scenarios","schema_version"]) and
  .schema_version==1 and .scenario_count==18 and .pass_count==18 and .fail_count==0 and
  (.scenarios|type=="array" and length==18) and
  all(.scenarios[];
    type=="object" and
    (keys|sort==["design_case","result","scenario_id"]) and
    .result=="PASS")
' "$index" >/dev/null

jq -n --slurpfile actual "$index" --slurpfile catalog "$catalog" -e '
  ($actual[0].scenarios|map({design_case,scenario_id})) ==
  ($catalog[0].scenarios|map({design_case,scenario_id}))
' >/dev/null
