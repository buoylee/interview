#!/usr/bin/env bash
set -euo pipefail
source "$(dirname "$0")/lib.sh"

scenario="${1:?usage: inject.sh SCENARIO}"
validate_scenario "$scenario"
[ ! -e "$STATE" ] || die "existing fault state requires restore: $STATE"
target=""
targets=""
old_flow_thresholds=""
quorum_targets=()

write_state() {
  local temporary_state="$STATE.tmp.$$"
  {
    printf 'SCENARIO=%s\n' "$scenario"
    printf 'TARGET=%s\n' "$target"
    printf 'TARGETS=%s\n' "$targets"
    printf 'OLD_FLOW_THRESHOLDS=%s\n' "$old_flow_thresholds"
  } > "$temporary_state"
  mv "$temporary_state" "$STATE"
}

member_threshold() {
  local member="$1" value
  value="$("${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" -Nse \
    'SELECT @@group_replication_flow_control_applier_threshold')" \
    || die "could not read flow-control threshold from $member"
  [[ "$value" =~ ^[0-9]+$ ]] || die "invalid flow-control threshold from $member"
  printf '%s\n' "$value"
}

wait_for_quorum_blocked() {
  local member="$1"
  local timeout="${MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS:-30}"
  local deadline values offline_mode super_read_only member_state

  validate_db_name "$member"
  [[ "$timeout" =~ ^[1-9][0-9]*$ ]] \
    || die "MYSQL_HA_QUORUM_BLOCK_TIMEOUT_SECONDS must be a positive integer"

  # The 30-second production default comfortably exceeds the Lab's configured
  # detection plus 5-second unreachable-majority timeout. Tests may shorten it.
  deadline=$((SECONDS + timeout))
  while [ "$SECONDS" -lt "$deadline" ]; do
    values="$(
      "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" -Nse \
        "SELECT @@offline_mode, @@super_read_only, COALESCE((SELECT MEMBER_STATE FROM performance_schema.replication_group_members WHERE MEMBER_ID = @@server_uuid), 'MISSING')" \
        2>/dev/null || true
    )"
    if [ -n "$values" ]; then
      read -r offline_mode super_read_only member_state <<< "$values"
      case "$offline_mode:$super_read_only" in
        0:1|1:0|1:1)
          record_event quorum_blocked "$scenario" "$member"
          return 0
          ;;
        0:0) ;;
      esac
    fi
    sleep 1
  done

  die "Primary was not fenced before quorum-loss deadline: $member"
}

# Read-only preparation and validation must finish before the first event or mutation.
case "$scenario" in
  planned-switchover)
    old_primary="$(primary_member)"
    target=db2
    [ "$old_primary" = db2 ] && target=db3
    assert_db_target "$old_primary"
    assert_db_target "$target"
    ;;
  primary-crash|primary-partition)
    target="$(primary_member)"
    assert_db_target "$target"
    [ "$scenario" != primary-partition ] || assert_ha_network
    ;;
  quorum-loss)
    target="$(primary_member)"
    while IFS= read -r member; do
      quorum_targets+=("$member")
    done < <(secondary_members)
    [ "${#quorum_targets[@]}" -eq 2 ] || die "quorum-loss requires exactly two ONLINE secondaries"
    [ "${quorum_targets[0]}" != "${quorum_targets[1]}" ] || die "quorum-loss secondaries must be distinct"
    assert_db_target "$target"
    for member in "${quorum_targets[@]}"; do
      assert_db_target "$member"
      [ "$member" != "$target" ] || die "quorum-loss target is not a secondary"
    done
    targets="${quorum_targets[0]},${quorum_targets[1]}"
    ;;
  slow-member)
    target=db3
    [ "$(primary_member)" = db3 ] && target=db2
    assert_db_target "$target"
    for member in db1 db2 db3; do
      assert_db_target "$member"
      threshold="$(member_threshold "$member")"
      old_flow_thresholds="${old_flow_thresholds:+$old_flow_thresholds,}$member:$threshold"
    done
    ;;
  router-failure)
    target=router-a
    assert_router_target "$target"
    ;;
  member-rejoin)
    target="$(secondary_members | head -n1)"
    assert_db_target "$target"
    ;;
esac

record_event fault_begin "$scenario" "$target"

case "$scenario" in
  planned-switchover)
    write_state
    "${DC[@]}" run --rm -e MYSQL_SEED="$old_primary" -e MYSQL_TARGET_MEMBER="$target" \
      shell mysqlsh --js --file=/bootstrap/set-primary.js
    ;;
  primary-crash)
    write_state
    docker update --restart=no "mysql-ha-$target" >/dev/null
    "${DC[@]}" kill "$target"
    ;;
  primary-partition)
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
    write_state
    "${DC[@]}" stop "${quorum_targets[@]}"
    ;;
  slow-member)
    write_state
    for member in db1 db2 db3; do
      "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
        -e "SET GLOBAL group_replication_flow_control_applier_threshold=10"
    done
    docker update --cpus 0.10 "mysql-ha-$target" >/dev/null
    ;;
  router-failure)
    write_state
    "${DC[@]}" stop router-a
    ;;
  member-rejoin)
    write_state
    docker update --restart=no "mysql-ha-$target" >/dev/null
    "${DC[@]}" kill "$target"
    ;;
esac

record_event fault_active "$scenario" "${target:-$targets}"

if [ "$scenario" = quorum-loss ]; then
  wait_for_quorum_blocked "$target"
fi
