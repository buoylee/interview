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
              attempts = IF(
                source_revision = VALUES(source_revision)
                  AND JSON_CONTAINS(payload, VALUES(payload))
                  AND JSON_CONTAINS(VALUES(payload), payload),
                attempts + 1, attempts),
              failure_class = IF(
                source_revision = VALUES(source_revision)
                  AND JSON_CONTAINS(payload, VALUES(payload))
                  AND JSON_CONTAINS(VALUES(payload), payload),
                VALUES(failure_class), failure_class),
              last_error = IF(
                source_revision = VALUES(source_revision)
                  AND JSON_CONTAINS(payload, VALUES(payload))
                  AND JSON_CONTAINS(VALUES(payload), payload),
                VALUES(last_error), last_error),
              status = IF(
                source_revision = VALUES(source_revision)
                  AND JSON_CONTAINS(payload, VALUES(payload))
                  AND JSON_CONTAINS(VALUES(payload), payload),
                'PENDING', status),
              resolved_at = IF(
                source_revision = VALUES(source_revision)
                  AND JSON_CONTAINS(payload, VALUES(payload))
                  AND JSON_CONTAINS(VALUES(payload), payload),
                NULL, resolved_at),
              updated_at = IF(
                source_revision = VALUES(source_revision)
                  AND JSON_CONTAINS(payload, VALUES(payload))
                  AND JSON_CONTAINS(VALUES(payload), payload),
                CURRENT_TIMESTAMP(6), updated_at)
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
            boolean validContract = jdbc.sql("""
                    SELECT COALESCE(
                      JSON_TYPE(CAST(:payload AS JSON)) = 'OBJECT'
                      AND JSON_LENGTH(CAST(:payload AS JSON)) > 0
                      AND JSON_TYPE(JSON_EXTRACT(CAST(:payload AS JSON), '$.product_id')) = 'INTEGER'
                      AND JSON_TYPE(JSON_EXTRACT(CAST(:payload AS JSON), '$.source_revision')) = 'INTEGER'
                      AND CAST(JSON_UNQUOTE(JSON_EXTRACT(
                            CAST(:payload AS JSON), '$.product_id')) AS UNSIGNED) = :productId
                      AND CAST(JSON_UNQUOTE(JSON_EXTRACT(
                            CAST(:payload AS JSON), '$.source_revision')) AS UNSIGNED) = :revision,
                      FALSE)
                    """).param("payload", record.payload())
                    .param("productId", record.productId())
                    .param("revision", record.sourceRevision())
                    .query(Boolean.class).single();
            if (!validContract) {
                throw new IllegalArgumentException(
                        "product JSON object must contain matching integer product_id and source_revision");
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
            boolean compatible = jdbc.sql("""
                    SELECT source_revision = :revision
                      AND JSON_CONTAINS(payload, CAST(:payload AS JSON))
                      AND JSON_CONTAINS(CAST(:payload AS JSON), payload)
                    FROM sync_dlq_record
                    WHERE event_id = :eventId
                    """).param("revision", record.sourceRevision())
                    .param("payload", record.payload())
                    .param("eventId", record.eventId())
                    .query(Boolean.class).single();
            if (!compatible) {
                throw new IllegalStateException(
                        "immutable product DLQ evidence conflicts with existing eventId");
            }
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
        if (!record.isNewPending()) {
            throw new IllegalArgumentException("new-pending publish command required");
        }
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
