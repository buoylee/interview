#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-m1-evidence-contract.sh
out="${1:-evidence/m1/m1-hard-delete}"

m1_require_evidence_files "$out" \
  input-commands.json index-create.json create-response.json \
  mysql-initial-snapshot.json es-initial-snapshot.json direct-sql.json \
  mysql-absence-snapshot.json es-snapshot.json target-observation.json \
  adapter.log current-run-topology-proof.txt pre-behavior-mapping-proof.json \
  current-run-mapping-proof.json result.json
m1_assert_current_mapping_evidence "$out"
m1_assert_derived_result scenarios/scripts/derive-m1-hard-delete-result.sh "$out"
jq -e '
  (.result == "OBSERVED_DELETE_PROPAGATION" or
   .result == "OBSERVED_DELETE_GAP") and
  .input_commands_match == true and
  .setup_complete == true and
  .direct_sql_fault_injection == true and
  .normal_business_path == false and
  .direct_sql_proven == true and
  .source_rows_absent == true and
  .mapping_continuity_verified == true and
  .bounded_observation_complete == true and
  .timestamps_ordered == true and
  .hard_delete_experiment_valid == true and
  .final_consistency_claim == false
' "$out/result.json" >/dev/null
