#!/usr/bin/env bash
set -euo pipefail

evidence="${M5_EVIDENCE_DIR:-evidence/m5/${M5_GATE_RUN:-manual}}"
mkdir -p "$evidence"
M5_EVIDENCE_DIR="$evidence" bash scenarios/scripts/run-m5-rebuild.sh

jq -e '
  length == 5 and
  (map(.scenario) | unique | length) == 5 and
  ([.[] | select(.scenario == "m5-rebuild-before-cutover-crash" and .terminal == "FAILED")] | length) == 1 and
  ([.[] | select(.scenario != "m5-rebuild-before-cutover-crash" and .terminal == "HEALTHY")] | length) == 4
' "$evidence/terminal-classifications.json" >/dev/null

curl -fsS http://127.0.0.1:8083/internal/pipeline/status >"$evidence/final-pipeline-status.json"
curl -fsS http://127.0.0.1:8082/actuator/health >"$evidence/final-consumer-health.json"
curl -fsS http://127.0.0.1:8083/actuator/health >"$evidence/final-verifier-health.json"
curl -fsS http://127.0.0.1:8082/internal/dlq/count >"$evidence/final-product-dlq.json"
curl -fsS http://127.0.0.1:8082/internal/record-dlq/count >"$evidence/final-record-dlq.json"
curl -fsS http://127.0.0.1:9200/_alias/products_search,products_write >"$evidence/final-aliases.json"
docker compose -f infra/compose.yaml exec -T mysql mysql -N -B -uroot -prootpass product_catalog \
  -e "SELECT JSON_OBJECT('closed',closed,'ownerRunId',BIN_TO_UUID(owner_run_id)) FROM product_write_gate WHERE singleton_id=1;" \
  | jq . >"$evidence/final-gate.json"

jq -e '.state == "HEALTHY" and (.activeConditions | length) == 0' "$evidence/final-pipeline-status.json" >/dev/null
jq -e '.status == "UP"' "$evidence/final-consumer-health.json" "$evidence/final-verifier-health.json" >/dev/null
jq -e '.unresolved == 0' "$evidence/final-product-dlq.json" "$evidence/final-record-dlq.json" >/dev/null
jq -e '.closed == 0 and .ownerRunId == null' "$evidence/final-gate.json" >/dev/null
jq -e 'length == 1 and (to_entries[0].value.aliases | has("products_search") and has("products_write"))' "$evidence/final-aliases.json" >/dev/null

echo "M5 rebuild end-to-end gate passed: $evidence"
