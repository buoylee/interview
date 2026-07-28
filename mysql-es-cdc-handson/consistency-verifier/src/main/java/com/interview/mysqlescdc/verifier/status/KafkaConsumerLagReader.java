package com.interview.mysqlescdc.verifier.status;

import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.DisposableBean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public final class KafkaConsumerLagReader implements ConsumerLagReader, DisposableBean {
    private static final String LOG_GAP = "LOG_GAP";
    private final KafkaOffsets offsets;
    private final PipelineConditionStore conditions;
    private final String topic;
    private final String consumerGroup;

    @Autowired
    public KafkaConsumerLagReader(
            @Value("${verification.kafka-bootstrap-servers}") String bootstrapServers,
            @Value("${verification.topic}") String topic,
            @Value("${verification.consumer-group}") String consumerGroup,
            PipelineConditionStore conditions) {
        this(new AdminClientKafkaOffsets(bootstrapServers), conditions, topic, consumerGroup);
    }

    KafkaConsumerLagReader(
            KafkaOffsets offsets, PipelineConditionStore conditions,
            String topic, String consumerGroup) {
        this.offsets = offsets;
        this.conditions = conditions;
        this.topic = topic;
        this.consumerGroup = consumerGroup;
    }

    @Override
    public ConsumerLagSnapshot read() {
        List<PartitionLag> partitions = new ArrayList<>();
        long total = 0;
        List<KafkaOffsetEvidence> evidenceRows = offsets.read(topic, consumerGroup);
        List<KafkaOffsetEvidence> gaps = new ArrayList<>();
        boolean allCommitted = !evidenceRows.isEmpty();
        for (KafkaOffsetEvidence evidence : evidenceRows) {
            Long committed = evidence.committedOffset();
            boolean virginEmpty = committed == null
                    && evidence.beginningOffset() == 0 && evidence.endOffset() == 0;
            allCommitted &= committed != null || virginEmpty;
            long effectiveCommitted = committed == null
                    ? evidence.beginningOffset() : committed;
            long lag = Math.max(0, evidence.endOffset() - effectiveCommitted);
            boolean gap = committed != null && committed < evidence.beginningOffset();
            total = Math.addExact(total, lag);
            partitions.add(new PartitionLag(evidence.topic(), evidence.partition(), committed,
                    evidence.beginningOffset(), evidence.endOffset(), lag, gap));
            if (gap) gaps.add(evidence);
        }
        if (!gaps.isEmpty()) conditions.activate(LOG_GAP, boundedGaps(gaps));
        return new ConsumerLagSnapshot(total, allCommitted, partitions);
    }

    private String boundedGaps(List<KafkaOffsetEvidence> gaps) {
        StringBuilder value = new StringBuilder("{\"partitions\":[");
        boolean truncated = false;
        boolean first = true;
        for (KafkaOffsetEvidence evidence : gaps) {
            String item = (first ? "" : ",")
                    + "{\"topic\":\"" + evidence.topic() + "\",\"partition\":"
                    + evidence.partition() + ",\"committed\":" + evidence.committedOffset()
                    + ",\"beginning\":" + evidence.beginningOffset() + "}";
            if (value.length() + item.length() + 30 > 512) {
                truncated = true;
                break;
            }
            value.append(item);
            first = false;
        }
        value.append("],\"truncated\":").append(truncated).append('}');
        return value.toString();
    }

    @Override
    public void destroy() throws Exception {
        if (offsets instanceof AutoCloseable closeable) closeable.close();
    }
}
