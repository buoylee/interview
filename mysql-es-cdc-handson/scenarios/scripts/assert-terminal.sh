#!/usr/bin/env bash
set -euo pipefail
catalog_row="${1:?catalog row required}";observations="${2:?observations required}";output="${3:?output required}"
jq -n --argjson row "$(cat "$catalog_row")" --slurpfile o "$observations" '
  ($o[0].observed_pipeline_state==$row.expected_terminal_state) as $terminal |
  (([$row.expected_intermediate_states[]]-[$o[0].observed_intermediate_states[]]|length)==0) as $intermediate |
  {passed:($terminal and $intermediate),failed:([if $intermediate then empty else "intermediate_states" end,if $terminal then empty else "terminal_pipeline_state" end])}
' >"$output"
jq -e '.passed==true' "$output" >/dev/null
