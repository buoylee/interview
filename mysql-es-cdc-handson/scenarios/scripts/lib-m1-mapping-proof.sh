#!/usr/bin/env bash

m1_is_sha256() {
  case "$1" in
    ''|*[!0-9a-f]*) return 1 ;;
  esac
  test "${#1}" -eq 64
}

m1_is_container_id() {
  m1_is_sha256 "$1"
}

build_pre_behavior_mapping_proof() {
  test "$#" -eq 8 || return 2

  local container_before="$1"
  local identity_before="$2"
  local cutoff="$3"
  local adapter_log="$4"
  local workspace_sha="$5"
  local container_sha="$6"
  local identity_after="$7"
  local container_after="$8"

  m1_is_container_id "$container_before" &&
    m1_is_container_id "$container_after" &&
    process_identity_is_unchanged "$identity_before" "$identity_after" &&
    test "$container_before" = "$container_after" &&
    m1_is_sha256 "$workspace_sha" &&
    m1_is_sha256 "$container_sha" &&
    test "$workspace_sha" = "$container_sha" &&
    adapter_mapping_load_is_current "$cutoff" "$adapter_log" || return 1

  jq -n \
    --arg container_id "$container_before" \
    --arg java_identity "$identity_before" \
    --arg java_cutoff_utc "$cutoff" \
    --arg workspace_mapping_sha256 "$workspace_sha" \
    --arg container_mapping_sha256 "$container_sha" '
    {
      contract:"m1-adapter-baseline-continuity-v1",
      phase:"pre_behavior",
      container_id:$container_id,
      java_identity:$java_identity,
      java_cutoff_utc:$java_cutoff_utc,
      workspace_mapping_sha256:$workspace_mapping_sha256,
      container_mapping_sha256:$container_mapping_sha256,
      loader_assertions:{
        start_loading_after_cutoff:true,
        loaded_after_cutoff:true
      },
      identity_stable_during_precheck:true,
      baseline_continuity_verified:false
    }
  '
}

write_pre_behavior_mapping_proof_atomically() {
  test "$#" -eq 9 || return 2

  local output="$1"
  shift
  local temporary status
  temporary=$(mktemp "${output}.tmp.XXXXXX") || return 1
  if build_pre_behavior_mapping_proof "$@" >"$temporary"; then
    mv "$temporary" "$output"
  else
    status=$?
    rm -f "$temporary"
    return "$status"
  fi
}

build_baseline_mapping_continuity_proof() {
  test "$#" -eq 6 || return 2

  local pre_proof="$1"
  local post_container_before="$2"
  local post_identity_before="$3"
  local post_mapping_sha="$4"
  local post_identity_after="$5"
  local post_container_after="$6"

  test -s "$pre_proof" &&
    m1_is_container_id "$post_container_before" &&
    m1_is_container_id "$post_container_after" &&
    test "$post_container_before" = "$post_container_after" &&
    process_identity_is_unchanged "$post_identity_before" "$post_identity_after" &&
    m1_is_sha256 "$post_mapping_sha" || return 1

  jq -e \
    --arg post_container "$post_container_before" \
    --arg post_identity "$post_identity_before" \
    --arg post_mapping_sha "$post_mapping_sha" '
    (keys | sort) == [
      "baseline_continuity_verified",
      "container_id",
      "container_mapping_sha256",
      "contract",
      "identity_stable_during_precheck",
      "java_cutoff_utc",
      "java_identity",
      "loader_assertions",
      "phase",
      "workspace_mapping_sha256"
    ] and
    .contract == "m1-adapter-baseline-continuity-v1" and
    .phase == "pre_behavior" and
    .baseline_continuity_verified == false and
    .identity_stable_during_precheck == true and
    .loader_assertions == {
      "start_loading_after_cutoff":true,
      "loaded_after_cutoff":true
    } and
    (.container_id | test("^[0-9a-f]{64}$")) and
    (.java_identity | test("^[0-9]+[|][0-9]+$")) and
    (.java_cutoff_utc | test("^[0-9]{4}-[0-9]{2}-[0-9]{2} [0-9]{2}:[0-9]{2}:[0-9]{2}[.][0-9]{3}$")) and
    (.workspace_mapping_sha256 | test("^[0-9a-f]{64}$")) and
    .container_mapping_sha256 == .workspace_mapping_sha256 and
    .container_id == $post_container and
    .java_identity == $post_identity and
    .container_mapping_sha256 == $post_mapping_sha
  ' "$pre_proof" >/dev/null || return 1

  jq \
    --arg post_container "$post_container_before" \
    --arg post_identity "$post_identity_before" \
    --arg post_mapping_sha "$post_mapping_sha" '
    .phase = "baseline_complete" |
    .baseline_continuity_verified = true |
    .post_behavior = {
      container_id:$post_container,
      java_identity:$post_identity,
      container_mapping_sha256:$post_mapping_sha,
      identity_stable_during_postcheck:true
    }
  ' "$pre_proof"
}

write_baseline_mapping_continuity_proof_atomically() {
  test "$#" -eq 7 || return 2

  local output="$1"
  shift
  local temporary status
  temporary=$(mktemp "${output}.tmp.XXXXXX") || return 1
  if build_baseline_mapping_continuity_proof "$@" >"$temporary"; then
    mv "$temporary" "$output"
  else
    status=$?
    rm -f "$temporary"
    return "$status"
  fi
}
