#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-m1-evidence-contract.sh
out="${1:-evidence/m1/m1-bulk-partial}"

m1_require_evidence_files "$out" \
  input-commands.json partial-index-create.json partial-mapping-proof.json \
  adapter-partial-run.json transaction-1401-1402.json source-1401-1402.json \
  adapter-partial-error.log adapter-after-partial-error.json \
  1401-before-fix.json 1402-before-fix.json partial-observation.json \
  transaction-1403.json source-1403.json 1403-before-fix.json \
  later-observation.json mapping-repair.json normal-mapping-proof.json \
  adapter-before-repair-start.json adapter-after-repair-start.json \
  adapter-repair-run.log 1402-after-restart.json retry-observation.json \
  etl-endpoint-proof.json etl-action.json 1402-final.json result.json

m1_assert_derived_result scenarios/scripts/derive-m1-bulk-partial-result.sh "$out"
jq -e '
  .scenario_id == "m1-bulk-partial" and
  .input_commands_match == true and
  .partial_mapping_proven == true and
  .same_source_transaction_proven == true and
  .source_snapshots_proven == true and
  (.current_run_error_proven | type) == "boolean" and
  (.bulk_partial_failure_observed | type) == "boolean" and
  (.valid_item_applied | type) == "boolean" and
  (.invalid_item_applied_before_mapping_fix | type) == "boolean" and
  (.invalid_source_value_preserved_before_fix | type) == "boolean" and
  (.later_batch_applied_before_mapping_fix | type) == "boolean" and
  .mapping_repair_proven == true and
  .same_container_restart_verified == true and
  .official_etl_endpoint_proven == true and
  (.invalid_item_retried_after_mapping_fix | type) == "boolean" and
  (.etl_required | type) == "boolean" and
  (.etl_invoked | type) == "boolean" and
  (.etl_repair_succeeded | type) == "boolean" and
  (.etl_required == (.invalid_item_retried_after_mapping_fix | not)) and
  (if .etl_required then
    .etl_invoked and .etl_repair_succeeded
   else
    (.etl_invoked | not) and .invalid_item_retried_after_mapping_fix and
    (.etl_repair_succeeded | not)
   end) and
  .partial_failure_experiment_valid == true and
  .final_consistency_claim == false
' "$out/result.json" >/dev/null
