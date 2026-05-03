#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: delete-outbox-for-transfer.sh <transfer-id>" >&2
  exit 1
fi

TRANSFER_ID="$1"
if [[ ! "$TRANSFER_ID" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
  echo "transfer id may only contain letters, numbers, underscore, dot, colon, or dash" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -ufunds -pfunds funds_core \
  -e "delete from outbox_message where aggregate_type = 'TRANSFER' and aggregate_id = '${TRANSFER_ID}'"
