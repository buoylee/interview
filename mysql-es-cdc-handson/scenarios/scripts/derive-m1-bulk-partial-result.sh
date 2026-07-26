#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
out="${1:-evidence/m1/m1-bulk-partial}"

jq -e -L scenarios/scripts -n '
  include "lib-m1-derived-proof";

  def sha256: type == "string" and test("^[0-9a-f]{64}$");
  def identity: type == "string" and test("^[0-9]+[|][0-9]+$");
  def millis: m1_rfc3339_millis_epoch;
  def get_valid($capture; $id; $price):
    ($capture | keys | sort) == ["body","http_status","requested_url","transport_ok"] and
    $capture.requested_url == ("http://127.0.0.1:9200/products_adapter_v1/_doc/" + ($id|tostring)) and
    $capture.transport_ok == true and
    if $capture.http_status == 200 then
      $capture.body.found == true and
      $capture.body._index == "products_adapter_v1" and
      $capture.body._id == ($id|tostring) and
      $capture.body._source.product_id == $id and
      $capture.body._source.price_cents == $price
    elif $capture.http_status == 404 then
      $capture.body == {
        _index:"products_adapter_v1",_id:($id|tostring),found:false
      }
    else false end;
  def get_valid_any_price($capture; $id):
    ($capture | keys | sort) == ["body","http_status","requested_url","transport_ok"] and
    $capture.requested_url == ("http://127.0.0.1:9200/products_adapter_v1/_doc/" + ($id|tostring)) and
    $capture.transport_ok == true and
    if $capture.http_status == 200 then
      $capture.body.found == true and
      $capture.body._index == "products_adapter_v1" and
      $capture.body._id == ($id|tostring) and
      $capture.body._source.product_id == $id and
      ($capture.body._source.price_cents | type) == "number"
    elif $capture.http_status == 404 then
      $capture.body == {
        _index:"products_adapter_v1",_id:($id|tostring),found:false
      }
    else false end;
  def found($capture): $capture.http_status == 200 and $capture.body.found == true;

  $input[0] as $commands |
  $partial_mapping[0] as $partial_mapping_capture |
  $partial_run[0] as $partial_java |
  $first_tx[0] as $first_transaction |
  $first_source[0] as $first_source_snapshot |
  $after_error[0] as $after_error_state |
  $get1401[0] as $before_1401 |
  $get1402[0] as $before_1402 |
  $partial_observation[0] as $partial_window |
  $later_tx[0] as $later_transaction |
  $later_source[0] as $later_source_snapshot |
  $get1403[0] as $before_1403 |
  $later_observation[0] as $later_window |
  $repair[0] as $mapping_repair |
  $normal_mapping[0] as $normal_mapping_capture |
  $before_repair[0] as $before_repair_state |
  $after_repair[0] as $after_repair_state |
  $get_after_restart[0] as $after_restart_1402 |
  $retry_observation[0] as $retry_window |
  $etl_proof[0] as $etl_endpoint_proof |
  $etl[0] as $etl_action |
  $get_final[0] as $final_1402 |

  ($commands == {
    scenario_id:"m1-bulk-partial",
    target_mapping:"price_cents is byte",
    same_source_transaction:[
      {product_id:1401,price_cents:100,expected_mapping:"valid"},
      {product_id:1402,price_cents:1000,expected_mapping:"invalid"}
    ],
    later_source_transaction:{
      product_id:1403,price_cents:101,
      purpose:"prove whether Adapter advances beyond the failed batch"
    },
    partial_observation_deadline_seconds:30,
    later_observation_deadline_seconds:30,
    retry_observation_deadline_seconds:30,
    question:"Does Adapter advance, retry, partially apply, or require ETL after one item fails?",
    final_consistency_claim:false
  }) as $input_match |
  ($partial_index[0] == {
    acknowledged:true,shards_acknowledged:true,index:"products_adapter_v1"
  } and
    $partial_mapping_capture.transport_ok == true and
    $partial_mapping_capture.http_status == 200 and
    $partial_mapping_capture.body.products_adapter_v1.mappings.dynamic == "strict" and
    $partial_mapping_capture.body.products_adapter_v1.mappings.properties.price_cents.type == "byte") as $partial_mapping_proven |
  (($partial_java.container_id | sha256) and
    ($partial_java.java_identity | identity) and
    ($partial_java.java_cutoff_utc | type == "string" and
      test("^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}$")) and
    ($partial_java.container_mapping_sha256 | sha256)) as $partial_process_proven |
  ($first_transaction.same_mysql_session == true and
    $first_transaction.committed == true and
    ($first_transaction.mysql_connection_id | type) == "number" and
    ($first_transaction.mysql_connection_id | floor) == $first_transaction.mysql_connection_id and
    ($first_transaction.transaction | startswith("START TRANSACTION;")) and
    ($first_transaction.transaction | endswith("COMMIT;")) and
    ($first_transaction.transaction | contains("(1401,")) and
    ($first_transaction.transaction | contains("M1-1401")) and
    ($first_transaction.transaction | contains(", 100,")) and
    ($first_transaction.transaction | contains("(1402,")) and
    ($first_transaction.transaction | contains("M1-1402")) and
    ($first_transaction.transaction | contains(", 1000,")) and
    ($first_transaction.transaction | contains("VALUES (1401, 0, 0), (1402, 0, 0)")) and
    ($first_transaction.transaction | contains("VALUES (1401, 1, 1), (1402, 1, 1)")) and
    ($first_transaction.started_at | millis) != null and
    ($first_transaction.committed_at | millis) != null and
    ($first_transaction.started_at | millis) < ($first_transaction.committed_at | millis)) as $same_transaction_proven |
  ($first_source_snapshot.products == [
    {product_id:1401,price_cents:100,revision:1,available_quantity:0,reserved_quantity:0},
    {product_id:1402,price_cents:1000,revision:1,available_quantity:0,reserved_quantity:0}
  ] and
    ($first_source_snapshot.captured_at | millis) != null and
    ($first_transaction.committed_at | millis) < ($first_source_snapshot.captured_at | millis)) as $first_source_proven |
  ($after_error_state.container_id == $partial_java.container_id and
    $after_error_state.java_identity == $partial_java.java_identity and
    $after_error_state.container_running == true and
    ($after_error_state.captured_at | millis) != null) as $failure_process_current |
  (($partial_log | split("\n") | map(select(length > 0))) as $lines |
    any($lines[];
      (.[0:23] >= $partial_java.java_cutoff_utc) and
      contains("ERROR") and contains("mapper_parsing_exception") and
      contains("1000") and contains("byte"))) as $current_run_error_proven |
  (($partial_log | split("\n") | map(select(length > 0))) as $lines |
    if $current_run_error_proven then true else
      any($lines[];
        (.[0:23] >= $partial_java.java_cutoff_utc) and
        contains("DML") and contains("\"id\":1402") and
        contains("\"price_cents\":1000"))
    end) as $current_run_log_proven |
  (get_valid($before_1401;1401;100) and get_valid_any_price($before_1402;1402) and
    $partial_window == {
      deadline_seconds:30,deadline_reached:$partial_window.deadline_reached,
      error_observed:$partial_window.error_observed,
      completed_at:$partial_window.completed_at
    } and
    ($partial_window.deadline_reached | type) == "boolean" and
    ($partial_window.error_observed | type) == "boolean" and
    $partial_window.error_observed == $current_run_error_proven and
    (if $current_run_error_proven then
      $partial_window.deadline_reached == false
     else $partial_window.deadline_reached == true end) and
    ($partial_window.completed_at | millis) != null) as $partial_observation_valid |
  ($later_transaction.separate_mysql_session == true and
    $later_transaction.committed == true and
    ($later_transaction.mysql_connection_id | type) == "number" and
    $later_transaction.mysql_connection_id != $first_transaction.mysql_connection_id and
    ($later_transaction.transaction | startswith("START TRANSACTION;")) and
    ($later_transaction.transaction | endswith("COMMIT;")) and
    ($later_transaction.transaction | contains("(1403,")) and
    ($later_transaction.transaction | contains("M1-1403")) and
    ($later_transaction.transaction | contains(", 101,")) and
    ($later_transaction.started_at | millis) != null and
    ($later_transaction.committed_at | millis) != null and
    ($later_transaction.started_at | millis) < ($later_transaction.committed_at | millis) and
    ($partial_window.completed_at | millis) < ($later_transaction.started_at | millis)) as $later_transaction_proven |
  ($later_source_snapshot == {
    captured_at:$later_source_snapshot.captured_at,product_id:1403,
    price_cents:101,revision:1,available_quantity:0,reserved_quantity:0
  } and
    ($later_source_snapshot.captured_at | millis) != null and
    ($later_transaction.committed_at | millis) < ($later_source_snapshot.captured_at | millis)) as $later_source_proven |
  (get_valid($before_1403;1403;101) and
    $later_window == {
      deadline_seconds:30,deadline_reached:$later_window.deadline_reached,
      completed_at:$later_window.completed_at
    } and
    ($later_window.deadline_reached | type) == "boolean" and
    ($later_window.completed_at | millis) != null) as $later_observation_valid |
  ($mapping_repair.delete.transport_ok == true and
    ($mapping_repair.delete.http_status == 200 or $mapping_repair.delete.http_status == 404) and
    $mapping_repair.create.transport_ok == true and
    $mapping_repair.create.http_status == 200 and
    $mapping_repair.create.body == {
      acknowledged:true,shards_acknowledged:true,index:"products_adapter_v1"
    } and
    $normal_mapping_capture.transport_ok == true and
    $normal_mapping_capture.http_status == 200 and
    $normal_mapping_capture.body.products_adapter_v1.mappings.dynamic == "strict" and
    $normal_mapping_capture.body.products_adapter_v1.mappings.properties.price_cents.type == "long") as $mapping_repair_proven |
  ($before_repair_state.container_id == $partial_java.container_id and
    $before_repair_state.java_identity == $partial_java.java_identity and
    $before_repair_state.container_running == false and
    $after_repair_state.container_id == $partial_java.container_id and
    ($after_repair_state.java_identity | identity) and
    $after_repair_state.java_identity != $partial_java.java_identity and
    $after_repair_state.container_running == true and
    ($after_repair_state.workspace_mapping_sha256 | sha256) and
    $after_repair_state.container_mapping_sha256 == $after_repair_state.workspace_mapping_sha256 and
    $after_repair_state.mapping_load_current == true and
    ($after_repair_state.java_cutoff_utc | type) == "string" and
    ($after_repair_state.captured_at | millis) != null) as $same_container_repair_restart |
  (($repair_log | split("\n") | map(select(length > 0))) as $lines |
    any($lines[];
      (.[0:23] >= $after_repair_state.java_cutoff_utc) and
      contains("## Start loading es mapping config ...")) and
    any($lines[];
      (.[0:23] >= $after_repair_state.java_cutoff_utc) and
      contains("## ES mapping config loaded"))) as $repair_mapping_load_current |
  (get_valid($after_restart_1402;1402;1000) and
    $retry_window == {
      deadline_seconds:30,deadline_reached:$retry_window.deadline_reached,
      completed_at:$retry_window.completed_at
    } and
    ($retry_window.deadline_reached | type) == "boolean" and
    ($retry_window.completed_at | millis) != null) as $retry_observation_valid |
  (found($after_restart_1402)) as $retried_after_fix |
  ($retried_after_fix | not) as $etl_required |
  (($etl_endpoint_proof | keys | sort) == [
      "instantiated_endpoint","launcher_jar_sha256","official_archive_sha256",
      "post_mapping","request_param_name","request_param_value","source_class"
    ] and
    $etl_endpoint_proof.official_archive_sha256 == "e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340" and
    ($etl_endpoint_proof.launcher_jar_sha256 | sha256) and
    $etl_endpoint_proof.source_class == "com.alibaba.otter.canal.adapter.launcher.rest.CommonRest" and
    $etl_endpoint_proof.post_mapping == "/etl/{type}/{task}" and
    $etl_endpoint_proof.request_param_name == "params" and
    $etl_endpoint_proof.instantiated_endpoint == "/etl/es8/products.yml" and
    $etl_endpoint_proof.request_param_value == "1401") as $etl_endpoint_proven |
  ($etl_endpoint_proven and
    $etl_action.official_archive_sha256 == $etl_endpoint_proof.official_archive_sha256 and
    $etl_action.source_class == "com.alibaba.otter.canal.adapter.launcher.rest.CommonRest" and
    $etl_action.method == "POST" and
    $etl_action.endpoint == "/etl/es8/products.yml" and
    $etl_action.params == "1401" and
    ($etl_action.invoked | type) == "boolean" and
    if $etl_required then
      $etl_action.invoked == true and $etl_action.transport_ok == true and
      ($etl_action.http_status | type) == "number" and
      ($etl_action.response_body | type) == "object"
    else
      $etl_action == {
        official_archive_sha256:"e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340",
        source_class:"com.alibaba.otter.canal.adapter.launcher.rest.CommonRest",
        method:"POST",endpoint:"/etl/es8/products.yml",params:"1401",
        invoked:false,transport_ok:null,http_status:null,response_body:null
      }
    end) as $etl_action_valid |
  (get_valid($final_1402;1402;1000)) as $final_get_valid |
  ($etl_action.invoked == true and $etl_action.transport_ok == true and
    $etl_action.http_status == 200 and
    $etl_action.response_body.succeeded == true and found($final_1402)) as $etl_repair_succeeded |
  ($input_match and $partial_mapping_proven and $partial_process_proven and
    $same_transaction_proven and $first_source_proven and
    $failure_process_current and $current_run_log_proven and
    $partial_observation_valid and $later_transaction_proven and
    $later_source_proven and $later_observation_valid and
    $mapping_repair_proven and $same_container_repair_restart and
    $repair_mapping_load_current and $retry_observation_valid and
    $etl_endpoint_proven and
    $etl_action_valid and $final_get_valid) as $experiment_valid |
  if $experiment_valid then {
    scenario_id:"m1-bulk-partial",
    input_commands_match:$input_match,
    partial_mapping_proven:$partial_mapping_proven,
    same_source_transaction_proven:$same_transaction_proven,
    source_snapshots_proven:($first_source_proven and $later_source_proven),
    current_run_error_proven:$current_run_error_proven,
    bulk_partial_failure_observed:
      ($current_run_error_proven and (found($before_1402) | not)),
    valid_item_applied:found($before_1401),
    invalid_item_applied_before_mapping_fix:found($before_1402),
    invalid_source_value_preserved_before_fix:
      (found($before_1402) and $before_1402.body._source.price_cents == 1000),
    later_batch_applied_before_mapping_fix:found($before_1403),
    mapping_repair_proven:$mapping_repair_proven,
    same_container_restart_verified:$same_container_repair_restart,
    official_etl_endpoint_proven:$etl_endpoint_proven,
    invalid_item_retried_after_mapping_fix:$retried_after_fix,
    etl_required:$etl_required,
    etl_invoked:$etl_action.invoked,
    etl_repair_succeeded:$etl_repair_succeeded,
    partial_failure_experiment_valid:true,
    captured_values:{
      invalid_source_price_cents:1000,
      invalid_target_price_before_fix:
        (if found($before_1402) then $before_1402.body._source.price_cents else null end)
    },
    evidence_files:{
      first_transaction:"transaction-1401-1402.json",
      later_transaction:"transaction-1403.json",
      partial_error_log:"adapter-partial-error.log",
      etl_endpoint_proof:"etl-endpoint-proof.json",
      etl_action:"etl-action.json"
    },
    final_consistency_claim:false
  } else error({
    input_match:$input_match,
    partial_mapping_proven:$partial_mapping_proven,
    partial_process_proven:$partial_process_proven,
    same_transaction_proven:$same_transaction_proven,
    first_transaction_debug:{
      session:$first_transaction.same_mysql_session,
      committed:$first_transaction.committed,
      connection_type:($first_transaction.mysql_connection_id|type),
      start:($first_transaction.transaction|startswith("START TRANSACTION;")),
      end:($first_transaction.transaction|endswith("COMMIT;")),
      id1401:($first_transaction.transaction|contains("(1401,")),
      id1402:($first_transaction.transaction|contains("(1402,")),
      inventory:($first_transaction.transaction|contains("VALUES (1401, 0, 0), (1402, 0, 0)")),
      revision:($first_transaction.transaction|contains("VALUES (1401, 1, 1), (1402, 1, 1)")),
      start_ms:($first_transaction.started_at|millis),
      commit_ms:($first_transaction.committed_at|millis)
    },
    first_source_proven:$first_source_proven,
    failure_process_current:$failure_process_current,
    current_run_error_proven:$current_run_error_proven,
    current_run_log_proven:$current_run_log_proven,
    partial_observation_valid:$partial_observation_valid,
    later_transaction_proven:$later_transaction_proven,
    later_source_proven:$later_source_proven,
    later_observation_valid:$later_observation_valid,
    mapping_repair_proven:$mapping_repair_proven,
    same_container_repair_restart:$same_container_repair_restart,
    repair_mapping_load_current:$repair_mapping_load_current,
    retry_observation_valid:$retry_observation_valid,
    etl_endpoint_proven:$etl_endpoint_proven,
    etl_endpoint_proof:$etl_endpoint_proof,
    etl_action_valid:$etl_action_valid,
    final_get_valid:$final_get_valid
  } | tostring) end
' \
  --slurpfile input "$out/input-commands.json" \
  --slurpfile partial_index "$out/partial-index-create.json" \
  --slurpfile partial_mapping "$out/partial-mapping-proof.json" \
  --slurpfile partial_run "$out/adapter-partial-run.json" \
  --slurpfile first_tx "$out/transaction-1401-1402.json" \
  --slurpfile first_source "$out/source-1401-1402.json" \
  --rawfile partial_log "$out/adapter-partial-error.log" \
  --slurpfile after_error "$out/adapter-after-partial-error.json" \
  --slurpfile get1401 "$out/1401-before-fix.json" \
  --slurpfile get1402 "$out/1402-before-fix.json" \
  --slurpfile partial_observation "$out/partial-observation.json" \
  --slurpfile later_tx "$out/transaction-1403.json" \
  --slurpfile later_source "$out/source-1403.json" \
  --slurpfile get1403 "$out/1403-before-fix.json" \
  --slurpfile later_observation "$out/later-observation.json" \
  --slurpfile repair "$out/mapping-repair.json" \
  --slurpfile normal_mapping "$out/normal-mapping-proof.json" \
  --slurpfile before_repair "$out/adapter-before-repair-start.json" \
  --slurpfile after_repair "$out/adapter-after-repair-start.json" \
  --rawfile repair_log "$out/adapter-repair-run.log" \
  --slurpfile get_after_restart "$out/1402-after-restart.json" \
  --slurpfile retry_observation "$out/retry-observation.json" \
  --slurpfile etl_proof "$out/etl-endpoint-proof.json" \
  --slurpfile etl "$out/etl-action.json" \
  --slurpfile get_final "$out/1402-final.json"
