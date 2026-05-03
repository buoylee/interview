package com.interview.financialconsistency.serviceprototype.kafka;

public record TransferEventEnvelope(
        String messageId,
        String aggregateType,
        String aggregateId,
        String eventType,
        String payload) {
}
