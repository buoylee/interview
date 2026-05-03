#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -ufunds -pfunds funds_core <<'SQL'
insert into transfer_order (transfer_id, request_id, from_account_id, to_account_id, currency, amount, status)
values ('BAD-LEDGER-1', 'manual-bad-ledger', 'A-001', 'B-001', 'USD', 10.0000, 'SUCCEEDED')
on duplicate key update status = values(status);

insert ignore into ledger_entry (entry_id, transfer_id, account_id, direction, currency, amount, entry_type)
values ('BAD-LEDGER-1-DEBIT', 'BAD-LEDGER-1', 'A-001', 'DEBIT', 'USD', 10.0000, 'TRANSFER');
SQL
