package com.interview.mysqlescdc.verifier.status;

public enum PipelineStatus {
    REBUILDING,
    REBUILD_REQUIRED,
    DEGRADED,
    CATCHING_UP,
    HEALTHY
}
