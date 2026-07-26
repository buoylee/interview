#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-m1-log-window.sh
source scenarios/scripts/lib-m1-mapping-proof.sh

fixture=$(mktemp -d "${TMPDIR:-/tmp}/m1-mapping-proof.XXXXXX")
trap 'rm -rf "$fixture"' EXIT

cutoff="2026-07-26 13:12:52.700"
container_id="229932d46a1e1234567890abcdef1234567890abcdef1234567890abcdef1234"
identity="40|123456"
mapping_sha="0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

printf '%s\n' \
  '2026-07-26 13:12:52.781 INFO ## Start loading es mapping config ...' \
  '2026-07-26 13:12:52.794 INFO ## ES mapping config loaded' \
  >"$fixture/adapter.log"

build_pre_behavior_mapping_proof \
  "$container_id" "$identity" "$cutoff" "$fixture/adapter.log" \
  "$mapping_sha" "$mapping_sha" "$identity" "$container_id" \
  >"$fixture/pre.json"

jq -e --arg container "$container_id" --arg identity "$identity" \
  --arg cutoff "$cutoff" --arg sha "$mapping_sha" '
  .contract == "m1-adapter-baseline-continuity-v1" and
  .phase == "pre_behavior" and
  .container_id == $container and
  .java_identity == $identity and
  .java_cutoff_utc == $cutoff and
  .workspace_mapping_sha256 == $sha and
  .container_mapping_sha256 == $sha and
  .loader_assertions.start_loading_after_cutoff == true and
  .loader_assertions.loaded_after_cutoff == true and
  .identity_stable_during_precheck == true and
  .baseline_continuity_verified == false
' "$fixture/pre.json" >/dev/null

if build_pre_behavior_mapping_proof \
    "$container_id" "$identity" "$cutoff" "$fixture/adapter.log" \
    "$mapping_sha" "$mapping_sha" "40|654321" "$container_id" \
    >/dev/null 2>&1; then
  echo "mapping pre-proof accepted Java identity drift during the SHA/log window" >&2
  exit 1
fi

if build_pre_behavior_mapping_proof \
    "$container_id" "$identity" "$cutoff" "$fixture/adapter.log" \
    "$mapping_sha" "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" \
    "$identity" "$container_id" >/dev/null 2>&1; then
  echo "mapping pre-proof accepted a container mapping SHA mismatch" >&2
  exit 1
fi

build_baseline_mapping_continuity_proof \
  "$fixture/pre.json" \
  "$container_id" "$identity" "$mapping_sha" "$identity" "$container_id" \
  >"$fixture/final.json"
jq -e '
  .phase == "baseline_complete" and
  .baseline_continuity_verified == true and
  .post_behavior.container_id == .container_id and
  .post_behavior.java_identity == .java_identity and
  .post_behavior.container_mapping_sha256 == .container_mapping_sha256
' "$fixture/final.json" >/dev/null

for drift in container identity sha; do
  post_container="$container_id"
  post_identity="$identity"
  post_sha="$mapping_sha"
  case "$drift" in
    container) post_container="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" ;;
    identity) post_identity="40|654321" ;;
    sha) post_sha="ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" ;;
  esac
  if build_baseline_mapping_continuity_proof \
      "$fixture/pre.json" \
      "$post_container" "$post_identity" "$post_sha" "$post_identity" "$post_container" \
      >/dev/null 2>&1; then
    echo "mapping continuity accepted post-behavior $drift drift" >&2
    exit 1
  fi
done

failed_output="$fixture/must-not-exist.json"
if write_pre_behavior_mapping_proof_atomically "$failed_output" \
    "$container_id" "$identity" "$cutoff" "$fixture/adapter.log" \
    "$mapping_sha" "$mapping_sha" "40|654321" "$container_id" \
    >/dev/null 2>&1; then
  echo "atomic pre-proof writer accepted identity drift" >&2
  exit 1
fi
test ! -e "$failed_output"
