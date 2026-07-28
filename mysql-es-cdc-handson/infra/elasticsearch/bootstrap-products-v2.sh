#!/usr/bin/env bash
set -euo pipefail

es_url="${ELASTICSEARCH_URL:-http://127.0.0.1:9200}"
index="products_v2"
tmp_dir="$(mktemp -d)"
trap 'rm -rf "$tmp_dir"' EXIT

read_status() {
  local path="$1"
  local output="$2"
  curl -sS -o "$output" -w '%{http_code}' "${es_url}${path}"
}

# Preflight is deliberately read-only. No mutation is allowed until every
# preexisting template, index, and alias has passed compatibility checks.
template_payload="${tmp_dir}/template.json"
template_status="$(read_status '/_index_template/products-search' "$template_payload")"
case "$template_status" in
  200)
    if ! jq -e --slurpfile expected infra/elasticsearch/index-template.json \
      '.index_templates | length == 1
       and .[0].index_template.index_patterns == $expected[0].index_patterns
       and .[0].index_template.template.mappings == $expected[0].template.mappings
       and (.[0].index_template.template.aliases // {}) == {}
       and (.[0].index_template.template.settings.index.number_of_shards | tonumber) == $expected[0].template.settings.number_of_shards
       and (.[0].index_template.template.settings.index.number_of_replicas | tonumber) == $expected[0].template.settings.number_of_replicas' \
      "$template_payload" >/dev/null; then
      echo "Existing products-search template is incompatible" >&2
      exit 1
    fi
    template_missing=false
    ;;
  404) template_missing=true ;;
  *)
    echo "Unexpected HTTP ${template_status} while checking products-search template" >&2
    exit 1
    ;;
esac

index_payload="${tmp_dir}/index.json"
index_status="$(curl -sS -o "$index_payload" -w '%{http_code}' -I "${es_url}/${index}")"
case "$index_status" in
  200)
    mapping_payload="${tmp_dir}/mapping.json"
    curl -fsS "${es_url}/${index}/_mapping" -o "$mapping_payload"
    actual_meta="$(jq -c --arg index "$index" '.[$index].mappings._meta' "$mapping_payload")"
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
      "$mapping_payload" >/dev/null; then
      echo "Existing ${index} has incompatible field mappings" >&2
      exit 1
    fi
    index_missing=false
    ;;
  404) index_missing=true ;;
  *)
    echo "Unexpected HTTP ${index_status} while checking ${index}" >&2
    exit 1
    ;;
esac

check_alias() {
  local alias="$1"
  local expected="$2"
  local output="${tmp_dir}/alias-${alias}.json"
  local status
  status="$(read_status "/_alias/${alias}" "$output")"
  case "$status" in
    404) printf 'missing' ;;
    200)
      if ! jq -e --arg index "$index" --arg alias "$alias" --argjson expected "$expected" \
        'keys == [$index] and .[$index].aliases[$alias] == $expected' "$output" >/dev/null; then
        echo "Existing alias ${alias} is incompatible or points outside ${index}" >&2
        exit 1
      fi
      printf 'compatible'
      ;;
    *)
      echo "Unexpected HTTP ${status} while checking alias ${alias}" >&2
      exit 1
      ;;
  esac
}

write_alias_state="$(check_alias products_write '{"is_write_index":true}')"
search_alias_state="$(check_alias products_search '{"filter":{"term":{"searchable":true}}}')"

# Mutation phase starts only after the complete read-only preflight succeeds.
if [[ "$template_missing" == true ]]; then
  curl -fsS -X PUT "${es_url}/_index_template/products-search" \
    -H 'Content-Type: application/json' \
    --data-binary @infra/elasticsearch/index-template.json >/dev/null
fi

if [[ "$index_missing" == true ]]; then
  curl -fsS -X PUT "${es_url}/${index}" \
    -H 'Content-Type: application/json' \
    -d '{"mappings":{"_meta":{"schema_version":1,"deletion_mode":"tombstone","generation":"products_v2"}}}' \
    >/dev/null
fi

if [[ "$write_alias_state" == missing || "$search_alias_state" == missing ]]; then
  curl -fsS -X POST "${es_url}/_aliases" \
    -H 'Content-Type: application/json' \
    -d '{
      "actions": [
        {"add":{"index":"products_v2","alias":"products_write","is_write_index":true}},
        {"add":{"index":"products_v2","alias":"products_search","filter":{"term":{"searchable":true}}}}
      ]
    }' >/dev/null
fi

curl -fsS "${es_url}/_alias/products_write" | jq -e \
  'keys == ["products_v2"] and .products_v2.aliases.products_write.is_write_index == true' >/dev/null
curl -fsS "${es_url}/_alias/products_search" | jq -e \
  'keys == ["products_v2"] and .products_v2.aliases.products_search.filter.term.searchable == true' >/dev/null
