#!/usr/bin/env bash
set -euo pipefail

root="$1"
assert_metric() { jq -e --arg name "$2" '.name==$name and .measurements[0].value '$3 "$root/$1" >/dev/null; }
assert_metric metric-pipeline-healthy.json cdc_pipeline_state '==1'
assert_metric metric-consumer-lag.json cdc_consumer_lag '==0'
assert_metric metric-unresolved-dlq.json cdc_unresolved_dlq '==0'
assert_metric metric-last-success.json cdc_reconciliation_last_success_epoch_seconds '>0'
assert_metric metric-runs-pass.json cdc_reconciliation_runs_total '>0'
assert_metric metric-runs-diff.json cdc_reconciliation_runs_total '>0'
assert_metric metric-repair-applied.json cdc_repair_actions_total '>0'
assert_metric m4-consumer-projection-bug/metric-differences-modified.json cdc_reconciliation_differences '>0'
