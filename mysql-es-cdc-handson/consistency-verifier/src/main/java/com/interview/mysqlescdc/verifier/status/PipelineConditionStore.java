package com.interview.mysqlescdc.verifier.status;

import java.time.Instant;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

public interface PipelineConditionStore {
    Set<String> activeConditions();

    void activate(String condition, String boundedDetailsJson);

    boolean clearLogGap(UUID rebuildRunId);

    long unresolvedDlqCount();

    Optional<LatestVerification> latestVerification();

    Optional<LatestVerification> latestConclusiveVerification();

    Optional<LatestVerification> latestSuccessfulPass();

    record LatestVerification(
            UUID runId,
            VerificationRunStatus status,
            long differenceCount,
            Instant finishedAt) {}
}
