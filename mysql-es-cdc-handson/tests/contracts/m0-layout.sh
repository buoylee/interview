#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

for path in \
  pom.xml \
  versions.env \
  mvnw \
  product-service/pom.xml \
  search-sync-consumer/pom.xml \
  consistency-verifier/pom.xml \
  product-service/Dockerfile \
  search-sync-consumer/Dockerfile \
  consistency-verifier/Dockerfile \
  scenarios/scripts/wait-for-http.sh \
  scenarios/scripts/smoke-m0.sh \
  scenarios/scripts/decode-canal-meta.sh \
  scenarios/scripts/assert-cursor-advanced.sh \
  scenarios/scripts/classify-canal-stop-npe.sh \
  scenarios/scripts/assert-m0-evidence.sh \
  scenarios/scripts/record-image-digests.sh \
  scenarios/scripts/verify-product-transactions.sh \
  tests/contracts/m0-evidence.sh \
  Makefile \
  README.md \
  docs/00-goals-and-invariants.md \
  evidence/m0/.gitkeep
do
  test -f "$path"
done

grep -Fq "SPRING_BOOT_VERSION=4.1.0" versions.env
grep -Fq "MYSQL_VERSION=8.4.8" versions.env
grep -Fq "CANAL_VERSION=1.1.8" versions.env
grep -Fq "KAFKA_VERSION=4.1.2" versions.env
grep -Fq "ELASTICSEARCH_VERSION=8.17.0" versions.env
grep -Fq "TOXIPROXY_VERSION=2.12.0" versions.env
grep -Fq "<java.version>21</java.version>" pom.xml

test "$(find . -name pom.xml -not -path '*/target/*' | wc -l | tr -d ' ')" = "4"

for script in scenarios/scripts/*.sh tests/contracts/*.sh; do
  test -x "$script"
done

for dockerfile in \
  product-service/Dockerfile \
  search-sync-consumer/Dockerfile \
  consistency-verifier/Dockerfile
do
  test "$(sed -n '1p' "$dockerfile")" = "FROM eclipse-temurin:21-jre"
done
