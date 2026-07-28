package com.interview.mysqlescdc.consumer.rebuild;

public interface ShadowReplayService {
    ShadowReplayStatus start(ShadowReplayRequest request);
    ShadowReplayStatus status(java.util.UUID runId);
    ShadowReplayStatus stop(java.util.UUID runId);
}
