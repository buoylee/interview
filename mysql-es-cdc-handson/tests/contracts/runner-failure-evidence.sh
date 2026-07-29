#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";runner="$root/scenarios/scripts/run-scenario.sh";tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
evidence="$tmp/evidence";fixture="$root/tests/fixtures/m6/runner-wrong-terminal.json";mkdir -p "$evidence"

set +e
M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" bash "$runner" duplicate-event >"$tmp/run.out" 2>"$tmp/run.err"
rc=$?
set -e
test "$rc" -ne 0
bundle="$evidence/duplicate-event";test -d "$bundle"
expected='differences.json es-snapshot.json fault.json input-commands.json kafka-offsets.json manifest.json mysql-snapshot.json recovery-actions.json result.json'
test "$(find -H "$bundle" -maxdepth 1 -type f -exec basename {} \;|LC_ALL=C sort|tr '\n' ' '|sed 's/ $//')" = "$expected"
jq -e '.result=="FAIL" and (.failed_assertions|index("terminal_pipeline_state"))!=null and .observed_pipeline_state=="DEGRADED" and (.cleanup_actions|length)==1 and .cleanup_failures==0 and (.started_at|type)=="string" and (.finished_at|type)=="string"' "$bundle/result.json" >/dev/null
bash "$root/tests/contracts/evidence-contract.sh" "$bundle" >/dev/null
bash "$root/tests/contracts/no-evidence-secrets.sh" "$bundle"/*.json >/dev/null

set +e
M6_EVIDENCE_ROOT="$evidence" M6_RUNNER_FIXTURE="$fixture" bash "$runner" not-in-catalog >/dev/null 2>&1
bad_rc=$?
set -e
test "$bad_rc" -eq 64;test ! -e "$evidence/not-in-catalog"

printf 'M6 transactional runner failure evidence contract passed\n'
