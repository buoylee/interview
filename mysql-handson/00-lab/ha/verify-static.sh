#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$ROOT/../../.." && pwd)"

docker compose --project-name mysql-ha --file "$ROOT/compose.yml" config --quiet
for script in "$ROOT"/faults/*.sh "$ROOT"/scenarios/*.sh; do bash -n "$script"; done
PYTHONPATH="$ROOT" python3 -m unittest discover -s "$ROOT/tests" -v
if rg -n 'T[B]D|T[O]DO|待[补]|待[跑]真值|place[holder]' \
  "$REPO/mysql-handson/09-replication-and-ha/ha-foundations.md" \
  "$REPO/mysql-handson/09-replication-and-ha/innodb-cluster"; then
  echo "unfinished marker found" >&2
  exit 1
fi
git -C "$REPO" diff --check
