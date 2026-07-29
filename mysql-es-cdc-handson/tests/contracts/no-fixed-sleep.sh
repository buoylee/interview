#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
scanner="$project_root/tests/contracts/scan-fixed-sleep.py"

if (( $# > 0 )); then
  targets=("$@")
else
  targets=()
  while IFS= read -r path; do targets+=("$path"); done < <(
    find "$project_root/scenarios/scripts/cases" "$project_root/tests/end-to-end" -type f -name '*.sh' 2>/dev/null | \
      awk '/\/cases\/[0-9][0-9]-|\/m6-/' | LC_ALL=C sort
  )
  test ! -f "$project_root/scenarios/scripts/run-scenario.sh" || targets+=("$project_root/scenarios/scripts/run-scenario.sh")
  test ! -f "$project_root/scenarios/scripts/wait-condition.sh" || targets+=("$project_root/scenarios/scripts/wait-condition.sh")
fi

if (( ${#targets[@]} > 0 )); then
  python3 "$scanner" "${targets[@]}"
fi
printf 'M6 fixed-sleep contract passed (%s files)\n' "${#targets[@]}"
