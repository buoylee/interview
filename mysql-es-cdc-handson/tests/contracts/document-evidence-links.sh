#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
catalog="$project_root/scenarios/catalog.json"
index="$project_root/evidence/index.json"
readme="$project_root/README.md"

test -f "$catalog" || { echo "missing scenario catalog: $catalog" >&2; exit 1; }
test -f "$index" || { echo "missing evidence index: $index" >&2; exit 1; }
test -f "$readme" || { echo "missing README: $readme" >&2; exit 1; }

catalog_ids=()
while IFS= read -r scenario_id; do
  catalog_ids+=("$scenario_id")
done < <(jq -r '.scenarios[].scenario_id' "$catalog")
test "${#catalog_ids[@]}" -eq 18 || { echo "catalog must contain exactly 18 scenarios" >&2; exit 1; }

tokens=()
while IFS= read -r token; do
  tokens+=("$token")
done < <(rg -o --no-filename 'evidence:[a-z0-9-]+' "$project_root/README.md" "$project_root/docs" | sort -u || true)
test "${#tokens[@]}" -gt 0 || { echo "no evidence tokens found in README/docs" >&2; exit 1; }

for token in "${tokens[@]}"; do
  scenario_id="${token#evidence:}"
  jq -e --arg id "$scenario_id" '.scenarios[] | select(.scenario_id == $id)' "$catalog" >/dev/null || {
    echo "unknown evidence token: $token" >&2
    exit 1
  }
  jq -e --arg id "$scenario_id" '.scenarios[] | select(.scenario_id == $id and .result == "PASS")' "$index" >/dev/null || {
    echo "evidence token does not have a PASS index result: $token" >&2
    exit 1
  }
  git -C "$project_root" ls-files --error-unmatch -- "evidence/$scenario_id/result.json" >/dev/null || {
    echo "evidence token lacks a tracked PASS bundle: $token" >&2
    exit 1
  }
  test "$(jq -r '.result' "$project_root/evidence/$scenario_id/result.json")" = "PASS" || {
    echo "evidence token bundle is not PASS: $token" >&2
    exit 1
  }
done

matrix="$(awk '
  /^## 责任矩阵（18 个故障场景）$/ { inside=1; next }
  /^## / && inside { exit }
  inside { print }
' "$readme")"
test -n "$matrix" || { echo "README responsibility matrix section is missing" >&2; exit 1; }

matrix_ids=()
while IFS= read -r scenario_id; do
  matrix_ids+=("$scenario_id")
done < <(printf '%s\n' "$matrix" | rg -o --no-filename 'evidence:[a-z0-9-]+' | sed 's/^evidence://' | sort -u || true)
test "${#matrix_ids[@]}" -eq 18 || {
  echo "README responsibility matrix must link exactly 18 scenario IDs; found ${#matrix_ids[@]}" >&2
  exit 1
}

expected_ids="$(printf '%s\n' "${catalog_ids[@]}" | sort)"
actual_ids="$(printf '%s\n' "${matrix_ids[@]}" | sort)"
test "$actual_ids" = "$expected_ids" || {
  echo "README responsibility matrix scenario IDs differ from catalog" >&2
  comm -3 <(printf '%s\n' "$expected_ids") <(printf '%s\n' "$actual_ids") >&2
  exit 1
}

printf 'Document evidence links passed: %s catalog scenarios, %s matrix scenarios\n' "${#catalog_ids[@]}" "${#matrix_ids[@]}"
