#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

for path in \
  pom.xml \
  versions.env \
  mvnw \
  product-service/pom.xml \
  search-sync-consumer/pom.xml \
  consistency-verifier/pom.xml
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
