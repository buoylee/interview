#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
catalog=scenarios/catalog.json
case_dir=scenarios/scripts/cases

expected="$(jq -r '.scenarios[] | [(.design_case|tostring|if length==1 then "0"+. else . end),.scenario_id] | join("-")+".sh"' "$catalog")"
actual="$(find "$case_dir" -maxdepth 1 -type f -name '*.sh' -print 2>/dev/null | sed 's#^.*/##' | sort)"
test "$(wc -l <<<"$expected" | tr -d ' ')" -eq 18
diff -u <(printf '%s\n' "$expected") <(printf '%s\n' "$actual")

while IFS= read -r file; do
  exports="$(bash -c '
    set -euo pipefail
    before="$(declare -F | sed "s/^declare -f //" | sort)"
    source "$1"
    after="$(declare -F | sed "s/^declare -f //" | sort)"
    comm -13 <(printf "%s\\n" "$before") <(printf "%s\\n" "$after")
  ' _ "$case_dir/$file")"
  test "$exports" = $'scenario_assert_intermediate\nscenario_mutate\nscenario_recover' || {
    echo "$file exports an invalid function surface:" >&2
    printf '%s\n' "$exports" >&2
    exit 1
  }
done <<<"$expected"

echo 'M6 executor coverage and three-function export surface pass'
