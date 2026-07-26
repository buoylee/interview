#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-m1-log-window.sh

old_log=$(mktemp "${TMPDIR:-/tmp}/m1-old-log.XXXXXX")
current_log=$(mktemp "${TMPDIR:-/tmp}/m1-current-log.XXXXXX")
trap 'rm -f "$old_log" "$current_log"' EXIT

cutoff="2026-07-26 10:14:00.100"
required_patterns=(
  "Load canal adapter: es8 succeed"
  "Start adapter for canal-client mq topic: products_adapter-g1 succeed"
  "Start to connect destination: products_adapter"
  "Subscribe destination: products_adapter succeed"
)

printf '%s\n' \
  "2026-07-26 10:13:59.880 [main] INFO ## Start loading es mapping config ... " \
  "2026-07-26 10:13:59.890 [main] INFO ## ES mapping config loaded" \
  "2026-07-26 10:13:59.900 [main] INFO Load canal adapter: es8 succeed" \
  "2026-07-26 10:13:59.910 [main] INFO Start adapter for canal-client mq topic: products_adapter-g1 succeed" \
  "2026-07-26 10:13:59.920 [Thread-4] INFO Start to connect destination: products_adapter" \
  "2026-07-26 10:13:59.930 [Thread-4] INFO Subscribe destination: products_adapter succeed" \
  >"$old_log"

if require_log_patterns_since "$cutoff" "$old_log" "${required_patterns[@]}"; then
  echo "old success lines must not satisfy a newer Java-process cutoff" >&2
  exit 1
fi

if adapter_mapping_load_is_current "$cutoff" "$old_log"; then
  echo "old mapping-load lines must not satisfy a newer Java-process cutoff" >&2
  exit 1
fi

printf '%s\n' \
  "2026-07-26 10:13:59.900 [main] INFO Load canal adapter: es8 succeed" \
  "2026-07-26 10:14:00.099 [main] INFO ## Start loading es mapping config ... " \
  "2026-07-26 10:14:00.100 [main] INFO ## ES mapping config loaded" \
  "2026-07-26 10:14:00.101 [main] INFO ## Start loading es mapping config ... " \
  "2026-07-26 10:14:00.102 [main] INFO ## ES mapping config loaded" \
  "2026-07-26 10:14:00.103 [main] INFO Load canal adapter: es8 succeed" \
  "2026-07-26 10:14:00.104 [main] INFO Start adapter for canal-client mq topic: products_adapter-g1 succeed" \
  "2026-07-26 10:14:00.105 [Thread-4] INFO Start to connect destination: products_adapter" \
  "2026-07-26 10:14:00.106 [Thread-4] INFO Subscribe destination: products_adapter succeed" \
  >"$current_log"

require_log_patterns_since "$cutoff" "$current_log" "${required_patterns[@]}"
adapter_mapping_load_is_current "$cutoff" "$current_log"
