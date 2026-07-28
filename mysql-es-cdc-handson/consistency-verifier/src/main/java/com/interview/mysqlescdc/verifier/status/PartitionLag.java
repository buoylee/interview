package com.interview.mysqlescdc.verifier.status;

public record PartitionLag(
        String topic,
        int partition,
        Long committedOffset,
        long beginningOffset,
        long endOffset,
        long lag,
        boolean retentionGap) {}
