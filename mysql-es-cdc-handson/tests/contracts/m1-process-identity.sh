#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-m1-log-window.sh

if process_identity_is_unchanged "77|123456" "77|654321"; then
  echo "same PID with different start_ticks must be treated as a changed process" >&2
  exit 1
fi

process_identity_is_unchanged "77|123456" "77|123456"

for malformed_identity in "77|" "|123456" "pid|123456" "77|ticks" "77|123456|"; do
  if process_identity_is_unchanged "$malformed_identity" "$malformed_identity"; then
    echo "malformed process identity must fail closed: $malformed_identity" >&2
    exit 1
  fi
done
