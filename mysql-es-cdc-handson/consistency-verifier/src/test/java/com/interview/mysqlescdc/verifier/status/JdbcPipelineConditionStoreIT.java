package com.interview.mysqlescdc.verifier.status;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.UUID;

import javax.sql.DataSource;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

class JdbcPipelineConditionStoreIT {
    private static final String MYSQL = "jdbc:mysql://localhost:3308/product_catalog"
            + "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC";
    private static final UUID RUN = UUID.fromString("00000000-0000-0000-0000-000000000505");
    private JdbcClient fixture;
    private MutableRebuildEvidence rebuildEvidence;
    private JdbcPipelineConditionStore store;

    @BeforeEach
    void setUp() {
        fixture = JdbcClient.create(dataSource("root", "rootpass"));
        cleanup();
        rebuildEvidence = new MutableRebuildEvidence();
        store = new JdbcPipelineConditionStore(
                JdbcClient.create(dataSource("verifier", "verifierpass")), rebuildEvidence);
    }

    @AfterEach
    void tearDown() {
        if (fixture != null) cleanup();
    }

    @Test
    void persists_idempotent_gap_counts_both_dlqs_and_refuses_unproven_clearance() {
        store.activate("LOG_GAP", "{\"partition\":1}");
        store.activate("LOG_GAP", "{\"partition\":1}");
        long unresolvedBeforeFixtures = store.unresolvedDlqCount();
        insertDlqFixtures();

        assertThat(store.activeConditions()).contains("LOG_GAP");
        assertThat(fixture.sql("""
                SELECT COUNT(*) FROM pipeline_condition WHERE condition_key = 'LOG_GAP'
                """).query(Long.class).single()).isOne();
        assertThat(store.unresolvedDlqCount()).isEqualTo(unresolvedBeforeFixtures + 2);
        assertThat(store.clearLogGap(RUN)).isFalse();
        assertThat(store.activeConditions()).contains("LOG_GAP");

        rebuildEvidence.successful = true;
        assertThat(store.clearLogGap(RUN)).isTrue();
        assertThat(store.activeConditions()).doesNotContain("LOG_GAP");
    }

    @Test
    void reads_latest_persisted_verification_evidence() {
        fixture.sql("""
                INSERT INTO verification_run(
                  run_id, target_name, status, source_watermark_start, source_watermark_end,
                  difference_count, started_at, finished_at)
                VALUES (UUID_TO_BIN(:runId), 'task5_status_it', 'PASS', 9, 9, 0,
                        '2030-01-01 00:00:00.000000', '2030-01-01 00:00:01.000000')
                """).param("runId", RUN.toString()).update();

        var latest = store.latestVerification().orElseThrow();

        assertThat(latest.runId()).isEqualTo(RUN);
        assertThat(latest.status()).isEqualTo(VerificationRunStatus.PASS);
        assertThat(latest.differenceCount()).isZero();
        assertThat(store.latestConclusiveVerification().orElseThrow()).isEqualTo(latest);
    }

    private void insertDlqFixtures() {
        fixture.sql("""
                INSERT INTO sync_dlq_record(
                  event_id, topic_name, partition_no, offset_no, product_id, source_revision,
                  payload, failure_class, last_error, status, attempts)
                VALUES ('task5:7:500:505', 'task5', 7, 500, 505, 1,
                        JSON_OBJECT(), 'Task5', 'fixture', 'PENDING', 1)
                """).update();
        fixture.sql("""
                INSERT INTO sync_record_dlq(
                  record_id, topic_name, partition_no, offset_no, raw_payload,
                  failure_class, last_error, status, attempts)
                VALUES ('task5:7:501', 'task5', 7, 501, '{}',
                        'Task5', 'fixture', 'PENDING', 1)
                """).update();
    }

    private void cleanup() {
        fixture.sql("DELETE FROM sync_dlq_record WHERE topic_name = 'task5'").update();
        fixture.sql("DELETE FROM sync_record_dlq WHERE topic_name = 'task5'").update();
        fixture.sql("DELETE FROM verification_run WHERE run_id = UUID_TO_BIN(:runId)")
                .param("runId", RUN.toString()).update();
        fixture.sql("DELETE FROM pipeline_condition WHERE condition_key = 'LOG_GAP'").update();
    }

    private DataSource dataSource(String user, String password) {
        return new DriverManagerDataSource(MYSQL, user, password);
    }

    private static final class MutableRebuildEvidence implements SuccessfulRebuildEvidence {
        private boolean successful;

        @Override
        public boolean isSuccessfulRebuild(UUID rebuildRunId) {
            return successful && RUN.equals(rebuildRunId);
        }
    }
}
