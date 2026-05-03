package com.interview.financialconsistency.serviceprototype.consumer;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class ConsumerProcessedEventRepository {
    private final JdbcTemplate jdbcTemplate;

    public ConsumerProcessedEventRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public boolean insertProcessed(
            String eventId,
            String transferId,
            String topic,
            int partitionId,
            long offsetValue,
            String consumerGroup) {
        try {
            jdbcTemplate.update(
                    """
                    insert into consumer_processed_event (
                        event_id, transfer_id, topic, partition_id, offset_value,
                        consumer_group, status, processed_at
                    )
                    values (?, ?, ?, ?, ?, ?, 'PROCESSED', current_timestamp(6))
                    """,
                    eventId,
                    transferId,
                    topic,
                    partitionId,
                    offsetValue,
                    consumerGroup);
            return true;
        } catch (DuplicateKeyException ex) {
            if (countByEventId(consumerGroup, eventId) > 0) {
                return false;
            }
            throw new IllegalStateException(
                    "Kafka offset already recorded for a different event in consumer group " + consumerGroup
                            + ": topic=" + topic + ", partition=" + partitionId + ", offset=" + offsetValue,
                    ex);
        }
    }

    public int countByEventId(String consumerGroup, String eventId) {
        Integer count = jdbcTemplate.queryForObject(
                "select count(*) from consumer_processed_event where consumer_group = ? and event_id = ?",
                Integer.class,
                consumerGroup,
                eventId);
        return count == null ? 0 : count;
    }
}
