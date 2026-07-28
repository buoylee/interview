package com.interview.mysqlescdc.verifier.status;

import java.util.UUID;

public interface SuccessfulRebuildEvidence {
    boolean isSuccessfulRebuild(UUID rebuildRunId);
}
