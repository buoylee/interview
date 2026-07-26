#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

scenario="${1:?usage: inject.sh SCENARIO}"
target=""
targets=""
record_event fault_begin "$scenario" pending

write_state() {
  [ ! -e "$STATE" ] || die "existing fault state requires restore: $STATE"
  local temporary_state="$STATE.tmp.$$"
  {
    printf 'SCENARIO=%q\n' "$scenario"
    printf 'TARGET=%q\n' "$target"
    printf 'TARGETS=%q\n' "$targets"
    printf 'OLD_FLOW_THRESHOLD=%q\n' "${old_threshold:-25000}"
  } > "$temporary_state"
  mv "$temporary_state" "$STATE"
}

case "$scenario" in
  planned-switchover)
    old_primary="$(primary_member)"
    target=db2
    [ "$old_primary" = db2 ] && target=db3
    assert_db_target "$old_primary"
    assert_db_target "$target"
    write_state
    "${DC[@]}" run --rm -e MYSQL_SEED="$old_primary" -e MYSQL_TARGET_MEMBER="$target" \
      shell mysqlsh --js --file=/bootstrap/set-primary.js
    ;;
  primary-crash)
    target="$(primary_member)"
    assert_db_target "$target"
    write_state
    docker update --restart=no "mysql-ha-$target" >/dev/null
    "${DC[@]}" kill "$target"
    ;;
  primary-partition)
    target="$(primary_member)"
    assert_db_target "$target"
    assert_ha_network
    write_state
    docker network disconnect --force "$NETWORK" "mysql-ha-$target"
    offline_mode=0
    super_read_only=0
    for _ in $(seq 1 20); do
      values="$(
        "${DC[@]}" exec -T "$target" mysql -uroot -p"$ROOT_PASSWORD" -Nse \
          "SELECT @@offline_mode, @@super_read_only" 2>/dev/null || true
      )"
      if [ -n "$values" ]; then
        read -r offline_mode super_read_only <<< "$values"
        if [ "$offline_mode" = 1 ] || [ "$super_read_only" = 1 ]; then break; fi
      fi
      sleep 1
    done
    if [ "$offline_mode" != 1 ] && [ "$super_read_only" != 1 ]; then
      die "isolated Primary was not fenced"
    fi
    if "${DC[@]}" exec -T "$target" mysql -h127.0.0.1 -uha_app -pha-app ha_lab \
      -e "INSERT INTO orders(request_id,payload,via_router) VALUES ('fence-probe-$target', JSON_OBJECT('probe',true), 'direct')"; then
      die "fenced Primary accepted an application write"
    fi
    printf '{"target":"%s","offline_mode":%s,"super_read_only":%s,"write_rejected":true}\n' \
      "$target" "$offline_mode" "$super_read_only" > "$HA_ROOT/evidence/fencing.json"
    ;;
  quorum-loss)
    target="$(primary_member)"
    targets="$(secondary_members | tr '\n' ' ' | xargs)"
    assert_db_target "$target"
    for member in $targets; do assert_db_target "$member"; done
    write_state
    "${DC[@]}" stop $targets
    # Do not wait past the Lab's 5-second unreachable-majority timeout here.
    # The running workload proves commits cannot complete without quorum.
    ;;
  slow-member)
    target=db3
    [ "$(primary_member)" = db3 ] && target=db2
    assert_db_target "$target"
    old_threshold="$(query_group 'SELECT @@group_replication_flow_control_applier_threshold')"
    write_state
    for member in db1 db2 db3; do
      assert_db_target "$member"
      "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
        -e "SET GLOBAL group_replication_flow_control_applier_threshold=10"
    done
    docker update --cpus 0.10 "mysql-ha-$target" >/dev/null
    ;;
  router-failure)
    target=router-a
    assert_router_target "$target"
    write_state
    "${DC[@]}" stop router-a
    ;;
  member-rejoin)
    target="$(secondary_members | head -n1)"
    assert_db_target "$target"
    write_state
    docker update --restart=no "mysql-ha-$target" >/dev/null
    "${DC[@]}" kill "$target"
    ;;
  *)
    echo "unsupported scenario: $scenario" >&2
    exit 2
    ;;
esac

record_event fault_active "$scenario" "${target:-$targets}"
