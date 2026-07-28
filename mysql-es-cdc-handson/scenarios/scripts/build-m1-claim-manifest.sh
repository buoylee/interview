#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
evidence_root="${1:-evidence/m1}"

jq -S -c -n \
  --slurpfile basic "$evidence_root/m1-basic/result.json" \
  --slurpfile restart "$evidence_root/m1-restart/result.json" \
  --slurpfile hard_delete "$evidence_root/m1-hard-delete/result.json" \
  --slurpfile partial "$evidence_root/m1-bulk-partial/result.json" '
  {
    schema:"m1-stable-claim-manifest-v1",
    basic:($basic[0] | {
      scenario_id,result,input_commands_match,mapping_continuity_verified,
      insert_observed,update_observed,non_computed_fields_match,
      forbidden_fields_absent,allowed_field_set_exact,
      source_updated_at_non_null,target_updated_at_is_null,
      updated_at_matches_source,final_consistency_claim
    }),
    restart:($restart[0] | {
      scenario_id,result,input_commands_match,setup_complete,
      source_proof_complete,mutations_complete,
      same_container_restart_verified,target_stale_while_down,
      mapping_continuity_verified,bounded_observation_complete,
      timestamps_ordered,target_deadline_reached,latest_target_observed,
      restart_experiment_valid,
      source_price_cents:.captured_values.source_price_cents,
      source_revision:.captured_values.source_revision,
      target_price_cents:.captured_values.target_price_cents,
      final_consistency_claim
    }),
    hard_delete:($hard_delete[0] | {
      scenario_id,result,input_commands_match,setup_complete,
      direct_sql_fault_injection,normal_business_path,direct_sql_proven,
      source_rows_absent,mapping_continuity_verified,
      bounded_observation_complete,timestamps_ordered,
      target_deadline_reached,delete_observed,document_still_present,
      hard_delete_experiment_valid,final_consistency_claim
    }),
    bulk_partial:($partial[0] | {
      scenario_id,input_commands_match,partial_mapping_proven,
      same_source_transaction_proven,source_snapshots_proven,
      current_run_error_proven,bulk_partial_failure_observed,
      valid_item_applied,invalid_item_applied_before_mapping_fix,
      invalid_source_value_preserved_before_fix,
      later_batch_applied_before_mapping_fix,mapping_repair_proven,
      same_container_restart_verified,official_etl_endpoint_proven,
      invalid_item_retried_after_mapping_fix,etl_required,etl_invoked,
      etl_repair_succeeded,partial_failure_experiment_valid,
      invalid_source_price_cents:.captured_values.invalid_source_price_cents,
      invalid_target_price_before_fix:.captured_values.invalid_target_price_before_fix,
      final_consistency_claim
    })
  }
'
