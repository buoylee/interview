package com.interview.mysqlescdc.verifier.rebuild;

import java.nio.ByteBuffer;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import java.util.UUID;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import tools.jackson.databind.json.JsonMapper;

@Component
public final class RecoveryBarrierObserver {
    private final String bootstrap;
    private final JsonMapper json = JsonMapper.builder().build();

    public RecoveryBarrierObserver(@Value("${lab.kafka-bootstrap-servers:localhost:29092}") String bootstrap) {
        this.bootstrap = bootstrap;
    }

    public RecoveryBarrierObservation observe(String topic, String kind, Barrier barrier,
            Map<Integer, Long> preOffsets, Duration timeout) {
        List<TopicPartition> assigned = List.of(new TopicPartition(topic, 0),
                new TopicPartition(topic, 1), new TopicPartition(topic, 2));
        if (!preOffsets.keySet().equals(Set.of(0, 1, 2))) {
            throw new IllegalArgumentException("exact caller pre-vector required");
        }
        Map<Integer, Long> offsets = new HashMap<>();
        List<CanalRecoveryEvidence.Sentinel> events = new ArrayList<>();
        try (var consumer = new KafkaConsumer<String, String>(properties())) {
            consumer.assign(assigned);
            assigned.forEach(tp -> consumer.seek(tp, preOffsets.get(tp.partition())));
            Instant deadline = Instant.now().plus(timeout);
            Instant duplicateDeadline = null;
            while (Instant.now().isBefore(deadline)) {
                for (var record : consumer.poll(Duration.ofMillis(200))) {
                    var root = json.readTree(record.value());
                    if (!"cdc_barrier".equals(root.path("table").asText())) continue;
                    for (var row : root.path("data")) {
                        UUID runId = decode(row.path("run_id").asText());
                        if (!barrier.runId().equals(runId)) continue;
                        String token = row.path("partition_token").asText();
                        int partition = record.partition();
                        long expected = preOffsets.get(partition);
                        if (record.key() != null || !token.equals(Integer.toString(partition))
                                || Math.floorMod(token.hashCode(), 3) != partition
                                || record.offset() != expected || offsets.containsKey(partition)) {
                            throw new IllegalStateException("recovery barrier routing/offset/duplicate mismatch");
                        }
                        long next = record.offset() + 1;
                        UUID eventId = UUID.nameUUIDFromBytes((record.topic() + ":" + partition + ":"
                                + record.offset() + ":" + record.value()).getBytes(StandardCharsets.UTF_8));
                        offsets.put(partition, next);
                        events.add(new CanalRecoveryEvidence.Sentinel(eventId, runId, partition, next));
                    }
                }
                if (offsets.size() == 3 && duplicateDeadline == null) {
                    duplicateDeadline = Instant.now().plusMillis(500);
                }
                if (duplicateDeadline != null && Instant.now().isAfter(duplicateDeadline)) break;
            }
        } catch (RuntimeException failure) { throw failure; }
        catch (Exception failure) { throw new IllegalStateException("raw recovery barrier observation failed", failure); }
        if (offsets.size() != 3) throw new IllegalStateException("raw recovery barrier observation timeout");
        events.sort(java.util.Comparator.comparingInt(CanalRecoveryEvidence.Sentinel::partition));
        return new RecoveryBarrierObservation(kind, barrier.runId(), Map.copyOf(preOffsets),
                Map.copyOf(offsets), List.copyOf(events));
    }

    private Properties properties() {
        Properties p = new Properties();
        p.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrap);
        p.put(ConsumerConfig.GROUP_ID_CONFIG, "canal-recovery-observer-" + UUID.randomUUID());
        p.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
        p.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "none");
        p.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
        p.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        p.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        return p;
    }

    private static UUID decode(String value) {
        byte[] bytes = value.getBytes(StandardCharsets.ISO_8859_1);
        if (bytes.length != 16) throw new IllegalStateException("barrier run identity mismatch");
        ByteBuffer buffer = ByteBuffer.wrap(bytes);
        return new UUID(buffer.getLong(), buffer.getLong());
    }
}
