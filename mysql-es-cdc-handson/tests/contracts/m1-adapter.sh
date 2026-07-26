#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

docker compose \
  -f infra/compose.yaml \
  -f infra/compose.adapter.yaml \
  config --quiet

rendered_config=$(mktemp "${TMPDIR:-/tmp}/m1-adapter-compose.XXXXXX")
profile_config=$(mktemp "${TMPDIR:-/tmp}/m1-adapter-profile-compose.XXXXXX")
trap 'rm -f "$rendered_config" "$profile_config"' EXIT
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

if test "${1:-}" = "--live"; then
  exec scenarios/scripts/verify-m1-topology.sh
fi
