#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
matrix=tests/end-to-end/m6-fault-matrix.sh
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

if M6_MATRIX_VERIFY_ONLY=true M6_EVIDENCE_ROOT="$tmp" bash "$matrix" >"$tmp/missing.out" 2>&1; then
  echo 'matrix accepted missing canonical bundles' >&2
  exit 1
fi
grep -E 'missing|canonical|bundle' "$tmp/missing.out" >/dev/null

echo 'M6 matrix fails closed when canonical bundles are missing'
