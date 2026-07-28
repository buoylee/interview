#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
for migration in 03-pipeline-control.sql 04-reconciliation-control.sql 05-rebuild-control.sql; do
  docker compose -f infra/compose.yaml exec -T mysql \
    mysql -uroot -prootpass <"infra/mysql/init/$migration"
done
bash infra/mysql/verify-pipeline-control-schema.sh product_catalog
bash infra/mysql/verify-reconciliation-control-schema.sh product_catalog
bash infra/mysql/verify-rebuild-control-schema.sh product_catalog
