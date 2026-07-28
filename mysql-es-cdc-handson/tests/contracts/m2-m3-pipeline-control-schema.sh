#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
fixture_schema="task4_wrong_check_fixture"

cleanup() {
  docker compose -f infra/compose.yaml exec -T mysql \
    mysql -uroot -prootpass -e "DROP DATABASE IF EXISTS ${fixture_schema}" >/dev/null 2>&1
}
trap cleanup EXIT
cleanup

docker compose -f infra/compose.yaml exec -T mysql \
  mysql -uroot -prootpass -e "
    CREATE DATABASE ${fixture_schema};
    CREATE TABLE ${fixture_schema}.sync_dlq_record LIKE product_catalog.sync_dlq_record;
    CREATE TABLE ${fixture_schema}.sync_record_dlq LIKE product_catalog.sync_record_dlq;
    ALTER TABLE ${fixture_schema}.sync_dlq_record
      ADD CONSTRAINT ck_dlq_identity CHECK (
        event_id = CONCAT(topic_name, ':', partition_no, ':', offset_no, ':', product_id)),
      ADD CONSTRAINT ck_dlq_coordinates CHECK (
        partition_no >= 0 AND offset_no >= 0 AND product_id > 0 AND source_revision > 0),
      ADD CONSTRAINT ck_dlq_attempts CHECK (attempts >= 0),
      ADD CONSTRAINT ck_dlq_lifecycle CHECK (
        (status = 'PENDING' AND resolved_at IS NULL)
        OR (status = 'RESOLVED' AND resolved_at IS NOT NULL));
    ALTER TABLE ${fixture_schema}.sync_record_dlq
      ADD CONSTRAINT ck_record_dlq_identity CHECK (
        record_id = CONCAT(topic_name, ':', partition_no, ':', offset_no)),
      ADD CONSTRAINT ck_record_dlq_coordinates CHECK (partition_no >= 0 AND offset_no >= 0),
      ADD CONSTRAINT ck_record_dlq_attempts CHECK (attempts > 0),
      ADD CONSTRAINT ck_record_dlq_lifecycle CHECK (
        (status = 'PENDING' AND resolved_at IS NULL)
        OR (status = 'RESOLVED' AND resolved_at IS NOT NULL));
  "

output_file="$(mktemp)"
trap 'rm -f "$output_file"; cleanup' EXIT
if bash infra/mysql/verify-pipeline-control-schema.sh "$fixture_schema" >"$output_file" 2>&1; then
  echo "schema verifier accepted a same-name wrong CHECK clause" >&2
  cat "$output_file" >&2
  exit 1
fi
grep -F "checks:sync_dlq_record" "$output_file" >/dev/null
grep -F "ck_dlq_attempts:(attempts>=0)" "$output_file" >/dev/null
rm -f "$output_file"
cleanup
trap - EXIT
