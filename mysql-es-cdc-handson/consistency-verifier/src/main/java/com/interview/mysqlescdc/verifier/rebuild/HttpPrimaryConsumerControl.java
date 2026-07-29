package com.interview.mysqlescdc.verifier.rebuild;

import java.time.Duration;
import java.time.Instant;
import java.util.Map;
import java.util.Set;
import org.apache.kafka.clients.admin.Admin;
import org.apache.kafka.clients.admin.AdminClientConfig;
import org.apache.kafka.common.TopicPartition;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

@Component
public final class HttpPrimaryConsumerControl implements PrimaryConsumerControl, AutoCloseable {
    private final ShadowReplayClient client;
    private final Admin admin;
    private final String groupId;

    public HttpPrimaryConsumerControl(ShadowReplayClient client,
            @Value("${verification.kafka-bootstrap-servers:localhost:29092}") String bootstrap,
            @Value("${verification.consumer-group:product-search-sync-v1}") String groupId) {
        this.client = client;
        this.admin = Admin.create(Map.of(AdminClientConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrap));
        this.groupId = groupId;
    }

    @Override
    public void awaitCommitted(String topic, Map<Integer, Long> required, Duration timeout) {
        requireExact(required);
        Instant deadline = Instant.now().plus(timeout);
        while (Instant.now().isBefore(deadline)) {
            try {
                var offsets = admin.listConsumerGroupOffsets(groupId).partitionsToOffsetAndMetadata().get();
                boolean settled = required.entrySet().stream().allMatch(entry -> {
                    var actual = offsets.get(new TopicPartition(topic, entry.getKey()));
                    return actual != null && actual.offset() >= entry.getValue();
                });
                if (settled) return;
                Thread.sleep(100);
            } catch (InterruptedException interrupted) {
                Thread.currentThread().interrupt();
                throw new IllegalStateException("primary offset wait interrupted", interrupted);
            } catch (Exception failure) {
                throw new IllegalStateException("cannot read primary committed offsets", failure);
            }
        }
        throw new IllegalStateException("primary committed offset timeout");
    }

    @Override public void pauseAndConfirm() {
        var status = client.pausePrimary();
        if (!Boolean.TRUE.equals(status.paused())) throw new IllegalStateException("primary pause not confirmed");
    }

    @Override public void resumeAndConfirm() {
        var status = client.resumePrimary();
        if (Boolean.TRUE.equals(status.paused())) throw new IllegalStateException("primary resume not confirmed");
    }

    private static void requireExact(Map<Integer, Long> offsets) {
        if (!offsets.keySet().equals(Set.of(0, 1, 2)) || offsets.values().stream().anyMatch(v -> v == null || v < 0)) {
            throw new IllegalArgumentException("exact partition offsets required");
        }
    }

    @Override public void close() { admin.close(Duration.ofSeconds(5)); }
}
