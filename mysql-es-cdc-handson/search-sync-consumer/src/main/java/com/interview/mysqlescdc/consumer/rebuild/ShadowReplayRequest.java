package com.interview.mysqlescdc.consumer.rebuild;

import java.util.Map;
import java.util.UUID;

public record ShadowReplayRequest(UUID runId, String topic, String target, Map<Integer, Long> offsets) {}
