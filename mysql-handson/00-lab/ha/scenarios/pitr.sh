#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
DC=(docker compose --project-name mysql-ha --file "$ROOT/compose.yml")
OUT="$ROOT/evidence/pitr"
PASSWORD="${MYSQL_ROOT_PASSWORD:-ha-root}"
KEEP_ID=pitr-keep

mkdir -p "$OUT"
find "$OUT" -mindepth 1 -maxdepth 1 -type f -delete

parse_status() {
  awk '
    NR == 1 && NF >= 2 && $1 ~ /^binlog\.[0-9]+$/ && $2 ~ /^[0-9]+$/ {
      file = $1; position = $2; valid = 1; next
    }
    { valid = 0 }
    END { if (NR == 1 && valid) print file, position; else exit 1 }
  '
}

make -C "$ROOT" reset
make -C "$ROOT" up
make -C "$ROOT" workload-once N=5
primary="$("${DC[@]}" exec -T db1 mysql -uroot -p"$PASSWORD" -Nse \
  "SELECT MEMBER_HOST FROM performance_schema.replication_group_members WHERE MEMBER_STATE='ONLINE' AND MEMBER_ROLE='PRIMARY'")"
case "$primary" in db1|db2|db3) ;; *) echo "expected exactly one source Primary" >&2; exit 1 ;; esac
printf '%s\n' "$primary" > "$OUT/source-primary.txt"

base_count="$("${DC[@]}" exec -T "$primary" mysql -uroot -p"$PASSWORD" -Nse \
  'SELECT COUNT(*) FROM ha_lab.orders')"
case "$base_count" in ''|*[!0-9]*) echo "invalid base row count" >&2; exit 1 ;; esac
printf '%s\n' "$base_count" > "$OUT/base-count.txt"

# No workload is running here. --source-data records the exact coordinate of
# the --single-transaction snapshot inside the dump, avoiding an external
# SHOW-status race at the backup boundary.
"${DC[@]}" exec -T "$primary" mysql -uroot -p"$PASSWORD" -e 'FLUSH BINARY LOGS'
"${DC[@]}" run --rm shell mysqldump -h"$primary" -uroot -p"$PASSWORD" \
  --single-transaction --source-data=2 --set-gtid-purged=OFF --databases ha_lab \
  > "$OUT/base.sql" 2> "$OUT/base-dump.stderr"
dump_status="$(sed -n \
  "s/^-- CHANGE REPLICATION SOURCE TO SOURCE_LOG_FILE='\([^']*\)', SOURCE_LOG_POS=\([0-9][0-9]*\);$/\1 \2/p" \
  "$OUT/base.sql")"
start_status="$(printf '%s\n' "$dump_status" | parse_status)" || {
  echo "dump does not contain exactly one valid source coordinate" >&2; exit 1;
}
start_file="${start_status%% *}"
start_pos="${start_status##* }"

"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uroot -p"$PASSWORD" -e \
  "INSERT INTO ha_lab.orders(request_id,payload,via_router,written_by) VALUES ('$KEEP_ID', JSON_OBJECT('keep',true), 'router-a', @@hostname)"
raw_stop="$("${DC[@]}" exec -T "$primary" mysql -uroot -p"$PASSWORD" -Nse 'SHOW BINARY LOG STATUS')"
stop_status="$(printf '%s\n' "$raw_stop" | parse_status)" || {
  echo "SHOW BINARY LOG STATUS was malformed or ambiguous" >&2; exit 1;
}
stop_file="${stop_status%% *}"
stop_pos="${stop_status##* }"
[ "$start_file" = "$stop_file" ] || {
  echo "binlog file changed inside PITR window; refusing cross-file replay" >&2; exit 1;
}
[ "$stop_pos" -gt "$start_pos" ] || {
  echo "stop position must be greater than start position" >&2; exit 1;
}
printf '%s %s %s\n' "$start_file" "$start_pos" "$stop_pos" > "$OUT/binlog-window.txt"

expected_count="$("${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uroot -p"$PASSWORD" -Nse \
  'SELECT COUNT(*) FROM ha_lab.orders')"
case "$expected_count" in ''|*[!0-9]*) echo "invalid expected row count" >&2; exit 1 ;; esac
[ "$expected_count" -eq $((base_count + 1)) ] || {
  echo "unexpected writes raced the backup/replay window" >&2; exit 1;
}
printf '%s\n' "$expected_count" > "$OUT/expected-count.txt"
projection_sql="SELECT CONCAT_WS(CHAR(9), IFNULL(CONCAT('H',HEX(request_id)),'N'), IFNULL(CONCAT('H',HEX(CAST(payload AS CHAR CHARACTER SET utf8mb4))),'N'), IFNULL(CONCAT('H',HEX(via_router)),'N'), IFNULL(CONCAT('H',HEX(written_by)),'N')) FROM ha_lab.orders ORDER BY request_id"
"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uroot -p"$PASSWORD" --batch --raw -Nse \
  "$projection_sql" > "$OUT/expected-projection.tsv"
[ "$(wc -l < "$OUT/expected-projection.tsv" | tr -d ' ')" = "$expected_count" ] || {
  echo "pre-DELETE projection row count is incomplete" >&2; exit 1;
}

"${DC[@]}" run --rm shell mysql -hrouter-a -P6446 -uroot -p"$PASSWORD" -e \
  'DELETE FROM ha_lab.orders'
: > "$OUT/member-zero.txt"
for member in db1 db2 db3; do
  count=-1
  for _ in $(seq 1 30); do
    count="$("${DC[@]}" exec -T "$member" mysql -uroot -p"$PASSWORD" -Nse \
      'SELECT COUNT(*) FROM ha_lab.orders')" || count=-1
    [ "$count" = 0 ] && break
    sleep 1
  done
  [ "$count" = 0 ] || { echo "$member did not replicate the DELETE" >&2; exit 1; }
  printf '%s %s\n' "$member" "$count" >> "$OUT/member-zero.txt"
done

"${DC[@]}" --profile recovery up -d recovery
: > "$OUT/recovery-readiness-errors.txt"
readiness_started=$SECONDS
recovery_ready=0
for _ in $(seq 1 60); do
  readiness_attempt=$_
  if readiness_output="$("${DC[@]}" exec -T recovery mysql -uroot -p"$PASSWORD" -Nse \
    'SELECT 1 /* recovery-readiness */' 2>> "$OUT/recovery-readiness-errors.txt")" && \
    [ "$readiness_output" = 1 ]; then
    recovery_ready=1
    break
  fi
  sleep 2
done
readiness_elapsed=$((SECONDS - readiness_started))
printf 'attempts=%s elapsed_seconds=%s authenticated=%s\n' \
  "$readiness_attempt" "$readiness_elapsed" "$recovery_ready" \
  > "$OUT/recovery-readiness.txt"
[ "$recovery_ready" = 1 ] || {
  echo "recovery did not accept authenticated SQL within 120 seconds" >&2; exit 1;
}
"${DC[@]}" exec -T recovery mysql -uroot -p"$PASSWORD" < "$OUT/base.sql"
"${DC[@]}" run --rm shell bash -o pipefail -c \
  "mysqlbinlog --read-from-remote-server --skip-gtids -h$primary -uroot -p'$PASSWORD' --start-position=$start_pos --stop-position=$stop_pos $start_file | mysql --binary-mode=1 -hrecovery -uroot -p'$PASSWORD'"

"${DC[@]}" exec -T recovery mysql -uroot -p"$PASSWORD" -Nse \
  "SELECT request_id FROM ha_lab.orders WHERE request_id='$KEEP_ID'" \
  > "$OUT/recovery-keep-row.txt"
[ "$(wc -l < "$OUT/recovery-keep-row.txt" | tr -d ' ')" = 1 ]
grep -qx "$KEEP_ID" "$OUT/recovery-keep-row.txt"
recovered_count="$("${DC[@]}" exec -T recovery mysql -uroot -p"$PASSWORD" -Nse \
  'SELECT COUNT(*) FROM ha_lab.orders')"
[ "$recovered_count" = "$expected_count" ] || {
  echo "recovered row count does not match pre-DELETE count" >&2; exit 1;
}
printf '%s\n' "$recovered_count" > "$OUT/recovered-count.txt"
"${DC[@]}" exec -T recovery mysql -uroot -p"$PASSWORD" --batch --raw -Nse \
  "$projection_sql" > "$OUT/recovered-projection.tsv"
[ "$(wc -l < "$OUT/recovered-projection.tsv" | tr -d ' ')" = "$recovered_count" ] || {
  echo "recovered projection row count is incomplete" >&2; exit 1;
}
cmp -s "$OUT/expected-projection.tsv" "$OUT/recovered-projection.tsv" || {
  echo "recovered rows do not byte-match the intended pre-DELETE projection" >&2; exit 1;
}

"${DC[@]}" exec -T "$primary" mysql -uroot -p"$PASSWORD" -Nse \
  "SELECT MEMBER_HOST,MEMBER_STATE,MEMBER_ROLE FROM performance_schema.replication_group_members ORDER BY MEMBER_HOST" \
  > "$OUT/final-topology.txt"
[ "$(wc -l < "$OUT/final-topology.txt" | tr -d ' ')" = 3 ]
[ "$(awk '$2 == "ONLINE" {n++} END {print n+0}' "$OUT/final-topology.txt")" = 3 ]
[ "$(awk '$2 == "ONLINE" && $3 == "PRIMARY" {n++} END {print n+0}' "$OUT/final-topology.txt")" = 1 ]
: > "$OUT/final-member-counts.txt"
for member in db1 db2 db3; do
  count="$("${DC[@]}" exec -T "$member" mysql -uroot -p"$PASSWORD" -Nse \
    'SELECT COUNT(*) FROM ha_lab.orders')"
  [ "$count" = 0 ] || { echo "$member changed after isolated recovery" >&2; exit 1; }
  printf '%s %s\n' "$member" "$count" >> "$OUT/final-member-counts.txt"
done

archive="$ROOT/evidence/runs/ha-cannot-replace-pitr/$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$archive"
find "$OUT" -mindepth 1 -maxdepth 1 -type f -exec cp {} "$archive"/ \;
printf '%s\n' "$archive"
