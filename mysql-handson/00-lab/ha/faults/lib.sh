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
  case "$1" in db1|db2|db3) ;; *) die "invalid database target: $1" ;; esac
  assert_project_container "mysql-ha-$1"
}

assert_router_target() {
  case "$1" in router-a|router-b) ;; *) die "invalid router target: $1" ;; esac
  assert_project_container "mysql-ha-$1"
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

primary_member() {
  query_group "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='PRIMARY' AND MEMBER_STATE='ONLINE'"
}

secondary_members() {
  query_group "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='SECONDARY' AND MEMBER_STATE='ONLINE' ORDER BY MEMBER_HOST"
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
