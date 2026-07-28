package com.interview.mysqlescdc.verifier.status;

import java.time.Instant;
import java.util.Set;
import java.util.UUID;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

public record PipelineSignals(
        Set<String> activeConditions,
        long unresolvedDlq,
        UUID latestRunId,
        VerificationRunStatus latestRunStatus,
        long latestDifferenceCount,
        Instant latestRunFinishedAt,
        VerificationRunStatus latestConclusiveStatus,
        long latestConclusiveDifferenceCount,
        Instant latestConclusiveFinishedAt,
        ConsumerLagSnapshot lag,
        Instant evaluatedAt) {

    public PipelineSignals {
        activeConditions = Set.copyOf(activeConditions);
        if (unresolvedDlq < 0 || latestDifferenceCount < 0
                || latestConclusiveDifferenceCount < 0) {
            throw new IllegalArgumentException("persisted counts cannot be negative");
        }
    }
}
