#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
docker compose -f infra/compose.yaml config --quiet

for image in \
  mysql:8.4.8 \
  canal/canal-server:v1.1.8 \
  apache/kafka:4.1.2 \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0 \
  ghcr.io/shopify/toxiproxy:2.12.0
do
  grep -Fq "image: $image" infra/compose.yaml
done

grep -Fq "canal.serverMode = kafka" infra/canal/canal.properties
grep -Fq "canal.file.data.dir = /home/admin/canal-data" infra/canal/canal.properties
grep -Fq 'canal.auto.reset.latest.pos.mode = ${CANAL_AUTO_RESET_LATEST_POS_MODE:false}' infra/canal/canal.properties
grep -Fq "canal.instance.global.mode = spring" infra/canal/canal.properties
grep -Fq "canal.instance.global.lazy = false" infra/canal/canal.properties
grep -Fq "canal.instance.global.spring.xml = classpath:spring/file-instance.xml" \
  infra/canal/canal.properties
grep -Fq "chown admin:admin /home/admin/canal-data && exec /home/admin/app.sh" \
  infra/compose.yaml
grep -Fq "canal-data:/home/admin/canal-data" infra/compose.yaml
grep -Fq "canal.mq.topic=product-search-revisions" infra/canal/instance.properties
grep -Fq "canal.mq.partitionsNum=3" infra/canal/instance.properties
grep -Fq "product_catalog.product_search_revision:product_id" \
  infra/canal/instance.properties
