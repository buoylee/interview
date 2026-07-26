#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-m1-log-window.sh
source scenarios/scripts/lib-m1-mapping-proof.sh

compose=(docker compose -f infra/compose.yaml -f infra/compose.adapter.yaml)
max_attempts="${M1_VERIFY_MAX_ATTEMPTS:-30}"

top_output=$(mktemp "${TMPDIR:-/tmp}/m1-top.XXXXXX")
server_log=$(mktemp "${TMPDIR:-/tmp}/m1-server.XXXXXX")
adapter_log=$(mktemp "${TMPDIR:-/tmp}/m1-adapter.XXXXXX")
http_body=$(mktemp "${TMPDIR:-/tmp}/m1-http.XXXXXX")
mapping_proof_capture=$(mktemp "${TMPDIR:-/tmp}/m1-mapping-proof.XXXXXX")
trap 'rm -f "$top_output" "$server_log" "$adapter_log" "$http_body" "$mapping_proof_capture"' EXIT

capture_runtime() {
  rm -f "$mapping_proof_capture" &&
    adapter_container_before=$(current_container_id canal-adapter) &&
    adapter_snapshot=$(current_java_process_state canal-adapter canal-adapter snapshot) &&
    server_snapshot=$(current_java_process_state canal-adapter-server otter-canal snapshot) &&
    IFS='|' read -r adapter_pid adapter_start_ticks adapter_cutoff adapter_extra <<<"$adapter_snapshot" &&
    IFS='|' read -r server_pid server_start_ticks server_cutoff server_extra <<<"$server_snapshot" &&
    test -z "$adapter_extra" &&
    test -z "$server_extra" &&
    test -n "$adapter_cutoff" &&
    test -n "$server_cutoff" &&
    adapter_identity="$adapter_pid|$adapter_start_ticks" &&
    server_identity="$server_pid|$server_start_ticks" &&
    process_identity_is_unchanged "$adapter_identity" "$adapter_identity" &&
    process_identity_is_unchanged "$server_identity" "$server_identity" &&
    "${compose[@]}" top canal-adapter canal-adapter-server >"$top_output" 2>/dev/null &&
    "${compose[@]}" exec -T canal-adapter-server \
      cat /home/admin/canal-server/logs/products_adapter/products_adapter.log \
      >"$server_log" 2>/dev/null &&
    "${compose[@]}" exec -T canal-adapter \
      cat /opt/canal-adapter/logs/adapter/adapter.log \
      >"$adapter_log" 2>/dev/null &&
    adapter_mapping_load_is_current "$adapter_cutoff" "$adapter_log" &&
    workspace_mapping_sha=$(sha256sum infra/canal-adapter/conf/es8/products.yml | awk '{ print $1 }') &&
    container_mapping_sha=$("${compose[@]}" exec -T canal-adapter \
      sha256sum /opt/canal-adapter/conf/es8/products.yml | awk '{ print $1 }') &&
    test "$workspace_mapping_sha" = "$container_mapping_sha" &&
    adapter_identity_after=$(current_java_process_state canal-adapter canal-adapter identity) &&
    server_identity_after=$(current_java_process_state canal-adapter-server otter-canal identity) &&
    adapter_container_after=$(current_container_id canal-adapter) &&
    process_identity_is_unchanged "$adapter_identity" "$adapter_identity_after" &&
    process_identity_is_unchanged "$server_identity" "$server_identity_after" &&
    write_pre_behavior_mapping_proof_atomically "$mapping_proof_capture" \
      "$adapter_container_before" "$adapter_identity" "$adapter_cutoff" "$adapter_log" \
      "$workspace_mapping_sha" "$container_mapping_sha" \
      "$adapter_identity_after" "$adapter_container_after"
}

current_container_id() {
  local service="$1"
  local container_id
  container_id=$("${compose[@]}" ps -q "$service" | tr -d '\r\n')
  m1_is_container_id "$container_id"
  printf '%s\n' "$container_id"
}

current_java_process_state() {
  local service="$1"
  local app_name="$2"
  local output_mode="$3"

  "${compose[@]}" exec -T "$service" sh -s -- "$app_name" "$output_mode" <<'SH'
set -eu

app_name="$1"
output_mode="$2"
case "$output_mode" in
  identity|snapshot) ;;
  *) exit 1 ;;
esac

pid=""
matches=0
for process_dir in /proc/[0-9]*; do
  test -r "$process_dir/cmdline" || continue
  command_line=$(tr '\000' ' ' <"$process_dir/cmdline" 2>/dev/null || true)
  case "$command_line" in
    *"-DappName=$app_name "*)
      matches=$((matches + 1))
      uid=$(awk '/^Uid:/ { print $2 }' "$process_dir/status")
      test "$uid" = "1000" || exit 1
      pid=${process_dir##*/}
      ;;
  esac
done
test "$matches" -eq 1

stat_line=$(cat "/proc/$pid/stat")
stat_tail=${stat_line##*) }
test "$stat_tail" != "$stat_line"
set -- $stat_tail
test "$#" -ge 20
start_ticks=${20}
case "$pid$start_ticks" in
  ''|*[!0-9]*) exit 1 ;;
esac

if test "$output_mode" = identity; then
  printf '%s|%s\n' "$pid" "$start_ticks"
  exit 0
fi

ticks_per_second=$(getconf CLK_TCK)
uptime_seconds=$(awk '{ print $1 }' /proc/uptime)
now_epoch_ms=$(date -u +%s%3N)
start_epoch_ms=$(awk \
  -v now_ms="$now_epoch_ms" \
  -v uptime="$uptime_seconds" \
  -v ticks="$start_ticks" \
  -v hz="$ticks_per_second" \
  'BEGIN { printf "%.0f\n", now_ms - ((uptime - (ticks / hz)) * 1000) + 100 }')
start_epoch_seconds=$((start_epoch_ms / 1000))
start_milliseconds=$((start_epoch_ms % 1000))
start_utc=$(date -u -d "@$start_epoch_seconds" '+%Y-%m-%d %H:%M:%S')
printf '%s|%s|%s.%03d\n' "$pid" "$start_ticks" "$start_utc" "$start_milliseconds"
SH
}

java_process_is_admin() {
  local service="$1"
  local app_name="$2"

  awk -v service="$service" -v app_name="$app_name" '
    $1 == service && index($0, "-DappName=" app_name) {
      seen += 1
      if ($4 == "1000" || $4 == "admin") {
        admin += 1
      } else {
        wrong_user += 1
      }
    }
    END {
      exit !(seen == 1 && admin == 1 && wrong_user == 0)
    }
  ' "$top_output" &&
    test "$("${compose[@]}" exec -T --user 1000 "$service" id -un | tr -d '\r')" = "admin"
}

tcp_ports_are_reachable() {
  nc -z 127.0.0.1 11121 >/dev/null 2>&1 &&
    nc -z 127.0.0.1 11122 >/dev/null 2>&1
}

server_destination_is_started() {
  require_log_patterns_since "$server_cutoff" "$server_log" \
    "start CannalInstance for 1-products_adapter" \
    'init table filter : ^product_catalog\.products$' \
    "start successful...."
}

adapter_worker_is_started() {
  require_log_patterns_since "$adapter_cutoff" "$adapter_log" \
    "Load canal adapter: es8 succeed" \
    "Start adapter for canal-client mq topic: products_adapter-g1 succeed" \
    "Start to connect destination: products_adapter" \
    "Subscribe destination: products_adapter succeed" &&
    ! log_pattern_exists_since "$adapter_cutoff" "$adapter_log" \
      "something goes wrong when starting up the canal client adapters"
}

formal_mapping_is_loaded() {
  jq -e \
    --arg container "$adapter_container_before" \
    --arg identity "$adapter_identity" \
    --arg cutoff "$adapter_cutoff" \
    --arg sha "$workspace_mapping_sha" '
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
  ' "$mapping_proof_capture" >/dev/null
}

publish_pre_behavior_mapping_proof() {
  local output="${M1_MAPPING_PROOF_OUTPUT:-}"
  test -n "$output" || return 0

  write_pre_behavior_mapping_proof_atomically "$output" \
    "$adapter_container_before" "$adapter_identity" "$adapter_cutoff" "$adapter_log" \
    "$workspace_mapping_sha" "$container_mapping_sha" \
    "$adapter_identity_after" "$adapter_container_after"
}

verify_mapping_continuity_live() {
  local pre_proof="$1"
  local output="$2"
  local post_container_before post_identity_before post_mapping_sha
  local post_identity_after post_container_after

  post_container_before=$(current_container_id canal-adapter) &&
    post_identity_before=$(current_java_process_state canal-adapter canal-adapter identity) &&
    post_mapping_sha=$("${compose[@]}" exec -T canal-adapter \
      sha256sum /opt/canal-adapter/conf/es8/products.yml | awk '{ print $1 }') &&
    post_identity_after=$(current_java_process_state canal-adapter canal-adapter identity) &&
    post_container_after=$(current_container_id canal-adapter) &&
    write_baseline_mapping_continuity_proof_atomically "$output" \
      "$pre_proof" "$post_container_before" "$post_identity_before" \
      "$post_mapping_sha" "$post_identity_after" "$post_container_after"
}

adapter_web_responds() {
  http_code=$(curl --silent --show-error \
    --connect-timeout 2 \
    --max-time 4 \
    --output "$http_body" \
    --write-out '%{http_code}' \
    http://127.0.0.1:8084/ 2>/dev/null) || return 1

  case "$http_code" in
    [1-5][0-9][0-9]) return 0 ;;
    *) return 1 ;;
  esac
}

runtime_evidence_is_ready() {
  capture_runtime &&
    java_process_is_admin canal-adapter canal-adapter &&
    java_process_is_admin canal-adapter-server otter-canal &&
    tcp_ports_are_reachable &&
    server_destination_is_started &&
    adapter_worker_is_started &&
    formal_mapping_is_loaded &&
    adapter_web_responds
}

if test "${1:-}" = "--mapping-continuity"; then
  test "$#" -eq 3 || {
    echo "usage: $0 --mapping-continuity PRE_PROOF OUTPUT" >&2
    exit 2
  }
  verify_mapping_continuity_live "$2" "$3"
  exit
fi

for attempt in $(seq 1 "$max_attempts"); do
  if runtime_evidence_is_ready; then
    publish_pre_behavior_mapping_proof
    printf '%s\n' \
      "M1 Adapter topology evidence passed:" \
      "- canal-adapter Java process: admin (UID 1000), non-root" \
      "- canal-adapter-server Java process: admin (UID 1000), non-root" \
      "- TCP ports 127.0.0.1:11121 and 127.0.0.1:11122: reachable" \
      "- products_adapter destination/filter/start log evidence: present" \
      "- es8/products_adapter-g1 connect/subscribe log evidence: present" \
      "- formal es8 products mapping: exact image file plus current-Java-run load evidence" \
      "- official Adapter web interface: HTTP $http_code (reachability only; not readiness)"
    exit 0
  fi

  if test "$attempt" -lt "$max_attempts"; then
    sleep 1
  fi
done

echo "M1 Adapter topology evidence did not converge after $max_attempts attempts" >&2
capture_runtime || true
report_check() {
  local description="$1"
  shift
  if "$@"; then
    echo "PASS: $description" >&2
  else
    echo "FAIL: $description" >&2
  fi
}

report_check "canal-adapter Java is admin/non-root" \
  java_process_is_admin canal-adapter canal-adapter
report_check "canal-adapter-server Java is admin/non-root" \
  java_process_is_admin canal-adapter-server otter-canal
report_check "host TCP ports are reachable" tcp_ports_are_reachable
report_check "products_adapter destination log evidence exists" \
  server_destination_is_started
report_check "Adapter worker log evidence exists" adapter_worker_is_started
report_check "formal products mapping loaded in current Adapter run" formal_mapping_is_loaded
report_check "official Adapter web interface responds" adapter_web_responds
exit 1
