#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

compose=(docker compose -f infra/compose.yaml)
topic=product-search-revisions
meta_path=/home/admin/canal-data/products/meta.dat
evidence_dir=evidence/m0
work_dir="$(mktemp -d "${TMPDIR:-/tmp}/m0-smoke.XXXXXX")"
trap 'rm -rf "$work_dir"' EXIT
mkdir -p "$evidence_dir"

wait_until() {
  local description="$1"
  local timeout="$2"
  shift 2
  local deadline=$((SECONDS + timeout))
  until "$@"; do
    if [ "$SECONDS" -ge "$deadline" ]; then
      echo "timeout waiting for $description after ${timeout}s" >&2
      return 1
    fi
    sleep 1
  done
}

sha256_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

copy_meta() {
  local output="$1"
  "${compose[@]}" exec -T canal /bin/bash -c \
    "test -s '$meta_path' && cat '$meta_path'" >"$output" 2>/dev/null
  test -s "$output"
}

kafka_end_offsets() {
  "${compose[@]}" exec -T kafka \
    /opt/kafka/bin/kafka-get-offsets.sh \
    --bootstrap-server kafka:9092 --topic "$topic" --time -1 \
    | jq -Rsc '
        split("\n")[:-1]
        | map(split(":") | {partition:(.[1]|tonumber),end_offset:(.[2]|tonumber)})
        | sort_by(.partition)
      '
}

vector_is_zero() {
  kafka_end_offsets | jq -e '
    length == 3 and (map(.partition) == [0,1,2]) and all(.[]; .end_offset == 0)
  ' >/dev/null
}

vector_has_one_revision() {
  kafka_end_offsets >"$work_dir/current-offsets.json" 2>/dev/null &&
    jq -e '
      length == 3 and (map(.partition) == [0,1,2]) and
      (map(.end_offset) | add) == 1 and
      ([.[] | select(.end_offset == 1)] | length) == 1
    ' "$work_dir/current-offsets.json" >/dev/null
}

vector_matches_file() {
  local expected="$1"
  kafka_end_offsets >"$work_dir/current-offsets.json" 2>/dev/null &&
    jq -e --slurpfile expected "$expected" '. == $expected[0]' \
      "$work_dir/current-offsets.json" >/dev/null
}

vector_has_exact_revision2_delta() {
  local before="$1"
  local expected_partition="$2"
  kafka_end_offsets >"$work_dir/current-offsets.json" 2>/dev/null &&
    jq -e --argjson partition "$expected_partition" --slurpfile before "$before" '
      length == 3 and
      (map(.partition) == [0,1,2]) and
      [range(0;3) as $i |
        {
          partition: .[$i].partition,
          delta: (.[$i].end_offset - $before[0][$i].end_offset)
        }
      ] as $delta |
      ($delta | map(.delta) | add) == 1 and
      ($delta | map(select(.delta == 1) | .partition)) == [$partition]
    ' "$work_dir/current-offsets.json" >/dev/null
}

capture_record() {
  local partition="$1"
  local offset="$2"
  local output="$3"
  local line partition_value offset_value key_value raw_value

  line="$("${compose[@]}" exec -T kafka \
    /opt/kafka/bin/kafka-console-consumer.sh \
    --bootstrap-server kafka:9092 \
    --topic "$topic" \
    --partition "$partition" \
    --offset "$offset" \
    --max-messages 1 \
    --timeout-ms 10000 \
    --property print.partition=true \
    --property partition.separator='|' \
    --property print.offset=true \
    --property offset.separator='|' \
    --property print.key=true \
    --property key.separator='|' \
    --property print.value=true)"

  if [[ "$line" =~ ^(Partition:)?([0-9]+)\|(Offset:)?([0-9]+)\|([^|]+)\|(.*)$ ]]; then
    partition_value="${BASH_REMATCH[2]}"
    offset_value="${BASH_REMATCH[4]}"
    key_value="${BASH_REMATCH[5]}"
    raw_value="${BASH_REMATCH[6]}"
  else
    echo "unexpected kafka-console-consumer metadata format: $line" >&2
    return 1
  fi

  test "$partition_value" = "$partition"
  test "$offset_value" = "$offset"
  test "$key_value" = "null"
  jq -e . <<<"$raw_value" >"$output"
}

cursor_changed_from() {
  local baseline_sha="$1"
  copy_meta "$work_dir/candidate-meta.dat" &&
    ./scenarios/scripts/decode-canal-meta.sh "$work_dir/candidate-meta.dat" \
      >"$work_dir/candidate-meta.json" &&
    test "$(sha256_file "$work_dir/candidate-meta.dat")" != "$baseline_sha"
}

cursor_advanced_from() {
  local before_decoded_cursor="$1"
  copy_meta "$work_dir/candidate-meta.dat" &&
    ./scenarios/scripts/decode-canal-meta.sh "$work_dir/candidate-meta.dat" \
      >"$work_dir/candidate-meta.json" &&
    ./scenarios/scripts/assert-cursor-advanced.sh \
      "$before_decoded_cursor" "$work_dir/candidate-meta.json"
}

canal_running_with_products() {
  local container_id
  container_id="$("${compose[@]}" ps -q canal)"
  test -n "$container_id" &&
    test "$(docker inspect -f '{{.State.Running}}' "$container_id")" = "true" &&
    "${compose[@]}" exec -T canal /bin/bash -c \
      "grep -F 'start CannalInstance for 1-products' /home/admin/canal-server/logs/products/products.log >/dev/null && grep -F 'find start position successfully' /home/admin/canal-server/logs/products/products.log >/dev/null" \
      2>/dev/null
}

startup_exact_resume_visible() {
  tail -n "+$restart_product_log_line" "$work_dir/products-after-restart.log" \
    | grep -Fq 'prepare to find start position just last position' &&
  tail -n "+$restart_product_log_line" "$work_dir/products-after-restart.log" \
    | grep -Fq "$pre_journal" &&
  tail -n "+$restart_product_log_line" "$work_dir/products-after-restart.log" \
    | grep -Eq "position[= :]${pre_position}([^0-9]|$)"
}

copy_internal_canal_logs() {
  "${compose[@]}" exec -T canal cat \
    /home/admin/canal-server/logs/products/products.log \
    >"$work_dir/products-after-restart.log" 2>/dev/null &&
  "${compose[@]}" exec -T canal cat \
    /home/admin/canal-server/logs/canal/canal.log \
    >"$work_dir/canal-after-restart.log" 2>/dev/null &&
  "${compose[@]}" exec -T canal cat \
    /home/admin/canal-server/logs/canal/canal_stdout.log \
    >"$work_dir/stdout-after-restart.log" 2>/dev/null
}

echo "M0 smoke: wait for product-service and Canal products producer"
./scenarios/scripts/wait-for-http.sh \
  http://localhost:8081/actuator/health/readiness 90
wait_until "Canal products MQ producer" 90 canal_running_with_products

mysql_binlog="$("${compose[@]}" exec -T mysql mysql -uroot -prootpass -Nse \
  "SELECT CONCAT(@@GLOBAL.binlog_format, ':', @@GLOBAL.binlog_row_image)")"
test "$mysql_binlog" = "ROW:FULL"
grep -Fxq 'canal.instance.binlog.format = ROW' infra/canal/canal.properties
grep -Fxq 'canal.instance.binlog.image = FULL' infra/canal/canal.properties

topic_description="$("${compose[@]}" exec -T kafka \
  /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 \
  --describe --topic "$topic")"
partition_count="$(awk '
  NR == 1 {for (i=1;i<=NF;i++) if ($i=="PartitionCount:") {print $(i+1); exit}}
' <<<"$topic_description")"
test "$partition_count" = "3"
wait_until "fresh three-partition zero-offset vector" 30 vector_is_zero

baseline_sha=missing
if copy_meta "$work_dir/baseline-meta.dat"; then
  baseline_sha="$(sha256_file "$work_dir/baseline-meta.dat")"
fi

echo "M0 smoke: commit revision 1 through product API"
curl -fsS -X POST http://localhost:8081/api/products \
  -H 'Content-Type: application/json' \
  -d '{"id":1001,"sku":"SKU-1001","name":"Keyboard","description":"Mechanical","categoryId":10,"priceCents":12999}' \
  | jq -e '.productId == 1001 and .revision == 1' >/dev/null

"${compose[@]}" exec -T mysql \
  mysql -uproduct -pproductpass product_catalog -Nse \
  "SELECT CONCAT(product_id, ':', revision, ':', active)
   FROM product_search_revision WHERE product_id = 1001" \
  | grep -Fx "1001:1:1" >/dev/null

wait_until "one revision-1 Kafka record" 60 vector_has_one_revision
cp "$work_dir/current-offsets.json" "$work_dir/pre-restart-offsets.json"
rev1_partition="$(jq -r '.[] | select(.end_offset == 1) | .partition' "$work_dir/pre-restart-offsets.json")"
rev1_offset=0
capture_record "$rev1_partition" "$rev1_offset" "$work_dir/revision1.json"
jq -e '
  .database == "product_catalog" and
  .table == "product_search_revision" and
  (.data | any(.product_id == "1001" and .revision == "1"))
' "$work_dir/revision1.json" >/dev/null
cp "$work_dir/revision1.json" "$evidence_dir/revision-message.json"

wait_until "revision-1 ACK-derived meta.dat persistence" 60 \
  cursor_changed_from "$baseline_sha"
cp "$work_dir/candidate-meta.dat" "$work_dir/pre-restart-meta.dat"
cp "$work_dir/candidate-meta.json" "$work_dir/pre-restart-meta.json"
pre_sha="$(sha256_file "$work_dir/pre-restart-meta.dat")"
pre_journal="$(jq -r '.journal' "$work_dir/pre-restart-meta.json")"
pre_position="$(jq -r '.position' "$work_dir/pre-restart-meta.json")"
kafka_end_offsets >"$work_dir/pre-restart-offsets.json"

echo "M0 smoke: normal Canal-only restart after ACK/cursor evidence"
"${compose[@]}" exec -T canal cat \
  /home/admin/canal-server/logs/products/products.log \
  >"$work_dir/products-before-stop.log"
"${compose[@]}" exec -T canal cat \
  /home/admin/canal-server/logs/canal/canal.log \
  >"$work_dir/canal-before-stop.log"
"${compose[@]}" exec -T canal cat \
  /home/admin/canal-server/logs/canal/canal_stdout.log \
  >"$work_dir/stdout-before-stop.log"
restart_product_log_line=$(( $(wc -l <"$work_dir/products-before-stop.log" | tr -d ' ') + 1 ))
restart_canal_log_line=$(( $(wc -l <"$work_dir/canal-before-stop.log" | tr -d ' ') + 1 ))
restart_stdout_log_line=$(( $(wc -l <"$work_dir/stdout-before-stop.log" | tr -d ' ') + 1 ))
"${compose[@]}" stop canal
"${compose[@]}" start canal
wait_until "restarted Canal products MQ producer" 90 canal_running_with_products

deadline=$((SECONDS + 90))
until copy_internal_canal_logs && startup_exact_resume_visible; do
  if [ "$SECONDS" -ge "$deadline" ]; then
    echo "timeout waiting for exact-resume startup log for $pre_journal:$pre_position" >&2
    tail -n "+$restart_product_log_line" "$work_dir/products-after-restart.log" >&2 || true
    exit 1
  fi
  sleep 1
done

{
  tail -n "+$restart_product_log_line" "$work_dir/products-after-restart.log"
  tail -n "+$restart_canal_log_line" "$work_dir/canal-after-restart.log"
  tail -n "+$restart_stdout_log_line" "$work_dir/stdout-after-restart.log"
} >"$work_dir/canal-stop-observation.log"
./scenarios/scripts/classify-canal-stop-npe.sh \
  "$work_dir/canal-stop-observation.log" >"$work_dir/canal-stop-npe.json"

copy_meta "$work_dir/post-restart-meta.dat"
./scenarios/scripts/decode-canal-meta.sh "$work_dir/post-restart-meta.dat" \
  >"$work_dir/post-restart-meta.json"
post_sha="$(sha256_file "$work_dir/post-restart-meta.dat")"
test "$post_sha" = "$pre_sha"
jq -e --slurpfile pre "$work_dir/pre-restart-meta.json" '
  .journal == $pre[0].journal and .position == $pre[0].position and
  .source == $pre[0].source
' "$work_dir/post-restart-meta.json" >/dev/null
wait_until "unchanged Kafka offsets before any post-restart write" 30 \
  vector_matches_file "$work_dir/pre-restart-offsets.json"
cp "$work_dir/current-offsets.json" "$work_dir/post-restart-offsets.json"

resume_excerpt="$(tail -n "+$restart_product_log_line" "$work_dir/products-after-restart.log" \
  | grep -E 'prepare to find start position just last position|find start position successfully|journalName|position' \
  | tail -n 12)"

echo "M0 smoke: commit revision 2 and prove expected next offset exactly once"
curl -fsS -X PUT http://localhost:8081/api/products/1001/price \
  -H 'Content-Type: application/json' \
  -d '{"priceCents":11999}' \
  | jq -e '.productId == 1001 and .revision == 2' >/dev/null

wait_until "one revision-2 offset delta on partition $rev1_partition" 60 \
  vector_has_exact_revision2_delta "$work_dir/pre-restart-offsets.json" "$rev1_partition"

# Require the exact vector to remain stable across three condition probes. This is
# a bounded duplicate check, not a timing-based success shortcut.
cp "$work_dir/current-offsets.json" "$work_dir/revision2-offsets.json"
for probe in 1 2 3; do
  wait_until "stable revision-2 end-offset vector probe $probe" 10 \
    vector_matches_file "$work_dir/revision2-offsets.json"
  if [ "$probe" -lt 3 ]; then
    sleep 1
  fi
done

rev2_offset=$((rev1_offset + 1))
capture_record "$rev1_partition" "$rev2_offset" "$work_dir/revision2.json"
jq -e '
  .database == "product_catalog" and
  .table == "product_search_revision" and
  (.data | any(.product_id == "1001" and .revision == "2")) and
  (.old | any(.revision == "1"))
' "$work_dir/revision2.json" >/dev/null

wait_until "revision-2 post-ACK decoded cursor advance" 60 \
  cursor_advanced_from "$work_dir/post-restart-meta.json"
cp "$work_dir/candidate-meta.json" "$work_dir/post-revision2-meta.json"
post_revision2_sha="$(sha256_file "$work_dir/candidate-meta.dat")"

jq -n \
  --argjson partition_count "$partition_count" \
  --argjson rev1_partition "$rev1_partition" \
  --argjson rev1_offset "$rev1_offset" \
  --argjson rev2_offset "$rev2_offset" \
  --arg pre_sha "$pre_sha" \
  --arg post_sha "$post_sha" \
  --arg post_revision2_sha "$post_revision2_sha" \
  --arg resume_excerpt "$resume_excerpt" \
  --slurpfile rev1 "$work_dir/revision1.json" \
  --slurpfile rev2 "$work_dir/revision2.json" \
  --slurpfile pre_meta "$work_dir/pre-restart-meta.json" \
  --slurpfile post_meta "$work_dir/post-restart-meta.json" \
  --slurpfile rev2_meta "$work_dir/post-revision2-meta.json" \
  --slurpfile pre_offsets "$work_dir/pre-restart-offsets.json" \
  --slurpfile post_offsets "$work_dir/post-restart-offsets.json" \
  --slurpfile rev2_offsets "$work_dir/revision2-offsets.json" \
  --slurpfile stop_npe "$work_dir/canal-stop-npe.json" '
  {
    milestone: "M0",
    contract: "mysql-canal-kafka-capture-restart-v1",
    topic: "product-search-revisions",
    topic_partition_count: $partition_count,
    revision1: {
      kafka: {partition:$rev1_partition,offset:$rev1_offset,key:null},
      raw: $rev1[0]
    },
    pre_restart: {
      meta_sha256: $pre_sha,
      meta: $pre_meta[0],
      kafka_end_offsets: $pre_offsets[0]
    },
    post_restart: {
      meta_sha256: $post_sha,
      meta: $post_meta[0],
      kafka_end_offsets: $post_offsets[0],
      startup_exact_resume: {matched:true,log_excerpt:$resume_excerpt},
      known_stop_npe: $stop_npe[0].known_stop_npe,
      unexpected_npe: $stop_npe[0].unexpected_npe
    },
    revision2: {
      kafka: {partition:$rev1_partition,offset:$rev2_offset,key:null},
      raw: $rev2[0],
      exactly_once_at_expected_next_offset: true,
      post_ack_cursor_advanced: true,
      post_ack_meta_sha256: $post_revision2_sha,
      post_ack_meta: $rev2_meta[0],
      kafka_end_offset_delta: [range(0;3) as $i | {
        partition:$rev2_offsets[0][$i].partition,
        before:$pre_offsets[0][$i].end_offset,
        after:$rev2_offsets[0][$i].end_offset,
        delta:($rev2_offsets[0][$i].end_offset - $pre_offsets[0][$i].end_offset)
      }]
    }
  }
' >"$evidence_dir/canal-position.json"

./scenarios/scripts/assert-m0-evidence.sh "$evidence_dir/canal-position.json"
echo "M0 smoke passed: rev1 ACK cursor persisted, exact Canal restart resumed, rev2 occupied the expected next offset once"
