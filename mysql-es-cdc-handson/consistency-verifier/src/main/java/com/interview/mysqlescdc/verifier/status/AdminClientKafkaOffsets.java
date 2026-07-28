package com.interview.mysqlescdc.verifier.status;

import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.apache.kafka.clients.admin.Admin;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.clients.admin.ListOffsetsResult.ListOffsetsResultInfo;
import org.apache.kafka.clients.admin.OffsetSpec;
import org.apache.kafka.clients.admin.TopicDescription;
import org.apache.kafka.clients.consumer.OffsetAndMetadata;
import org.apache.kafka.common.TopicPartition;

final class AdminClientKafkaOffsets implements KafkaOffsets, AutoCloseable {
    private static final Duration CLOSE_TIMEOUT = Duration.ofSeconds(5);
    private final Admin admin;

    AdminClientKafkaOffsets(String bootstrapServers) {
        admin = Admin.create(Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers));
    }

    @Override
    public List<KafkaOffsetEvidence> read(String topic, String consumerGroup) {
        try {
            TopicDescription description = admin.describeTopics(List.of(topic))
                    .allTopicNames().get().get(topic);
            List<TopicPartition> partitions = description.partitions().stream()
                    .map(info -> new TopicPartition(topic, info.partition())).toList();
            Map<TopicPartition, OffsetAndMetadata> committed = admin
                    .listConsumerGroupOffsets(consumerGroup).partitionsToOffsetAndMetadata().get();
            Map<TopicPartition, OffsetSpec> earliestRequest = new HashMap<>();
            Map<TopicPartition, OffsetSpec> latestRequest = new HashMap<>();
            for (TopicPartition partition : partitions) {
                earliestRequest.put(partition, OffsetSpec.earliest());
                latestRequest.put(partition, OffsetSpec.latest());
            }
            Map<TopicPartition, ListOffsetsResultInfo> beginnings =
                    admin.listOffsets(earliestRequest).all().get();
            Map<TopicPartition, ListOffsetsResultInfo> ends =
                    admin.listOffsets(latestRequest).all().get();
            List<KafkaOffsetEvidence> evidence = new ArrayList<>(partitions.size());
            for (TopicPartition partition : partitions) {
                OffsetAndMetadata position = committed.get(partition);
                evidence.add(new KafkaOffsetEvidence(topic, partition.partition(),
                        position == null ? null : position.offset(),
                        beginnings.get(partition).offset(), ends.get(partition).offset()));
            }
            return evidence;
        } catch (Exception exception) {
            if (exception instanceof InterruptedException) Thread.currentThread().interrupt();
            throw new IllegalStateException("cannot read Kafka consumer offsets", exception);
        }
    }

    @Override
    public void close() {
        admin.close(CLOSE_TIMEOUT);
    }
}
