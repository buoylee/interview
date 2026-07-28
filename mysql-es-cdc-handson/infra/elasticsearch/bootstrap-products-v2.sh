#!/usr/bin/env bash
set -euo pipefail

es_url="${ELASTICSEARCH_URL:-http://127.0.0.1:9200}"
index="products_v2"

curl -fsS -X PUT "${es_url}/_index_template/products-search" \
  -H 'Content-Type: application/json' \
  --data-binary @infra/elasticsearch/index-template.json >/dev/null

index_status="$(curl -sS -o /dev/null -w '%{http_code}' -I "${es_url}/${index}")"
case "$index_status" in
  200)
    mapping_payload="$(curl -fsS "${es_url}/${index}/_mapping")"
    actual_meta="$(jq -c --arg index "$index" '.[$index].mappings._meta' <<<"$mapping_payload")"
    if ! jq -e '.schema_version == 1
      and .deletion_mode == "tombstone"
      and .generation == "products_v2"
      and (keys | sort) == ["deletion_mode", "generation", "schema_version"]' <<<"$actual_meta" >/dev/null; then
      echo "Existing ${index} has incompatible _meta: ${actual_meta}" >&2
      exit 1
    fi
    if ! jq -e --arg index "$index" --slurpfile expected infra/elasticsearch/index-template.json \
      '.[$index].mappings.dynamic == $expected[0].template.mappings.dynamic
       and .[$index].mappings.properties == $expected[0].template.mappings.properties' \
      <<<"$mapping_payload" >/dev/null; then
      echo "Existing ${index} has incompatible field mappings" >&2
      exit 1
    fi
    ;;
  404)
    curl -fsS -X PUT "${es_url}/${index}" \
      -H 'Content-Type: application/json' \
      -d '{"mappings":{"_meta":{"schema_version":1,"deletion_mode":"tombstone","generation":"products_v2"}}}' \
      >/dev/null
    ;;
  *)
    echo "Unexpected HTTP ${index_status} while checking ${index}" >&2
    exit 1
    ;;
esac

check_existing_alias() {
  local alias="$1"
  local expected="$2"
  local status payload
  status="$(curl -sS -o /dev/null -w '%{http_code}' "${es_url}/_alias/${alias}")"
  case "$status" in
    404) return 0 ;;
    200)
      payload="$(curl -fsS "${es_url}/_alias/${alias}")"
      if ! jq -e --arg index "$index" --arg alias "$alias" --argjson expected "$expected" \
        'keys == [$index] and .[$index].aliases[$alias] == $expected' <<<"$payload" >/dev/null; then
        echo "Existing alias ${alias} is incompatible or points outside ${index}" >&2
        exit 1
      fi
      ;;
    *)
      echo "Unexpected HTTP ${status} while checking alias ${alias}" >&2
      exit 1
      ;;
  esac
}

check_existing_alias products_write '{"is_write_index":true}'
check_existing_alias products_search '{"filter":{"term":{"searchable":true}}}'

curl -fsS -X POST "${es_url}/_aliases" \
  -H 'Content-Type: application/json' \
  -d '{
    "actions": [
      {"add":{"index":"products_v2","alias":"products_write","is_write_index":true}},
      {"add":{"index":"products_v2","alias":"products_search","filter":{"term":{"searchable":true}}}}
    ]
  }' >/dev/null

curl -fsS "${es_url}/_alias/products_write" | jq -e \
  'keys == ["products_v2"] and .products_v2.aliases.products_write.is_write_index == true' >/dev/null
curl -fsS "${es_url}/_alias/products_search" | jq -e \
  'keys == ["products_v2"] and .products_v2.aliases.products_search.filter.term.searchable == true' >/dev/null
