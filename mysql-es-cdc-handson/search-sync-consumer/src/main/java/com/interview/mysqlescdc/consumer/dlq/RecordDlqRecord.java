package com.interview.mysqlescdc.consumer.dlq;

import java.time.Instant;

public record RecordDlqRecord(
        String recordId,
        String topic,
        int partition,
        long offset,
        String rawKey,
        String rawPayload,
        String failureClass,
        String lastError,
        DlqStatus status,
        int attempts,
        Instant createdAt,
        Instant updatedAt,
        Instant resolvedAt) {

    public RecordDlqRecord(
            String recordId,
            String topic,
            int partition,
            long offset,
            String rawKey,
            String rawPayload,
            String failureClass,
            String lastError) {
        this(recordId, topic, partition, offset, rawKey, rawPayload, failureClass,
                lastError, DlqStatus.PENDING, 1, null, null, null);
    }
}
