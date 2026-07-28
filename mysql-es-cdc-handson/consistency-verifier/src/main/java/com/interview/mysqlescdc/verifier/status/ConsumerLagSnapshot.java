package com.interview.mysqlescdc.verifier.status;

import java.util.List;

public record ConsumerLagSnapshot(
        long totalLag,
        boolean allPartitionsCommitted,
        List<PartitionLag> partitions) {

    public ConsumerLagSnapshot {
        if (totalLag < 0) throw new IllegalArgumentException("consumer lag cannot be negative");
        partitions = List.copyOf(partitions);
    }
}
