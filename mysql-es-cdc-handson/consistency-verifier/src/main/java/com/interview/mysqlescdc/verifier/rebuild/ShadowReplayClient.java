package com.interview.mysqlescdc.verifier.rebuild;

import java.util.Map;
import java.util.UUID;

public interface ShadowReplayClient {
    ControlStatus start(UUID runId, String topic, String target, Map<Integer,Long> offsets);
    ControlStatus status();
    ControlStatus stop();
    ControlStatus pausePrimary();
    ControlStatus resumePrimary();
    record ControlStatus(String state, Map<Integer,Long> nextOffsets, String failureClass,
            Boolean running, Boolean paused) {}
}
