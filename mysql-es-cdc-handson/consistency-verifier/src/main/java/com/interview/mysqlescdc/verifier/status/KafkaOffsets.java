package com.interview.mysqlescdc.verifier.status;

import java.util.List;

interface KafkaOffsets {
    List<KafkaOffsetEvidence> read(String topic, String consumerGroup);
}
