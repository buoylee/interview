#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
parse_fault_state

rejoin() {
  local target="$1" seed state
  assert_db_target "$target"
  docker update --restart=always "mysql-ha-$target" >/dev/null
  "${DC[@]}" up -d "$target"
  record_event rejoin_begin "$SCENARIO" "$target"
  for _ in $(seq 1 60); do
    if "${DC[@]}" exec -T "$target" mysqladmin ping -uroot -p"$ROOT_PASSWORD" --silent; then break; fi
    sleep 1
  done
  state="$(query_group "SELECT MEMBER_STATE FROM performance_schema.replication_group_members WHERE MEMBER_HOST='$target'" || true)"
  if [ "$state" != ONLINE ]; then
    seed="$(primary_member)"
    assert_db_target "$seed"
    "${DC[@]}" run --rm -e MYSQL_SEED="$seed" -e MYSQL_TARGET_MEMBER="$target" \
      shell mysqlsh --js --file=/bootstrap/rejoin.js
  fi
  for _ in $(seq 1 90); do
    state="$(query_group "SELECT MEMBER_STATE FROM performance_schema.replication_group_members WHERE MEMBER_HOST='$target'" || true)"
    [ "$state" = ONLINE ] && break
    sleep 1
  done
  [ "$state" = ONLINE ] || die "member did not return ONLINE: $target"
  record_event rejoin_online "$SCENARIO" "$target"
}

threshold_for() {
  case "$1" in
    db1) printf '%s\n' "$STATE_THRESHOLD_DB1" ;;
    db2) printf '%s\n' "$STATE_THRESHOLD_DB2" ;;
    db3) printf '%s\n' "$STATE_THRESHOLD_DB3" ;;
    *) die "invalid threshold member: $1" ;;
  esac
}

case "$SCENARIO" in
  planned-switchover) ;;
  primary-crash|member-rejoin) rejoin "$TARGET" ;;
  primary-partition)
    assert_db_target "$TARGET"
    assert_ha_network
    if ! network_connected "mysql-ha-$TARGET"; then
      docker network connect "$NETWORK" "mysql-ha-$TARGET" >/dev/null
    fi
    rejoin "$TARGET"
    ;;
  quorum-loss)
    record_event quorum_restore_begin "$SCENARIO" "$TARGETS"
    for member in "${STATE_TARGETS[@]}"; do rejoin "$member"; done
    ;;
  slow-member)
    assert_db_target "$TARGET"
    docker update --cpus 0 "mysql-ha-$TARGET" >/dev/null
    for member in db1 db2 db3; do
      assert_db_target "$member"
      "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
        -e "SET GLOBAL group_replication_flow_control_applier_threshold=$(threshold_for "$member")"
    done
    ;;
  router-failure)
    assert_router_target router-a
    "${DC[@]}" up -d router-a
    wait_for_router router-a || die "router-a did not accept traffic"
    ;;
esac

wait_for_online 3 || die "cluster did not return to three ONLINE members"
record_event fault_end "$SCENARIO" "${TARGET:-$TARGETS}"
rm -f "$STATE"
