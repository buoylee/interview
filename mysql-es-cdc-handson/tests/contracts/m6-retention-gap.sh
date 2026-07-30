#!/usr/bin/env bash
set -euo pipefail
if test -z "${MYSQL_PWD:-}"; then
  echo 'MYSQL_PWD required' >&2
  exit 64
fi
root="$(cd "$(dirname "$0")/../.." && pwd)";tmp="$(mktemp -d)";project="mysql-es-cdc-handson-m6-retention-$$"
case "$project" in mysql-es-cdc-handson-m6-?*) ;;*) exit 64;;esac
override="$tmp/no-host-ports.yaml";marker="$tmp/provenance.json";cleanup="$tmp/cleanup"
cat >"$override" <<'YAML'
services:
  mysql: {ports: !reset []}
  kafka: {ports: !reset []}
  elasticsearch: {ports: !reset []}
  toxiproxy: {ports: !reset []}
  canal: {ports: !reset []}
  product-service: {ports: !reset []}
  search-sync-consumer: {ports: !reset []}
  consistency-verifier: {ports: !reset []}
YAML
compose=(docker compose -p "$project" -f "$root/infra/compose.yaml" -f "$override")
cleanup_project(){ "${compose[@]}" --profile m0-tools down --volumes --remove-orphans >/dev/null 2>&1||true;rm -rf "$tmp"; }
trap cleanup_project EXIT INT TERM
export COMPOSE_PROJECT_NAME="$project" MYSQL_PWD MYSQL_USER=root
export M6_RETENTION_DESTRUCTIVE_ACK=I_UNDERSTAND_M6_DEDICATED_RETENTION_DESTROYS_LOGS SCENARIO_PROVENANCE_FILE="$marker" SCENARIO_CLEANUP_FILE="$cleanup"
jq -n --arg project "$project" '{purpose:"m6-dedicated-retention",compose_project:$project}' >"$marker"
"${compose[@]}" --profile m0-tools up -d --build
"${compose[@]}" exec -T consistency-verifier sh -c 'until curl -fsS http://127.0.0.1:8083/actuator/health >/dev/null;do sleep 1;done'
payload='{"database":"product_catalog","table":"product_search_revision","isDdl":false,"type":"UPDATE","data":[{"product_id":"900001","revision":"1","active":"1"}]}'
seed_ack="$tmp/seed-ack.json";seed_record="$tmp/seed-record.json"
"${compose[@]}" exec -T consistency-verifier curl -fsS -X POST http://127.0.0.1:8083/internal/lab/scenario-events -H 'Content-Type: application/json' -d "$(jq -cn --arg payload "$payload" '{topic:"product-search-revisions",partition:0,payload:$payload}')" >"$seed_ack"
jq -e 'type=="object" and keys==["offset","partition","topic"] and .topic=="product-search-revisions" and .partition==0 and (.offset|type)=="number" and (.offset|floor)==.offset and .offset>=0' "$seed_ack" >/dev/null
seed_topic="$(jq -r .topic "$seed_ack")";seed_partition="$(jq -r .partition "$seed_ack")";seed_offset="$(jq -r .offset "$seed_ack")"
"${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-console-consumer.sh --bootstrap-server kafka:9092 --topic "$seed_topic" --partition "$seed_partition" --offset "$seed_offset" --max-messages 1 --timeout-ms 10000 >"$seed_record"
bash "$root/scenarios/scripts/assert-retention-seed.sh" "$seed_ack" "$seed_record"
"$root/scenarios/scripts/wait-condition.sh" 'consumer commits seed event' 60 1 bash -c 'docker compose -p "$1" -f "$2" exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:9092 --group product-search-sync-v1 --describe 2>/dev/null|awk '\''$2=="product-search-revisions"&&$4~/^[0-9]+$/{found=1}END{exit !found}'\''' _ "$project" "$root/infra/compose.yaml"

snapshot(){
  "${compose[@]}" exec -T -e MYSQL_PWD="$MYSQL_PWD" mysql mysql -N -B -uroot -e 'SELECT @@GLOBAL.binlog_expire_logs_seconds;SHOW BINARY LOGS'|sha256sum
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-configs.sh --bootstrap-server kafka:9092 --entity-type topics --entity-name product-search-revisions --describe|sha256sum
  "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server kafka:9092 --group product-search-sync-v1 --describe 2>/dev/null|sha256sum
  "${compose[@]}" ps --format json|jq -sS '[.[]|{Service,State}]'|sha256sum
}
before_negative="$(snapshot)"
set +e
M6_RETENTION_DESTRUCTIVE_ACK= SCENARIO_STATE_DIR="$tmp/noack" bash "$root/scenarios/scripts/fault-retention.sh" apply mysql >/dev/null 2>&1;noack_rc=$?
SCENARIO_PROVENANCE_FILE="$tmp/missing" SCENARIO_STATE_DIR="$tmp/nomarker" bash "$root/scenarios/scripts/fault-retention.sh" apply mysql >/dev/null 2>&1;marker_rc=$?
COMPOSE_PROJECT_NAME=shared-project SCENARIO_STATE_DIR="$tmp/wrong-project" bash "$root/scenarios/scripts/fault-retention.sh" apply mysql >/dev/null 2>&1;project_rc=$?
set -e
test "$noack_rc" -eq 64;test "$marker_rc" -eq 64;test "$project_rc" -eq 64
test ! -e "$tmp/noack";test ! -e "$tmp/nomarker";test ! -e "$tmp/wrong-project";test ! -e "$cleanup"
test "$(snapshot)" = "$before_negative"

export SCENARIO_STATE_DIR="$tmp/mysql";bash "$root/scenarios/scripts/fault-retention.sh" apply mysql >"$tmp/mysql-result.json"
jq -e '.recorded_present==false' "$tmp/mysql-result.json" >/dev/null
jq -e '. as $s|.action=="safe-old-file-purge-confirmed" and .before_files==(.before_files|sort) and .after_files==(.after_files|sort) and (.before_files|index($s.recorded_old))!=null and (.after_files|index($s.recorded_old))==null and .current_after!=.recorded_old' "$SCENARIO_STATE_DIR/mysql-retention.json" >/dev/null

config_before="$("${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-configs.sh --bootstrap-server kafka:9092 --entity-type topics --entity-name product-search-revisions --describe|sed 's/^.*Configs: //')"
export SCENARIO_STATE_DIR="$tmp/kafka";bash "$root/scenarios/scripts/fault-retention.sh" apply kafka >"$tmp/kafka-result.json"
jq -e '.gap==true' "$tmp/kafka-result.json" >/dev/null
jq -e '. as $s|.action=="delete-records-confirmed" and (.after.beginning[($s.partition|tostring)]>$s.captured_committed)' "$SCENARIO_STATE_DIR/kafka-retention.json" >/dev/null
config_after="$("${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-configs.sh --bootstrap-server kafka:9092 --entity-type topics --entity-name product-search-revisions --describe|sed 's/^.*Configs: //')";test "$config_after" = "$config_before"
bash "$root/tests/contracts/no-evidence-secrets.sh" "$cleanup" >/dev/null
! grep -Eq 'MYSQL_PWD|_PWD|rootpass|eval' "$cleanup"
bash "$root/scenarios/scripts/fault-retention.sh" remove kafka >/dev/null
printf 'M6 real dedicated retention gaps contract passed\n'
