#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";marker="$root/.m6-manifest-untracked-$$";output="$root/.m6-manifest-output-$$.json"
trap 'rm -f "$marker" "$output"' EXIT
touch "$marker"
bash "$root/scenarios/scripts/capture-manifest.sh" "$output"
jq -e '.git.dirty==true and .git.tracked_dirty==true or .git.dirty==true and .git.untracked_count>=1' "$output" >/dev/null
relative_output="$(git -C "$root" rev-parse --show-prefix)$(basename "$output")"
jq -e --arg path "$relative_output" '.git.untracked_count>=1 and .git.excluded_runtime_output==[$path]' "$output" >/dev/null
printf 'M6 manifest dirty-state contract passed\n'
