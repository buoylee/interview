#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: mark-outbox-pending.sh <message-id>" >&2
  exit 1
fi

MESSAGE_ID="$1"
if [[ ! "$MESSAGE_ID" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
  echo "message id may only contain letters, numbers, underscore, dot, colon, or dash" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

EXISTS="$(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -N -B -ufunds -pfunds funds_core \
  -e "select count(*) from outbox_message where message_id = '${MESSAGE_ID}'")"

if [ "$EXISTS" -ne 1 ]; then
  echo "message not found: $MESSAGE_ID" >&2
  exit 1
fi

AFFECTED_ROWS="$(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -N -B -ufunds -pfunds funds_core \
  -e "update outbox_message set status = 'PENDING', locked_at = null, locked_by = null, published_at = null where message_id = '${MESSAGE_ID}'; select row_count();")"

if [ "$AFFECTED_ROWS" -ne 1 ]; then
  echo "fixture reset failed: expected to update 1 outbox message, updated $AFFECTED_ROWS" >&2
  exit 1
fi

echo "fixture reset: marked outbox message $MESSAGE_ID as PENDING, cleared locks, and cleared published_at"
echo "affected rows: $AFFECTED_ROWS"
