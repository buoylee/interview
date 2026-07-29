#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
matrix=tests/end-to-end/m6-fault-matrix.sh

# A scenario may read stdin. Read catalog rows on a dedicated descriptor so one
# case cannot consume the remaining matrix rows from the loop's standard input.
grep -Fq 'while IFS= read -r scenario <&3; do' "$matrix"
grep -Fq 'done 3< <(' "$matrix"

echo 'M6 matrix isolates catalog iteration from scenario stdin'
