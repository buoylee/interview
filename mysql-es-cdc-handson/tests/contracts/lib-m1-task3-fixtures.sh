#!/usr/bin/env bash

m1_task3_write_mapping_proofs() {
  local out="$1"
  local container_id="$2"
  local java_identity="$3"
  local mapping_sha="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

  jq -n \
    --arg container "$container_id" \
    --arg identity "$java_identity" \
    --arg sha "$mapping_sha" '
    {
      contract:"m1-adapter-baseline-continuity-v1",
      phase:"pre_behavior",
      container_id:$container,
      java_identity:$identity,
      java_cutoff_utc:"2026-07-26 14:00:00.000",
      workspace_mapping_sha256:$sha,
      container_mapping_sha256:$sha,
      loader_assertions:{start_loading_after_cutoff:true,loaded_after_cutoff:true},
      identity_stable_during_precheck:true,
      baseline_continuity_verified:false
    }
  ' >"$out/pre-behavior-mapping-proof.json"

  jq '
    .phase = "baseline_complete" |
    .baseline_continuity_verified = true |
    .post_behavior = {
      container_id:.container_id,
      java_identity:.java_identity,
      container_mapping_sha256:.container_mapping_sha256,
      identity_stable_during_postcheck:true
    }
  ' "$out/pre-behavior-mapping-proof.json" >"$out/current-run-mapping-proof.json"

  printf '%s\n' \
    'M1 Adapter topology evidence passed:' \
    '- formal es8 products mapping: exact image file plus current-Java-run load evidence' \
    >"$out/current-run-topology-proof.txt"
  printf '%s\n' \
    '2026-07-26 14:00:00.001 INFO ## Start loading es mapping config ...' \
    '2026-07-26 14:00:00.002 INFO ## ES mapping config loaded' \
    >"$out/adapter.log"
}

m1_task3_write_common_setup() {
  local out="$1"
  local scenario="$2"
  local id="$3"
  local sku="$4"
  local name="$5"
  local description="$6"

  cp "scenarios/definitions/$scenario.json" "$out/input-commands.json"
  printf '%s\n' \
    '{"acknowledged":true,"shards_acknowledged":true,"index":"products_adapter_v1"}' \
    >"$out/index-create.json"
  printf '{"productId":%s,"revision":1}\n' "$id" >"$out/create-response.json"
  jq -n --argjson id "$id" --arg sku "$sku" --arg name "$name" \
    --arg description "$description" '
    {
      product:{
        product_id:$id,sku:$sku,name:$name,description:$description,
        category_id:10,price_cents:100,status:"ACTIVE",
        updated_at:"2026-07-26T14:00:01.000000Z"
      },
      revision:{product_id:$id,revision:1,active:true},
      inventory:{product_id:$id,available_quantity:0,reserved_quantity:0}
    }
  ' >"$out/mysql-initial-snapshot.json"
  jq -n --argjson id "$id" --arg sku "$sku" --arg name "$name" \
    --arg description "$description" '
    {
      found:true,
      _source:{
        product_id:$id,sku:$sku,name:$name,description:$description,
        category_id:10,price_cents:100,status:"ACTIVE",updated_at:null
      }
    }
  ' >"$out/es-initial-snapshot.json"
}
