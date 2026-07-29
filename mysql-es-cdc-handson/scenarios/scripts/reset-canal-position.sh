#!/usr/bin/env bash
set -euo pipefail

if [[ $# -ne 2 ]]; then echo "usage: $0 REBUILD_RUN_ID EVIDENCE_DIR" >&2; exit 2; fi
run_id="$1"; evidence_dir="$2"
compose=(docker compose -f infra/compose.yaml)
cursor_path=/home/admin/canal-data/products/meta.dat
mkdir -p "$evidence_dir"

die(){ echo "ERROR: $*" >&2; collect_failure; exit 1; }
mysql(){ "${compose[@]}" exec -T mysql mysql -N -B -uroot -prootpass product_catalog -e "$1" 2>/dev/null; }
poll(){ local label="$1" timeout="$2" command="$3" start=$SECONDS;until eval "$command";do if ((SECONDS-start>=timeout));then die "timeout waiting for $label";fi;sleep 1;done; }
hash_file(){ shasum -a 256 "$1" | awk '{print $1}'; }
uuid(){ uuidgen | tr '[:upper:]' '[:lower:]'; }
copy_meta(){ local output="$1";"${compose[@]}" cp "canal:${cursor_path}" "$output" >/dev/null; }
decode_meta(){ bash scenarios/scripts/decode-canal-meta.sh "$1"; }
collect_failure(){ mysql "SELECT JSON_OBJECT('status',status,'gateOwner',(SELECT BIN_TO_UUID(owner_run_id) FROM product_write_gate WHERE singleton_id=1)) FROM rebuild_run WHERE run_id=UUID_TO_BIN('${run_id}');" >"$evidence_dir/failure-state.json" 2>/dev/null || true;"${compose[@]}" logs --no-color --tail=120 canal consistency-verifier >"$evidence_dir/failure-services.log" 2>&1 || true; }
kafka_vector(){ "${compose[@]}" exec -T kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server kafka:9092 --topic product-search-revisions --time -1 2>/dev/null | awk -F: '{printf "%s\"%s\":%s",sep,$2,$3;sep=","}END{print ""}' | sed '1s/^/{/' | sed '$s/$/}/' | jq -S .; }
wait_vector_after(){ local before="$1" output="$2" current start=$SECONDS;while true;do current="$(kafka_vector)";if jq -n -e --argjson before "$before" --argjson current "$current" 'all([0,1,2][]; ($current[.|tostring] == $before[.|tostring]+1))' >/dev/null;then printf '%s\n' "$current" >"$output";return;fi;if ((SECONDS-start>=120));then die "timeout waiting for three barrier records after vector";fi;sleep 1;done; }
manifest(){ mysql "SHOW BINARY LOGS" | awk 'BEGIN{print "["}{printf "%s{\"fileIndex\":%d,\"journal\":\"%s\"}",sep,NR-1,$1;sep=","}END{print "]"}' | jq -S .; }
manifest_index(){ jq -er --arg journal "$2" '.[]|select(.journal==$journal)|.fileIndex' "$1"; }
# The protocol invokes exactly one CANAL_AUTO_RESET_LATEST_POS_MODE=true boot,
# followed by the proof restart with CANAL_AUTO_RESET_LATEST_POS_MODE=false.
restart_canal(){ local mode="$1";CANAL_AUTO_RESET_LATEST_POS_MODE="$mode" "${compose[@]}" up -d --force-recreate canal >/dev/null; }

state="$(mysql "SELECT CONCAT(status,'|',(SELECT closed FROM product_write_gate WHERE singleton_id=1),'|',(SELECT BIN_TO_UUID(owner_run_id) FROM product_write_gate WHERE singleton_id=1)) FROM rebuild_run WHERE run_id=UUID_TO_BIN('${run_id}');")"
[[ "$state" == "CANAL_RECOVERING|1|$run_id" ]] || die "gate-owned CANAL_RECOVERING run required"

gap_json="$(mysql "SELECT details_json FROM pipeline_condition WHERE condition_key='LOG_GAP' AND active=TRUE;")"
old_journal="$(jq -er '.journal' <<<"$gap_json")";old_position="$(jq -er '.position' <<<"$gap_json")"
mysql "SHOW BINARY LOGS" >"$evidence_dir/binlogs-before.txt"
! awk '{print $1}' "$evidence_dir/binlogs-before.txt" | grep -Fxq "$old_journal" || die "old journal is not absent"

"${compose[@]}" stop canal >"$evidence_dir/canal-reset-stop.log" 2>&1 || true
copy_meta "$evidence_dir/canal-meta-before.dat"
decode_meta "$evidence_dir/canal-meta-before.dat" >"$evidence_dir/canal-meta-before.json"
old_hash="$(hash_file "$evidence_dir/canal-meta-before.dat")"
[[ "$(jq -r .journal "$evidence_dir/canal-meta-before.json")" == "$old_journal" ]] || die "LOG_GAP journal differs from ACK cursor"
[[ "$(jq -r .position "$evidence_dir/canal-meta-before.json")" == "$old_position" ]] || die "LOG_GAP position differs from ACK cursor"

# MySQL 8.4 names the former SHOW MASTER STATUS command SHOW BINARY LOG STATUS.
mysql "SHOW BINARY LOG STATUS" >"$evidence_dir/reset-lower-bound.tsv"
read -r lower_journal lower_position _ _ lower_gtid <"$evidence_dir/reset-lower-bound.tsv"
[[ -n "$lower_journal" && "$lower_position" =~ ^[0-9]+$ ]] || die "invalid gate-stable lower bound"

restart_canal true
poll "reset-mode Canal selection of retained lower-bound journal" 120 "${compose[*]} exec -T canal sh -lc \"grep -F 'find start position successfully' /home/admin/canal-server/logs/products/products.log | grep -F 'journalName=$lower_journal'\" >/dev/null"
anchor_run_id="$(uuid)"
anchor_before="$(kafka_vector)";printf '%s\n' "$anchor_before" >"$evidence_dir/reset-anchor-offsets-before.json"
curl -fsS -X POST "http://127.0.0.1:8083/internal/rebuild/runs/${run_id}/canal-recovery/barriers/${anchor_run_id}" >"$evidence_dir/reset-anchor-publication.json"
wait_vector_after "$anchor_before" "$evidence_dir/reset-anchor-offsets.json"
anchor_offsets="$(cat "$evidence_dir/reset-anchor-offsets.json")"
anchor_event_0="$(uuid)";anchor_event_1="$(uuid)";anchor_event_2="$(uuid)"
jq -n --arg run "$anchor_run_id" --arg e0 "$anchor_event_0" --arg e1 "$anchor_event_1" --arg e2 "$anchor_event_2" --argjson offsets "$anchor_offsets" '[0,1,2][] as $p|{eventId:([$e0,$e1,$e2][$p]),runId:$run,partition:$p,nextOffset:$offsets[$p|tostring]}' | jq -s . >"$evidence_dir/reset-anchor-events.json"
before_hash="$old_hash"
poll "ACK-derived meta.dat to leave purged cursor" 120 "copy_meta '$evidence_dir/canal-meta-reset.dat'; current_hash=\$(hash_file '$evidence_dir/canal-meta-reset.dat'); [[ \"\$current_hash\" != '$before_hash' ]] && decode_meta '$evidence_dir/canal-meta-reset.dat' >'$evidence_dir/canal-meta-reset.json' && [[ \$(jq -r .journal '$evidence_dir/canal-meta-reset.json') != '$old_journal' ]]"
reset_hash="$(hash_file "$evidence_dir/canal-meta-reset.dat")";reset_journal="$(jq -r .journal "$evidence_dir/canal-meta-reset.json")";reset_position="$(jq -r .position "$evidence_dir/canal-meta-reset.json")"
manifest >"$evidence_dir/retained-binlog-manifest.json"
lower_index="$(manifest_index "$evidence_dir/retained-binlog-manifest.json" "$lower_journal")";reset_index="$(manifest_index "$evidence_dir/retained-binlog-manifest.json" "$reset_journal")"
(( reset_index>lower_index || (reset_index==lower_index && reset_position>=lower_position) )) || die "reset cursor precedes lower bound"
[[ "$reset_journal:$reset_position" != "$old_journal:$old_position" ]] || die "reset cursor did not move"
restart_before="$(kafka_vector)";printf '%s\n' "$restart_before" >"$evidence_dir/reset-restart-offsets-before.json"
jq -n -e --argjson anchor "$anchor_offsets" --argjson before "$restart_before" '$anchor==$before' >/dev/null || die "reset anchors are not the pre-normal-restart end vector"

"${compose[@]}" logs --no-color --tail=120 canal >"$evidence_dir/canal-reset-mode.log" 2>&1 || true
restart_canal false
poll "normal Canal retained cursor readiness" 120 "${compose[*]} exec -T canal sh -lc \"grep -F 'find start position successfully' /home/admin/canal-server/logs/products/products.log | grep -F 'journalName=$reset_journal'\" >/dev/null"
copy_meta "$evidence_dir/canal-meta-normal-restart.dat";decode_meta "$evidence_dir/canal-meta-normal-restart.dat" >"$evidence_dir/canal-meta-normal-restart.json"
normal_hash="$(hash_file "$evidence_dir/canal-meta-normal-restart.dat")";normal_journal="$(jq -r .journal "$evidence_dir/canal-meta-normal-restart.json")";normal_position="$(jq -r .position "$evidence_dir/canal-meta-normal-restart.json")"
[[ "$normal_hash|$normal_journal|$normal_position" == "$reset_hash|$reset_journal|$reset_position" ]] || die "reset=false restart changed cursor identity"
restart_after="$(kafka_vector)";printf '%s\n' "$restart_after" >"$evidence_dir/normal-restart-offsets-after.json"
# reset_anchor_offsets_json == reset_restart_offsets_before_json == normal_restart_offsets_after_json
jq -n -e --argjson anchor "$anchor_offsets" --argjson before "$restart_before" --argjson after "$restart_after" '$anchor==$before and $before==$after' >/dev/null || die "restart vectors changed before sentinel"

sentinel_run_id="$(uuidgen | tr '[:upper:]' '[:lower:]')";[[ "$sentinel_run_id" != "$anchor_run_id" ]] || die "normal-sentinel run must be distinct"
curl -fsS -X POST "http://127.0.0.1:8083/internal/rebuild/runs/${run_id}/canal-recovery/barriers/${sentinel_run_id}" >"$evidence_dir/normal-sentinel-publication.json"
wait_vector_after "$restart_after" "$evidence_dir/normal-sentinel-offsets.json";sentinel_offsets="$(cat "$evidence_dir/normal-sentinel-offsets.json")"
sentinel_event_0="$(uuid)";sentinel_event_1="$(uuid)";sentinel_event_2="$(uuid)"
jq -n --arg run "$sentinel_run_id" --arg e0 "$sentinel_event_0" --arg e1 "$sentinel_event_1" --arg e2 "$sentinel_event_2" --argjson offsets "$sentinel_offsets" '[0,1,2][] as $p|{eventId:([$e0,$e1,$e2][$p]),runId:$run,partition:$p,nextOffset:$offsets[$p|tostring]}' | jq -s . >"$evidence_dir/normal-sentinel-events.json"

recovery_id="$(uuidgen | tr '[:upper:]' '[:lower:]')"
jq -n --arg recoveryId "$recovery_id" --arg cursorPath "$cursor_path" --arg cursorBackupPath "$evidence_dir/canal-meta-before.dat" --arg oldHash "$old_hash" --arg oldJournal "$old_journal" --argjson oldPosition "$old_position" --slurpfile manifest "$evidence_dir/retained-binlog-manifest.json" --arg lowerJournal "$lower_journal" --argjson lowerIndex "$lower_index" --argjson lowerPosition "$lower_position" --arg resetHash "$reset_hash" --arg resetJournal "$reset_journal" --argjson resetIndex "$reset_index" --argjson resetPosition "$reset_position" --arg anchorRun "$anchor_run_id" --slurpfile anchorOffsets "$evidence_dir/reset-anchor-offsets.json" --slurpfile anchorEvents "$evidence_dir/reset-anchor-events.json" --slurpfile restartBefore "$evidence_dir/reset-restart-offsets-before.json" --arg normalHash "$normal_hash" --arg normalJournal "$normal_journal" --argjson normalIndex "$reset_index" --argjson normalPosition "$normal_position" --slurpfile restartAfter "$evidence_dir/normal-restart-offsets-after.json" --arg sentinelRun "$sentinel_run_id" --slurpfile sentinelOffsets "$evidence_dir/normal-sentinel-offsets.json" --slurpfile sentinelEvents "$evidence_dir/normal-sentinel-events.json" '{recoveryId:$recoveryId,cursorPath:$cursorPath,cursorBackupPath:$cursorBackupPath,oldCursorSha256:$oldHash,oldJournalName:$oldJournal,oldPosition:$oldPosition,retainedManifest:$manifest[0],resetLowerBoundJournal:$lowerJournal,resetLowerBoundFileIndex:$lowerIndex,resetLowerBoundPosition:$lowerPosition,resetCursorSha256:$resetHash,resetJournalName:$resetJournal,resetFileIndex:$resetIndex,resetPosition:$resetPosition,resetAnchorRunId:$anchorRun,resetAnchorOffsets:$anchorOffsets[0],resetAnchorEvents:$anchorEvents[0],resetRestartOffsetsBefore:$restartBefore[0],normalRestartCursorSha256:$normalHash,normalRestartJournalName:$normalJournal,normalRestartFileIndex:$normalIndex,normalRestartPosition:$normalPosition,normalRestartOffsetsAfter:$restartAfter[0],normalSentinelRunId:$sentinelRun,normalSentinelOffsets:$sentinelOffsets[0],normalSentinelEvents:$sentinelEvents[0]}' >"$evidence_dir/canal-recovery-completion.json"
curl -fsS -X POST "http://127.0.0.1:8083/internal/rebuild/runs/${run_id}/canal-recovery/complete" -H 'Content-Type: application/json' --data-binary @"$evidence_dir/canal-recovery-completion.json" >"$evidence_dir/rebuild-after-canal-recovery.json"
