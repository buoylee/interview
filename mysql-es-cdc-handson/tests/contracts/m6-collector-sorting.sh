#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/../.." && pwd)";filter="$root/scenarios/scripts/lib/sort-capture.jq"
test -f "$filter" || { echo 'missing output-side capture sorter' >&2;exit 1; }
jq -e -f "$filter" <<'JSON' >/dev/null
{"documents":[{"product_id":9},{"product_id":2},{"product_id":5}]}
JSON
test "$(jq -c -f "$filter" <<<'{"documents":[{"product_id":9},{"product_id":2},{"product_id":5}]}')" = '{"documents":[{"product_id":2},{"product_id":5},{"product_id":9}]}'
test "$(jq -c -f "$filter" <<<'{"beginning":[{"partition":2},{"partition":0}],"end":[{"partition":1},{"partition":0}],"primary":[{"partition":2},{"partition":1}],"shadow_and_barrier":[{"run_id":"b","phase":"Z","partition_id":2},{"run_id":"a","phase":"B","partition_id":1},{"run_id":"a","phase":"A","partition_id":2}]}')" = '{"beginning":[{"partition":0},{"partition":2}],"end":[{"partition":0},{"partition":1}],"primary":[{"partition":1},{"partition":2}],"shadow_and_barrier":[{"run_id":"a","phase":"A","partition_id":2},{"run_id":"a","phase":"B","partition_id":1},{"run_id":"b","phase":"Z","partition_id":2}]}'
for collector in capture-mysql.sh capture-elasticsearch.sh capture-kafka.sh;do grep -Fq 'sort-capture.jq' "$root/scenarios/scripts/$collector";done
printf 'M6 collector output sorting contract passed\n'
