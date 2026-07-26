#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-m1-evidence-contract.sh
out="${1:-evidence/m1/m1-restart}"

m1_require_evidence_files "$out" \
  input-commands.json index-create.json create-response.json \
  mysql-initial-snapshot.json es-initial-snapshot.json \
  adapter-before-stop.json adapter-stopped.json price-response.json \
  inventory-response.json mysql-while-down-snapshot.json \
  es-while-down-snapshot.json adapter-after-start.json \
  mysql-snapshot.json es-snapshot.json target-observation.json timestamps.json \
  adapter.log current-run-topology-proof.txt pre-behavior-mapping-proof.json \
  current-run-mapping-proof.json result.json
m1_assert_current_mapping_evidence "$out"
m1_assert_derived_result scenarios/scripts/derive-m1-restart-result.sh "$out"
jq -e '
  (.result == "OBSERVED_RESTART_RECOVERY" or
   .result == "OBSERVED_RESTART_GAP") and
  .input_commands_match == true and
  .setup_complete == true and
  .source_proof_complete == true and
  .mutations_complete == true and
  .same_container_restart_verified == true and
  .target_stale_while_down == true and
  .mapping_continuity_verified == true and
  .bounded_observation_complete == true and
  .timestamps_ordered == true and
  .restart_experiment_valid == true and
  .final_consistency_claim == false
' "$out/result.json" >/dev/null
