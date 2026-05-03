package com.interview.financialconsistency.serviceprototype.outbox;

import java.util.List;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class OutboxRepository {
    private final JdbcTemplate jdbcTemplate;

    public OutboxRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void insertPending(
            String messageId,
            String aggregateType,
            String aggregateId,
            String eventType,
            String payload) {
        jdbcTemplate.update(
                """
                insert into outbox_message (
                    message_id, aggregate_type, aggregate_id, event_type,
                    payload, status
                )
                values (?, ?, ?, ?, cast(? as json), 'PENDING')
                """,
                messageId,
                aggregateType,
                aggregateId,
                eventType,
                payload);
    }

    public int countByAggregate(String aggregateType, String aggregateId) {
        Integer count = jdbcTemplate.queryForObject(
                """
                select count(*)
                from outbox_message
                where aggregate_type = ?
                  and aggregate_id = ?
                """,
                Integer.class,
                aggregateType,
                aggregateId);
        return count == null ? 0 : count;
    }

    public int claimPublishable(int batchSize, String publisherId) {
        return jdbcTemplate.update(
                """
                update outbox_message
                set status = 'PUBLISHING',
                    locked_by = ?,
                    locked_at = current_timestamp(6),
                    attempt_count = attempt_count + 1,
                    last_error = null
                where status in ('PENDING', 'FAILED_RETRYABLE')
                order by created_at, message_id
                limit ?
                """,
                publisherId,
                batchSize);
    }

    public List<OutboxMessageRecord> findClaimedBy(String publisherId) {
        return jdbcTemplate.query(
                """
                select message_id, aggregate_type, aggregate_id, event_type, payload, status, attempt_count
                from outbox_message
                where status = 'PUBLISHING'
                  and locked_by = ?
                order by created_at, message_id
                """,
                (rs, rowNum) -> new OutboxMessageRecord(
                        rs.getString("message_id"),
                        rs.getString("aggregate_type"),
                        rs.getString("aggregate_id"),
                        rs.getString("event_type"),
                        rs.getString("payload"),
                        rs.getString("status"),
                        rs.getInt("attempt_count")),
                publisherId);
    }

    public void markPublished(String messageId) {
        int updated = jdbcTemplate.update(
                """
                update outbox_message
                set status = 'PUBLISHED',
                    published_at = current_timestamp(6),
                    locked_at = null,
                    locked_by = null,
                    last_error = null
                where message_id = ?
                """,
                messageId);
        if (updated != 1) {
            throw new IllegalStateException("Expected to mark one outbox message published but updated " + updated);
        }
    }

    public void markFailedRetryable(String messageId, String error) {
        int updated = jdbcTemplate.update(
                """
                update outbox_message
                set status = 'FAILED_RETRYABLE',
                    locked_at = null,
                    locked_by = null,
                    last_error = ?
                where message_id = ?
                """,
                error == null ? "" : error.substring(0, Math.min(error.length(), 1024)),
                messageId);
        if (updated != 1) {
            throw new IllegalStateException("Expected to mark one outbox message retryable but updated " + updated);
        }
    }
}
