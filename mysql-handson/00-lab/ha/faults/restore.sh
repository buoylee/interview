#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"
[ -f "$STATE" ] || { echo "missing fault state" >&2; exit 2; }
source "$STATE"

case "${SCENARIO:-}" in
  planned-switchover|primary-crash|primary-partition|quorum-loss|slow-member|router-failure|member-rejoin) ;;
  *) die "invalid recovery scenario in state" ;;
esac

rejoin() {
  local target="$1" seed state
  assert_db_target "$target"
  docker update --restart=on-failure "mysql-ha-$target" >/dev/null 2>&1 || true
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

case "$SCENARIO" in
  planned-switchover) ;;
  primary-crash|member-rejoin) rejoin "$TARGET" ;;
  primary-partition)
    assert_db_target "$TARGET"
    assert_ha_network
    docker network connect "$NETWORK" "mysql-ha-$TARGET" >/dev/null 2>&1 || true
    rejoin "$TARGET"
    ;;
  quorum-loss)
    record_event quorum_restore_begin "$SCENARIO" "$TARGETS"
    for member in $TARGETS; do rejoin "$member"; done
    ;;
  slow-member)
    assert_db_target "$TARGET"
    docker update --cpus 0 "mysql-ha-$TARGET" >/dev/null
    for member in db1 db2 db3; do
      assert_db_target "$member"
      "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
        -e "SET GLOBAL group_replication_flow_control_applier_threshold=$OLD_FLOW_THRESHOLD"
    done
    ;;
  router-failure)
    assert_router_target router-a
    "${DC[@]}" up -d router-a
    ;;
esac

wait_for_online 3 || die "cluster did not return to three ONLINE members"
record_event fault_end "$SCENARIO" "${TARGET:-$TARGETS}"
rm -f "$STATE"
