#!/usr/bin/env bash
set -euo pipefail

HA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DC=(docker compose --project-name mysql-ha --file "$HA_ROOT/compose.yml")
NETWORK=mysql-ha-net
EVENTS="$HA_ROOT/evidence/events.jsonl"
STATE="$HA_ROOT/evidence/fault-state.env"
ROOT_PASSWORD="${MYSQL_ROOT_PASSWORD:-ha-root}"

mkdir -p "$HA_ROOT/evidence"

now_utc() {
  python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat(timespec="microseconds"))'
}

record_event() {
  local phase="$1" scenario="$2" target="$3"
  printf '{"at":"%s","phase":"%s","scenario":"%s","target":"%s"}\n' \
    "$(now_utc)" "$phase" "$scenario" "$target" >> "$EVENTS"
}

die() {
  echo "$*" >&2
  exit 1
}

validate_scenario() {
  case "$1" in
    planned-switchover|primary-crash|primary-partition|quorum-loss|slow-member|router-failure|member-rejoin) ;;
    *) die "unsupported scenario: $1" ;;
  esac
}

validate_db_name() {
  case "$1" in db1|db2|db3) ;; *) die "invalid database target: $1" ;; esac
}

validate_router_name() {
  case "$1" in router-a|router-b) ;; *) die "invalid router target: $1" ;; esac
}

assert_project_container() {
  local container="$1" project
  project="$(docker inspect --format '{{ index .Config.Labels "com.docker.compose.project" }}' "$container" 2>/dev/null)" \
    || die "container not found: $container"
  [ "$project" = mysql-ha ] || die "container is not owned by mysql-ha: $container"
}

assert_ha_network() {
  local project
  project="$(docker network inspect --format '{{ index .Labels "com.docker.compose.project" }}' "$NETWORK" 2>/dev/null)" \
    || die "network not found: $NETWORK"
  [ "$project" = mysql-ha ] || die "network is not owned by mysql-ha: $NETWORK"
}

assert_db_target() {
  validate_db_name "$1"
  assert_project_container "mysql-ha-$1"
}

assert_router_target() {
  validate_router_name "$1"
  assert_project_container "mysql-ha-$1"
}

network_connected() {
  local container="$1"
  docker inspect --format '{{range $name, $_ := .NetworkSettings.Networks}}{{println $name}}{{end}}' "$container" \
    | grep -Fx "$NETWORK" >/dev/null
}

wait_for_router() {
  local router="$1"
  local attempts="${2:-60}"
  assert_router_target "$router"
  for _ in $(seq 1 "$attempts"); do
    if "${DC[@]}" run --rm shell mysqladmin ping -h"$router" -P6446 -uroot -p"$ROOT_PASSWORD" --silent; then
      return 0
    fi
    sleep 1
  done
  return 1
}

parse_fault_state() {
  local line key value
  local seen_scenario=0 seen_target=0 seen_targets=0 seen_thresholds=0
  SCENARIO=""
  TARGET=""
  TARGETS=""
  OLD_FLOW_THRESHOLDS=""
  [ -f "$STATE" ] || { echo "missing fault state" >&2; return 2; }

  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      SCENARIO=*) key=SCENARIO; value="${line#SCENARIO=}" ;;
      TARGET=*) key=TARGET; value="${line#TARGET=}" ;;
      TARGETS=*) key=TARGETS; value="${line#TARGETS=}" ;;
      OLD_FLOW_THRESHOLDS=*) key=OLD_FLOW_THRESHOLDS; value="${line#OLD_FLOW_THRESHOLDS=}" ;;
      *) echo "invalid fault state entry" >&2; return 2 ;;
    esac
    case "$key" in
      SCENARIO) [ "$seen_scenario" -eq 0 ] || { echo "duplicate SCENARIO" >&2; return 2; }; SCENARIO="$value"; seen_scenario=1 ;;
      TARGET) [ "$seen_target" -eq 0 ] || { echo "duplicate TARGET" >&2; return 2; }; TARGET="$value"; seen_target=1 ;;
      TARGETS) [ "$seen_targets" -eq 0 ] || { echo "duplicate TARGETS" >&2; return 2; }; TARGETS="$value"; seen_targets=1 ;;
      OLD_FLOW_THRESHOLDS) [ "$seen_thresholds" -eq 0 ] || { echo "duplicate OLD_FLOW_THRESHOLDS" >&2; return 2; }; OLD_FLOW_THRESHOLDS="$value"; seen_thresholds=1 ;;
    esac
  done < "$STATE"
  [ "$seen_scenario" -eq 1 ] && [ "$seen_target" -eq 1 ] \
    && [ "$seen_targets" -eq 1 ] && [ "$seen_thresholds" -eq 1 ] \
    || { echo "fault state has missing keys" >&2; return 2; }
  validate_fault_state
}

validate_fault_state() {
  local entry member value
  validate_scenario "$SCENARIO"
  case "$SCENARIO" in
    planned-switchover|primary-crash|primary-partition|member-rejoin)
      validate_db_name "$TARGET"
      [ -z "$TARGETS" ] && [ -z "$OLD_FLOW_THRESHOLDS" ] \
        || die "unexpected recovery state values for $SCENARIO"
      ;;
    router-failure)
      [ "$TARGET" = router-a ] && [ -z "$TARGETS" ] && [ -z "$OLD_FLOW_THRESHOLDS" ] \
        || die "invalid router-failure recovery state"
      ;;
    quorum-loss)
      validate_db_name "$TARGET"
      [ -z "$OLD_FLOW_THRESHOLDS" ] || die "unexpected thresholds for quorum-loss"
      IFS=, read -r -a STATE_TARGETS <<< "$TARGETS"
      [ "${#STATE_TARGETS[@]}" -eq 2 ] || die "quorum-loss requires exactly two targets"
      validate_db_name "${STATE_TARGETS[0]}"
      validate_db_name "${STATE_TARGETS[1]}"
      [ "${STATE_TARGETS[0]}" != "${STATE_TARGETS[1]}" ] \
        && [ "$TARGET" != "${STATE_TARGETS[0]}" ] \
        && [ "$TARGET" != "${STATE_TARGETS[1]}" ] \
        || die "quorum-loss targets must be distinct secondaries"
      ;;
    slow-member)
      validate_db_name "$TARGET"
      [ -z "$TARGETS" ] || die "unexpected targets for slow-member"
      IFS=, read -r -a state_thresholds <<< "$OLD_FLOW_THRESHOLDS"
      [ "${#state_thresholds[@]}" -eq 3 ] || die "slow-member requires three saved thresholds"
      STATE_THRESHOLD_DB1=""
      STATE_THRESHOLD_DB2=""
      STATE_THRESHOLD_DB3=""
      for entry in "${state_thresholds[@]}"; do
        member="${entry%%:*}"
        value="${entry#*:}"
        [ "$member" != "$entry" ] && [[ "$value" =~ ^[0-9]+$ ]] \
          || die "invalid saved flow-control threshold"
        case "$member" in
          db1) [ -z "$STATE_THRESHOLD_DB1" ] || die "duplicate db1 threshold"; STATE_THRESHOLD_DB1="$value" ;;
          db2) [ -z "$STATE_THRESHOLD_DB2" ] || die "duplicate db2 threshold"; STATE_THRESHOLD_DB2="$value" ;;
          db3) [ -z "$STATE_THRESHOLD_DB3" ] || die "duplicate db3 threshold"; STATE_THRESHOLD_DB3="$value" ;;
          *) die "invalid threshold member: $member" ;;
        esac
      done
      [ -n "$STATE_THRESHOLD_DB1" ] && [ -n "$STATE_THRESHOLD_DB2" ] && [ -n "$STATE_THRESHOLD_DB3" ] \
        || die "missing saved flow-control threshold"
      ;;
  esac
}

query_group() {
  local sql="$1" seed output
  for seed in db1 db2 db3; do
    if output="$("${DC[@]}" exec -T "$seed" mysql -uroot -p"$ROOT_PASSWORD" -Nse "$sql" 2>/dev/null)"; then
      printf '%s\n' "$output"
      return 0
    fi
  done
  return 1
}

validate_member_query_output() {
  local mode="$1" output="$2" member seen="," count=0
  while IFS= read -r member; do
    [ -n "$member" ] || return 1
    validate_db_name "$member"
    case "$seen" in *",$member,"*) return 1 ;; esac
    seen="$seen$member,"
    count=$((count + 1))
  done <<< "$output"
  [ "$count" -gt 0 ] || return 1
  [ "$mode" != primary ] || [ "$count" -eq 1 ]
}

query_nonempty_group_members() {
  local mode="$1" sql="$2" seed output
  for seed in db1 db2 db3; do
    if output="$("${DC[@]}" exec -T "$seed" mysql -uroot -p"$ROOT_PASSWORD" -Nse "$sql" 2>/dev/null)" \
      && [ -n "$output" ] \
      && (validate_member_query_output "$mode" "$output") 2>/dev/null; then
      printf '%s\n' "$output"
      return 0
    fi
  done
  return 1
}

primary_member() {
  query_nonempty_group_members primary \
    "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='PRIMARY' AND MEMBER_STATE='ONLINE'"
}

secondary_members() {
  query_nonempty_group_members secondary \
    "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='SECONDARY' AND MEMBER_STATE='ONLINE' ORDER BY MEMBER_HOST"
}

wait_for_online() {
  local expected="$1" count
  for _ in $(seq 1 60); do
    count="$(query_group "SELECT COUNT(*) FROM performance_schema.replication_group_members WHERE MEMBER_STATE='ONLINE'" || true)"
    [ "$count" = "$expected" ] && return 0
    sleep 1
  done
  return 1
}

validate_gtid_hex() {
  local value="$1"
  case "$value" in ''|*[!0-9A-Fa-f]*) return 1 ;; esac
  [ $((${#value} % 2)) -eq 0 ]
}

query_member() {
  local member="$1" sql="$2"
  validate_db_name "$member"
  "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" -Nse "$sql"
}
