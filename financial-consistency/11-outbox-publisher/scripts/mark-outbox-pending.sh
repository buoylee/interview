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

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -ufunds -pfunds funds_core \
  -e "update outbox_message set status = 'PENDING', locked_at = null, locked_by = null where message_id = '${MESSAGE_ID}'"
