package com.interview.mysqlescdc.verifier.run;

import java.util.Map;
import java.util.UUID;

import com.interview.mysqlescdc.verifier.diff.DifferenceType;

public record VerificationRunReport(
        UUID runId,
        String target,
        VerificationRunStatus status,
        long sourceWatermarkStart,
        Long sourceWatermarkEnd,
        long expectedCount,
        long actualCount,
        long differenceCount,
        Map<DifferenceType, Long> counts,
        String failureClass,
        String failureMessage) {

    public VerificationRunReport {
        counts = Map.copyOf(counts);
    }
}
