#!/usr/bin/env bash
set -euo pipefail

reset=scenarios/scripts/reset-canal-position.sh
runner=scenarios/scripts/run-m5-rebuild.sh
fresh=scenarios/scripts/run-m5-formal-final.sh

! grep -Eq 'anchor_event_[012]|sentinel_event_[012]|randomUUID|uuid.*event' "$reset"
grep -Fq 'RESET_ANCHOR' "$reset"
grep -Fq 'NORMAL_SENTINEL' "$reset"
grep -Fq 'reset-anchor-meta-before-publication' "$reset"
grep -Fq 'LAB_SNAPSHOT_PAGE_DELAY_MS' infra/compose.yaml
grep -Fq 'scan_page_size": 200' scenarios/definitions/m5-concurrent-rebuild.json
grep -Fq 'source_count' "$runner"
grep -Eq 'DEGRADED|REBUILD_REQUIRED' "$runner"
grep -Fq 'caller recovery events differ from durable raw observation' consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/CanalRecoveryService.java
grep -Fq 'record.offset() != expected' consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/RecoveryBarrierObserver.java
grep -Fq 'action.put("version_type","external")' consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/SnapshotGenerationWriter.java
! grep -Fq 'version_type","external_gte' consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/rebuild/SnapshotGenerationWriter.java
grep -Fq 'products_write' "$runner"
grep -Fq 'make reset' "$fresh"
grep -Fq 'formal-final-1' "$fresh"
grep -Fq 'formal-final-2' "$fresh"
grep -Eq '^formal-final-m5:' Makefile
test "$(grep -c '^## M5：可验证的全量重建$' README.md)" -eq 1

echo 'M5 review fixes contract passed'
