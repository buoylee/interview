#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

compose=(docker compose -f infra/compose.yaml -f infra/compose.adapter.yaml)
max_attempts="${M1_VERIFY_MAX_ATTEMPTS:-30}"

top_output=$(mktemp "${TMPDIR:-/tmp}/m1-top.XXXXXX")
server_log=$(mktemp "${TMPDIR:-/tmp}/m1-server.XXXXXX")
adapter_log=$(mktemp "${TMPDIR:-/tmp}/m1-adapter.XXXXXX")
http_body=$(mktemp "${TMPDIR:-/tmp}/m1-http.XXXXXX")
trap 'rm -f "$top_output" "$server_log" "$adapter_log" "$http_body"' EXIT

capture_runtime() {
  "${compose[@]}" top canal-adapter canal-adapter-server >"$top_output" 2>/dev/null &&
    "${compose[@]}" exec -T canal-adapter-server \
      cat /home/admin/canal-server/logs/products_adapter/products_adapter.log \
      >"$server_log" 2>/dev/null &&
    "${compose[@]}" logs --no-color canal-adapter >"$adapter_log" 2>/dev/null
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
  grep -Fq "start CannalInstance for 1-products_adapter" "$server_log" &&
    grep -Fq 'init table filter : ^product_catalog\.products$' "$server_log" &&
    grep -Fq "start successful...." "$server_log"
}

adapter_worker_is_started() {
  grep -Fq "Load canal adapter: es8 succeed" "$adapter_log" &&
    grep -Fq "Start adapter for canal-client mq topic: products_adapter-g1 succeed" \
      "$adapter_log" &&
    grep -Fq "Start to connect destination: products_adapter" "$adapter_log" &&
    grep -Fq "Subscribe destination: products_adapter succeed" "$adapter_log" &&
    ! grep -Fq "something goes wrong when starting up the canal client adapters" \
      "$adapter_log"
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
    adapter_web_responds
}

for attempt in $(seq 1 "$max_attempts"); do
  if runtime_evidence_is_ready; then
    printf '%s\n' \
      "M1 Adapter topology evidence passed:" \
      "- canal-adapter Java process: admin (UID 1000), non-root" \
      "- canal-adapter-server Java process: admin (UID 1000), non-root" \
      "- TCP ports 127.0.0.1:11121 and 127.0.0.1:11122: reachable" \
      "- products_adapter destination/filter/start log evidence: present" \
      "- es8/products_adapter-g1 connect/subscribe log evidence: present" \
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
report_check "official Adapter web interface responds" adapter_web_responds
exit 1
