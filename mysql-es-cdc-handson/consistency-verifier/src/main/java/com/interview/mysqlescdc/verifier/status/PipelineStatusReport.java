package com.interview.mysqlescdc.verifier.status;

import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

public record PipelineStatusReport(
        PipelineStatus state,
        long kafkaLag,
        boolean allPartitionsCommitted,
        List<PartitionLag> partitions,
        long unresolvedDlq,
        UUID latestRunId,
        VerificationRunStatus latestRunStatus,
        long latestDifferenceCount,
        Instant latestRunFinishedAt,
        Instant latestSuccessfulPassFinishedAt,
        Set<String> activeConditions,
        Instant evaluatedAt) {}
