package com.interview.mysqlescdc.verifier.diff;

import java.util.EnumMap;
import java.util.Map;
import java.util.Objects;
import java.util.UUID;

public record ConsistencyReport(
        UUID runId,
        long sourceWatermarkStart,
        long sourceWatermarkEnd,
        long expectedCount,
        long actualCount,
        long differenceCount,
        Map<DifferenceType, Long> counts,
        boolean conclusive) {

    public ConsistencyReport {
        Objects.requireNonNull(runId, "runId");
        counts = Map.copyOf(new EnumMap<>(counts));
        if (expectedCount < 0 || actualCount < 0 || differenceCount < 0) {
            throw new IllegalArgumentException("counts must be non-negative");
        }
    }
}
