#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";marker="$root/.m6-manifest-untracked-$$";output="$root/.m6-manifest-output-$$.json"
trap 'rm -f "$marker" "$output"' EXIT
touch "$marker"
bash "$root/scenarios/scripts/capture-manifest.sh" "$output"
jq -e '.git.dirty==true and .git.tracked_dirty==true or .git.dirty==true and .git.untracked_count>=1' "$output" >/dev/null
jq -e '.git.untracked_count>=1 and (.git.excluded_runtime_output|index("'"$(basename "$output")"'"))!=null' "$output" >/dev/null
printf 'M6 manifest dirty-state contract passed\n'
