#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
validator=scenarios/scripts/validate-m6-index.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

jq '{schema_version:1,scenario_count:18,pass_count:18,fail_count:0,scenarios:[.scenarios[]|{design_case,scenario_id,result:"PASS"}]}' scenarios/catalog.json >"$tmp/index.json"
bash "$validator" "$tmp/index.json" >/dev/null

expect_rejected() {
  local name="$1" filter="$2"
  jq "$filter" "$tmp/index.json" >"$tmp/$name.json"
  if bash "$validator" "$tmp/$name.json" >"$tmp/$name.out" 2>&1; then
    echo "matrix validator accepted $name tamper" >&2
    exit 1
  fi
}

expect_rejected missing-row '.scenarios |= .[0:17]'
expect_rejected reordered '.scenarios[0:2] |= reverse'
expect_rejected duplicate-id '.scenarios[1].scenario_id=.scenarios[0].scenario_id'
expect_rejected wrong-case '.scenarios[0].design_case=99'
expect_rejected fail-row '.scenarios[7].result="FAIL"|.pass_count=17|.fail_count=1'
expect_rejected wrong-count '.scenario_count=17'
expect_rejected extra-field '.unexpected=true'

echo 'M6 matrix index tamper contract passes'
