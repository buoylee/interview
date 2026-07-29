#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)"
assets=(infra/toxiproxy/bootstrap.sh scenarios/scripts/wait-condition.sh scenarios/scripts/fault-network.sh scenarios/scripts/fault-process.sh scenarios/scripts/fault-retention.sh scenarios/scripts/capture-mysql.sh scenarios/scripts/capture-elasticsearch.sh scenarios/scripts/capture-kafka.sh scenarios/scripts/capture-manifest.sh)
for asset in "${assets[@]}";do test -x "$root/$asset"||{ echo "missing primitive: $asset" >&2;exit 1;};done
tmp="$(mktemp -d)";trap 'rm -rf "$tmp"' EXIT
export SCENARIO_CLEANUP_FILE="$tmp/cleanup"
bash "$root/infra/toxiproxy/bootstrap.sh" >/dev/null
for fault in kafka-timeout elasticsearch-timeout canal-mysql-timeout;do
 bash "$root/scenarios/scripts/fault-network.sh" remove "$fault"|jq -e '.active==false' >/dev/null
 bash "$root/scenarios/scripts/fault-network.sh" apply "$fault"|jq -e '.active==true' >/dev/null
 bash "$root/scenarios/scripts/fault-network.sh" apply "$fault"|jq -e '.active==true' >/dev/null
 bash "$root/scenarios/scripts/fault-network.sh" status "$fault"|jq -e '.active==true' >/dev/null
 bash "$root/scenarios/scripts/fault-network.sh" remove "$fault"|jq -e '.active==false' >/dev/null
 bash "$root/scenarios/scripts/fault-network.sh" remove "$fault"|jq -e '.active==false' >/dev/null
done
test "$(wc -l <"$tmp/cleanup"|tr -d ' ')" -eq 6
printf 'M6 primitive asset/network idempotence contract passed\n'
