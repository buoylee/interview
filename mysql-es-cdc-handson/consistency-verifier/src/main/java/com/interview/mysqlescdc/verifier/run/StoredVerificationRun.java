package com.interview.mysqlescdc.verifier.run;

import java.util.UUID;

public record StoredVerificationRun(
        UUID runId,
        String target,
        VerificationRunStatus status,
        long sourceWatermarkStart,
        Long sourceWatermarkEnd,
        long differenceCount) {}
