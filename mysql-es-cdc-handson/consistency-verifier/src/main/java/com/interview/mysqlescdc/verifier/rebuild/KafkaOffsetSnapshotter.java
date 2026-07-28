package com.interview.mysqlescdc.verifier.rebuild;
import java.util.Map;
import java.util.UUID;
import org.apache.kafka.common.TopicPartition;
public interface KafkaOffsetSnapshotter {
    Map<TopicPartition,Long> endOffsets(String topic);
    void assertRetained(String topic,Map<TopicPartition,Long> required);
    Map<TopicPartition,Long> captureAndPersist(UUID runId,String topic);
}
