package com.interview.mysqlescdc.consumer.rebuild;

public interface ShadowReplayService {
    ShadowReplayStatus start(ShadowReplayRequest request);
    ShadowReplayStatus status();
    ShadowReplayStatus stop();
}
