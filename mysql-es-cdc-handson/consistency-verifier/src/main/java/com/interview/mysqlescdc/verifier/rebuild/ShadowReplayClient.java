package com.interview.mysqlescdc.verifier.rebuild;

import java.util.Map;
import java.util.UUID;

public interface ShadowReplayClient {
    ControlStatus start(UUID runId, String topic, String target, Map<Integer,Long> offsets);
    ControlStatus status(UUID runId);
    ControlStatus stop(UUID runId);
    ControlStatus pausePrimary();
    ControlStatus resumePrimary();
    record ControlStatus(UUID runId, String target, java.util.Set<Integer> assigned,
            Map<Integer,Long> nextOffsets, Boolean running, String state, String failureClass, Boolean paused) {}
}
