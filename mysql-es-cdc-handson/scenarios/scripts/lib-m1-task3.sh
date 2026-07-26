#!/usr/bin/env bash

m1_task3_utc_millis() {
  jq -nr '
    now as $sample |
    ($sample | floor) as $epoch_seconds |
    ((($sample - $epoch_seconds) * 1000) | floor) as $milliseconds |
    ($epoch_seconds | gmtime | strftime("%Y-%m-%dT%H:%M:%S")) + "." +
      ($milliseconds | tostring | "00" + . | .[-3:]) + "Z"
  '
}

m1_task3_container_id() {
  local id
  id=$(compose_adapter ps -aq canal-adapter | tr -d '\r\n') || return 1
  m1_is_container_id "$id" || return 1
  printf '%s\n' "$id"
}

m1_task3_adapter_identity() {
  compose_adapter exec -T canal-adapter sh -s <<'SH'
set -eu
pid=""
matches=0
for process_dir in /proc/[0-9]*; do
  test -r "$process_dir/cmdline" || continue
  command_line=$(tr '\000' ' ' <"$process_dir/cmdline" 2>/dev/null || true)
  case "$command_line" in
    *"-DappName=canal-adapter "*)
      matches=$((matches + 1))
      uid=$(awk '/^Uid:/ { print $2 }' "$process_dir/status")
      test "$uid" = "1000" || exit 1
      pid=${process_dir##*/}
      ;;
  esac
done
test "$matches" -eq 1
stat_line=$(cat "/proc/$pid/stat")
stat_tail=${stat_line##*) }
test "$stat_tail" != "$stat_line"
set -- $stat_tail
test "$#" -ge 20
start_ticks=${20}
case "$pid$start_ticks" in
  ''|*[!0-9]*) exit 1 ;;
esac
printf '%s|%s\n' "$pid" "$start_ticks"
SH
}

m1_task3_container_running() {
  local container_id="$1"
  local running
  running=$(docker inspect --format '{{.State.Running}}' "$container_id") || return 1
  case "$running" in
    true|false) printf '%s\n' "$running" ;;
    *) return 1 ;;
  esac
}

m1_task3_reset_fixture_and_index() {
  local product_id="$1"
  local index_output="$2"
  local delete_body delete_status
  delete_body=$(mktemp "${TMPDIR:-/tmp}/m1-index-delete.XXXXXX") || return 1

  delete_status=$(curl -sS --connect-timeout 2 --max-time 10 \
    -o "$delete_body" -w '%{http_code}' -X DELETE \
    http://127.0.0.1:9200/products_adapter_v1) || {
      rm -f "$delete_body"
      return 1
    }
  case "$delete_status" in
    200) jq -e '.acknowledged == true' "$delete_body" >/dev/null ;;
    404) jq -e '.status == 404' "$delete_body" >/dev/null ;;
    *) rm -f "$delete_body"; return 1 ;;
  esac
  rm -f "$delete_body"
  poll_until 30 es_index_is_absent

  mysql_adapter <<SQL
START TRANSACTION;
DELETE FROM product_search_revision WHERE product_id = $product_id;
DELETE FROM inventory WHERE product_id = $product_id;
DELETE FROM products WHERE id = $product_id;
COMMIT;
SQL
  test "$(mysql_adapter -e "SELECT
    (SELECT COUNT(*) FROM products WHERE id = $product_id) +
    (SELECT COUNT(*) FROM product_search_revision WHERE product_id = $product_id) +
    (SELECT COUNT(*) FROM inventory WHERE product_id = $product_id)")" = "0"

  curl -fsS --connect-timeout 2 --max-time 10 -X PUT \
    http://127.0.0.1:9200/products_adapter_v1 \
    -H 'Content-Type: application/json' \
    --data-binary @infra/elasticsearch/adapter-index.json \
    | jq -e 'select(.acknowledged == true and .index == "products_adapter_v1")' \
    >"$index_output"
  poll_until 30 es_index_exists
}

m1_task3_snapshot_source() {
  local product_id="$1"
  local output="$2"
  local row
  row=$(mysql_adapter -e "SELECT
    p.id, p.sku, p.name, p.description, p.category_id, p.price_cents, p.status,
    DATE_FORMAT(p.updated_at, '%Y-%m-%dT%H:%i:%s.%fZ'),
    r.product_id, r.revision, r.active,
    i.product_id, i.available_quantity, i.reserved_quantity
    FROM products p
    JOIN product_search_revision r ON r.product_id = p.id
    JOIN inventory i ON i.product_id = p.id
    WHERE p.id = $product_id") || return 1
  test -n "$row" || return 1

  local id sku name description category price status updated_at
  local revision_product revision active inventory_product available reserved extra
  IFS=$'\t' read -r id sku name description category price status updated_at \
    revision_product revision active inventory_product available reserved extra <<<"$row"
  test -z "${extra:-}" && test "$id" = "$product_id" || return 1
  test "$revision_product" = "$product_id" && test "$inventory_product" = "$product_id" || return 1
  case "$id$category$price$revision$active$available$reserved" in
    *[!0-9]*) return 1 ;;
  esac

  jq -n \
    --argjson id "$id" --arg sku "$sku" --arg name "$name" \
    --arg description "$description" --argjson category "$category" \
    --argjson price "$price" --arg status "$status" --arg updated_at "$updated_at" \
    --argjson revision "$revision" --argjson active "$active" \
    --argjson available "$available" --argjson reserved "$reserved" '
    {
      product:{
        product_id:$id,sku:$sku,name:$name,description:$description,
        category_id:$category,price_cents:$price,status:$status,updated_at:$updated_at
      },
      revision:{product_id:$id,revision:$revision,active:($active == 1)},
      inventory:{
        product_id:$id,available_quantity:$available,reserved_quantity:$reserved
      }
    }
  ' >"$output"
}

m1_task3_capture_es() {
  local product_id="$1"
  local output="$2"
  curl -sS --connect-timeout 2 --max-time 4 \
    "http://127.0.0.1:9200/products_adapter_v1/_doc/$product_id" \
    | jq -e . >"$output"
}

m1_task3_es_matches_source_price() {
  local product_id="$1"
  local source_file="$2"
  local price="$3"
  local actual
  actual=$(curl -fsS --connect-timeout 2 --max-time 4 \
    "http://127.0.0.1:9200/products_adapter_v1/_doc/$product_id") || return 1
  jq -e --slurpfile source "$source_file" --argjson price "$price" '
    .found == true and
    (._source | keys | sort) == [
      "category_id","description","name","price_cents",
      "product_id","sku","status","updated_at"
    ] and
    ._source.updated_at == null and
    ._source.price_cents == $price and
    (._source | del(.updated_at)) ==
      ($source[0].product | del(.updated_at) | .price_cents = $price)
  ' <<<"$actual" >/dev/null
}

m1_task3_capture_initial() {
  local product_id="$1"
  local source_output="$2"
  local target_output="$3"
  m1_task3_snapshot_source "$product_id" "$source_output"
  poll_until 60 m1_task3_es_matches_source_price "$product_id" "$source_output" 100
  m1_task3_capture_es "$product_id" "$target_output"
  m1_task3_es_matches_source_price "$product_id" "$source_output" 100
}

m1_task3_capture_adapter_log() {
  local output="$1"
  compose_adapter exec -T canal-adapter \
    cat /opt/canal-adapter/logs/adapter/adapter.log >"$output"
}
