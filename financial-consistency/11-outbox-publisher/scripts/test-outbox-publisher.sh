#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/service"

export MYSQL_HOST_PORT="${MYSQL_HOST_PORT:-3308}"
export KAFKA_HOST_PORT="${KAFKA_HOST_PORT:-9092}"

docker compose -f "$ROOT_DIR/docker-compose.yml" up -d mysql kafka

for attempt in {1..90}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -prootpass --silent >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 90 ]; then
    echo "MySQL did not become ready in time" >&2
    exit 1
  fi
done

for attempt in {1..90}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server kafka:9092 --list >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 90 ]; then
    echo "Kafka did not become ready in time" >&2
    exit 1
  fi
done

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create \
  --if-not-exists \
  --topic funds.transfer.events \
  --partitions 1 \
  --replication-factor 1

mvn -f "$SERVICE_DIR/pom.xml" test
bash "$ROOT_DIR/scripts/test-replay-transfer-event.sh"
