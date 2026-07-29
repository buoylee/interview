#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/../.." && pwd)"
scenario_id="${1:?scenario required}"
phase="${2:?phase required}"
run_dir="${3:?run directory required}"
token="${4:?owner token required}"
test "$(cat "$run_dir/owner-token")" = "$token" || { echo 'case ownership mismatch' >&2; exit 73; }
test "${COMPOSE_PROJECT_NAME:-}" = mysql-es-cdc-handson-m6-task4 || { echo 'dedicated M6 project required' >&2; exit 64; }
cd "$root"
mkdir -p "$run_dir/raw"
export M6_CASE_RUN_DIR="$run_dir" M6_CASE_TOKEN="$token"

m6_execute_case() {
  local declared="$1" requested_phase="$2"
  test "$declared" = "$scenario_id" && test "$requested_phase" = "$phase" || {
    echo 'case identity or phase mismatch' >&2
    return 64
  }
  source scenarios/scripts/m6-case-runtime.sh
  m6_case_dispatch "$declared" "$requested_phase"
}

case_file="$(jq -er --arg id "$scenario_id" '.scenarios[]|select(.scenario_id==$id)|[(.design_case|tostring|if length==1 then "0"+. else . end),.scenario_id]|join("-")+".sh"' scenarios/catalog.json)"
source "scenarios/scripts/cases/$case_file"
case "$phase" in
  mutate) scenario_mutate ;;
  intermediate) scenario_assert_intermediate ;;
  recover) scenario_recover ;;
  *) echo "unknown case phase: $phase" >&2; exit 64 ;;
esac
