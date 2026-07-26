#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
out="${1:-evidence/m1/m1-restart}"

jq -L scenarios/scripts -n '
  include "lib-m1-derived-proof";

  ($input[0]) as $commands |
  ($commands.source_product) as $product |
  ({
    product_id:$product.id,sku:$product.sku,name:$product.name,
    description:$product.description,category_id:$product.category_id,
    status:$product.status
  }) as $expected_product |
  ($commands == {
    scenario_id:"m1-restart",
    product_id:1201,
    fault:"stop only canal-adapter while source revisions advance",
    recovery:"start the same container without deleting its state",
    source_product:{
      id:1201,sku:"M1-1201",name:"Restart Keyboard",
      description:"restart observation",category_id:10,
      price_cents:100,status:"ACTIVE"
    },
    mutations:[
      {operation:"change_price",price_cents:200,expected_revision:2},
      {operation:"replace_inventory",available_quantity:7,reserved_quantity:2,expected_revision:3}
    ],
    target_deadline_seconds:60,
    expected_observation:"document reaches the latest source value or evidence records the gap",
    final_consistency_claim:false
  }) as $input_match |
  ($initial_source[0]) as $initial |
  ($down_source[0]) as $down |
  ($final_source[0]) as $source |
  ($initial.product == ($expected_product + {
      price_cents:100,updated_at:$initial.product.updated_at
    }) and
    ($initial.product.updated_at | m1_source_timestamp) and
    $initial.revision == {product_id:1201,revision:1,active:true} and
    $initial.inventory == {
      product_id:1201,available_quantity:0,reserved_quantity:0
    } and
    $down.product == ($expected_product + {
      price_cents:200,updated_at:$down.product.updated_at
    }) and
    ($down.product.updated_at | m1_source_timestamp) and
    $down.revision == {product_id:1201,revision:3,active:true} and
    $down.inventory == {
      product_id:1201,available_quantity:7,reserved_quantity:2
    } and
    $source == $down) as $source_proof_complete |
  ($index[0] == {
      acknowledged:true,shards_acknowledged:true,index:"products_adapter_v1"
    } and
    $create[0] == {productId:1201,revision:1} and
    m1_managed_target($initial_target[0];$expected_product;100)) as $setup_complete |
  ($price[0] == {productId:1201,revision:2} and
    $inventory[0] == {productId:1201,revision:3}) as $mutations_complete |
  ($before[0]) as $before_state |
  ($stopped[0]) as $stopped_state |
  ($after[0]) as $after_state |
  (($before_state.container_id | m1_sha256) and
    ($before_state.java_identity | m1_identity) and
    $stopped_state.container_id == $before_state.container_id and
    $stopped_state.stopped_java_identity == $before_state.java_identity and
    $stopped_state.java_process_absent == true and
    $after_state.container_id == $before_state.container_id and
    ($after_state.java_identity | m1_identity) and
    $after_state.java_identity != $before_state.java_identity) as $same_container_restart |
  (m1_mapping_continuity(
    $pre_proof[0];$mapping_proof[0];
    $after_state.container_id;$after_state.java_identity
  )) as $mapping_continuity_verified |
  (m1_managed_target($down_target[0];$expected_product;100)) as $target_stale_while_down |
  ($observation[0].deadline_seconds == 60 and
    $observation[0].observation_completed == true and
    ($observation[0].deadline_reached | type) == "boolean" and
    ($observation[0].completed_at | type) == "string") as $bounded_observation_complete |
  ($timestamps[0]) as $time |
  (($time | keys | sort) == [
      "completed_at","restarted_at","source_mutated_at","started_at","stopped_at"
    ] and
    ($time.started_at | type) == "string" and
    ($time.stopped_at | type) == "string" and
    ($time.source_mutated_at | type) == "string" and
    ($time.restarted_at | type) == "string" and
    ($time.completed_at | type) == "string" and
    $time.started_at <= $before_state.captured_at and
    $before_state.captured_at <= $time.stopped_at and
    $stopped_state.captured_at == $time.stopped_at and
    $time.stopped_at <= $time.source_mutated_at and
    $time.source_mutated_at <= $time.restarted_at and
    $after_state.captured_at == $time.restarted_at and
    $time.restarted_at <= $time.completed_at and
    $observation[0].completed_at == $time.completed_at) as $timestamps_ordered |
  (m1_managed_target($target[0];$expected_product;200)) as $latest_target_observed |
  (m1_managed_target($target[0];$expected_product;100)) as $stale_target_observed |
  ($input_match and $setup_complete and $mutations_complete and
    $source_proof_complete and $same_container_restart and
    $mapping_continuity_verified and $target_stale_while_down and
    $bounded_observation_complete and $timestamps_ordered) as $restart_experiment_valid |
  ($restart_experiment_valid and $latest_target_observed) as $recovered |
  ($restart_experiment_valid and $stale_target_observed and
    $observation[0].deadline_reached == true) as $bounded_gap |
  {
    scenario_id:"m1-restart",
    result:(if $recovered then "OBSERVED_RESTART_RECOVERY"
      elif $bounded_gap then "OBSERVED_RESTART_GAP"
      else "OBSERVED_ASSERTION_MISMATCH" end),
    input_commands_match:$input_match,
    setup_complete:$setup_complete,
    source_proof_complete:$source_proof_complete,
    mutations_complete:$mutations_complete,
    same_container_restart_verified:$same_container_restart,
    target_stale_while_down:$target_stale_while_down,
    mapping_continuity_verified:$mapping_continuity_verified,
    bounded_observation_complete:$bounded_observation_complete,
    timestamps_ordered:$timestamps_ordered,
    target_deadline_reached:$observation[0].deadline_reached,
    latest_target_observed:$latest_target_observed,
    restart_experiment_valid:$restart_experiment_valid,
    captured_values:{
      container_id:$before_state.container_id,
      java_identity_before:$before_state.java_identity,
      java_identity_after:$after_state.java_identity,
      source_price_cents:$source.product.price_cents,
      source_revision:$source.revision.revision,
      target_price_cents:$target[0]._source.price_cents
    },
    evidence_files:{
      source:"mysql-snapshot.json",target:"es-snapshot.json",
      adapter_log:"adapter.log",mapping_proof:"current-run-mapping-proof.json",
      timestamps:"timestamps.json"
    },
    final_consistency_claim:false
  }
' \
  --slurpfile input "$out/input-commands.json" \
  --slurpfile index "$out/index-create.json" \
  --slurpfile create "$out/create-response.json" \
  --slurpfile initial_source "$out/mysql-initial-snapshot.json" \
  --slurpfile initial_target "$out/es-initial-snapshot.json" \
  --slurpfile before "$out/adapter-before-stop.json" \
  --slurpfile stopped "$out/adapter-stopped.json" \
  --slurpfile price "$out/price-response.json" \
  --slurpfile inventory "$out/inventory-response.json" \
  --slurpfile down_source "$out/mysql-while-down-snapshot.json" \
  --slurpfile down_target "$out/es-while-down-snapshot.json" \
  --slurpfile after "$out/adapter-after-start.json" \
  --slurpfile final_source "$out/mysql-snapshot.json" \
  --slurpfile target "$out/es-snapshot.json" \
  --slurpfile observation "$out/target-observation.json" \
  --slurpfile timestamps "$out/timestamps.json" \
  --slurpfile pre_proof "$out/pre-behavior-mapping-proof.json" \
  --slurpfile mapping_proof "$out/current-run-mapping-proof.json"
