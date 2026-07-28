package com.interview.mysqlescdc.consumer.dlq;

import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Optional;

import javax.sql.DataSource;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DataSourceTransactionManager;
import org.springframework.stereotype.Repository;
import org.springframework.transaction.support.TransactionTemplate;

@Repository
public class JdbcRecordDlqStore implements RecordDlqStore {
    private static final String INSERT = """
            INSERT INTO sync_record_dlq (
              record_id, topic_name, partition_no, offset_no, raw_key, raw_payload,
              failure_class, last_error, status, attempts
            ) VALUES (
              :recordId, :topic, :partition, :offset, :rawKey, :rawPayload,
              :failureClass, :lastError, 'PENDING', 1
            )
            ON DUPLICATE KEY UPDATE
              attempts = attempts + 1,
              failure_class = VALUES(failure_class),
              last_error = VALUES(last_error),
              status = 'PENDING',
              resolved_at = NULL,
              updated_at = CURRENT_TIMESTAMP(6)
            """;
    private final JdbcClient jdbc;
    private final TransactionTemplate transactions;

    public JdbcRecordDlqStore(DataSource dataSource) {
        this.jdbc = JdbcClient.create(dataSource);
        this.transactions = new TransactionTemplate(new DataSourceTransactionManager(dataSource));
    }

    @Override
    public void publish(RecordDlqRecord record) {
        validate(record);
        transactions.executeWithoutResult(ignored -> jdbc.sql(INSERT)
                .param("recordId", record.recordId())
                .param("topic", record.topic())
                .param("partition", record.partition())
                .param("offset", record.offset())
                .param("rawKey", record.rawKey())
                .param("rawPayload", record.rawPayload())
                .param("failureClass", record.failureClass())
                .param("lastError", record.lastError())
                .update());
    }

    @Override
    public Optional<RecordDlqRecord> findPending(String recordId) {
        JdbcDlqStore.requireText(recordId, "recordId");
        return jdbc.sql("""
                SELECT record_id, topic_name, partition_no, offset_no, raw_key,
                       raw_payload, failure_class, last_error, status, attempts,
                       created_at, updated_at, resolved_at
                FROM sync_record_dlq
                WHERE record_id = :recordId AND status = 'PENDING'
                """).param("recordId", recordId).query(this::map).optional();
    }

    @Override
    public void resolve(String recordId) {
        JdbcDlqStore.requireText(recordId, "recordId");
        transactions.executeWithoutResult(ignored -> jdbc.sql("""
                UPDATE sync_record_dlq
                SET status = 'RESOLVED', resolved_at = CURRENT_TIMESTAMP(6),
                    updated_at = CURRENT_TIMESTAMP(6)
                WHERE record_id = :recordId AND status = 'PENDING'
                """).param("recordId", recordId).update());
    }

    @Override
    public long unresolvedCount() {
        return jdbc.sql("SELECT COUNT(*) FROM sync_record_dlq WHERE status = 'PENDING'")
                .query(Long.class).single();
    }

    private static void validate(RecordDlqRecord record) {
        if (record == null) {
            throw new IllegalArgumentException("record required");
        }
        JdbcDlqStore.requireText(record.recordId(), "recordId");
        JdbcDlqStore.requireText(record.topic(), "topic");
        if (record.rawPayload() == null) {
            throw new IllegalArgumentException("rawPayload required");
        }
        JdbcDlqStore.requireText(record.failureClass(), "failureClass");
        JdbcDlqStore.requireText(record.lastError(), "lastError");
        if (record.partition() < 0 || record.offset() < 0) {
            throw new IllegalArgumentException("non-negative source coordinates required");
        }
        String expected = record.topic() + ':' + record.partition() + ':' + record.offset();
        if (!expected.equals(record.recordId())) {
            throw new IllegalArgumentException("recordId does not agree with source identity");
        }
    }

    private RecordDlqRecord map(ResultSet rs, int rowNumber) throws SQLException {
        return new RecordDlqRecord(
                rs.getString("record_id"), rs.getString("topic_name"),
                rs.getInt("partition_no"), rs.getLong("offset_no"),
                rs.getString("raw_key"), rs.getString("raw_payload"),
                rs.getString("failure_class"), rs.getString("last_error"),
                DlqStatus.valueOf(rs.getString("status")), rs.getInt("attempts"),
                JdbcDlqStore.instant(rs, "created_at"),
                JdbcDlqStore.instant(rs, "updated_at"),
                JdbcDlqStore.instant(rs, "resolved_at"));
    }
}
