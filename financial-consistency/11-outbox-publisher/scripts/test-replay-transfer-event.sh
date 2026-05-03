#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

export MYSQL_HOST_PORT="${MYSQL_HOST_PORT:-3308}"
export KAFKA_HOST_PORT="${KAFKA_HOST_PORT:-9092}"

docker compose -f "$ROOT_DIR/docker-compose.yml" up -d mysql kafka >/dev/null

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
  --replication-factor 1 >/dev/null

if ! docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -N -B -ufunds -pfunds funds_core \
  -e "select 1 from outbox_message limit 1" >/dev/null 2>&1; then
  mvn -f "$ROOT_DIR/service/pom.xml" -Dtest=SchemaMigrationTest test >/dev/null
fi

MESSAGE_ID="M-script-replay-test"
TRANSFER_ID="T-script-replay-test"

cleanup_fixture() {
  docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -ufunds -pfunds funds_core <<SQL >/dev/null 2>&1 || true
delete from consumer_processed_event where event_id = '$MESSAGE_ID';
delete from outbox_message where message_id = '$MESSAGE_ID';
SQL
}

fixture_count() {
  docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -N -B -ufunds -pfunds funds_core <<SQL
select count(*) from outbox_message where message_id = '$MESSAGE_ID';
SQL
}

trap cleanup_fixture EXIT

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -ufunds -pfunds funds_core <<SQL >/dev/null
delete from consumer_processed_event where event_id = '$MESSAGE_ID';
delete from outbox_message where message_id = '$MESSAGE_ID';
insert into outbox_message (
  message_id, aggregate_type, aggregate_id, event_type, payload, status
) values (
  '$MESSAGE_ID',
  'TRANSFER',
  '$TRANSFER_ID',
  'TransferSucceeded',
  json_object(
    'transferId', '$TRANSFER_ID',
    'fromAccountId', 'A-001',
    'toAccountId', 'B-001',
    'currency', 'USD',
    'amount', '42.0000'
  ),
  'PUBLISHED'
);
SQL

START_OFFSET="$(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka \
  /opt/kafka/bin/kafka-get-offsets.sh \
  --bootstrap-server kafka:9092 \
  --topic funds.transfer.events \
  | awk -F: '$2 == "0" {print $3}')"

bash "$ROOT_DIR/scripts/replay-transfer-event.sh" "$MESSAGE_ID"

CONSUMED="$(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic funds.transfer.events \
  --partition 0 \
  --offset "$START_OFFSET" \
  --max-messages 1 \
  --timeout-ms 10000 \
  --property print.key=true \
  --property key.separator='|')"

KEY="${CONSUMED%%|*}"
VALUE="${CONSUMED#*|}"

test "$KEY" = "$TRANSFER_ID"
printf '%s' "$VALUE" | jq -e \
  --arg message_id "$MESSAGE_ID" \
  --arg transfer_id "$TRANSFER_ID" \
  '
  .messageId == $message_id
  and .aggregateType == "TRANSFER"
  and .aggregateId == $transfer_id
  and .eventType == "TransferSucceeded"
  and ((.payload | fromjson).transferId == $transfer_id)
  ' >/dev/null

cleanup_fixture
trap - EXIT

test "$(fixture_count)" = "0"
