#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "$0")/../.." && pwd)"
scanner="$project_root/tests/contracts/no-evidence-secrets.sh"
fixtures="$project_root/tests/fixtures/m6/secrets"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

test -x "$scanner" || { echo 'missing evidence secret scanner' >&2; exit 1; }
for fixture in "$fixtures"/reject-*; do
  diagnostic="$tmp/$(basename "$fixture").txt"
  if bash "$scanner" "$fixture" >"$diagnostic" 2>&1; then
    echo "secret fixture accepted: $(basename "$fixture")" >&2
    exit 1
  fi
  grep -F "$(basename "$fixture")" "$diagnostic" >/dev/null
  test "$(wc -c <"$diagnostic" | tr -d ' ')" -le 512 || { echo 'secret diagnostic is unbounded' >&2; exit 1; }
  if grep -F 'value-do-not-echo' "$diagnostic" >/dev/null; then
    echo 'secret value leaked into diagnostic' >&2
    exit 1
  fi
done
for fixture in "$fixtures"/allow-*; do bash "$scanner" "$fixture" >/dev/null; done

repo="$tmp/repo"
mkdir -p "$repo/evidence/test-scenario"
git -C "$repo" init -q
git -C "$repo" config user.email fixture@example.invalid
git -C "$repo" config user.name fixture
result="$repo/evidence/test-scenario/result.json"

printf '%s\n' '{"status":"clean"}' >"$result"
git -C "$repo" add evidence/test-scenario/result.json
git -C "$repo" commit -qm baseline
M6_SECRET_SCAN_ROOT="$repo" bash "$scanner" >/dev/null

printf '%s\n' '{"password":"value-do-not-echo"}' >"$result"
git -C "$repo" add evidence/test-scenario/result.json
printf '%s\n' '{"status":"sanitized-worktree"}' >"$result"
diagnostic="$tmp/index-sanitized.txt"
if M6_SECRET_SCAN_ROOT="$repo" bash "$scanner" >"$diagnostic" 2>&1; then
  echo 'staged secret hidden by sanitized worktree' >&2
  exit 1
fi
grep -F 'evidence/test-scenario/result.json' "$diagnostic" >/dev/null
grep -F 'source=index' "$diagnostic" >/dev/null
test "$(wc -c <"$diagnostic" | tr -d ' ')" -le 512
! grep -F 'value-do-not-echo' "$diagnostic" >/dev/null

git -C "$repo" reset -q --hard HEAD
new_result="$repo/evidence/test-scenario/staged-new.json"
printf '%s\n' '{"secret":"value-do-not-echo"}' >"$new_result"
git -C "$repo" add evidence/test-scenario/staged-new.json
rm "$new_result"
diagnostic="$tmp/index-missing-worktree.txt"
if M6_SECRET_SCAN_ROOT="$repo" bash "$scanner" >"$diagnostic" 2>&1; then
  echo 'staged-new secret hidden by missing worktree' >&2
  exit 1
fi
grep -F 'evidence/test-scenario/staged-new.json' "$diagnostic" >/dev/null
grep -F 'source=index' "$diagnostic" >/dev/null
! grep -F 'value-do-not-echo' "$diagnostic" >/dev/null

git -C "$repo" reset -q --hard HEAD
printf '%s\n' '{"status":"staged-clean"}' >"$result"
git -C "$repo" add evidence/test-scenario/result.json
printf '%s\n' '{"Authorization":"value-do-not-echo"}' >"$result"
diagnostic="$tmp/worktree-secret.txt"
if M6_SECRET_SCAN_ROOT="$repo" bash "$scanner" >"$diagnostic" 2>&1; then
  echo 'working-tree secret was not rejected' >&2
  exit 1
fi
grep -F 'source=worktree' "$diagnostic" >/dev/null
! grep -F 'value-do-not-echo' "$diagnostic" >/dev/null

git -C "$repo" reset -q --hard HEAD
git -C "$repo" mv evidence/test-scenario/result.json evidence/test-scenario/renamed.json
printf '%s\n' '{"api_key":"value-do-not-echo"}' >"$repo/evidence/test-scenario/renamed.json"
git -C "$repo" add evidence/test-scenario/renamed.json
printf '%s\n' '{"status":"sanitized-rename"}' >"$repo/evidence/test-scenario/renamed.json"
diagnostic="$tmp/index-renamed.txt"
if M6_SECRET_SCAN_ROOT="$repo" bash "$scanner" >"$diagnostic" 2>&1; then
  echo 'staged renamed secret hidden by sanitized worktree' >&2
  exit 1
fi
grep -F 'evidence/test-scenario/renamed.json' "$diagnostic" >/dev/null
grep -F 'source=index' "$diagnostic" >/dev/null

git -C "$repo" reset -q --hard HEAD
git -C "$repo" rm -q evidence/test-scenario/result.json
M6_SECRET_SCAN_ROOT="$repo" bash "$scanner" >/dev/null

printf 'M6 evidence secret tamper negatives passed\n'
