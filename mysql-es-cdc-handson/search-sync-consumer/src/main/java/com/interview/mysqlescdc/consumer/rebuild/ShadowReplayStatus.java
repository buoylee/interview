package com.interview.mysqlescdc.consumer.rebuild;

import java.util.Map;
import java.util.UUID;

public record ShadowReplayStatus(UUID runId, ShadowReplayState state, Map<Integer, Long> nextOffsets,
        String failureClass) {}
