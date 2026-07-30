#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

contract_dir=${VERIFY_FAST_CONTRACT_DIR:-tests/contracts}
manifest=${VERIFY_FAST_CONTRACT_MANIFEST:-tests/contracts/verify-fast-self-contained.txt}
exclusions=${VERIFY_FAST_CONTRACT_EXCLUSIONS:-tests/contracts/verify-fast-excluded.txt}

test -d "$contract_dir"
test -f "$manifest"
test -f "$exclusions"

state=$(mktemp -d "${TMPDIR:-/tmp}/verify-fast-contracts.XXXXXX")
trap 'rm -rf "$state"' EXIT

awk 'NF && $1 !~ /^#/ { print $1 }' "$manifest" >"$state/selected"
awk -F'|' '
  /^[[:space:]]*($|#)/ { next }
  NF != 2 || $1 == "" || $2 == "" {
    print "Invalid verify-fast exclusion: " $0 > "/dev/stderr"
    bad = 1
    next
  }
  { print $1 }
  END { exit bad }
' "$exclusions" >"$state/excluded"

find "$contract_dir" -maxdepth 1 -type f -name '*.sh' -exec basename {} \; |
  sort >"$state/actual"
sort "$state/selected" >"$state/selected.sorted"
sort "$state/excluded" >"$state/excluded.sorted"
cat "$state/selected.sorted" "$state/excluded.sorted" | sort >"$state/classified"

if test -s <(uniq -d "$state/classified"); then
  echo "Duplicate or overlapping verify-fast classification:" >&2
  uniq -d "$state/classified" >&2
  exit 1
fi

if ! diff -u "$state/actual" "$state/classified" >"$state/coverage.diff"; then
  while IFS= read -r contract; do
    grep -Fxq "$contract" "$state/classified" ||
      echo "Unclassified contract: $contract" >&2
  done <"$state/actual"
  while IFS= read -r contract; do
    grep -Fxq "$contract" "$state/actual" ||
      echo "Classified contract does not exist: $contract" >&2
  done <"$state/classified"
  exit 1
fi

while IFS= read -r contract; do
  test -n "$contract" || continue
  case "$contract" in
    \#*) continue ;;
  esac
  echo "verify-fast contract: $contract"
  if ! bash "$contract_dir/$contract"; then
    echo "verify-fast contract failed: $contract" >&2
    exit 1
  fi
done <"$manifest"
