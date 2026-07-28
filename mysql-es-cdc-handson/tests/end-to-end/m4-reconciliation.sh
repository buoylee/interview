#!/usr/bin/env bash
set -euo pipefail

round="${M4_GATE_RUN:-manual}"
evidence="${M4_EVIDENCE_DIR:-evidence/m4/gate-${round}}"
M4_EVIDENCE_DIR="$evidence" bash scenarios/scripts/run-m4-reconciliation.sh

jq -e '
  length==7
  and map(.scenario)|unique|length==7
  and any(.[];.scenario=="m4-source-moves-during-scan" and .classification=="INCONCLUSIVE" and .repair=="REJECTED")
  and any(.[];.scenario=="m4-consumer-projection-bug" and .difference=="MODIFIED/category_name" and .fresh_pass=="PASS" and .state_after=="HEALTHY")
  and ([.[]|select(.scenario!="m4-source-moves-during-scan")|.fresh_pass]|all(.=="PASS"))
' "$evidence/terminal-classifications.json" >/dev/null

curl -fsS http://127.0.0.1:8083/internal/pipeline/status >"$evidence/final-status.json"
curl -fsS http://127.0.0.1:8083/actuator/health >"$evidence/final-health.json"
curl -fsS http://127.0.0.1:8083/actuator/metrics/cdc_reconciliation_last_success_epoch_seconds >"$evidence/final-last-success-metric.json"
curl -fsS http://127.0.0.1:8082/internal/dlq/count >"$evidence/final-product-dlq.json"
curl -fsS http://127.0.0.1:8082/internal/record-dlq/count >"$evidence/final-record-dlq.json"

jq -e '.state=="HEALTHY" and .kafkaLag==0 and .unresolvedDlq==0 and .latestRunStatus=="PASS" and .latestDifferenceCount==0 and (.activeConditions|length)==0' "$evidence/final-status.json" >/dev/null
jq -e '.status=="UP"' "$evidence/final-health.json" >/dev/null
jq -e '.measurements[0].value>0' "$evidence/final-last-success-metric.json" >/dev/null
jq -e '.unresolved==0' "$evidence/final-product-dlq.json" "$evidence/final-record-dlq.json" >/dev/null

docker compose -f infra/compose.yaml exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e \
  "SELECT COUNT(*) FROM verification_difference WHERE repaired_at IS NULL;" | grep -qx 0

echo "M4 end-to-end gate passed: $evidence"
