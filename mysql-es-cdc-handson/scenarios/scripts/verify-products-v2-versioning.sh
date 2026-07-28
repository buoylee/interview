#!/usr/bin/env bash
set -euo pipefail

es_url="${ELASTICSEARCH_URL:-http://127.0.0.1:9200}"
product_id="${PRODUCT_ID:-$((923000000 + RANDOM * 10 + RANDOM % 10))}"
tombstone_id="${TOMBSTONE_ID:-$((product_id + 1))}"

bash infra/elasticsearch/bootstrap-products-v2.sh

bulk() {
  curl -fsS -X POST "${es_url}/_bulk?require_alias=true&refresh=true" \
    -H 'Content-Type: application/x-ndjson' --data-binary "${1}"$'\n'
}

higher_action="$(jq -cn --arg id "$product_id" '{index:{_index:"products_write",_id:$id,version:8,version_type:"external"}}')"
higher_document="$(jq -cn --argjson id "$product_id" '{product_id:$id,sku:("LIVE-"+($id|tostring)),name:"Higher revision",description:"live proof",category_id:10,category_name:"Proof",price_cents:800,available_quantity:8,searchable:true,source_revision:8,source_updated_at:"2026-07-22T01:02:03Z"}')"
higher="$(bulk "$(printf '%s\n%s\n' "$higher_action" "$higher_document")")"
jq -e '.items | length == 1 and .[0].index.status == 201' <<<"$higher" >/dev/null

for revision in 8 7; do
  conflict_action="$(jq -cn --arg id "$product_id" --argjson revision "$revision" '{index:{_index:"products_write",_id:$id,version:$revision,version_type:"external"}}')"
  conflict_document="$(jq -cn --argjson id "$product_id" --argjson revision "$revision" '{product_id:$id,sku:("LIVE-"+($id|tostring)),name:"Must not overwrite",description:"conflict",category_id:10,category_name:"Proof",price_cents:$revision,available_quantity:8,searchable:true,source_revision:$revision,source_updated_at:"2026-07-22T01:02:03Z"}')"
  conflict="$(bulk "$(printf '%s\n%s\n' "$conflict_action" "$conflict_document")")"
  jq -e '.items | length == 1
    and .[0].index.status == 409
    and .[0].index.error.type == "version_conflict_engine_exception"' <<<"$conflict" >/dev/null
done

curl -fsS "${es_url}/products_write/_doc/${product_id}" | jq -e \
  '._version == 8 and ._source.source_revision == 8 and ._source.price_cents == 800 and ._source.name == "Higher revision"' >/dev/null

tombstone_action="$(jq -cn --arg id "$tombstone_id" '{index:{_index:"products_write",_id:$id,version:9,version_type:"external"}}')"
tombstone_document="$(jq -cn --argjson id "$tombstone_id" '{product_id:$id,sku:null,name:null,description:null,category_id:null,category_name:null,price_cents:null,available_quantity:null,searchable:false,source_revision:9,source_updated_at:"2026-07-22T01:02:03Z"}')"
tombstone="$(bulk "$(printf '%s\n%s\n' "$tombstone_action" "$tombstone_document")")"
jq -e '.items | length == 1 and (.[0].index.status == 200 or .[0].index.status == 201)' <<<"$tombstone" >/dev/null

curl -fsS -X POST "${es_url}/products_search/_search" \
  -H 'Content-Type: application/json' \
  -d "{\"query\":{\"ids\":{\"values\":[\"${tombstone_id}\"]}}}" | jq -e '.hits.total.value == 0' >/dev/null

echo "products_v2 external-version and filtered-alias proof passed"
