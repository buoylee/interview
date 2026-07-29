#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
migration=infra/mysql/init/06-m6-condition-ownership.sql
test -f "$migration" || { echo 'missing M6 condition ownership migration' >&2; exit 1; }
grep -Fq 'owner_rebuild_run_id' "$migration"
grep -Fq 'rebuild_reason' "$migration"

mysql=(docker compose -f infra/compose.yaml exec -T mysql mysql -uroot -prootpass product_catalog)
before="$(${mysql[@]} -N -B -e "SELECT COUNT(*) FROM rebuild_run; SELECT COUNT(*) FROM pipeline_condition")"
for round in 1 2; do
  bash infra/mysql/apply-reconciliation-control.sh >/dev/null
  after="$(${mysql[@]} -N -B -e "SELECT COUNT(*) FROM rebuild_run; SELECT COUNT(*) FROM pipeline_condition")"
  test "$after" = "$before" || { echo "ownership migration changed rows in round $round" >&2; exit 1; }
done

${mysql[@]} -N -B -e "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='product_catalog' AND TABLE_NAME='pipeline_condition' AND COLUMN_NAME='owner_rebuild_run_id'" | grep -Fx owner_rebuild_run_id >/dev/null
${mysql[@]} -N -B -e "SELECT COLUMN_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA='product_catalog' AND TABLE_NAME='rebuild_run' AND COLUMN_NAME='rebuild_reason'" | grep -Fx rebuild_reason >/dev/null
echo 'M6 condition ownership migration passed'
