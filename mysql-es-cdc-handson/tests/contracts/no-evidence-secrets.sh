#!/usr/bin/env bash
set -euo pipefail

project_root="${M6_SECRET_SCAN_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}"
scanner="$project_root/tests/contracts/scan-evidence-secrets.py"
test -f "$scanner" || scanner="$(cd "$(dirname "$0")" && pwd)/scan-evidence-secrets.py"

in_scope() {
  case "$1" in
    evidence/*|scenarios/*.json|scenarios/scripts/*.sh|scenarios/scripts/*/*.sh|tests/end-to-end/*.sh) return 0 ;;
    *) return 1 ;;
  esac
}

if (( $# > 0 )); then
  targets=("$@")
else
  failed=0
  staged="$(git -C "$project_root" diff --cached --name-only --diff-filter=ACMR | LC_ALL=C sort -u)"
  while IFS= read -r path; do
    test -n "$path" || continue
    in_scope "$path" || continue
    if git -C "$project_root" cat-file -e ":$path" 2>/dev/null; then
      if ! git -C "$project_root" show ":$path" | python3 "$scanner" --stdin "$path" index; then failed=1; fi
    fi
  done <<<"$staged"

  targets=()
  candidates="$(cd "$project_root" && { git ls-files; git diff --cached --name-only --diff-filter=ACMR; } | LC_ALL=C sort -u)"
  while IFS= read -r path; do
    in_scope "$path" || continue
    test -f "$project_root/$path" && targets+=("$project_root/$path")
  done <<<"$candidates"
fi

if (( ${#targets[@]} > 0 )); then
  if ! python3 "$scanner" "${targets[@]}"; then failed=1; fi
fi
printf 'M6 evidence secret contract passed (%s files)\n' "${#targets[@]}"
exit "${failed:-0}"
