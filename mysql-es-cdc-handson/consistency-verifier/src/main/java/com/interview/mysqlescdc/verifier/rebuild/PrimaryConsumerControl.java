package com.interview.mysqlescdc.verifier.rebuild;

import java.time.Duration;
import java.util.Map;

public interface PrimaryConsumerControl {
    void awaitCommitted(String topic, Map<Integer, Long> requiredNextOffsets, Duration timeout);
    void pauseAndConfirm();
    void resumeAndConfirm();
}
