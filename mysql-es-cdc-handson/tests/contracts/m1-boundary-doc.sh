#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

test -x scenarios/scripts/render-m1-boundary.sh
test -x scenarios/scripts/assert-m1-boundary-doc.sh
test -x scenarios/scripts/build-m1-claim-manifest.sh
grep -Eq '^up-adapter:' Makefile
grep -Eq '^scenario-m1:' Makefile
grep -Eq '^verify-m1:' Makefile
grep -Eq '^\.PHONY:.*(^|[[:space:]])gate-m1([[:space:]]|$)' Makefile

gate_recipe=$(awk '
  /^gate-m1:/ { in_gate = 1; next }
  in_gate && /^[^[:space:]#][^:]*:/ { exit }
  in_gate { print }
' Makefile)

step_line() {
  local expected="$1"
  printf '%s\n' "$gate_recipe" | grep -nF "$expected" | head -n 1 | cut -d: -f1
}

verify_line=$(step_line '$(MAKE) verify-m1')
stop_line=$(step_line '$(COMPOSE_ADAPTER) stop canal-adapter canal-adapter-server')
remove_line=$(step_line '$(COMPOSE_ADAPTER) rm -f canal-adapter canal-adapter-server')
absence_line=$(step_line '$(COMPOSE_ADAPTER) ps -a -q canal-adapter canal-adapter-server')
reset_line=$(step_line '$(MAKE) reset')
smoke_line=$(step_line '$(MAKE) smoke-m0')
docs_clean_line=$(step_line 'git diff --exit-code -- docs/01-canal-boundary.md')
tracked_clean_line=$(step_line 'git status --porcelain --untracked-files=no')

test "$verify_line" -lt "$stop_line"
test "$stop_line" -lt "$remove_line"
test "$remove_line" -lt "$absence_line"
test "$absence_line" -lt "$reset_line"
test "$reset_line" -lt "$smoke_line"
test "$smoke_line" -lt "$docs_clean_line"
test "$docs_clean_line" -lt "$tracked_clean_line"

output=$(mktemp "${TMPDIR:-/tmp}/m1-boundary-doc.XXXXXX")
fixture_root=$(mktemp -d "${TMPDIR:-/tmp}/m1-boundary-fixtures.XXXXXX")
trap 'rm -f "$output"; rm -rf "$fixture_root"' EXIT
M1_BOUNDARY_OUTPUT="$output" bash scenarios/scripts/render-m1-boundary.sh
bash scenarios/scripts/assert-m1-boundary-doc.sh "$output"
diff -u "$output" docs/01-canal-boundary.md

copy_evidence() {
  local destination="$1"
  mkdir -p "$destination"
  cp -R evidence/m1/m1-basic "$destination/"
  cp -R evidence/m1/m1-restart "$destination/"
  cp -R evidence/m1/m1-hard-delete "$destination/"
  cp -R evidence/m1/m1-bulk-partial "$destination/"
}

coercion_root="$fixture_root/coercion"
copy_evidence "$coercion_root"
M1_EVIDENCE_DIR="$coercion_root" \
M1_BOUNDARY_OUT="$fixture_root/coercion.md" \
  bash scenarios/scripts/render-m1-boundary.sh
grep -Fq 'observed coercion boundary' "$fixture_root/coercion.md"

genuine_root="$fixture_root/genuine"
copy_evidence "$genuine_root"
genuine_partial="$genuine_root/m1-bulk-partial"
cutoff=$(jq -r '.java_cutoff_utc' "$genuine_partial/adapter-partial-run.json")
printf '%s ERROR Bulk request failed mapper_parsing_exception value [1000] out of range for byte\n' \
  "$cutoff" >"$genuine_partial/adapter-partial-error.log"
jq '.deadline_reached = false | .error_observed = true' \
  "$genuine_partial/partial-observation.json" \
  >"$genuine_partial/partial-observation.json.tmp"
mv "$genuine_partial/partial-observation.json.tmp" \
  "$genuine_partial/partial-observation.json"
printf '%s\n' \
  '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1402","transport_ok":true,"http_status":404,"body":{"_index":"products_adapter_v1","_id":"1402","found":false}}' \
  >"$genuine_partial/1402-before-fix.json"
bash scenarios/scripts/derive-m1-bulk-partial-result.sh "$genuine_partial" \
  >"$genuine_partial/result.json"
M1_EVIDENCE_DIR="$genuine_root" \
M1_BOUNDARY_OUT="$fixture_root/genuine.md" \
  bash scenarios/scripts/render-m1-boundary.sh
grep -Fq 'did produce a genuine Bulk partial failure' "$fixture_root/genuine.md"

auto_retry_root="$fixture_root/auto-retry"
copy_evidence "$auto_retry_root"
auto_retry_partial="$auto_retry_root/m1-bulk-partial"
cp "$auto_retry_partial/1402-final.json" \
  "$auto_retry_partial/1402-after-restart.json"
jq '.deadline_reached = false' "$auto_retry_partial/retry-observation.json" \
  >"$auto_retry_partial/retry-observation.json.tmp"
mv "$auto_retry_partial/retry-observation.json.tmp" \
  "$auto_retry_partial/retry-observation.json"
jq '
  .invoked = false |
  .transport_ok = null |
  .http_status = null |
  .response_body = null
' "$auto_retry_partial/etl-action.json" \
  >"$auto_retry_partial/etl-action.json.tmp"
mv "$auto_retry_partial/etl-action.json.tmp" \
  "$auto_retry_partial/etl-action.json"
bash scenarios/scripts/derive-m1-bulk-partial-result.sh "$auto_retry_partial" \
  >"$auto_retry_partial/result.json"
M1_EVIDENCE_DIR="$auto_retry_root" \
M1_BOUNDARY_OUT="$fixture_root/auto-retry.md" \
  bash scenarios/scripts/render-m1-boundary.sh
if ! grep -Fq \
    'was verified but not invoked because the invalid item automatically reappeared' \
    "$fixture_root/auto-retry.md"; then
  echo "auto-retry document did not say ETL was skipped after automatic recovery" >&2
  exit 1
fi
if grep -Fq 'before invoking `POST /etl/es8/products.yml?params=1401`' \
    "$fixture_root/auto-retry.md"; then
  echo "auto-retry document falsely claimed the ETL endpoint was invoked" >&2
  exit 1
fi

etl_failure_root="$fixture_root/etl-failure"
copy_evidence "$etl_failure_root"
etl_failure_partial="$etl_failure_root/m1-bulk-partial"
printf '%s\n' \
  '{"requested_url":"http://127.0.0.1:9200/products_adapter_v1/_doc/1402","transport_ok":true,"http_status":404,"body":{"_index":"products_adapter_v1","_id":"1402","found":false}}' \
  >"$etl_failure_partial/1402-final.json"
if bash scenarios/scripts/derive-m1-bulk-partial-result.sh "$etl_failure_partial" \
    >"$etl_failure_partial/result.json" 2>/dev/null; then
  if M1_EVIDENCE_DIR="$etl_failure_root" \
      M1_BOUNDARY_OUT="$fixture_root/etl-failure.md" \
      bash scenarios/scripts/render-m1-boundary.sh >/dev/null 2>&1; then
    echo "renderer emitted a successful document for failed ETL completion" >&2
    exit 1
  fi
fi
test ! -e "$fixture_root/etl-failure.md"

stable_a="$fixture_root/stable-a"
stable_b="$fixture_root/stable-b"
copy_evidence "$stable_a"
copy_evidence "$stable_b"
jq '.updated_at = "2026-07-26T16:00:00.000001Z"' \
  "$stable_b/m1-basic/mysql-insert-snapshot.json" \
  >"$stable_b/m1-basic/mysql-insert-snapshot.json.tmp"
mv "$stable_b/m1-basic/mysql-insert-snapshot.json.tmp" \
  "$stable_b/m1-basic/mysql-insert-snapshot.json"
jq '.updated_at = "2026-07-26T16:00:01.000001Z"' \
  "$stable_b/m1-basic/mysql-snapshot.json" \
  >"$stable_b/m1-basic/mysql-snapshot.json.tmp"
mv "$stable_b/m1-basic/mysql-snapshot.json.tmp" \
  "$stable_b/m1-basic/mysql-snapshot.json"
bash scenarios/scripts/derive-m1-result.sh "$stable_b/m1-basic" \
  >"$stable_b/m1-basic/result.json"
test "$(sha256sum "$stable_a/m1-basic/result.json" | awk '{print $1}')" != \
  "$(sha256sum "$stable_b/m1-basic/result.json" | awk '{print $1}')"
M1_EVIDENCE_DIR="$stable_a" M1_BOUNDARY_OUT="$fixture_root/stable-a.md" \
  bash scenarios/scripts/render-m1-boundary.sh
M1_EVIDENCE_DIR="$stable_b" M1_BOUNDARY_OUT="$fixture_root/stable-b.md" \
  bash scenarios/scripts/render-m1-boundary.sh
cmp -s "$fixture_root/stable-a.md" "$fixture_root/stable-b.md"
