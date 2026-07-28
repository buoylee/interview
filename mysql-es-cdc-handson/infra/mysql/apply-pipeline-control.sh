#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
docker compose -f infra/compose.yaml exec -T mysql \
  mysql -uroot -prootpass \
  < infra/mysql/init/03-pipeline-control.sql
bash infra/mysql/verify-pipeline-control-schema.sh product_catalog
