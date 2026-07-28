package com.interview.mysqlescdc.consumer.dlq;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;

import org.junit.jupiter.api.Test;

class RecordDlqRecordTest {
    private static final Instant CREATED = Instant.parse("2026-07-22T01:00:00Z");
    private static final Instant UPDATED = Instant.parse("2026-07-22T01:01:00Z");

    @Test
    void canonical_raw_record_rejects_invalid_lifecycle() {
        assertInvalid(null, 1, CREATED, UPDATED, null);
        assertInvalid(DlqStatus.PENDING, -1, CREATED, UPDATED, null);
        assertInvalid(DlqStatus.PENDING, 1, CREATED, UPDATED, UPDATED);
        assertInvalid(DlqStatus.RESOLVED, 1, CREATED, UPDATED, null);
        assertInvalid(DlqStatus.RESOLVED, 1, CREATED, UPDATED, CREATED.minusSeconds(1));
        assertInvalid(DlqStatus.PENDING, 1, null, UPDATED, null);
        assertInvalid(DlqStatus.PENDING, 1, UPDATED, CREATED, null);
    }

    @Test
    void publish_rejects_a_persisted_raw_record_before_database_access() throws Exception {
        JdbcRecordDlqStore store = new JdbcRecordDlqStore(
                new org.springframework.jdbc.datasource.SimpleDriverDataSource(
                        new com.mysql.cj.jdbc.Driver(), "jdbc:mysql://127.0.0.1:1/nope", "x", "x"));
        RecordDlqRecord persisted = valid(DlqStatus.PENDING, 1, CREATED, UPDATED, null);
        assertThatThrownBy(() -> store.publish(persisted))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("publish command");
    }

    private static void assertInvalid(
            DlqStatus status, int attempts, Instant created, Instant updated, Instant resolved) {
        assertThatThrownBy(() -> valid(status, attempts, created, updated, resolved))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private static RecordDlqRecord valid(
            DlqStatus status, int attempts, Instant created, Instant updated, Instant resolved) {
        return new RecordDlqRecord("products.revision:7:94201", "products.revision", 7,
                94201, null, "raw", "failure", "error", status, attempts,
                created, updated, resolved);
    }
}
