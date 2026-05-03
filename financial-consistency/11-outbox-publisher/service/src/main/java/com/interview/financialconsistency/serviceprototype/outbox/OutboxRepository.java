package com.interview.financialconsistency.serviceprototype.outbox;

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
}
