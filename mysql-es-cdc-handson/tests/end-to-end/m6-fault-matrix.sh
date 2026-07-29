#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
evidence_root="${M6_EVIDENCE_ROOT:-evidence}"
runtime_root="${M6_RUNTIME_EVIDENCE_ROOT:-$evidence_root/.attempts}"
catalog=scenarios/catalog.json
index="$evidence_root/index.json"

verify_bundles() {
  local scenario bundle result
  while IFS= read -r scenario; do
    bundle="$evidence_root/$scenario"
    test -d "$bundle" && test ! -L "$bundle" || { echo "missing materialized canonical bundle: $scenario" >&2; return 1; }
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
  mkdir -p "$runtime_root"
  M6_EVIDENCE_ROOT="$runtime_root" bash scenarios/scripts/run-scenario.sh "$scenario"
  bash tests/contracts/evidence-contract.sh "$runtime_root/$scenario" >/dev/null
done 3< <(jq -r '.scenarios[].scenario_id' "$catalog")

mkdir -p "$evidence_root"
python3 scenarios/scripts/materialize-m6-evidence.py "$runtime_root" "$evidence_root" "$catalog"
bash scenarios/scripts/validate-m6-index.sh "$index"
verify_bundles
echo 'M6 full fault matrix passed: 18/18/0'
