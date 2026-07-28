package com.interview.mysqlescdc.consumer.dlq;

import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.time.Instant;

import org.junit.jupiter.api.Test;

class DlqRecordTest {
    private static final Instant CREATED = Instant.parse("2026-07-22T01:00:00Z");
    private static final Instant UPDATED = Instant.parse("2026-07-22T01:01:00Z");

    @Test
    void canonical_product_record_rejects_invalid_lifecycle_and_publish_state() {
        assertInvalid(null, 1, CREATED, UPDATED, null);
        assertInvalid(DlqStatus.PENDING, 0, CREATED, UPDATED, null);
        assertInvalid(DlqStatus.PENDING, 1, CREATED, UPDATED, UPDATED);
        assertInvalid(DlqStatus.RESOLVED, 1, CREATED, UPDATED, null);
        assertInvalid(DlqStatus.RESOLVED, 1, CREATED, UPDATED, CREATED.minusSeconds(1));
        assertInvalid(DlqStatus.PENDING, 1, null, UPDATED, null);
        assertInvalid(DlqStatus.PENDING, 1, UPDATED, CREATED, null);
    }

    @Test
    void publish_rejects_a_persisted_or_forged_product_record() throws Exception {
        JdbcDlqStore store = new JdbcDlqStore(new org.springframework.jdbc.datasource.SimpleDriverDataSource(
                new com.mysql.cj.jdbc.Driver(), "jdbc:mysql://127.0.0.1:1/nope", "x", "x"));
        DlqRecord persisted = valid(DlqStatus.PENDING, 1, CREATED, UPDATED, null);
        assertThatThrownBy(() -> store.publish(persisted))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("publish command");
    }

    private static void assertInvalid(
            DlqStatus status, int attempts, Instant created, Instant updated, Instant resolved) {
        assertThatThrownBy(() -> valid(status, attempts, created, updated, resolved))
                .isInstanceOf(IllegalArgumentException.class);
    }

    private static DlqRecord valid(
            DlqStatus status, int attempts, Instant created, Instant updated, Instant resolved) {
        return new DlqRecord("products.revision:1:42:92101", "products.revision", 1, 42,
                92101, 7, "{\"product_id\":92101,\"source_revision\":7}",
                "failure", "error", status, attempts, created, updated, resolved);
    }
}
