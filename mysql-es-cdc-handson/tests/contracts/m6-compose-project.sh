#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib/m6-compose-project.sh

test "$(m6_compose_project mysql-es-cdc-handson-m6-task4)" = mysql-es-cdc-handson-m6-task4
test "$(m6_compose_project mysql-es-cdc-handson-m6-task6)" = mysql-es-cdc-handson-m6-task6

for rejected in '' mysql-es-cdc-handson shared mysql-es-cdc-handson-m6-task6-extra mysql-es-cdc-handson-m6-task7; do
  if m6_compose_project "$rejected" >/dev/null 2>&1; then
    echo "accepted non-locked M6 Compose project: $rejected" >&2
    exit 1
  fi
done

test "$(m6_compose_marker_name mysql-es-cdc-handson-m6-task4)" = .m6-task4-project.json
test "$(m6_compose_marker_name mysql-es-cdc-handson-m6-task6)" = .m6-task6-project.json
grep -Fq 'M6_RUNNER_EXECUTION_MODE=real M6_EVIDENCE_ROOT="$runtime_root" bash scenarios/scripts/run-scenario.sh "$scenario"' \
  tests/end-to-end/m6-fault-matrix.sh

printf 'M6 locked Compose project contract passed\n'
