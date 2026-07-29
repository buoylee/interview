#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";case "${COMPOSE_PROJECT_NAME:-}" in *m6*) ;;*) echo 'retention gap contract requires isolated M6 COMPOSE_PROJECT_NAME' >&2;exit 64;;esac
tmp="$(mktemp -d)";trap 'rm -rf "$tmp"' EXIT;export MYSQL_PWD="${MYSQL_PWD:?MYSQL_PWD required}" SCENARIO_CLEANUP_FILE="$tmp/cleanup"
export SCENARIO_STATE_DIR="$tmp/mysql";mkdir -p "$SCENARIO_STATE_DIR";bash "$root/scenarios/scripts/fault-retention.sh" apply mysql >"$tmp/mysql-result.json"
jq -e '.recorded_present==false' "$tmp/mysql-result.json" >/dev/null
jq -e '. as $s|.action=="safe-old-file-purge-confirmed" and .before_files==(.before_files|sort) and .after_files==(.after_files|sort) and (.before_files|index($s.recorded_old))!=null and (.after_files|index($s.recorded_old))==null and .current_after!=.recorded_old' "$SCENARIO_STATE_DIR/mysql-retention.json" >/dev/null
test "$(jq -r .expire_before "$SCENARIO_STATE_DIR/mysql-retention.json")" = "$(docker compose -f "$root/infra/compose.yaml" exec -T -e MYSQL_PWD="$MYSQL_PWD" mysql mysql -N -B -uroot -e 'SELECT @@GLOBAL.binlog_expire_logs_seconds')"
config_before="$(docker compose -f "$root/infra/compose.yaml" exec -T kafka /opt/kafka/bin/kafka-configs.sh --bootstrap-server kafka:9092 --entity-type topics --entity-name product-search-revisions --describe|sed 's/^.*Configs: //')"
export SCENARIO_STATE_DIR="$tmp/kafka";mkdir -p "$SCENARIO_STATE_DIR";bash "$root/scenarios/scripts/fault-retention.sh" apply kafka >"$tmp/kafka-result.json"
jq -e '.gap==true' "$tmp/kafka-result.json" >/dev/null
jq -e '. as $s|.action=="delete-records-confirmed" and (.after.beginning[($s.partition|tostring)]>$s.captured_committed)' "$SCENARIO_STATE_DIR/kafka-retention.json" >/dev/null
config_after="$(docker compose -f "$root/infra/compose.yaml" exec -T kafka /opt/kafka/bin/kafka-configs.sh --bootstrap-server kafka:9092 --entity-type topics --entity-name product-search-revisions --describe|sed 's/^.*Configs: //')";test "$config_after" = "$config_before"
bash "$root/scenarios/scripts/fault-retention.sh" remove kafka >/dev/null
printf 'M6 real isolated retention gaps contract passed\n'
