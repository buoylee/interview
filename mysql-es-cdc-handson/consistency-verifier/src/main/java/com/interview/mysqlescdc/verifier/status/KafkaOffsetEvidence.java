package com.interview.mysqlescdc.verifier.status;

public record KafkaOffsetEvidence(
        String topic,
        int partition,
        Long committedOffset,
        long beginningOffset,
        long endOffset) {}
