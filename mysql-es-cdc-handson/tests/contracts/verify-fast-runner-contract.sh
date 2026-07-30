#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

runner=tests/run-verify-fast-contracts.sh
test -x "$runner" || {
  echo "verify-fast contract runner is missing or not executable" >&2
  exit 1
}

fixture=$(mktemp -d "${TMPDIR:-/tmp}/verify-fast-runner.XXXXXX")
trap 'rm -rf "$fixture"' EXIT
mkdir -p "$fixture/contracts"

write_contract() {
  local name=$1
  local marker=$2
  local exit_code=$3
  printf '#!/usr/bin/env bash\nprintf "%%s\\n" "%s" >>"$VERIFY_FAST_TEST_MARKERS"\nexit %s\n' \
    "$marker" "$exit_code" >"$fixture/contracts/$name"
  chmod +x "$fixture/contracts/$name"
}

write_contract 01-pass.sh first 0
write_contract 02-fail.sh failed 23
write_contract 03-after.sh after 0

printf '%s\n' 01-pass.sh 02-fail.sh 03-after.sh >"$fixture/manifest.txt"
: >"$fixture/exclusions.txt"
: >"$fixture/markers"

if VERIFY_FAST_CONTRACT_DIR="$fixture/contracts" \
    VERIFY_FAST_CONTRACT_MANIFEST="$fixture/manifest.txt" \
    VERIFY_FAST_CONTRACT_EXCLUSIONS="$fixture/exclusions.txt" \
    VERIFY_FAST_TEST_MARKERS="$fixture/markers" \
    bash "$runner" >"$fixture/fail-fast.out" 2>&1; then
  echo "verify-fast runner swallowed a selected contract failure" >&2
  exit 1
fi
test "$(printf '%s\n' first failed)" = "$(cat "$fixture/markers")"
! grep -Fxq after "$fixture/markers"

printf '%s\n' 01-pass.sh >"$fixture/manifest.txt"
printf '%s\n' '02-fail.sh|parameterized helper' >"$fixture/exclusions.txt"
: >"$fixture/markers"
if VERIFY_FAST_CONTRACT_DIR="$fixture/contracts" \
    VERIFY_FAST_CONTRACT_MANIFEST="$fixture/manifest.txt" \
    VERIFY_FAST_CONTRACT_EXCLUSIONS="$fixture/exclusions.txt" \
    VERIFY_FAST_TEST_MARKERS="$fixture/markers" \
    bash "$runner" >"$fixture/coverage.out" 2>&1; then
  echo "verify-fast runner accepted an unclassified contract" >&2
  exit 1
fi
grep -Fq 'Unclassified contract: 03-after.sh' "$fixture/coverage.out"
test ! -s "$fixture/markers"

printf '%s\n' 01-pass.sh 03-after.sh >"$fixture/manifest.txt"
: >"$fixture/markers"
VERIFY_FAST_CONTRACT_DIR="$fixture/contracts" \
  VERIFY_FAST_CONTRACT_MANIFEST="$fixture/manifest.txt" \
  VERIFY_FAST_CONTRACT_EXCLUSIONS="$fixture/exclusions.txt" \
  VERIFY_FAST_TEST_MARKERS="$fixture/markers" \
  bash "$runner" >"$fixture/success.out" 2>&1
test "$(printf '%s\n' first after)" = "$(cat "$fixture/markers")"

echo "verify-fast runner fail-fast and coverage contract passed"
