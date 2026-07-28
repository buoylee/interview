#!/usr/bin/env bash
set -euo pipefail

[[ "$#" -eq 2 ]] || { echo "expected product and record DLQ evidence" >&2; exit 2; }
jq -s -e 'length==2 and all(.[]; .unresolved==0)' "$1" "$2" >/dev/null
