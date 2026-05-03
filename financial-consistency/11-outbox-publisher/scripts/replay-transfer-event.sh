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

if ! command -v jq >/dev/null 2>&1; then
  echo "jq is required to build the replay envelope" >&2
  exit 1
fi

decode_base64() {
  if printf '' | base64 --decode >/dev/null 2>&1; then
    base64 --decode
  else
    base64 -D
  fi
}

ROW="$(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -N -B -ufunds -pfunds funds_core \
  -e "select message_id, aggregate_type, aggregate_id, event_type, replace(to_base64(cast(payload as char)), '\n', '') from outbox_message where message_id = '${MESSAGE_ID}'")"

if [ -z "$ROW" ]; then
  echo "message not found: $MESSAGE_ID" >&2
  exit 1
fi

IFS=$'\t' read -r ROW_MESSAGE_ID AGGREGATE_TYPE AGGREGATE_ID EVENT_TYPE PAYLOAD_BASE64 <<< "$ROW"
PAYLOAD_JSON="$(printf '%s' "$PAYLOAD_BASE64" | decode_base64)"
ENVELOPE="$(jq -cn \
  --arg messageId "$ROW_MESSAGE_ID" \
  --arg aggregateType "$AGGREGATE_TYPE" \
  --arg aggregateId "$AGGREGATE_ID" \
  --arg eventType "$EVENT_TYPE" \
  --arg payload "$PAYLOAD_JSON" \
  '{
    messageId: $messageId,
    aggregateType: $aggregateType,
    aggregateId: $aggregateId,
    eventType: $eventType,
    payload: $payload
  }')"

printf '%s:%s\n' "$AGGREGATE_ID" "$ENVELOPE" | docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka \
  /opt/kafka/bin/kafka-console-producer.sh \
  --bootstrap-server kafka:9092 \
  --topic funds.transfer.events \
  --property parse.key=true \
  --property key.separator=:
