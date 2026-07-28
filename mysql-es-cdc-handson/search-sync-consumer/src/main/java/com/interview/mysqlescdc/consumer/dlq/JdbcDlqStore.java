package com.interview.mysqlescdc.consumer.dlq;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Timestamp;
import java.util.Optional;

import javax.sql.DataSource;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.support.TransactionTemplate;

@Repository
public class JdbcDlqStore implements DlqStore {
    private static final String INSERT = """
            INSERT INTO sync_dlq_record (
              event_id, topic_name, partition_no, offset_no, product_id,
              source_revision, payload, failure_class, last_error, status, attempts
            ) VALUES (
              :eventId, :topic, :partition, :offset, :productId,
              :revision, CAST(:payload AS JSON), :failureClass, :lastError, 'PENDING', 1
            )
            ON DUPLICATE KEY UPDATE
              attempts = attempts + 1,
              failure_class = VALUES(failure_class),
              last_error = VALUES(last_error),
              status = 'PENDING',
              resolved_at = NULL,
              updated_at = CURRENT_TIMESTAMP(6)
            """;
    private static final String SELECT_PENDING = """
            SELECT event_id, topic_name, partition_no, offset_no, product_id,
                   source_revision, payload, failure_class, last_error, status,
                   attempts, created_at, updated_at, resolved_at
            FROM sync_dlq_record
            WHERE event_id = :eventId AND status = 'PENDING'
            """;

    private final JdbcClient jdbc;
    private final TransactionTemplate transactions;

    public JdbcDlqStore(DataSource dataSource) {
        this.jdbc = JdbcClient.create(dataSource);
        this.transactions = new TransactionTemplate(new DataSourceTransactionManager(dataSource));
    }

    @Override
    public void publish(DlqRecord record) {
        validate(record);
        transactions.executeWithoutResult(ignored -> {
            boolean validJson = jdbc.sql("SELECT JSON_VALID(:payload)")
                    .param("payload", record.payload())
                    .query(Boolean.class)
                    .single();
            if (!validJson) {
                throw new IllegalArgumentException("valid product JSON payload required");
            }
            jdbc.sql(INSERT)
                    .param("eventId", record.eventId())
                    .param("topic", record.topic())
                    .param("partition", record.partition())
                    .param("offset", record.offset())
                    .param("productId", record.productId())
                    .param("revision", record.sourceRevision())
                    .param("payload", record.payload())
                    .param("failureClass", record.failureClass())
                    .param("lastError", record.lastError())
                    .update();
        });
    }

    @Override
    public Optional<DlqRecord> findPending(String eventId) {
        requireText(eventId, "eventId");
        return jdbc.sql(SELECT_PENDING)
                .param("eventId", eventId)
                .query(this::map)
                .optional();
    }

    @Override
    public void resolve(String eventId) {
        requireText(eventId, "eventId");
        transactions.executeWithoutResult(ignored -> jdbc.sql("""
                UPDATE sync_dlq_record
                SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP(6),
                    updated_at = CURRENT_TIMESTAMP(6)
                WHERE event_id = :eventId AND status = 'PENDING'
                """).param("eventId", eventId).update());
    }

    @Override
    public long unresolvedCount() {
        return jdbc.sql("SELECT COUNT(*) FROM sync_dlq_record WHERE status = 'PENDING'")
                .query(Long.class).single();
    }

    private void validate(DlqRecord record) {
        if (record == null) {
            throw new IllegalArgumentException("record required");
        }
        requireText(record.eventId(), "eventId");
        requireText(record.topic(), "topic");
        requireText(record.failureClass(), "failureClass");
        requireText(record.lastError(), "lastError");
        if (record.partition() < 0 || record.offset() < 0
                || record.productId() < 1 || record.sourceRevision() < 1) {
            throw new IllegalArgumentException("non-negative source coordinates and positive business IDs required");
        }
        String expected = record.topic() + ':' + record.partition() + ':'
                + record.offset() + ':' + record.productId();
        if (!expected.equals(record.eventId())) {
            throw new IllegalArgumentException("eventId does not agree with source identity");
        }
        requireText(record.payload(), "payload");
    }

    private DlqRecord map(ResultSet rs, int rowNumber) throws SQLException {
        return new DlqRecord(
                rs.getString("event_id"), rs.getString("topic_name"),
                rs.getInt("partition_no"), rs.getLong("offset_no"),
                rs.getLong("product_id"), rs.getLong("source_revision"),
                rs.getString("payload"), rs.getString("failure_class"),
                rs.getString("last_error"), DlqStatus.valueOf(rs.getString("status")),
                rs.getInt("attempts"), instant(rs, "created_at"),
                instant(rs, "updated_at"), instant(rs, "resolved_at"));
    }

    static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " required");
        }
    }

    static java.time.Instant instant(ResultSet rs, String column) throws SQLException {
        Timestamp value = rs.getTimestamp(column);
        return value == null ? null : value.toInstant();
    }
}
