package com.interview.mysqlescdc.consumer.rebuild;

import java.util.Map;
import java.util.UUID;

public record ShadowReplayStatus(UUID runId, String target, java.util.Set<Integer> assigned,
        Map<Integer, Long> nextOffsets, boolean running, ShadowReplayState state, String failureClass) {}
