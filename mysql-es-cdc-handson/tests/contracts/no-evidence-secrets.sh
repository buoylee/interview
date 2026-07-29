#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
scanner="$project_root/tests/contracts/scan-evidence-secrets.py"

if (( $# > 0 )); then
  targets=("$@")
else
  targets=()
  candidates="$(cd "$project_root" && { git ls-files; git diff --cached --name-only --diff-filter=ACMR; } | LC_ALL=C sort -u)"
  while IFS= read -r path; do
    case "$path" in
      evidence/*|scenarios/*.json|scenarios/scripts/*.sh|scenarios/scripts/*/*.sh|tests/end-to-end/*.sh)
        test -f "$project_root/$path" && targets+=("$project_root/$path")
        ;;
    esac
  done <<<"$candidates"
fi

if (( ${#targets[@]} > 0 )); then
  python3 "$scanner" "${targets[@]}"
fi
printf 'M6 evidence secret contract passed (%s files)\n' "${#targets[@]}"
