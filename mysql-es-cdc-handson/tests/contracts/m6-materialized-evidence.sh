#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
runtime="$tmp/runtime"
canonical="$tmp/canonical"
scenario=manual-elasticsearch-drift
run=11111111-1111-4111-8111-111111111111
mkdir -p "$runtime/.runs/$scenario/$run" "$canonical"
cp tests/fixtures/m6/evidence-valid/*.json "$runtime/.runs/$scenario/$run/"
ln -s ".runs/$scenario/$run" "$runtime/$scenario"
jq -n --arg scenario "$scenario" '{scenarios:[{design_case:12,scenario_id:$scenario}]}' >"$tmp/catalog.json"

python3 scenarios/scripts/materialize-m6-evidence.py \
  "$runtime" "$canonical" "$tmp/catalog.json"

test -d "$canonical/$scenario"
test ! -L "$canonical/$scenario"
test ! -e "$canonical/.runs"
actual="$(find "$canonical/$scenario" -maxdepth 1 -type f -name '*.json' -exec basename {} \; | LC_ALL=C sort)"
expected="$(printf '%s\n' differences.json es-snapshot.json fault.json input-commands.json kafka-offsets.json manifest.json mysql-snapshot.json recovery-actions.json result.json | LC_ALL=C sort)"
test "$actual" = "$expected"
jq -e '.scenario_count==1 and .pass_count==1 and .fail_count==0 and .scenarios==[{"design_case":12,"scenario_id":"manual-elasticsearch-drift","result":"PASS"}]' "$canonical/index.json" >/dev/null

echo 'M6 materialized evidence contract passed'
