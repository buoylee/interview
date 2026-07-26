#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
source scenarios/scripts/lib-adapter.sh

scenario="m1-basic"
product_id=1101
out="evidence/m1/$scenario"
rm -rf "$out"
mkdir -p "$out"
cp "scenarios/definitions/$scenario.json" "$out/input-commands.json"

poll_until 60 product_api_is_ready
bash tests/contracts/m1-adapter.sh --live >"$out/current-run-mapping-proof.txt"

fixture_exists=$(mysql_adapter -e \
  "SELECT COUNT(*) FROM products WHERE id = $product_id")

if test "$fixture_exists" = "1"; then
  if ! es_index_exists; then
    curl -fsS -X PUT http://127.0.0.1:9200/products_adapter_v1 \
      -H 'Content-Type: application/json' \
      --data-binary @infra/elasticsearch/adapter-index.json >/dev/null
    poll_until 30 es_index_exists
  fi

  curl -fsS -X PUT \
    "http://127.0.0.1:9200/products_adapter_v1/_doc/$product_id?refresh=wait_for" \
    -H 'Content-Type: application/json' \
    -d '{"product_id":1101,"sku":"cleanup-marker","name":"cleanup-marker","description":"cleanup-marker","category_id":10,"price_cents":0,"status":"ACTIVE","updated_at":"2000-01-01T00:00:00.000000Z"}' \
    >/dev/null
fi

mysql_adapter <<SQL
START TRANSACTION;
DELETE FROM product_search_revision WHERE product_id = $product_id;
DELETE FROM inventory WHERE product_id = $product_id;
DELETE FROM products WHERE id = $product_id;
COMMIT;
SQL

if test "$fixture_exists" = "1"; then
  poll_until 60 es_document_is_absent "$product_id"
fi

curl -fsS -X DELETE http://127.0.0.1:9200/products_adapter_v1 >/dev/null || true
poll_until 30 es_index_is_absent
curl -fsS -X PUT http://127.0.0.1:9200/products_adapter_v1 \
  -H 'Content-Type: application/json' \
  --data-binary @infra/elasticsearch/adapter-index.json \
  | jq -e 'select(.acknowledged == true)' >"$out/index-create.json"
poll_until 30 es_index_exists

curl -fsS -X POST http://127.0.0.1:8081/api/products \
  -H 'Content-Type: application/json' \
  -d '{"id":1101,"sku":"M1-1101","name":"Adapter Keyboard","description":"initial","categoryId":10,"priceCents":100}' \
  | jq -e 'select(. == {"productId":1101,"revision":1})' \
  >"$out/create-response.json"

capture_product_gap_evidence "$product_id" 100 \
  "$out/mysql-insert-snapshot.json" "$out/es-insert-snapshot.json"

curl -fsS -X PUT http://127.0.0.1:8081/api/products/1101/price \
  -H 'Content-Type: application/json' \
  -d '{"priceCents":120}' \
  | jq -e 'select(. == {"productId":1101,"revision":2})' \
  >"$out/update-response.json"

capture_product_gap_evidence "$product_id" 120 \
  "$out/mysql-snapshot.json" "$out/es-snapshot.json"
compose_adapter exec -T canal-adapter \
  cat /opt/canal-adapter/logs/adapter/adapter.log >"$out/adapter.log"

bash scenarios/scripts/derive-m1-result.sh "$out" >"$out/result.json"

bash scenarios/scripts/assert-m1-evidence.sh "$out"
