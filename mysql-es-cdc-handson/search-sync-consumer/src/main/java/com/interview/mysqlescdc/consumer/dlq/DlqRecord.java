package com.interview.mysqlescdc.consumer.dlq;

import java.time.Instant;

public record DlqRecord(
        String eventId,
        String topic,
        int partition,
        long offset,
        long productId,
        long sourceRevision,
        String payload,
        String failureClass,
        String lastError,
        DlqStatus status,
        int attempts,
        Instant createdAt,
        Instant updatedAt,
        Instant resolvedAt) {

    public DlqRecord(
            String eventId,
            String topic,
            int partition,
            long offset,
            long productId,
            long sourceRevision,
            String payload,
            String failureClass,
            String lastError) {
        this(eventId, topic, partition, offset, productId, sourceRevision, payload,
                failureClass, lastError, DlqStatus.PENDING, 1, null, null, null);
    }
}
