package com.interview.mysqlescdc.verifier.rebuild;

import java.util.UUID;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import tools.jackson.databind.json.JsonMapper;

@Service
public class CanalRecoveryService {
    private final JdbcClient jdbc;
    private final RebuildRunStore runs;
    private final WriteGate gate;
    private final JsonMapper json = JsonMapper.builder().build();

    public CanalRecoveryService(JdbcClient jdbc, RebuildRunStore runs, WriteGate gate) {
        this.jdbc = jdbc; this.runs = runs; this.gate = gate;
    }

    @Transactional public RebuildStatus start(UUID runId) {
        gate.close(runId, "MySQL binlog-gap recovery");
        runs.transition(runId, "CANAL_RECOVERY_REQUIRED", "CANAL_RECOVERING");
        return runs.get(runId);
    }

    @Transactional public RebuildStatus complete(UUID runId, CanalRecoveryEvidence evidence) {
        evidence.validate();
        try {
            int inserted = jdbc.sql("""
                    INSERT INTO canal_position_recovery(
                      recovery_id,rebuild_run_id,status,cursor_path,cursor_backup_path,
                      old_cursor_sha256,old_journal_name,old_position,retained_binlog_files_json,
                      reset_lower_bound_journal,reset_lower_bound_file_index,reset_lower_bound_position,
                      reset_cursor_sha256,reset_journal_name,reset_file_index,reset_position,
                      reset_anchor_run_id,reset_anchor_offsets_json,reset_anchor_events_json,
                      reset_restart_offsets_before_json,normal_restart_cursor_sha256,
                      normal_restart_journal_name,normal_restart_file_index,normal_restart_position,
                      normal_restart_offsets_after_json,normal_sentinel_run_id,
                      normal_sentinel_offsets_json,normal_sentinel_events_json,finished_at)
                    VALUES(UUID_TO_BIN(:recovery),UUID_TO_BIN(:run),'COMPLETED',:cursor,:backup,
                      :oldHash,:oldJournal,:oldPosition,CAST(:manifest AS JSON),
                      :lowerJournal,:lowerIndex,:lowerPosition,:resetHash,:resetJournal,:resetIndex,:resetPosition,
                      UUID_TO_BIN(:anchorRun),CAST(:anchorOffsets AS JSON),CAST(:anchorEvents AS JSON),
                      CAST(:beforeOffsets AS JSON),:normalHash,:normalJournal,:normalIndex,:normalPosition,
                      CAST(:afterOffsets AS JSON),UUID_TO_BIN(:sentinelRun),CAST(:sentinelOffsets AS JSON),
                      CAST(:sentinelEvents AS JSON),CURRENT_TIMESTAMP(6))
                    """).param("recovery", evidence.recoveryId().toString()).param("run", runId.toString())
                    .param("cursor", evidence.cursorPath()).param("backup", evidence.cursorBackupPath())
                    .param("oldHash", evidence.oldCursorSha256()).param("oldJournal", evidence.oldJournalName()).param("oldPosition", evidence.oldPosition())
                    .param("manifest", json.writeValueAsString(evidence.retainedManifest()))
                    .param("lowerJournal", evidence.resetLowerBoundJournal()).param("lowerIndex", evidence.resetLowerBoundFileIndex()).param("lowerPosition", evidence.resetLowerBoundPosition())
                    .param("resetHash", evidence.resetCursorSha256()).param("resetJournal", evidence.resetJournalName()).param("resetIndex", evidence.resetFileIndex()).param("resetPosition", evidence.resetPosition())
                    .param("anchorRun", evidence.resetAnchorRunId().toString()).param("anchorOffsets", json.writeValueAsString(evidence.resetAnchorOffsets())).param("anchorEvents", json.writeValueAsString(evidence.resetAnchorEvents()))
                    .param("beforeOffsets", json.writeValueAsString(evidence.resetRestartOffsetsBefore()))
                    .param("normalHash", evidence.normalRestartCursorSha256()).param("normalJournal", evidence.normalRestartJournalName()).param("normalIndex", evidence.normalRestartFileIndex()).param("normalPosition", evidence.normalRestartPosition())
                    .param("afterOffsets", json.writeValueAsString(evidence.normalRestartOffsetsAfter())).param("sentinelRun", evidence.normalSentinelRunId().toString())
                    .param("sentinelOffsets", json.writeValueAsString(evidence.normalSentinelOffsets())).param("sentinelEvents", json.writeValueAsString(evidence.normalSentinelEvents())).update();
            if (inserted != 1) throw new IllegalStateException("Canal recovery evidence persistence lost");
        } catch (RuntimeException runtime) { throw runtime; }
        catch (Exception serialization) { throw new IllegalStateException("Canal evidence serialization failed", serialization); }
        jdbc.sql("UPDATE rebuild_run SET canal_recovery_id=UUID_TO_BIN(:recovery) WHERE run_id=UUID_TO_BIN(:run) AND status='CANAL_RECOVERING'")
                .param("recovery", evidence.recoveryId().toString()).param("run", runId.toString()).update();
        runs.transition(runId, "CANAL_RECOVERING", "CREATED");
        return runs.get(runId);
    }
}
