package com.interview.mysqlescdc.verifier.status;

import java.sql.Timestamp;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Repository;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

@Repository
public class JdbcPipelineConditionStore implements PipelineConditionStore {
    private final JdbcClient jdbc;
    private final SuccessfulRebuildEvidence rebuildEvidence;

    public JdbcPipelineConditionStore(
            JdbcClient jdbc, SuccessfulRebuildEvidence rebuildEvidence) {
        this.jdbc = jdbc;
        this.rebuildEvidence = rebuildEvidence;
    }

    @Override
    public Set<String> activeConditions() {
        return Set.copyOf(jdbc.sql("""
                SELECT condition_key FROM pipeline_condition
                WHERE active = TRUE ORDER BY condition_key
                """).query(String.class).list());
    }

    @Override
    public void activate(String condition, String boundedDetailsJson) {
        requireCondition(condition);
        if (boundedDetailsJson == null || boundedDetailsJson.length() > 512) {
            throw new IllegalArgumentException("condition details must be bounded JSON");
        }
        jdbc.sql("""
                INSERT INTO pipeline_condition(
                  condition_key, active, details_json, observed_at, cleared_at)
                VALUES (:key, TRUE, CAST(:details AS JSON), CURRENT_TIMESTAMP(6), NULL)
                ON DUPLICATE KEY UPDATE active = TRUE, details_json = VALUES(details_json),
                  observed_at = VALUES(observed_at), cleared_at = NULL
                """).param("key", condition).param("details", boundedDetailsJson).update();
    }

    @Override
    public boolean clearLogGap(UUID rebuildRunId) {
        if (rebuildRunId == null || !rebuildEvidence.isSuccessfulRebuild(rebuildRunId)) {
            return false;
        }
        jdbc.sql("""
                UPDATE pipeline_condition
                SET active = FALSE, cleared_at = CURRENT_TIMESTAMP(6)
                WHERE condition_key = 'LOG_GAP' AND active = TRUE
                """).update();
        return true;
    }

    @Override
    public long unresolvedDlqCount() {
        return jdbc.sql("""
                SELECT
                  (SELECT COUNT(*) FROM sync_dlq_record WHERE status = 'pending') +
                  (SELECT COUNT(*) FROM sync_record_dlq WHERE status = 'pending')
                """).query(Long.class).single();
    }

    @Override
    public Optional<LatestVerification> latestVerification() {
        return latest("""
                SELECT BIN_TO_UUID(run_id) AS run_id, status, difference_count, finished_at
                FROM verification_run
                ORDER BY started_at DESC, run_id DESC LIMIT 1
                """);
    }

    @Override
    public Optional<LatestVerification> latestConclusiveVerification() {
        return latest("""
                SELECT BIN_TO_UUID(run_id) AS run_id, status, difference_count, finished_at
                FROM verification_run
                WHERE status IN ('PASS', 'DIFF', 'REPAIRED')
                ORDER BY finished_at DESC, run_id DESC LIMIT 1
                """);
    }

    private Optional<LatestVerification> latest(String query) {
        return jdbc.sql(query).query((rs, row) -> {
                    Timestamp finished = rs.getTimestamp("finished_at");
                    return new LatestVerification(UUID.fromString(rs.getString("run_id")),
                            VerificationRunStatus.valueOf(rs.getString("status")),
                            rs.getLong("difference_count"),
                            finished == null ? null : finished.toInstant());
                }).optional();
    }

    private void requireCondition(String condition) {
        if (!Set.of("LOG_GAP", "REBUILD_REQUIRED", "REBUILD_IN_PROGRESS").contains(condition)) {
            throw new IllegalArgumentException("unsupported pipeline condition");
        }
    }
}
