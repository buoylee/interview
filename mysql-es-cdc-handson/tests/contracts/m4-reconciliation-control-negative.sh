#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
compose=(docker compose -f infra/compose.yaml)
extra_grant=false
fk_modified=false
index_invisible=false

cleanup() {
  if $extra_grant; then
    "${compose[@]}" exec -T mysql mysql -uroot -prootpass product_catalog \
      -e "REVOKE INSERT ON product_catalog.source_change_watermark FROM 'verifier'@'%';" \
      >/dev/null 2>&1 || true
    extra_grant=false
  fi
  if $fk_modified; then
    "${compose[@]}" exec -T mysql mysql -uroot -prootpass product_catalog \
      -e "ALTER TABLE verification_difference DROP FOREIGN KEY fk_verification_difference_run;" \
      >/dev/null 2>&1 || true
    "${compose[@]}" exec -T mysql mysql -uroot -prootpass product_catalog -e "
      ALTER TABLE verification_difference
        ADD CONSTRAINT fk_verification_difference_run FOREIGN KEY (run_id)
        REFERENCES verification_run(run_id) ON UPDATE NO ACTION ON DELETE NO ACTION;
    " >/dev/null 2>&1 || true
    fk_modified=false
  fi
  if $index_invisible; then
    "${compose[@]}" exec -T mysql mysql -uroot -prootpass product_catalog \
      -e "ALTER TABLE verification_run ALTER INDEX idx_verification_run_finished VISIBLE;" \
      >/dev/null 2>&1 || true
    index_invisible=false
  fi
}
trap cleanup EXIT

must_reject() {
  local label=$1
  if bash infra/mysql/verify-reconciliation-control-schema.sh product_catalog >/dev/null 2>&1; then
    echo "schema verifier accepted $label" >&2
    exit 1
  fi
}

extra_grant=true
"${compose[@]}" exec -T mysql mysql -uroot -prootpass product_catalog \
  -e "GRANT INSERT ON product_catalog.source_change_watermark TO 'verifier'@'%';"
must_reject 'an extra fact/control-table DML grant'
cleanup

fk_modified=true
"${compose[@]}" exec -T mysql mysql -uroot -prootpass product_catalog \
  -e "ALTER TABLE verification_difference DROP FOREIGN KEY fk_verification_difference_run;"
"${compose[@]}" exec -T mysql mysql -uroot -prootpass product_catalog -e "
  ALTER TABLE verification_difference
    ADD CONSTRAINT fk_verification_difference_run FOREIGN KEY (run_id)
    REFERENCES verification_run(run_id) ON UPDATE NO ACTION ON DELETE CASCADE;
"
must_reject 'an ON DELETE CASCADE FK'
cleanup

index_invisible=true
"${compose[@]}" exec -T mysql mysql -uroot -prootpass product_catalog \
  -e "ALTER TABLE verification_run ALTER INDEX idx_verification_run_finished INVISIBLE;"
must_reject 'an invisible index'
cleanup

trap - EXIT
bash infra/mysql/verify-reconciliation-control-schema.sh product_catalog
