#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
contract="$project_root/tests/contracts/scenario-catalog.sh"
catalog="$project_root/scenarios/catalog.json"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

expect_rejected() {
  local name="$1" filter="$2"
  jq "$filter" "$catalog" >"$tmp/$name.json"
  if bash "$contract" "$tmp/$name.json" >/dev/null 2>&1; then
    echo "tampered catalog accepted: $name" >&2
    exit 1
  fi
}

expect_rejected missing-row 'del(.scenarios[17])'
expect_rejected duplicate-id '.scenarios[1].scenario_id=.scenarios[0].scenario_id'
expect_rejected duplicate-case '.scenarios[1].design_case=1'
expect_rejected invalid-id '.scenarios[0].scenario_id="Canal_restart"'
expect_rejected invalid-case '.scenarios[0].design_case=19'
expect_rejected invalid-milestone '.scenarios[0].milestone="M7"'
expect_rejected empty-intermediate '.scenarios[0].expected_intermediate_states=[]'
expect_rejected invalid-terminal '.scenarios[0].expected_terminal_state="REBUILDING"'
expect_rejected invalid-timeout-low '.scenarios[0].timeout_seconds=29'
expect_rejected invalid-timeout-high '.scenarios[0].timeout_seconds=1801'
expect_rejected extra-scenario-field '.scenarios[0].unexpected=true'
expect_rejected extra-fault-field '.scenarios[0].fault.unexpected=true'
expect_rejected extra-root-field '.unexpected=true'
expect_rejected weakened-intermediate '.scenarios[2].expected_intermediate_states=["CATCHING_UP"]'
expect_rejected weakened-rebuild '.scenarios[2].requires_rebuild=false'
expect_rejected weakened-recovery '.scenarios[2].recovery_action="skip the missing position"'
expect_rejected merged-crash-states '.scenarios[15].expected_intermediate_states=["REBUILDING"]'

printf 'M6 scenario catalog tamper negatives passed\n'
