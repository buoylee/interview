package com.interview.financialconsistency.serviceprototype.outbox;

public record OutboxMessageRecord(
        String messageId,
        String aggregateType,
        String aggregateId,
        String eventType,
        String payload,
        String status,
        int attemptCount) {
}
