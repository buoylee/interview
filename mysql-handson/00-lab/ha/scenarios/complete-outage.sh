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

persisted_start_on_boot() {
  local member="$1" value
  value="$("${DC[@]}" exec -T "$member" mysql -uroot -pha-root -Nse \
    "SELECT VARIABLE_VALUE FROM performance_schema.persisted_variables WHERE VARIABLE_NAME = 'group_replication_start_on_boot'")"
  case "$value" in ON|OFF) printf '%s\n' "$value" ;; *) return 1 ;; esac
}

record_persisted_start_on_boot() {
  local output="$1" member value
  : > "$output"
  for member in db1 db2 db3; do
    value="$(persisted_start_on_boot "$member")"
    printf '{"member":"%s","persistedStartOnBoot":"%s"}\n' "$member" "$value" >> "$output"
  done
}

set_persisted_start_on_boot() {
  local value="$1" member
  for member in db1 db2 db3; do
    "${DC[@]}" exec -T "$member" mysql -uroot -pha-root -e \
      "SET PERSIST_ONLY group_replication_start_on_boot = $value"
  done
}

verify_persisted_start_on_boot() {
  local expected="$1" member
  for member in db1 db2 db3; do
    [ "$(persisted_start_on_boot "$member")" = "$expected" ]
  done
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
  "$OUT/final-status.json" \
  "$OUT/start-on-boot-before.jsonl" \
  "$OUT/start-on-boot-off.jsonl" \
  "$OUT/start-on-boot-after.jsonl"
make -C "$ROOT" up
make -C "$ROOT" workload-once N=20
make -C "$ROOT" verify

seed="$("${DC[@]}" exec -T db1 mysql -uroot -pha-root -Nse "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_ROLE='PRIMARY' AND MEMBER_STATE='ONLINE'")"
printf '%s\n' "$seed" > "$OUT/seed.txt"
"${DC[@]}" stop router-a router-b

gtid="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse 'SELECT @@GLOBAL.gtid_executed')"
for member in db1 db2 db3; do
  waited="$("${DC[@]}" exec -T "$member" mysql -uroot -pha-root -Nse "SELECT WAIT_FOR_EXECUTED_GTID_SET('$gtid', 30)")"
  [ "$waited" = 0 ]
done
before="$("${DC[@]}" exec -T "$seed" mysql -uroot -pha-root -Nse 'SELECT request_id FROM ha_lab.orders ORDER BY request_id')"
printf '%s\n' "$before" > "$OUT/before-ids.txt"
record_persisted_start_on_boot "$OUT/start-on-boot-before.jsonl"
set_persisted_start_on_boot OFF
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
set_persisted_start_on_boot ON
record_persisted_start_on_boot "$OUT/start-on-boot-after.jsonl"
verify_persisted_start_on_boot ON
"${DC[@]}" up -d router-a router-b
until "${DC[@]}" run --rm shell mysqladmin ping -hrouter-a -P6446 -uha_app -pha-app --silent; do sleep 2; done
make -C "$ROOT" verify
after="$("${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uha_app -pha-app -Nse 'SELECT request_id FROM ha_lab.orders ORDER BY request_id')"
printf '%s\n' "$after" > "$OUT/after-ids.txt"
[ "$before" = "$after" ]
"${DC[@]}" run --rm shell mysqlsh --js --file=/bootstrap/status.js > "$OUT/final-status.json"
record recovery_verified
