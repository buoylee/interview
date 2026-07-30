#!/usr/bin/env bash
set -euo pipefail

definitions=(
  m5-concurrent-rebuild
  m5-rebuild-before-cutover-crash
  m5-rebuild-after-cutover-crash
  m5-kafka-gap-rebuild
  m5-mysql-binlog-gap-rebuild
)
for scenario in "${definitions[@]}"; do
  file="scenarios/definitions/${scenario}.json"
  test -f "$file"
  jq -e --arg id "$scenario" '.scenario_id==$id' "$file" >/dev/null
done

runner=scenarios/scripts/run-m5-rebuild.sh
reset=scenarios/scripts/reset-canal-position.sh
e2e=tests/end-to-end/m5-rebuild.sh
runbook=docs/05-rebuild-runbook.md
for file in "$runner" "$reset" "$e2e" "$runbook"; do test -f "$file"; done

for phase in SNAPSHOTTING GATING VERIFYING CUTTING_OVER CUTOVER_COMMITTED COMPLETED FAILED; do
  grep -Fq "$phase" "$runner"
done
for evidence in source_watermark startOffsets barrierOffsets shadowOffsets verificationRunId gateOwner aliasState; do
  grep -Fq "$evidence" "$runner"
done
grep -Fq 'failure-status.json' "$runner"
grep -Fq 'failure-aliases.json' "$runner"
grep -Fq 'failure-offsets.json' "$runner"
grep -Fq 'failure-shadow.json' "$runner"
jq -e '.rebuild_reason == "KAFKA_OFFSET_GAP"' \
  scenarios/definitions/m5-kafka-gap-rebuild.json >/dev/null
grep -Fq 'start_rebuild "$run" "$reason"' "$runner"
grep -Fq 'curl -fsS -X POST http://127.0.0.1:8083/internal/rebuild/runs' "$runner"

grep -Fq 'CANAL_AUTO_RESET_LATEST_POS_MODE=true' "$reset"
grep -Fq 'CANAL_AUTO_RESET_LATEST_POS_MODE=false' "$reset"
grep -Fq '/home/admin/canal-data/products/meta.dat' "$reset"
grep -Fq 'SHOW BINARY LOGS' "$reset"
grep -Fq 'SHOW MASTER STATUS' "$reset"
grep -Fq 'reset-anchor' "$reset"
grep -Fq 'normal-sentinel' "$reset"
grep -Fq '/canal-recovery/complete' "$reset"
grep -Fq 'reset_anchor_offsets_json == reset_restart_offsets_before_json == normal_restart_offsets_after_json' "$reset"

if grep -Eq 'docker volume rm|down --volumes|rm[[:space:]]+-rf|rm[[:space:]].*meta[.]dat|rm[[:space:]].*canal-data' "$reset"; then
  echo 'unsafe Canal cursor/volume deletion found' >&2
  exit 1
fi
grep -Eq 'CANAL_AUTO_RESET_LATEST_POS_MODE:.*false' infra/compose.yaml
grep -Eq 'canal-data:/home/admin/canal-data' infra/compose.yaml

for heading in '## Preconditions' '## Build invariant' '## Cutover invariant' '## Atomic boundary' '## Guarantee boundary'; do
  grep -Fq "$heading" "$runbook"
done
grep -Eq '^rebuild:' Makefile
grep -Eq '^scenario-m5:' Makefile
grep -Eq '^verify-m5:' Makefile
grep -Fq 'make verify-m5' README.md

echo 'M5 rebuild completion assets contract passed'
