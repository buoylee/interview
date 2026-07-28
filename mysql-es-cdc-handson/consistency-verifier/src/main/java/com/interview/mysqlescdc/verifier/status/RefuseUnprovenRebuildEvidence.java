package com.interview.mysqlescdc.verifier.status;

import java.util.UUID;

import org.springframework.stereotype.Component;

@Component
public final class RefuseUnprovenRebuildEvidence implements SuccessfulRebuildEvidence {
    @Override
    public boolean isSuccessfulRebuild(UUID rebuildRunId) {
        return false;
    }
}
