#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: replay-transfer-event.sh <message-id>" >&2
  exit 1
fi

MESSAGE_ID="$1"
if [[ ! "$MESSAGE_ID" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
  echo "message id may only contain letters, numbers, underscore, dot, colon, or dash" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PAYLOAD="$(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -N -B -ufunds -pfunds funds_core \
  -e "select concat(aggregate_id, ':', json_object('messageId', message_id, 'aggregateType', aggregate_type, 'aggregateId', aggregate_id, 'eventType', event_type, 'payload', cast(payload as char))) from outbox_message where message_id = '${MESSAGE_ID}'")"

if [ -z "$PAYLOAD" ]; then
  echo "message not found: $MESSAGE_ID" >&2
  exit 1
fi

printf '%s\n' "$PAYLOAD" | docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic funds.transfer.events \
  --property parse.key=true \
  --property key.separator=:
