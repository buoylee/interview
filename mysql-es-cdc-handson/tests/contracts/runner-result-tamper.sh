#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";writer="$root/scenarios/scripts/write-result.sh";fixture="$root/tests/fixtures/m6/runner-wrong-terminal.json";tmp="$(mktemp -d)";run=11111111-1111-4111-8111-111111111111;started=2026-07-29T06:00:00Z
trap 'rm -rf "$tmp"' EXIT
jq --arg run "$run" '.observed_pipeline_state="HEALTHY"|.verification.run_id=$run|.watermark_run_id=$run' "$fixture" >"$tmp/good.json"
jq '{cleanup_actions,cleanup_failures:([.cleanup_actions[]|select(.success!=true)]|length)}' "$tmp/good.json" >"$tmp/recovery.json"
bash "$writer" duplicate-event "$run" "$started" "$tmp/good.json" "$tmp/recovery.json" "$tmp/pass.json"
jq -e '.result=="PASS" and (.failed_assertions|length)==0' "$tmp/pass.json" >/dev/null

expect_fail(){ local name="$1" filter="$2" source="${3:-$tmp/good.json}" recovery="${4:-$tmp/recovery.json}";jq "$filter" "$source" >"$tmp/$name.json";set +e;bash "$writer" duplicate-event "$run" "$started" "$tmp/$name.json" "$recovery" "$tmp/$name-result.json" >/dev/null 2>&1;rc=$?;set -e;test "$rc" -ne 0;test ! -f "$tmp/$name-result.json"||jq -e '.result=="FAIL" and (.failed_assertions|length)>0' "$tmp/$name-result.json" >/dev/null; }
expect_fail forged-pass '.result="PASS"'
expect_fail missing-assertion 'del(.scenario_lag_satisfied)'
expect_fail stale-run '.verification.run_id="22222222-2222-4222-8222-222222222222"'
expect_fail stale-watermark-run '.watermark_run_id="22222222-2222-4222-8222-222222222222"'
expect_fail inconclusive '.verification.status="INCONCLUSIVE"|.verification.conclusive=false'
expect_fail nonzero-diff '.exact_diff_count=1'
expect_fail product-dlq '.product_unresolved_dlq_count=1'
expect_fail record-dlq '.record_unresolved_dlq_count=1'
expect_fail tombstone '.tombstone_mismatch_count=1'
jq '.cleanup_actions[0].success=false|.cleanup_failures=1' "$tmp/recovery.json" >"$tmp/bad-cleanup.json"
expect_fail cleanup '.' "$tmp/good.json" "$tmp/bad-cleanup.json"

printf 'M6 non-forgeable result tamper contract passed\n'
