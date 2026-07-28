#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
docker compose -f infra/compose.yaml --profile m0-tools config --quiet

rendered_config=$(mktemp "${TMPDIR:-/tmp}/m0-compose.XXXXXX")
default_config=$(mktemp "${TMPDIR:-/tmp}/m0-compose-default.XXXXXX")
trap 'rm -f "$rendered_config" "$default_config"' EXIT
docker compose -f infra/compose.yaml --profile m0-tools config --format json >"$rendered_config"
docker compose -f infra/compose.yaml config --format json >"$default_config"

jq -e '
  (.services | keys) == ["canal","elasticsearch","kafka","kafka-init","mysql","product-service","toxiproxy"] and
  .services["product-service"] != null and
  .services["search-sync-consumer"] == null and
  .services["consistency-verifier"] == null
' "$default_config" >/dev/null

jq -e '
  ([
    .services | to_entries[] as $service |
    ($service.value.ports // [])[] |
    {service: $service.key, host_ip, published, target}
  ] | sort_by(.service, .published, .target)) == [
    {"service":"canal","host_ip":"127.0.0.1","published":"11111","target":11111},
    {"service":"canal","host_ip":"127.0.0.1","published":"11112","target":11112},
    {"service":"elasticsearch","host_ip":"127.0.0.1","published":"9200","target":9200},
    {"service":"kafka","host_ip":"127.0.0.1","published":"29092","target":29092},
    {"service":"mysql","host_ip":"127.0.0.1","published":"3308","target":3306},
    {"service":"product-service","host_ip":"127.0.0.1","published":"8081","target":8081},
    {"service":"toxiproxy","host_ip":"127.0.0.1","published":"8474","target":8474},
    {"service":"toxiproxy","host_ip":"127.0.0.1","published":"8666","target":8666},
    {"service":"toxiproxy","host_ip":"127.0.0.1","published":"8667","target":8667},
    {"service":"toxiproxy","host_ip":"127.0.0.1","published":"8668","target":8668}
  ]
' "$default_config" >/dev/null

jq -e '
  (.services | keys) == ["canal","consistency-verifier","elasticsearch","kafka","kafka-init","mysql","product-service","search-sync-consumer","toxiproxy"] and
  .services.mysql.image == "mysql:8.4.8" and
  .services.canal.image == "canal/canal-server:v1.1.8" and
  .services.kafka.image == "apache/kafka:4.1.2" and
  .services["kafka-init"].image == "apache/kafka:4.1.2" and
  .services.elasticsearch.image == "docker.elastic.co/elasticsearch/elasticsearch:8.17.0" and
  .services.toxiproxy.image == "ghcr.io/shopify/toxiproxy:2.12.0" and
  .services["product-service"].image == "mysql-es-cdc-handson/product-service:0.1.0-local" and
  .services["search-sync-consumer"].image == "mysql-es-cdc-handson/search-sync-consumer:0.1.0-local" and
  .services["consistency-verifier"].image == "mysql-es-cdc-handson/consistency-verifier:0.1.0-local" and
  (.services["product-service"].depends_on | keys) == ["mysql"] and
  .services["product-service"].depends_on.mysql.condition == "service_healthy" and
  .services["search-sync-consumer"].profiles == ["m0-tools"] and
  .services["consistency-verifier"].profiles == ["m0-tools"] and
  (.services["search-sync-consumer"].depends_on | keys) == ["kafka-init","mysql","toxiproxy"] and
  .services["search-sync-consumer"].depends_on.mysql.condition == "service_healthy" and
  .services["search-sync-consumer"].depends_on["kafka-init"].condition == "service_completed_successfully" and
  .services["search-sync-consumer"].depends_on.toxiproxy.condition == "service_started" and
  .services["search-sync-consumer"].environment.SPRING_KAFKA_BOOTSTRAP_SERVERS == "toxiproxy:8667" and
  .services["search-sync-consumer"].environment.PIPELINE_ELASTICSEARCH_BASE_URL == "http://toxiproxy:8666" and
  (.services["consistency-verifier"].depends_on | keys) == ["kafka-init","mysql","toxiproxy"] and
  .services["consistency-verifier"].depends_on["kafka-init"].condition == "service_completed_successfully" and
  .services["consistency-verifier"].depends_on.mysql.condition == "service_healthy" and
  .services["consistency-verifier"].depends_on.toxiproxy.condition == "service_started" and
  .services["consistency-verifier"].environment.SPRING_DATASOURCE_USERNAME == "verifier" and
  .services["consistency-verifier"].environment.KAFKA_BOOTSTRAP_SERVERS == "toxiproxy:8667" and
  .services["consistency-verifier"].environment.SPRING_KAFKA_BOOTSTRAP_SERVERS == "toxiproxy:8667" and
  .services["consistency-verifier"].environment.VERIFICATION_ELASTICSEARCH_URL == "http://toxiproxy:8666" and
  (.services["kafka-init"].depends_on | keys) == ["kafka"] and
  .services["kafka-init"].depends_on.kafka.condition == "service_healthy" and
  (.services.canal.depends_on | keys) == ["kafka-init","mysql","toxiproxy"] and
  .services.canal.depends_on["kafka-init"].condition == "service_completed_successfully" and
  .services.canal.depends_on.mysql.condition == "service_healthy" and
  .services.canal.depends_on.toxiproxy.condition == "service_started" and
  (.services.toxiproxy.depends_on | keys) == ["elasticsearch","kafka","mysql"] and
  .services.toxiproxy.depends_on.elasticsearch.condition == "service_healthy" and
  .services.toxiproxy.depends_on.kafka.condition == "service_healthy" and
  .services.toxiproxy.depends_on.mysql.condition == "service_healthy" and
  .services["kafka-init"].entrypoint == ["/bin/bash","/create-topics.sh"] and
  .services.kafka.environment.KAFKA_NODE_ID == "1" and
  .services.kafka.environment.KAFKA_CONTROLLER_QUORUM_VOTERS == "1@kafka:9093" and
  .services.kafka.environment.KAFKA_PROCESS_ROLES == "broker,controller" and
  .services.kafka.environment.KAFKA_CONTROLLER_LISTENER_NAMES == "CONTROLLER" and
  .services.kafka.environment.KAFKA_INTER_BROKER_LISTENER_NAME == "BROKER" and
  .services.kafka.environment.KAFKA_LISTENERS == "BROKER://:9092,CLIENT://:9094,EXTERNAL://:29092,CONTROLLER://:9093" and
  .services.kafka.environment.KAFKA_ADVERTISED_LISTENERS == "BROKER://kafka:9092,CLIENT://toxiproxy:8667,EXTERNAL://localhost:29092" and
  .services.kafka.environment.KAFKA_LISTENER_SECURITY_PROTOCOL_MAP == "CONTROLLER:PLAINTEXT,BROKER:PLAINTEXT,CLIENT:PLAINTEXT,EXTERNAL:PLAINTEXT" and
  ([.services.mysql.ports[] | [.published, .target]] == [["3308",3306]]) and
  ([.services.kafka.ports[] | [.published, .target]] == [["29092",29092]]) and
  ([.services.canal.ports[] | [.published, .target]] == [["11111",11111],["11112",11112]]) and
  ([.services.elasticsearch.ports[] | [.published, .target]] == [["9200",9200]]) and
  ([.services.toxiproxy.ports[] | [.published, .target]] == [["8474",8474],["8666",8666],["8667",8667],["8668",8668]]) and
  ([.services["product-service"].ports[] | [.published, .target]] == [["8081",8081]]) and
  ([.services["search-sync-consumer"].ports[] | [.published, .target]] == [["8082",8082]]) and
  ([.services["consistency-verifier"].ports[] | [.published, .target]] == [["8083",8083]]) and
  .services.canal.environment.CANAL_AUTO_RESET_LATEST_POS_MODE == "false" and
  (.services.canal.command == ["/bin/bash","-c","chown admin:admin /home/admin/canal-data && exec /home/admin/app.sh"]) and
  any(.services.canal.volumes[]; .type == "volume" and .source == "canal-data" and .target == "/home/admin/canal-data")
' "$rendered_config" >/dev/null

jq -e '
  ([
    .services | to_entries[] as $service |
    ($service.value.ports // [])[] |
    {service: $service.key, host_ip, published, target}
  ] | sort_by(.service, .published, .target)) == [
    {"service":"canal","host_ip":"127.0.0.1","published":"11111","target":11111},
    {"service":"canal","host_ip":"127.0.0.1","published":"11112","target":11112},
    {"service":"consistency-verifier","host_ip":"127.0.0.1","published":"8083","target":8083},
    {"service":"elasticsearch","host_ip":"127.0.0.1","published":"9200","target":9200},
    {"service":"kafka","host_ip":"127.0.0.1","published":"29092","target":29092},
    {"service":"mysql","host_ip":"127.0.0.1","published":"3308","target":3306},
    {"service":"product-service","host_ip":"127.0.0.1","published":"8081","target":8081},
    {"service":"search-sync-consumer","host_ip":"127.0.0.1","published":"8082","target":8082},
    {"service":"toxiproxy","host_ip":"127.0.0.1","published":"8474","target":8474},
    {"service":"toxiproxy","host_ip":"127.0.0.1","published":"8666","target":8666},
    {"service":"toxiproxy","host_ip":"127.0.0.1","published":"8667","target":8667},
    {"service":"toxiproxy","host_ip":"127.0.0.1","published":"8668","target":8668}
  ]
' "$rendered_config" >/dev/null

for image in \
  mysql:8.4.8 \
  canal/canal-server:v1.1.8 \
  apache/kafka:4.1.2 \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0 \
  ghcr.io/shopify/toxiproxy:2.12.0
do
  grep -Fq "image: $image" infra/compose.yaml
done

grep -Fxq "canal.serverMode = kafka" infra/canal/canal.properties
grep -Fxq "canal.file.data.dir = /home/admin/canal-data" infra/canal/canal.properties
grep -Fxq "canal.mq.servers = toxiproxy:8667" infra/canal/canal.properties
grep -Fxq 'canal.auto.reset.latest.pos.mode = ${CANAL_AUTO_RESET_LATEST_POS_MODE:false}' infra/canal/canal.properties
grep -Fxq "canal.instance.global.mode = spring" infra/canal/canal.properties
grep -Fxq "canal.instance.global.lazy = false" infra/canal/canal.properties
grep -Fxq "canal.instance.global.spring.xml = classpath:spring/file-instance.xml" \
  infra/canal/canal.properties
grep -Fq "chown admin:admin /home/admin/canal-data && exec /home/admin/app.sh" \
  infra/compose.yaml
grep -Fq "canal-data:/home/admin/canal-data" infra/compose.yaml
grep -Fxq "canal.mq.topic=product-search-revisions" infra/canal/instance.properties
grep -Fxq "canal.mq.partitionsNum=3" infra/canal/instance.properties
grep -Fxq "canal.instance.master.address=toxiproxy:8668" infra/canal/instance.properties
grep -Fxq 'canal.instance.filter.regex=product_catalog\\.product_search_revision' \
  infra/canal/instance.properties
grep -Fxq "canal.mq.partitionHash=product_catalog.product_search_revision:product_id" \
  infra/canal/instance.properties

jq -e '
  length == 3 and
  (map({name,listen,upstream,enabled}) | sort_by(.name)) == [
    {"name":"canal-mysql","listen":"0.0.0.0:8668","upstream":"mysql:3306","enabled":true},
    {"name":"elasticsearch","listen":"0.0.0.0:8666","upstream":"elasticsearch:9200","enabled":true},
    {"name":"kafka","listen":"0.0.0.0:8667","upstream":"kafka:9094","enabled":true}
  ]
' infra/toxiproxy/proxies.json >/dev/null

# Fast guard only: live acceptance still proves the behavior against Kafka.
grep -Fq 'PartitionCount:' infra/kafka/create-topics.sh
grep -Fq 'expected_partitions=3' infra/kafka/create-topics.sh
grep -Fq 'if [ "$partition_count" != "$expected_partitions" ]; then' \
  infra/kafka/create-topics.sh
grep -Fq 'reset or migrate the Kafka volume' infra/kafka/create-topics.sh
grep -Fxq '  exit 1' infra/kafka/create-topics.sh
