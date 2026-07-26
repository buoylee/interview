#!/usr/bin/env bash

compose_adapter() {
  docker compose -f infra/compose.yaml -f infra/compose.adapter.yaml "$@"
}

mysql_adapter() {
  compose_adapter exec -T mysql \
    mysql -uproduct -pproductpass product_catalog \
      --batch --raw --skip-column-names "$@"
}

poll_until() {
  local max_attempts="$1"
  shift

  local attempt
  for attempt in $(seq 1 "$max_attempts"); do
    if "$@"; then
      return 0
    fi
    if test "$attempt" -lt "$max_attempts"; then
      sleep 1
    fi
  done
  return 1
}

product_api_is_ready() {
  curl -fsS --connect-timeout 2 --max-time 4 \
    http://127.0.0.1:8081/actuator/health \
    | jq -e '.status == "UP"' >/dev/null
}

es_index_exists() {
  curl -fsS --connect-timeout 2 --max-time 4 \
    http://127.0.0.1:9200/products_adapter_v1 >/dev/null
}

es_index_is_absent() {
  local status
  status=$(curl -sS --connect-timeout 2 --max-time 4 \
    -o /dev/null -w '%{http_code}' \
    http://127.0.0.1:9200/products_adapter_v1) || return 1
  test "$status" = "404"
}

es_document_is_absent() {
  local id="$1"
  local status
  status=$(curl -sS --connect-timeout 2 --max-time 4 \
    -o /dev/null -w '%{http_code}' \
    "http://127.0.0.1:9200/products_adapter_v1/_doc/$id") || return 1
  test "$status" = "404"
}

snapshot_product() {
  local id="$1"
  mysql_adapter -e "SELECT JSON_OBJECT(
    'product_id', id,
    'sku', sku,
    'name', name,
    'description', description,
    'category_id', category_id,
    'price_cents', price_cents,
    'status', status,
    'updated_at', DATE_FORMAT(updated_at, '%Y-%m-%dT%H:%i:%s.%fZ')
  ) FROM products WHERE id = $id"
}

es_document_matches_gap() {
  local id="$1"
  local expected_file="$2"
  local expected_price="$3"
  local actual

  actual=$(curl -fsS --connect-timeout 2 --max-time 4 \
    "http://127.0.0.1:9200/products_adapter_v1/_doc/$id") || return 1
  jq -e --argjson expected "$(cat "$expected_file")" '
    def allowed_fields:
      ["category_id","description","name","price_cents",
       "product_id","sku","status","updated_at"];
    .found == true and
    (._source | keys | sort) == [
      "category_id",
      "description",
      "name",
      "price_cents",
      "product_id",
      "sku",
      "status",
      "updated_at"
    ] and
    ._source.price_cents == $expected_price and
    ($expected.updated_at | type) == "string" and
    ($expected.updated_at | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9:.]+Z$")) and
    ._source.updated_at == null and
    (._source | del(.updated_at)) == ($expected | del(.updated_at)) and
    (._source | has("category_name") | not) and
    (._source | has("inventory") | not) and
    (._source | has("searchable") | not) and
    (._source | has("source_revision") | not)
  ' --argjson expected_price "$expected_price" <<<"$actual" >/dev/null
}

capture_product_gap_evidence() {
  local id="$1"
  local expected_price="$2"
  local mysql_file="$3"
  local es_file="$4"

  snapshot_product "$id" | jq -e . >"$mysql_file"
  poll_until 60 es_document_matches_gap "$id" "$mysql_file" "$expected_price"
  curl -fsS --connect-timeout 2 --max-time 4 \
    "http://127.0.0.1:9200/products_adapter_v1/_doc/$id" \
    | jq -e . >"$es_file"
  es_document_matches_gap "$id" "$mysql_file" "$expected_price"
}
