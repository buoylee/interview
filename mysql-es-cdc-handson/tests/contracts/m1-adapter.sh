#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

docker compose \
  -f infra/compose.yaml \
  -f infra/compose.adapter.yaml \
  config --quiet

rendered_config=$(mktemp "${TMPDIR:-/tmp}/m1-adapter-compose.XXXXXX")
profile_config=$(mktemp "${TMPDIR:-/tmp}/m1-adapter-profile-compose.XXXXXX")
mapping_select=$(mktemp "${TMPDIR:-/tmp}/m1-adapter-mapping-select.XXXXXX")
expected_mapping_select=$(mktemp "${TMPDIR:-/tmp}/m1-adapter-expected-select.XXXXXX")
trap 'rm -f "$rendered_config" "$profile_config" "$mapping_select" "$expected_mapping_select"' EXIT
docker compose \
  -f infra/compose.yaml \
  -f infra/compose.adapter.yaml \
  config --format json >"$rendered_config"
docker compose \
  -f infra/compose.yaml \
  -f infra/compose.adapter.yaml \
  --profile m0-tools \
  config --format json >"$profile_config"

jq -e --arg adapter_context "$PWD/infra/canal-adapter" '
  .services["canal-adapter-server"].image == "canal/canal-server:v1.1.8" and
  (.services["canal-adapter-server"] | has("build") | not) and
  .services["canal-adapter-server"].profiles == null and
  (.services["canal-adapter-server"].depends_on | keys) == ["mysql"] and
  .services["canal-adapter-server"].depends_on.mysql.condition == "service_healthy" and
  (.services["canal-adapter"] | has("image") | not) and
  .services["canal-adapter"].build == {
    "context": $adapter_context,
    "dockerfile": "Dockerfile"
  } and
  .services["canal-adapter"].profiles == null and
  (.services["canal-adapter"].depends_on | keys) == ["canal-adapter-server","elasticsearch"] and
  .services["canal-adapter"].depends_on["canal-adapter-server"].condition == "service_started" and
  .services["canal-adapter"].depends_on.elasticsearch.condition == "service_healthy" and
  .services["search-sync-consumer"] == null and
  .services["consistency-verifier"] == null
' "$rendered_config" >/dev/null

jq -e '
  .services["search-sync-consumer"].profiles == ["m0-tools"] and
  .services["consistency-verifier"].profiles == ["m0-tools"]
' "$profile_config" >/dev/null

jq -e '
  ([
    .services | to_entries[] as $service |
    ($service.value.ports // [])[] |
    select(.published == "8084" or .published == "11121" or .published == "11122") |
    {service: $service.key, host_ip, published, target}
  ] | sort_by(.service, .published, .target)) == [
    {"service":"canal-adapter","host_ip":"127.0.0.1","published":"8084","target":8081},
    {"service":"canal-adapter-server","host_ip":"127.0.0.1","published":"11121","target":11111},
    {"service":"canal-adapter-server","host_ip":"127.0.0.1","published":"11122","target":11112}
  ] and
  all(
    .services | to_entries[] as $service |
    ($service.value.ports // [])[];
    .host_ip == "127.0.0.1"
  )
' "$rendered_config" >/dev/null

test "$(cat infra/canal-adapter/SHA256SUMS)" = \
  "e9366226860b6939ace0eb6d46a1a365d71ab45b4292c66e73bba8d9f067a340  canal.adapter-1.1.8.tar.gz"
grep -Fxq "FROM canal/canal-server:v1.1.8" infra/canal-adapter/Dockerfile
grep -Fq "COPY artifacts/canal.adapter-1.1.8.tar.gz" infra/canal-adapter/Dockerfile
grep -Fq "COPY conf/ /opt/canal-adapter/conf/" infra/canal-adapter/Dockerfile
grep -Fxq "USER admin" infra/canal-adapter/Dockerfile
grep -Fq "291072978" infra/canal-adapter/fetch-release.sh
grep -Fxq "canal.serverMode = tcp" infra/canal-adapter-server/canal.properties
grep -Fxq "canal.instance.global.mode = spring" \
  infra/canal-adapter-server/canal.properties
grep -Fxq "canal.instance.global.lazy = false" \
  infra/canal-adapter-server/canal.properties
grep -Fxq "canal.instance.global.spring.xml = classpath:spring/file-instance.xml" \
  infra/canal-adapter-server/canal.properties
grep -Fxq "canal.instance.mysql.slaveId=1235" \
  infra/canal-adapter-server/instance.properties
grep -Fxq 'canal.instance.filter.regex=product_catalog\\.products' \
  infra/canal-adapter-server/instance.properties
grep -Fq "name: es8" infra/canal-adapter/conf/application.yml
grep -Fq "canal.tcp.server.host: canal-adapter-server:11111" \
  infra/canal-adapter/conf/application.yml
grep -Eq '^  accessKey:[[:space:]]*$' infra/canal-adapter/conf/application.yml
grep -Eq '^  secretKey:[[:space:]]*$' infra/canal-adapter/conf/application.yml

test -f infra/canal-adapter/conf/es8/products.yml
test -f infra/elasticsearch/adapter-index.json
test -f scenarios/definitions/m1-basic.json
test -x scenarios/scripts/lib-adapter.sh
test -x scenarios/scripts/run-m1-basic.sh
test -x scenarios/scripts/assert-m1-evidence.sh
test -x scenarios/scripts/derive-m1-result.sh
test -f evidence/m1/.gitkeep
if git check-ignore -q evidence/m1/.gitkeep; then
  echo "evidence/m1/.gitkeep must be tracked while runtime M1 evidence stays ignored" >&2
  exit 1
fi

grep -Fxq "dataSourceKey: defaultDS" infra/canal-adapter/conf/es8/products.yml
grep -Fxq "destination: products_adapter" infra/canal-adapter/conf/es8/products.yml
grep -Fxq "groupId: g1" infra/canal-adapter/conf/es8/products.yml
grep -Fxq "  _index: products_adapter_v1" infra/canal-adapter/conf/es8/products.yml
grep -Fxq "  _id: _id" infra/canal-adapter/conf/es8/products.yml
grep -Fxq "  upsert: true" infra/canal-adapter/conf/es8/products.yml
grep -Fxq "    FROM products p" infra/canal-adapter/conf/es8/products.yml
grep -Fxq "  etlCondition: WHERE p.id > {}" infra/canal-adapter/conf/es8/products.yml
grep -Fxq "  commitBatch: 1000" infra/canal-adapter/conf/es8/products.yml

awk '
  /^[[:space:]]+SELECT$/ { in_select = 1; next }
  /^[[:space:]]+FROM products p$/ { in_select = 0 }
  in_select {
    sub(/^[[:space:]]+/, "")
    sub(/,[[:space:]]*$/, "")
    print
  }
' infra/canal-adapter/conf/es8/products.yml >"$mapping_select"
cat >"$expected_mapping_select" <<'EOF'
p.id AS _id
p.id AS product_id
p.sku
p.name
p.description
p.category_id
p.price_cents
p.status
DATE_FORMAT(p.updated_at, '%Y-%m-%dT%H:%i:%s.%fZ') AS updated_at
EOF
diff -u "$expected_mapping_select" "$mapping_select"
! grep -Eq 'category_name|inventory|searchable|source_revision' \
  infra/canal-adapter/conf/es8/products.yml

jq -e '
  .settings == {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s"
  } and
  .mappings.dynamic == "strict" and
  (.mappings.properties | keys | sort) == [
    "category_id",
    "description",
    "name",
    "price_cents",
    "product_id",
    "sku",
    "status",
    "updated_at"
  ] and
  .mappings.properties == {
    "product_id": {"type": "long"},
    "sku": {"type": "keyword"},
    "name": {"type": "text"},
    "description": {"type": "text"},
    "category_id": {"type": "long"},
    "price_cents": {"type": "long"},
    "status": {"type": "keyword"},
    "updated_at": {"type": "date"}
  } and
  (keys | sort) == ["mappings", "settings"] and
  (.mappings | keys | sort) == ["dynamic", "properties"]
' infra/elasticsearch/adapter-index.json >/dev/null

jq -e '
  . == {
    "scenario_id": "m1-basic",
    "purpose": "Observe Adapter insert and update behavior and the official 1.1.8 computed updated_at gap",
    "source_products": [{
      "id": 1101,
      "sku": "M1-1101",
      "name": "Adapter Keyboard",
      "description": "initial",
      "category_id": 10,
      "price_cents": 100,
      "status": "ACTIVE"
    }],
    "mutations": [{
      "operation": "change_price",
      "product_id": 1101,
      "price_cents": 120
    }],
    "expected_observation": {
      "result": "OBSERVED_INSERT_UPDATE_WITH_COMPUTED_FIELD_GAP",
      "source_updated_at_non_null": true,
      "target_updated_at_is_null": true,
      "updated_at_matches_source": false,
      "final_consistency_claim": false
    }
  }
' scenarios/definitions/m1-basic.json >/dev/null

if test "${1:-}" = "--live"; then
  exec scenarios/scripts/verify-m1-topology.sh
fi
