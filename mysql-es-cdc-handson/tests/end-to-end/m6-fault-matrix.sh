#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
evidence_root="${M6_EVIDENCE_ROOT:-evidence}"
catalog=scenarios/catalog.json
index="$evidence_root/index.json"

verify_bundles() {
  local scenario bundle result
  while IFS= read -r scenario; do
    bundle="$evidence_root/$scenario"
    test -L "$bundle" || { echo "missing canonical bundle: $scenario" >&2; return 1; }
    bash tests/contracts/evidence-contract.sh "$bundle" >/dev/null
    bash tests/contracts/no-evidence-secrets.sh "$bundle"/*.json >/dev/null
    result="$(jq -er .result "$bundle/result.json")"
    test "$result" = PASS || { echo "canonical bundle is not PASS: $scenario" >&2; return 1; }
  done < <(jq -r '.scenarios[].scenario_id' "$catalog")
}

if test "${M6_MATRIX_VERIFY_ONLY:-false}" = true; then
  test -f "$index" || { echo 'missing canonical evidence index' >&2; exit 1; }
  bash scenarios/scripts/validate-m6-index.sh "$index"
  verify_bundles
  exit 0
fi

test "${COMPOSE_PROJECT_NAME:-}" = mysql-es-cdc-handson-m6-task4 || {
  echo 'COMPOSE_PROJECT_NAME must be mysql-es-cdc-handson-m6-task4' >&2
  exit 64
}

while IFS= read -r scenario <&3; do
  bash scenarios/scripts/run-scenario.sh "$scenario"
  bash tests/contracts/evidence-contract.sh "$evidence_root/$scenario" >/dev/null
done 3< <(jq -r '.scenarios[].scenario_id' "$catalog")

mkdir -p "$evidence_root"
tmp="$(mktemp "$evidence_root/.index.XXXXXX")";rows="$(mktemp "$evidence_root/.rows.XXXXXX")"
trap 'rm -f "$tmp" "$rows"' EXIT
while IFS=$'\t' read -r design_case scenario; do
  result="$(jq -er .result "$evidence_root/$scenario/result.json")"
  jq -cn --argjson design_case "$design_case" --arg scenario_id "$scenario" --arg result "$result" \
    '{design_case:$design_case,scenario_id:$scenario_id,result:$result}' >>"$rows"
done < <(jq -r '.scenarios[]|[.design_case,.scenario_id]|@tsv' "$catalog")
jq -s '
  . as $rows |
  {schema_version:1,scenario_count:($rows|length),pass_count:([$rows[]|select(.result=="PASS")]|length),fail_count:([$rows[]|select(.result=="FAIL")]|length),scenarios:$rows}
' "$rows" >"$tmp"
bash scenarios/scripts/validate-m6-index.sh "$tmp"
mv "$tmp" "$index"
trap - EXIT
rm -f "$rows"
verify_bundles
echo 'M6 full fault matrix passed: 18/18/0'
