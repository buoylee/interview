#!/usr/bin/env bash
# Operator expectations:
# - `docker compose start` only starts processes; it does not recover a fully
#   stopped Group Replication cluster on its own.
# - First make every known member reachable. Before the outage this drill
#   proves all three applied the candidate Primary GTID set, saves that Primary
#   as the seed, then uses dryRun:true before the actual reboot.
# - The normal path never uses force:true: a lower-GTID or divergent member
#   must not be forced into becoming the seed.
# - Recovery evidence is one writable Primary, three ONLINE members, and the
#   same ordered business-ID set before and after recovery; running containers
#   alone are not success.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DC=(docker compose --project-name mysql-ha --file "$ROOT/compose.yml")
OUT="$ROOT/evidence/complete-outage"

now_utc() {
  python3 -c 'from datetime import datetime, timezone; print(datetime.now(timezone.utc).isoformat(timespec="microseconds"))'
}

record() {
  printf '{"at":"%s","phase":"%s"}\n' "$(now_utc)" "$1" >> "$OUT/events.jsonl"
}

validate_gtid_set() {
  case "$1" in ''|*[!0-9A-Fa-f,:-]*) return 1 ;; esac
}

validate_db_name() {
  case "$1" in db1|db2|db3) ;; *) return 1 ;; esac
}

gtid_executed() {
  local member="$1" value
  validate_db_name "$member"
  value="$("${DC[@]}" exec -T "$member" mysql -uroot -pha-root -Nse 'SELECT @@GLOBAL.gtid_executed')"
  validate_gtid_set "$value"
  printf '%s\n' "$value"
}

gtid_subset() {
  local member_gtid="$1" seed_gtid="$2" subset
  validate_gtid_set "$member_gtid"
  validate_gtid_set "$seed_gtid"
  subset="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse \
    "SELECT GTID_SUBSET('$member_gtid', '$seed_gtid')")"
  case "$subset" in 0|1) printf '%s\n' "$subset" ;; *) return 1 ;; esac
}

persisted_start_on_boot() {
  local member="$1" value
  value="$("${DC[@]}" exec -T "$member" mysql -uroot -pha-root -Nse \
    "SELECT VARIABLE_VALUE FROM performance_schema.persisted_variables WHERE VARIABLE_NAME = 'group_replication_start_on_boot'")"
  case "$value" in ON|OFF) printf '%s\n' "$value" ;; *) return 1 ;; esac
}

START_ON_BOOT_DB1=""
START_ON_BOOT_DB2=""
START_ON_BOOT_DB3=""

record_persisted_start_on_boot() {
  local output="$1" capture_original="${2:-0}" member value
  : > "$output"
  for member in db1 db2 db3; do
    value="$(persisted_start_on_boot "$member")"
    if [ "$capture_original" = 1 ]; then
      case "$member" in
        db1) START_ON_BOOT_DB1="$value" ;;
        db2) START_ON_BOOT_DB2="$value" ;;
        db3) START_ON_BOOT_DB3="$value" ;;
      esac
    fi
    printf '{"member":"%s","persistedStartOnBoot":"%s"}\n' "$member" "$value" >> "$output"
  done
}

set_member_persisted_start_on_boot() {
  local member="$1" value="$2"
  validate_db_name "$member"
  case "$value" in ON|OFF) ;; *) return 1 ;; esac
  "${DC[@]}" exec -T "$member" mysql -uroot -pha-root -e \
    "SET PERSIST_ONLY group_replication_start_on_boot = $value"
}

set_all_persisted_start_on_boot() {
  local value="$1" member
  for member in db1 db2 db3; do
    set_member_persisted_start_on_boot "$member" "$value"
  done
}

verify_persisted_start_on_boot() {
  local expected="$1" member
  for member in db1 db2 db3; do
    [ "$(persisted_start_on_boot "$member")" = "$expected" ]
  done
}

restore_persisted_start_on_boot() {
  set_member_persisted_start_on_boot db1 "$START_ON_BOOT_DB1"
  set_member_persisted_start_on_boot db2 "$START_ON_BOOT_DB2"
  set_member_persisted_start_on_boot db3 "$START_ON_BOOT_DB3"
}

verify_restored_start_on_boot() {
  [ "$(persisted_start_on_boot db1)" = "$START_ON_BOOT_DB1" ]
  [ "$(persisted_start_on_boot db2)" = "$START_ON_BOOT_DB2" ]
  [ "$(persisted_start_on_boot db3)" = "$START_ON_BOOT_DB3" ]
}

make -C "$ROOT" reset
mkdir -p "$OUT"
rm -f \
  "$OUT/events.jsonl" \
  "$OUT/reboot-dry-run.txt" \
  "$OUT/reboot-actual.txt" \
  "$OUT/seed.txt" \
  "$OUT/before-ids.txt" \
  "$OUT/after-ids.txt" \
  "$OUT/gtid-before.jsonl" \
  "$OUT/gtid-subset.jsonl" \
  "$OUT/router-rollback-probe.json" \
  "$OUT/final-status.json" \
  "$OUT/start-on-boot-before.jsonl" \
  "$OUT/start-on-boot-off.jsonl" \
  "$OUT/start-on-boot-after.jsonl"
make -C "$ROOT" up
make -C "$ROOT" workload-once N=20
make -C "$ROOT" verify

seed="$("${DC[@]}" exec -T db1 mysql -uroot -pha-root -Nse "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='PRIMARY' AND MEMBER_STATE='ONLINE'")"
validate_db_name "$seed"
printf '%s\n' "$seed" > "$OUT/seed.txt"
gtid="$(gtid_executed "$seed")"
: > "$OUT/gtid-before.jsonl"
: > "$OUT/gtid-subset.jsonl"
for member in db1 db2 db3; do
  member_gtid="$(gtid_executed "$member")"
  printf '{"member":"%s","gtidExecuted":"%s"}\n' "$member" "$member_gtid" >> "$OUT/gtid-before.jsonl"
  waited="$("${DC[@]}" exec -T "$member" mysql -uroot -pha-root -Nse "SELECT WAIT_FOR_EXECUTED_GTID_SET('$gtid', 30)")"
  [ "$waited" = 0 ]
  subset="$(gtid_subset "$member_gtid" "$gtid")"
  printf '{"member":"%s","subsetOfSeed":%s}\n' "$member" "$subset" >> "$OUT/gtid-subset.jsonl"
  [ "$subset" = 1 ]
done
"${DC[@]}" stop router-a router-b
"${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse \
  'SELECT request_id FROM ha_lab.orders ORDER BY request_id' > "$OUT/before-ids.txt"
record_persisted_start_on_boot "$OUT/start-on-boot-before.jsonl" 1
set_all_persisted_start_on_boot OFF
record_persisted_start_on_boot "$OUT/start-on-boot-off.jsonl"
verify_persisted_start_on_boot OFF

record outage_begin
"${DC[@]}" stop db1 db2 db3
"${DC[@]}" up -d db1 db2 db3
for member in db1 db2 db3; do
  until "${DC[@]}" exec -T "$member" mysqladmin ping -uroot -pha-root --silent; do sleep 2; done
done

record dry_run_begin
"${DC[@]}" run --rm -e MYSQL_SEED="$seed" -e MYSQL_REBOOT_DRY_RUN=1 shell \
  mysqlsh --js --file=/bootstrap/reboot.js 2>&1 | tee "$OUT/reboot-dry-run.txt"
record actual_reboot_begin
"${DC[@]}" run --rm -e MYSQL_SEED="$seed" -e MYSQL_REBOOT_DRY_RUN=0 shell \
  mysqlsh --js --file=/bootstrap/reboot.js 2>&1 | tee "$OUT/reboot-actual.txt"

online=0
for _ in $(seq 1 90); do
  online="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse "SELECT COUNT(*) FROM performance_schema.replication_group_members WHERE MEMBER_STATE='ONLINE'")"
  [ "$online" = 3 ] && break
  sleep 1
done
[ "$online" = 3 ]
topology="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse \
  "SELECT COUNT(*), SUM(MEMBER_ROLE = 'PRIMARY') FROM performance_schema.replication_group_members WHERE MEMBER_STATE = 'ONLINE'")"
[ "$topology" = $'3\t1' ]
primary="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse \
  "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_STATE = 'ONLINE' AND MEMBER_ROLE = 'PRIMARY'")"
validate_db_name "$primary"
writable="$("${DC[@]}" exec -T "$primary" mysql -uroot -pha-root -Nse \
  'SELECT @@GLOBAL.read_only, @@GLOBAL.super_read_only, @@GLOBAL.offline_mode')"
[ "$writable" = $'0\t0\t0' ]
restore_persisted_start_on_boot
record_persisted_start_on_boot "$OUT/start-on-boot-after.jsonl"
verify_restored_start_on_boot
"${DC[@]}" up -d router-a router-b
until "${DC[@]}" run --rm shell mysqladmin ping -hrouter-a -P6446 -uha_app -pha-app --silent; do sleep 2; done
probe_id="recovery-probe-$(date +%s)-$$"
"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -e \
  "START TRANSACTION; INSERT INTO ha_lab.orders (request_id, payload, via_router, written_by) VALUES ('$probe_id', JSON_OBJECT('probe', 'complete-outage'), 'router-a', 'complete-outage'); ROLLBACK;"
probe_remaining="$("${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse \
  "SELECT COUNT(*) FROM ha_lab.orders WHERE request_id = '$probe_id'")"
[ "$probe_remaining" = 0 ]
printf '{"requestId":"%s","remainingRows":%s,"rolledBack":true}\n' \
  "$probe_id" "$probe_remaining" > "$OUT/router-rollback-probe.json"
make -C "$ROOT" verify
"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse \
  'SELECT request_id FROM ha_lab.orders ORDER BY request_id' > "$OUT/after-ids.txt"
cmp -s "$OUT/before-ids.txt" "$OUT/after-ids.txt"
"${DC[@]}" run --rm shell mysqlsh --js --file=/bootstrap/status.js > "$OUT/final-status.json"
record recovery_verified
