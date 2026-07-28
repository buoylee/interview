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

    public DlqRecord {
        requireText(eventId, "eventId");
        requireText(topic, "topic");
        requireText(payload, "payload");
        requireText(failureClass, "failureClass");
        requireText(lastError, "lastError");
        if (partition < 0 || offset < 0 || productId < 1 || sourceRevision < 1) {
            throw new IllegalArgumentException("non-negative source coordinates and positive business IDs required");
        }
        String expected = topic + ':' + partition + ':' + offset + ':' + productId;
        if (!expected.equals(eventId)) {
            throw new IllegalArgumentException("eventId does not agree with source identity");
        }
        validateLifecycle(status, attempts, createdAt, updatedAt, resolvedAt);
    }

    public static DlqRecord newPending(
            String eventId,
            String topic,
            int partition,
            long offset,
            long productId,
            long sourceRevision,
            String payload,
            String failureClass,
            String lastError) {
        return new DlqRecord(eventId, topic, partition, offset, productId, sourceRevision, payload,
                failureClass, lastError, DlqStatus.PENDING, 1, null, null, null);
    }

    public boolean isNewPending() {
        return status == DlqStatus.PENDING && attempts == 1
                && createdAt == null && updatedAt == null && resolvedAt == null;
    }

    private static void validateLifecycle(
            DlqStatus status, int attempts, Instant createdAt, Instant updatedAt, Instant resolvedAt) {
        if (status == null || attempts < 1) {
            throw new IllegalArgumentException("status and positive attempts required");
        }
        boolean command = createdAt == null && updatedAt == null;
        if (command) {
            if (status != DlqStatus.PENDING || attempts != 1 || resolvedAt != null) {
                throw new IllegalArgumentException("invalid new-pending lifecycle");
            }
            return;
        }
        if (createdAt == null || updatedAt == null || updatedAt.isBefore(createdAt)) {
            throw new IllegalArgumentException("valid persisted timestamps required");
        }
        if (status == DlqStatus.PENDING && resolvedAt != null) {
            throw new IllegalArgumentException("pending record cannot be resolved");
        }
        if (status == DlqStatus.RESOLVED
                && (resolvedAt == null || resolvedAt.isBefore(createdAt) || resolvedAt.isAfter(updatedAt))) {
            throw new IllegalArgumentException("resolved record requires an ordered resolvedAt");
        }
    }

    private static void requireText(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " required");
        }
    }
}
