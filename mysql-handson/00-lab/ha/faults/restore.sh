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
  local seed="$1" out="$2" phase="$3" seed_hex member member_hex waited subset
  assert_db_target "$seed"
  seed_hex="$(gtid_executed_hex "$seed")"
  printf '%s\n' "$seed" > "$out-seed.txt"
  printf '%s\n' "$seed_hex" > "$out-gtid-$phase-seed-hex.txt"
  : > "$out-gtid-$phase.jsonl"
  for member in db1 db2 db3; do
    waited="$(query_member "$member" \
      "SELECT WAIT_FOR_EXECUTED_GTID_SET(CONVERT(UNHEX('$seed_hex') USING utf8mb4), 30)")" \
      || die "GTID barrier failed on $member"
    [ "$waited" = 0 ] || die "$member does not contain candidate seed GTIDs"
    member_hex="$(gtid_executed_hex "$member")"
    subset="$(query_member "$seed" \
      "SELECT GTID_SUBSET(CONVERT(UNHEX('$member_hex') USING utf8mb4), CONVERT(UNHEX('$seed_hex') USING utf8mb4))")" \
      || die "GTID subset check failed for $member"
    case "$subset" in 0|1) ;; *) die "invalid GTID subset result for $member" ;; esac
    printf '{"phase":"%s","member":"%s","seedGtidHex":"%s","memberGtidHexAfterWait":"%s","containsSeed":true,"subsetOfSeed":%s}\n' \
      "$phase" "$member" "$seed_hex" "$member_hex" "$subset" >> "$out-gtid-$phase.jsonl"
    [ "$subset" = 1 ] || die "candidate seed does not contain all GTIDs from $member"
  done
}

quiesce_routers() {
  local out="$1" timeout="$2" router
  for router in router-a router-b; do assert_router_target "$router"; done
  "${DC[@]}" stop router-a router-b \
    > "$out-router-stop.stdout.txt" 2> "$out-router-stop.stderr.txt" \
    || die "could not stop both Routers before quorum recovery"
  : > "$out-router-stopped.jsonl"
  for router in router-a router-b; do
    wait_for_router_stopped "$router" "$timeout" \
      || die "$router did not reach stopped state"
    printf '{"router":"%s","running":false}\n' "$router" >> "$out-router-stopped.jsonl"
  done
}

apply_member_fences() {
  local out="$1" member
  for member in db1 db2 db3; do
    "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
      -e 'SET GLOBAL read_only=ON; SET GLOBAL super_read_only=ON; SET GLOBAL offline_mode=ON' \
      > "$out-fence-$member.stdout.txt" 2> "$out-fence-$member.stderr.txt" \
      || die "could not fence writes on $member"
  done
}

verify_member_fences() {
  local out="$1" phase="$2" member values
  : > "$out-fence-$phase.jsonl"
  for member in db1 db2 db3; do
    values="$(query_member "$member" \
      'SELECT @@GLOBAL.read_only, @@GLOBAL.super_read_only, @@GLOBAL.offline_mode')" \
      || die "could not verify write fence on $member"
    [ "$values" = $'1\t1\t1' ] || die "write fence is not exact on $member"
    printf '{"phase":"%s","member":"%s","readOnly":1,"superReadOnly":1,"offlineMode":1}\n' \
      "$phase" "$member" >> "$out-fence-$phase.jsonl"
  done
}

stop_group_replication() {
  local out="$1" member state stop_status stdout_path stderr_path
  : > "$out-group-stopped.jsonl"
  : > "$out-stop-status.jsonl"
  for member in db1 db2 db3; do
    stdout_path="$out-stop-$member.stdout.txt"
    stderr_path="$out-stop-$member.stderr.txt"
    stop_status=0
    "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" \
      -e 'STOP GROUP_REPLICATION' > "$stdout_path" 2> "$stderr_path" \
      || stop_status=$?
    printf '{"member":"%s","exitStatus":%s}\n' \
      "$member" "$stop_status" >> "$out-stop-status.jsonl"
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

restore_post_reboot_access() {
  local seed="$1" out="$2" member role values primary="" sql
  : > "$out-post-access.jsonl"
  for member in db1 db2 db3; do
    role="$(query_member "$seed" \
      "SELECT MEMBER_ROLE FROM performance_schema.replication_group_members WHERE MEMBER_HOST = '$member' AND MEMBER_STATE = 'ONLINE'")" \
      || die "could not identify recovered role for $member"
    case "$role" in
      PRIMARY)
        [ -z "$primary" ] || die "recovered cluster has more than one Primary"
        primary="$member"
        sql='SET GLOBAL super_read_only=OFF; SET GLOBAL read_only=OFF; SET GLOBAL offline_mode=OFF'
        ;;
      SECONDARY)
        sql='SET GLOBAL read_only=ON; SET GLOBAL super_read_only=ON; SET GLOBAL offline_mode=OFF'
        ;;
      *) die "invalid recovered role for $member" ;;
    esac
    "${DC[@]}" exec -T "$member" mysql -uroot -p"$ROOT_PASSWORD" -e "$sql" \
      > "$out-post-access-$member.stdout.txt" 2> "$out-post-access-$member.stderr.txt" \
      || die "could not restore post-reboot access on $member"
    values="$(query_member "$member" \
      'SELECT @@GLOBAL.read_only, @@GLOBAL.super_read_only, @@GLOBAL.offline_mode')" \
      || die "could not verify post-reboot access on $member"
    if [ "$role" = PRIMARY ]; then
      [ "$values" = $'0\t0\t0' ] || die "recovered Primary is not writable"
      printf '{"member":"%s","role":"PRIMARY","readOnly":0,"superReadOnly":0,"offlineMode":0}\n' \
        "$member" >> "$out-post-access.jsonl"
    else
      [ "$values" = $'1\t1\t0' ] || die "recovered Secondary is not read-only"
      printf '{"member":"%s","role":"SECONDARY","readOnly":1,"superReadOnly":1,"offlineMode":0}\n' \
        "$member" >> "$out-post-access.jsonl"
    fi
  done
  [ -n "$primary" ] || die "recovered cluster has no Primary"
  printf '%s\n' "$primary"
}

start_routers() {
  local out="$1" timeout="$2" router
  "${DC[@]}" up -d router-a router-b \
    > "$out-router-start.stdout.txt" 2> "$out-router-start.stderr.txt" \
    || die "could not start both Routers after quorum recovery"
  : > "$out-router-ready.jsonl"
  for router in router-a router-b; do
    wait_for_router "$router" "$timeout" || die "$router did not accept traffic"
    printf '{"router":"%s","ready":true}\n' "$router" >> "$out-router-ready.jsonl"
  done
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
  for suffix in seed.txt gtid-before.jsonl gtid-subset.jsonl gtid-initial-seed-hex.txt gtid-final-seed-hex.txt gtid-initial.jsonl gtid-final.jsonl fence-initial.jsonl fence-final.jsonl group-stopped.jsonl stop-status.jsonl reboot-dry-run.txt reboot-actual.txt topology.txt writable-primary.txt post-access.jsonl router-stopped.jsonl router-ready.jsonl router-rollback-probe.json router-stop.stdout.txt router-stop.stderr.txt router-start.stdout.txt router-start.stderr.txt; do
    rm -f "$out-$suffix"
  done
  for member in db1 db2 db3; do
    rm -f "$out-stop-$member.txt" \
      "$out-stop-$member.stdout.txt" "$out-stop-$member.stderr.txt" \
      "$out-fence-$member.stdout.txt" "$out-fence-$member.stderr.txt" \
      "$out-post-access-$member.stdout.txt" "$out-post-access-$member.stderr.txt"
  done
  quiesce_routers "$out" "$timeout"
  for member in "${STATE_TARGETS[@]}"; do
    docker update --restart=always "mysql-ha-$member" >/dev/null
    "${DC[@]}" up -d "$member"
  done
  for member in db1 db2 db3; do
    wait_for_mysql "$member" "$timeout" || die "member did not become reachable: $member"
  done
  apply_member_fences "$out"
  verify_member_fences "$out" initial
  prove_quorum_recovery_seed "$TARGET" "$out" initial
  prove_quorum_recovery_seed "$TARGET" "$out" final
  verify_member_fences "$out" final
  stop_group_replication "$out"
  run_quorum_reboot "$TARGET" "$out"
  wait_for_quorum_topology "$TARGET" "$timeout" > "$out-topology.txt" \
    || die "cluster did not recover exactly three ONLINE members and one Primary"
  primary="$(restore_post_reboot_access "$TARGET" "$out")"
  printf '%s\n' "$primary" > "$out-writable-primary.txt"
  start_routers "$out" "$timeout"
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
