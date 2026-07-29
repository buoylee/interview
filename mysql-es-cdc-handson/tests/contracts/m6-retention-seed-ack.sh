#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";contract="${1:-$root/tests/contracts/m6-retention-gap.sh}"

! grep -Eq '"revision":"?0"?' "$contract" || { echo 'retention seed revision must be positive' >&2;exit 1; }
grep -Fq 'seed-ack.json' "$contract" || { echo 'retention seed ACK is not persisted' >&2;exit 1; }
grep -Fq '.topic=="product-search-revisions"' "$contract" || { echo 'retention seed ACK topic is not asserted' >&2;exit 1; }
grep -Fq '.partition==0 and (.offset|type)=="number" and .offset>=0' "$contract" || { echo 'retention seed ACK coordinates are not asserted' >&2;exit 1; }
grep -Fq '.injected_rows==1' "$contract" || { echo 'retention seed injected-row count is not asserted' >&2;exit 1; }

if [ "$#" -eq 0 ]; then
  tampered="$(mktemp)";trap 'rm -f "$tampered"' EXIT
  sed 's/"revision":"1"/"revision":"0"/' "$contract" >"$tampered"
  if bash "$0" "$tampered" >/dev/null 2>&1;then echo 'revision-zero tamper was accepted' >&2;exit 1;fi
fi

printf 'M6 retention positive seed and actual ACK contract passed\n'
