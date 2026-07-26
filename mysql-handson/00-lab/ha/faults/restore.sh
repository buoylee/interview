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

restore_timeout() {
  local timeout="${MYSQL_HA_RESTORE_TIMEOUT_SECONDS:-90}"
  [[ "$timeout" =~ ^[1-9][0-9]*$ ]] \
    || die "MYSQL_HA_RESTORE_TIMEOUT_SECONDS must be a positive integer"
  printf '%s\n' "$timeout"
}

wait_for_mysql() {
  local member="$1" timeout="$2" deadline
  validate_db_name "$member"
  deadline=$((SECONDS + timeout))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if "${DC[@]}" exec -T "$member" mysqladmin ping -uroot -p"$ROOT_PASSWORD" --silent; then
      return 0
    fi
    sleep 1
  done
  return 1
}

gtid_executed_hex() {
  local member="$1" value
  value="$(query_member "$member" 'SELECT HEX(@@GLOBAL.gtid_executed)')" \
    || die "could not read GTID set from $member"
  validate_gtid_hex "$value" || die "invalid GTID hex from $member"
  printf '%s\n' "$value"
}

prove_quorum_recovery_seed() {
  local seed="$1" out="$2" seed_hex member member_hex waited subset
  assert_db_target "$seed"
  seed_hex="$(gtid_executed_hex "$seed")"
  printf '%s\n' "$seed" > "$out-seed.txt"
  : > "$out-gtid-before.jsonl"
  : > "$out-gtid-subset.jsonl"
  for member in db1 db2 db3; do
    member_hex="$(gtid_executed_hex "$member")"
    printf '{"member":"%s","gtidExecutedHex":"%s"}\n' \
      "$member" "$member_hex" >> "$out-gtid-before.jsonl"
    waited="$(query_member "$member" \
      "SELECT WAIT_FOR_EXECUTED_GTID_SET(CONVERT(UNHEX('$seed_hex') USING utf8mb4), 30)")" \
      || die "GTID barrier failed on $member"
    [ "$waited" = 0 ] || die "$member does not contain candidate seed GTIDs"
    subset="$(query_member "$seed" \
      "SELECT GTID_SUBSET(CONVERT(UNHEX('$member_hex') USING utf8mb4), CONVERT(UNHEX('$seed_hex') USING utf8mb4))")" \
      || die "GTID subset check failed for $member"
    case "$subset" in 0|1) ;; *) die "invalid GTID subset result for $member" ;; esac
    printf '{"member":"%s","containsSeed":true,"subsetOfSeed":%s}\n' \
      "$member" "$subset" >> "$out-gtid-subset.jsonl"
    [ "$subset" = 1 ] || die "candidate seed does not contain all GTIDs from $member"
  done
}

stop_group_replication() {
  local out="$1" member state stop_status stop_output
  : > "$out-group-stopped.jsonl"
  for member in db1 db2 db3; do
    stop_output="$out-stop-$member.txt"
    stop_status=0
    "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
      -e 'STOP GROUP_REPLICATION' > "$stop_output" 2>&1 \
      || stop_status=$?
    if [ "$stop_status" -ne 0 ]; then
      state="$(query_member "$member" \
        "SELECT COALESCE((SELECT MEMBER_STATE FROM performance_schema.replication_group_members WHERE MEMBER_ID = @@server_uuid), 'MISSING')")" \
        || die "could not verify Group Replication state on $member"
      case "$state" in OFFLINE|MISSING) ;; *) die "could not stop Group Replication on $member" ;; esac
    fi
    state="$(query_member "$member" \
      "SELECT COALESCE((SELECT MEMBER_STATE FROM performance_schema.replication_group_members WHERE MEMBER_ID = @@server_uuid), 'MISSING')")" \
      || die "could not verify Group Replication stopped on $member"
    case "$state" in OFFLINE|MISSING) ;; *) die "Group Replication is still active on $member" ;; esac
    printf '{"member":"%s","stopCommandStatus":%s,"groupReplicationStopped":true,"memberState":"%s"}\n' \
      "$member" "$stop_status" "$state" >> "$out-group-stopped.jsonl"
  done
}

run_quorum_reboot() {
  local seed="$1" out="$2"
  "${DC[@]}" run --rm -e MYSQL_SEED="$seed" -e MYSQL_REBOOT_DRY_RUN=1 shell \
    mysqlsh --js --file=/bootstrap/reboot.js 2>&1 | tee "$out-reboot-dry-run.txt"
  grep -Fx \
    "{\"dryRun\":true,\"cluster\":\"haLabCluster\",\"seed\":\"$seed\",\"ok\":true}" \
    "$out-reboot-dry-run.txt" >/dev/null \
    || die "complete-outage dry-run did not return the expected success report"
  "${DC[@]}" run --rm -e MYSQL_SEED="$seed" -e MYSQL_REBOOT_DRY_RUN=0 shell \
    mysqlsh --js --file=/bootstrap/reboot.js 2>&1 | tee "$out-reboot-actual.txt"
}

wait_for_quorum_topology() {
  local seed="$1" timeout="$2" deadline topology
  deadline=$((SECONDS + timeout))
  while [ "$SECONDS" -lt "$deadline" ]; do
    if topology="$(query_member "$seed" \
      "SELECT COUNT(*), SUM(MEMBER_ROLE = 'PRIMARY') FROM performance_schema.replication_group_members WHERE MEMBER_STATE = 'ONLINE'" 2>/dev/null)" \
      && [ "$topology" = $'3\t1' ]; then
      printf '%s\n' "$topology"
      return 0
    fi
    sleep 1
  done
  return 1
}

quorum_writable_primary() {
  local seed="$1" primary writable
  primary="$(query_member "$seed" \
    "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_STATE = 'ONLINE' AND MEMBER_ROLE = 'PRIMARY'")" \
    || return 1
  validate_db_name "$primary" || return 1
  writable="$(query_member "$primary" \
    'SELECT @@GLOBAL.read_only, @@GLOBAL.super_read_only, @@GLOBAL.offline_mode')" \
    || return 1
  [ "$writable" = $'0\t0\t0' ] || return 1
  printf '%s\n' "$primary"
}

probe_router_rollback() {
  local out="$1" timeout="$2" probe_id remaining
  wait_for_router router-a "$timeout" || die "router-a did not accept traffic after quorum recovery"
  probe_id="quorum-recovery-probe-$(date +%s)-$$"
  "${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -e \
    "START TRANSACTION; INSERT INTO ha_lab.orders (request_id, payload, via_router, written_by) VALUES ('$probe_id', JSON_OBJECT('probe', 'quorum-recovery'), 'router-a', 'quorum-recovery'); ROLLBACK;"
  remaining="$("${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse \
    "SELECT COUNT(*) FROM ha_lab.orders WHERE request_id = '$probe_id'")" \
    || die "could not verify Router rollback probe"
  [ "$remaining" = 0 ] || die "Router rollback probe left residue or returned malformed output"
  printf '{"requestId":"%s","remainingRows":0,"rolledBack":true}\n' \
    "$probe_id" > "$out-router-rollback-probe.json"
}

restore_quorum_loss() {
  local timeout out member primary
  timeout="$(restore_timeout)"
  out="$HA_ROOT/evidence/quorum-recovery"
  record_event quorum_restore_begin "$SCENARIO" "$TARGETS"
  for suffix in seed.txt gtid-before.jsonl gtid-subset.jsonl group-stopped.jsonl reboot-dry-run.txt reboot-actual.txt topology.txt writable-primary.txt router-rollback-probe.json; do
    rm -f "$out-$suffix"
  done
  for member in db1 db2 db3; do rm -f "$out-stop-$member.txt"; done
  for member in "${STATE_TARGETS[@]}"; do
    docker update --restart=always "mysql-ha-$member" >/dev/null
    "${DC[@]}" up -d "$member"
  done
  for member in db1 db2 db3; do
    wait_for_mysql "$member" "$timeout" || die "member did not become reachable: $member"
  done
  prove_quorum_recovery_seed "$TARGET" "$out"
  stop_group_replication "$out"
  run_quorum_reboot "$TARGET" "$out"
  wait_for_quorum_topology "$TARGET" "$timeout" > "$out-topology.txt" \
    || die "cluster did not recover exactly three ONLINE members and one Primary"
  primary="$(quorum_writable_primary "$TARGET")" \
    || die "recovered cluster does not have exactly one writable Primary"
  printf '%s\n' "$primary" > "$out-writable-primary.txt"
  probe_router_rollback "$out" "$timeout"
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
    restore_quorum_loss
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

[ "$SCENARIO" = quorum-loss ] || wait_for_online 3 \
  || die "cluster did not return to three ONLINE members"
record_event fault_end "$SCENARIO" "${TARGET:-$TARGETS}"
rm -f "$STATE"
