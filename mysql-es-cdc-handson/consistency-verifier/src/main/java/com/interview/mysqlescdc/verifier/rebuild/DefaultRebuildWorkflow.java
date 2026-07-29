package com.interview.mysqlescdc.verifier.rebuild;

import com.interview.mysqlescdc.verifier.run.VerificationRequest;
import com.interview.mysqlescdc.verifier.run.VerificationRunReport;
import com.interview.mysqlescdc.verifier.run.VerificationRunService;
import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;
import com.interview.mysqlescdc.verifier.status.PipelineConditionStore;
import java.time.Duration;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import org.apache.kafka.common.TopicPartition;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Component;

@Component
public final class DefaultRebuildWorkflow implements RebuildCoordinator.Workflow {
    private static final Duration SETTLE_TIMEOUT = Duration.ofSeconds(60);
    private final JdbcClient jdbc;
    private final KafkaOffsetSnapshotter offsets;
    private final GenerationManager generations;
    private final ConsistentSourceScanner scanner;
    private final SnapshotGenerationWriter writer;
    private final ShadowReplayClient shadow;
    private final WriteGate gate;
    private final BarrierPublisher barriers;
    private final BarrierObserver observer;
    private final PrimaryConsumerControl primary;
    private final VerificationRunService verifier;
    private final PipelineConditionStore conditions;
    private SourceSnapshotCursor snapshot;
    private Barrier barrier;
    private Map<TopicPartition, Long> preBarrier;

    public DefaultRebuildWorkflow(JdbcClient jdbc, KafkaOffsetSnapshotter offsets,
            GenerationManager generations, ConsistentSourceScanner scanner,
            SnapshotGenerationWriter writer, ShadowReplayClient shadow, WriteGate gate,
            BarrierPublisher barriers, BarrierObserver observer, PrimaryConsumerControl primary,
            VerificationRunService verifier, PipelineConditionStore conditions) {
        this.jdbc = jdbc;
        this.offsets = offsets;
        this.generations = generations;
        this.scanner = scanner;
        this.writer = writer;
        this.shadow = shadow;
        this.gate = gate;
        this.barriers = barriers;
        this.observer = observer;
        this.primary = primary;
        this.verifier = verifier;
        this.conditions = conditions;
    }

    @Override public void captureStart(UUID runId) {
        RebuildRequestData run = run(runId);
        offsets.captureAndPersist(runId, run.topic());
    }

    @Override public void createGeneration(UUID runId) { generations.create(runId); }
    @Override public void openSnapshot(UUID runId) { snapshot = scanner.open(); }

    @Override public void startShadow(UUID runId) {
        RebuildRequestData run = run(runId);
        var status = shadow.start(runId, run.topic(), run.generation(), integerOffsets(load(runId, "START")));
        requireShadowHealthy(status, runId, run.generation());
    }

    @Override public void scanSnapshot(UUID runId) {
        if (snapshot == null) throw new IllegalStateException("source snapshot not open");
        RebuildRequestData run = run(runId);
        writer.write(runId, run.generation(), snapshot, run.pageSize());
        snapshot = null;
    }

    @Override public void closeSnapshot(UUID runId) {
        if (snapshot != null) { snapshot.close(); snapshot = null; }
    }

    @Override public void assertRetained(UUID runId) {
        RebuildRequestData run = run(runId);
        offsets.assertRetained(run.topic(), load(runId, "START"));
    }

    @Override public void closeGate(UUID runId) { gate.close(runId, "verified rebuild cutover"); }

    @Override public void publishBarrier(UUID runId) {
        RebuildRequestData run = run(runId);
        preBarrier = offsets.endOffsets(run.topic());
        barrier = barriers.publish(runId, 3);
    }

    @Override public void observeBarrier(UUID runId) {
        RebuildRequestData run = run(runId);
        if (barrier == null || preBarrier == null) throw new IllegalStateException("barrier publication evidence absent");
        Map<TopicPartition, Long> observed = observer.awaitAll(run.topic(), barrier, preBarrier, SETTLE_TIMEOUT);
        persist(runId, "BARRIER", observed);
    }

    @Override public void awaitPrimary(UUID runId) {
        RebuildRequestData run = run(runId);
        primary.awaitCommitted(run.topic(), integerOffsets(load(runId, "BARRIER")), SETTLE_TIMEOUT);
    }

    @Override public void awaitShadow(UUID runId) {
        RebuildRequestData run = run(runId);
        Map<Integer, Long> required = integerOffsets(load(runId, "BARRIER"));
        long deadline = System.nanoTime() + SETTLE_TIMEOUT.toNanos();
        while (System.nanoTime() < deadline) {
            var status = shadow.status(runId);
            requireShadowHealthy(status, runId, run.generation());
            if (required.entrySet().stream().allMatch(e -> status.nextOffsets().getOrDefault(e.getKey(), -1L) >= e.getValue())) {
                persist(runId, "SHADOW", topicOffsets(run.topic(), status.nextOffsets()));
                offsets.assertRetained(run.topic(), load(runId, "START"));
                return;
            }
            sleep();
        }
        throw new IllegalStateException("shadow durable offset timeout");
    }

    @Override public void pausePrimary(UUID runId) { primary.pauseAndConfirm(); }

    @Override public void verifyPhysical(UUID runId) {
        RebuildRequestData run = run(runId);
        writer.refresh(run.generation());
        VerificationRunReport report = verifier.run(new VerificationRequest(run.generation(), run.pageSize()));
        int changed = jdbc.sql("""
                UPDATE rebuild_run SET verification_run_id=UUID_TO_BIN(:verification),
                  source_watermark=:watermark
                WHERE run_id=UUID_TO_BIN(:run) AND status IN ('VERIFYING','CUTOVER_COMMITTED')
                """).param("verification", report.runId().toString())
                .param("watermark", report.sourceWatermarkStart())
                .param("run", runId.toString()).update();
        if (changed != 1) throw new IllegalStateException("verification evidence persistence lost");
    }

    @Override public void requireEligible(UUID runId) {
        RebuildRequestData run = run(runId);
        Eligibility row = jdbc.sql("""
                SELECT v.status, v.difference_count differenceCount,
                  (v.source_watermark_start=v.source_watermark_end) stable,
                  g.closed gateClosed, BIN_TO_UUID(g.owner_run_id) gateOwner
                FROM rebuild_run r JOIN verification_run v ON v.run_id=r.verification_run_id
                JOIN product_write_gate g ON g.singleton_id=1
                WHERE r.run_id=UUID_TO_BIN(:run)
                """).param("run", runId.toString()).query(Eligibility.class).single();
        var shadowStatus = shadow.status(runId);
        requireShadowHealthy(shadowStatus, runId, run.generation());
        if (!VerificationRunStatus.PASS.name().equals(row.status()) || row.differenceCount() != 0
                || !row.stable() || conditions.unresolvedDlqCount() != 0 || !row.gateClosed()
                || !runId.toString().equals(row.gateOwner())
                || !shadowStatus.nextOffsets().equals(integerOffsets(load(runId, "SHADOW")))
                || aliasTopology(runId) != RebuildCoordinator.AliasTopology.OLD) {
            throw new IllegalStateException("rebuild cutover eligibility absent or stale");
        }
    }

    @Override public void cutover(UUID runId) {
        RebuildRequestData run = run(runId);
        generations.atomicCutover(new IndexGeneration(runId, run.generation(), java.time.Instant.EPOCH));
    }

    @Override public void stopShadow(UUID runId) { shadow.stop(runId); }
    @Override public void resumePrimary(UUID runId) { primary.resumeAndConfirm(); }
    @Override public void clearLogGap(UUID runId) {
        if (!conditions.clearLogGap(runId)) {
            throw new IllegalStateException("successful rebuild condition clear refused");
        }
    }
    @Override public void openGate(UUID runId) { gate.open(runId); }

    @Override public RebuildCoordinator.AliasTopology aliasTopology(UUID runId) {
        if (!(generations instanceof RestGenerationManager rest)) return RebuildCoordinator.AliasTopology.CONTRADICTORY;
        RebuildRequestData run = run(runId);
        return rest.topology(new IndexGeneration(runId, run.generation(), java.time.Instant.EPOCH));
    }

    @Override public void activateRebuildRequired(UUID runId) {
        conditions.activate("REBUILD_REQUIRED", "{\"rebuildRunId\":\"" + runId + "\"}");
    }

    private RebuildRequestData run(UUID runId) {
        return jdbc.sql("SELECT generation_name generation,topic_name topic,page_size pageSize FROM rebuild_run WHERE run_id=UUID_TO_BIN(:run)")
                .param("run", runId.toString()).query(RebuildRequestData.class).single();
    }

    private Map<TopicPartition, Long> load(UUID runId, String phase) {
        RebuildRequestData run = run(runId);
        Map<TopicPartition, Long> result = new LinkedHashMap<>();
        jdbc.sql("SELECT partition_id,next_offset FROM rebuild_partition_offset WHERE run_id=UUID_TO_BIN(:run) AND phase=:phase AND topic_name=:topic")
                .param("run", runId.toString()).param("phase", phase).param("topic", run.topic())
                .query((rs, n) -> Map.entry(new TopicPartition(run.topic(), rs.getInt(1)), rs.getLong(2)))
                .list().forEach(e -> result.put(e.getKey(), e.getValue()));
        if (!result.keySet().equals(Set.of(new TopicPartition(run.topic(), 0), new TopicPartition(run.topic(), 1), new TopicPartition(run.topic(), 2)))) {
            throw new IllegalStateException("exact persisted offset vector absent");
        }
        return Map.copyOf(result);
    }

    private void persist(UUID runId, String phase, Map<TopicPartition, Long> values) {
        values.forEach((partition, value) -> {
            jdbc.sql("""
                    INSERT IGNORE INTO rebuild_partition_offset(run_id,phase,topic_name,partition_id,next_offset)
                    VALUES(UUID_TO_BIN(:run),:phase,:topic,:partition,:offset)
                    """).param("run", runId.toString()).param("phase", phase).param("topic", partition.topic())
                    .param("partition", partition.partition()).param("offset", value).update();
            long actual = jdbc.sql("""
                    SELECT next_offset FROM rebuild_partition_offset
                    WHERE run_id=UUID_TO_BIN(:run) AND phase=:phase AND topic_name=:topic AND partition_id=:partition
                    """).param("run", runId.toString()).param("phase", phase).param("topic", partition.topic())
                    .param("partition", partition.partition()).query(Long.class).single();
            if (actual != value) throw new IllegalStateException("conflicting offset evidence");
        });
    }

    private static Map<Integer, Long> integerOffsets(Map<TopicPartition, Long> source) {
        Map<Integer, Long> result = new LinkedHashMap<>();
        source.forEach((partition, offset) -> result.put(partition.partition(), offset));
        return Map.copyOf(result);
    }

    private static Map<TopicPartition, Long> topicOffsets(String topic, Map<Integer, Long> source) {
        Map<TopicPartition, Long> result = new LinkedHashMap<>();
        source.forEach((partition, offset) -> result.put(new TopicPartition(topic, partition), offset));
        return Map.copyOf(result);
    }

    private static void requireShadowHealthy(ShadowReplayClient.ControlStatus status, UUID runId, String generation) {
        if (status == null || !runId.equals(status.runId()) || !generation.equals(status.target())
                || !Set.of(0, 1, 2).equals(status.assigned()) || status.failureClass() != null
                || status.nextOffsets() == null) throw new IllegalStateException("shadow replay evidence invalid");
    }

    private static void sleep() {
        try { Thread.sleep(100); } catch (InterruptedException interrupted) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("shadow wait interrupted", interrupted);
        }
    }

    private record RebuildRequestData(String generation, String topic, int pageSize) {}
    private record Eligibility(String status, long differenceCount, boolean stable,
            boolean gateClosed, String gateOwner) {}
}
