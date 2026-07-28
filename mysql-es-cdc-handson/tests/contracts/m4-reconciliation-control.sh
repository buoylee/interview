#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

grep -Fq 'CREATE TABLE IF NOT EXISTS source_change_watermark' infra/mysql/init/04-reconciliation-control.sql
grep -Fq 'ON DUPLICATE KEY UPDATE value = value' infra/mysql/init/04-reconciliation-control.sql
grep -Fq 'change epoch' infra/mysql/init/04-reconciliation-control.sql
grep -Fq 'bash infra/mysql/verify-reconciliation-control-schema.sh product_catalog' \
  infra/mysql/apply-reconciliation-control.sh

rendered=$(mktemp "${TMPDIR:-/tmp}/m4-compose.XXXXXX")
trap 'rm -f "$rendered"' EXIT
docker compose -f infra/compose.yaml --profile m0-tools config --format json >"$rendered"
jq -e '
  .services["consistency-verifier"].ports == [{"mode":"ingress","target":8083,"published":"8083","protocol":"tcp","host_ip":"127.0.0.1"}] and
  .services["consistency-verifier"].environment.SPRING_DATASOURCE_URL == "jdbc:mysql://mysql:3306/product_catalog?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC" and
  .services["consistency-verifier"].environment.SPRING_DATASOURCE_USERNAME == "verifier" and
  .services["consistency-verifier"].environment.SPRING_KAFKA_BOOTSTRAP_SERVERS == "toxiproxy:8667" and
  .services["consistency-verifier"].environment.VERIFICATION_ELASTICSEARCH_URL == "http://toxiproxy:8666" and
  (.services["consistency-verifier"].depends_on | keys) == ["kafka-init","mysql","toxiproxy"]
' "$rendered" >/dev/null

pom=consistency-verifier/pom.xml
for artifact in spring-boot-starter-actuator spring-boot-starter-webmvc spring-boot-starter-jdbc spring-kafka mysql-connector-j spring-boot-starter-test; do
  grep -Fq "<artifactId>$artifact</artifactId>" "$pom"
done
if grep -Fq '<artifactId>search-sync-consumer</artifactId>' "$pom"; then
  echo 'verifier must not depend on search-sync-consumer' >&2
  exit 1
fi
