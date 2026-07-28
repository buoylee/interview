package com.interview.mysqlescdc.verifier.repair;

import java.util.UUID;

public record RepairReport(
        UUID runId,
        long sourceWatermarkStart,
        long sourceWatermarkEnd,
        int applied,
        int stale,
        int skipped,
        int failed,
        boolean sourceStable,
        boolean repaired) {}
