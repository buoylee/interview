#!/usr/bin/env bash
set -euo pipefail

compose=infra/compose.yaml
reset=scenarios/scripts/reset-canal-position.sh
test -f "$reset"
grep -Eq 'CANAL_AUTO_RESET_LATEST_POS_MODE:.*false' "$compose"
grep -Eq 'canal-data:/home/admin/canal-data' "$compose"
grep -Fq 'cursor_path=/home/admin/canal-data/products/meta.dat' "$reset"
grep -Fq 'CANAL_RECOVERING|1|' "$reset"
grep -Fq 'SHOW BINARY LOGS' "$reset"
grep -Fq 'SHOW MASTER STATUS' "$reset"
grep -Fq 'CANAL_AUTO_RESET_LATEST_POS_MODE="$mode"' "$reset"
[[ "$(grep -c 'restart_canal true' "$reset")" == 1 ]]
grep -Fq 'restart_canal false' "$reset"
grep -Fq 'reset cursor precedes lower bound' "$reset"
grep -Fq 'reset=false restart changed cursor identity' "$reset"
grep -Fq 'normal-sentinel run must be distinct' "$reset"
grep -Fq 'reset_anchor_offsets_json == reset_restart_offsets_before_json == normal_restart_offsets_after_json' "$reset"
for field in oldCursorSha256 oldJournalName oldPosition retainedManifest resetLowerBoundJournal resetLowerBoundFileIndex resetLowerBoundPosition resetCursorSha256 resetJournalName resetFileIndex resetPosition resetAnchorRunId resetAnchorOffsets resetAnchorEvents resetRestartOffsetsBefore normalRestartCursorSha256 normalRestartJournalName normalRestartFileIndex normalRestartPosition normalRestartOffsetsAfter normalSentinelRunId normalSentinelOffsets normalSentinelEvents; do
  grep -Fq "$field" "$reset"
done
if grep -Eq 'docker volume rm|down --volumes|rm[[:space:]]+-rf|rm[[:space:]].*meta[.]dat|rm[[:space:]].*canal-data' "$reset"; then
  echo 'Canal recovery must preserve meta.dat and canal-data volume' >&2;exit 1
fi
bash -n "$reset"
echo 'Canal position recovery contract passed'
