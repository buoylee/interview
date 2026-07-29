package com.interview.mysqlescdc.verifier.rebuild;

import java.util.UUID;
import java.util.function.Supplier;

public final class RebuildCoordinator {
    public enum AliasTopology { OLD, NEW, CONTRADICTORY }

    public interface Workflow {
        void captureStart(UUID runId);
        void createGeneration(UUID runId);
        void openSnapshot(UUID runId);
        void startShadow(UUID runId);
        void scanSnapshot(UUID runId);
        void closeSnapshot(UUID runId);
        void assertRetained(UUID runId);
        void closeGate(UUID runId);
        void publishBarrier(UUID runId);
        void observeBarrier(UUID runId);
        void awaitPrimary(UUID runId);
        void awaitShadow(UUID runId);
        void pausePrimary(UUID runId);
        void verifyPhysical(UUID runId);
        void requireEligible(UUID runId);
        void cutover(UUID runId);
        void stopShadow(UUID runId);
        void resumePrimary(UUID runId);
        void clearLogGap(UUID runId);
        void openGate(UUID runId);
        default AliasTopology aliasTopology(UUID runId) { return AliasTopology.OLD; }
        default void activateRebuildRequired(UUID runId) {}
    }

    private final RebuildRunStore store;
    private final Workflow flow;
    private final RebuildFailpointRegistry failpoints;
    private final CriticalSection critical;

    @FunctionalInterface
    interface CriticalSection { RebuildStatus run(Supplier<RebuildStatus> work); }

    public RebuildCoordinator(RebuildRunStore store, Workflow flow, RebuildFailpointRegistry failpoints) {
        this(store, flow, failpoints, Supplier::get);
    }

    public RebuildCoordinator(RebuildRunStore store, Workflow flow,
            RebuildFailpointRegistry failpoints, RebuildAdvisoryLock lock) {
        this(store, flow, failpoints, lock::execute);
    }

    private RebuildCoordinator(RebuildRunStore store, Workflow flow,
            RebuildFailpointRegistry failpoints, CriticalSection critical) {
        this.store = store;
        this.flow = flow;
        this.failpoints = failpoints;
        this.critical = critical;
    }

    public RebuildStatus start(RebuildRequest request) {
        return critical.run(() -> {
            if ("MYSQL_BINLOG_GAP".equals(request.reason())) {
                store.create(request);
                store.transition(request.runId(), "CREATED", "CANAL_RECOVERY_REQUIRED");
                return store.get(request.runId());
            }
            return run(request);
        });
    }

    public RebuildStatus resume(UUID runId) {
        return critical.run(() -> recover(runId));
    }

    public RebuildStatus startCanalRecovery(UUID runId, CanalRecoveryService recovery) {
        return critical.run(() -> recovery.start(runId));
    }

    public RebuildStatus completeCanalRecovery(UUID runId, CanalRecoveryEvidence evidence,
            CanalRecoveryService recovery) {
        return critical.run(() -> { recovery.complete(runId, evidence); return recover(runId); });
    }

    private RebuildStatus run(RebuildRequest request) {
        UUID runId = request.runId();
        boolean cutover = false;
        store.create(request);
        try {
            flow.captureStart(runId);
            flow.createGeneration(runId);
            store.transition(runId, "CREATED", "SNAPSHOTTING");
            flow.openSnapshot(runId);
            flow.startShadow(runId);
            flow.scanSnapshot(runId);
            flow.closeSnapshot(runId);
            store.transition(runId, "SNAPSHOTTING", "REPLAYING");
            flow.assertRetained(runId);
            store.transition(runId, "REPLAYING", "GATING");
            flow.closeGate(runId);
            flow.publishBarrier(runId);
            flow.observeBarrier(runId);
            flow.awaitPrimary(runId);
            flow.awaitShadow(runId);
            flow.pausePrimary(runId);
            store.transition(runId, "GATING", "VERIFYING");
            flow.verifyPhysical(runId);
            flow.requireEligible(runId);
            store.transition(runId, "VERIFYING", "CUTTING_OVER");
            failpoints.check(RebuildFailpoint.BEFORE_ALIAS_SWITCH);
            flow.cutover(runId);
            cutover = true;
            store.transition(runId, "CUTTING_OVER", "CUTOVER_COMMITTED");
            failpoints.check(RebuildFailpoint.AFTER_ALIAS_SWITCH_BEFORE_GATE_OPEN);
            completeForward(runId);
            return store.get(runId);
        } catch (RuntimeException primary) {
            handleFailure(runId, cutover, primary);
            throw primary;
        }
    }

    private RebuildStatus recover(UUID runId) {
        RebuildStatus status = store.get(runId);
        if ("COMPLETED".equals(status.status()) || "FAILED".equals(status.status())) return status;
        if ("CANAL_RECOVERY_REQUIRED".equals(status.status())) return status;
        if ("CANAL_RECOVERING".equals(status.status())) {
            flow.closeGate(runId);
            return status;
        }
        if ("CREATED".equals(status.status())) return runAfterCanalRecovery(runId);
        AliasTopology topology = flow.aliasTopology(runId);
        if (topology == AliasTopology.CONTRADICTORY
                || (status.aliasSwapped() && topology == AliasTopology.OLD)) {
            flow.closeGate(runId);
            flow.activateRebuildRequired(runId);
            throw new IllegalStateException("persisted rebuild state contradicts alias topology");
        }
        if (status.aliasSwapped() || topology == AliasTopology.NEW) {
            if (!"CUTOVER_COMMITTED".equals(status.status())) {
                store.transition(runId, status.status(), "CUTOVER_COMMITTED");
            }
            flow.verifyPhysical(runId);
            completeForward(runId);
            return store.get(runId);
        }
        RuntimeException interrupted = new IllegalStateException("rebuild interrupted before cutover");
        cleanupBeforeCutover(runId, interrupted);
        store.fail(runId, interrupted);
        return store.get(runId);
    }

    private RebuildStatus runAfterCanalRecovery(UUID runId) {
        boolean cutover = false;
        try {
            flow.captureStart(runId);
            flow.createGeneration(runId);
            store.transition(runId, "CREATED", "SNAPSHOTTING");
            flow.openSnapshot(runId);
            flow.startShadow(runId);
            flow.openGate(runId);
            flow.scanSnapshot(runId);
            flow.closeSnapshot(runId);
            store.transition(runId, "SNAPSHOTTING", "REPLAYING");
            flow.assertRetained(runId);
            store.transition(runId, "REPLAYING", "GATING");
            flow.closeGate(runId);
            flow.publishBarrier(runId);
            flow.observeBarrier(runId);
            flow.awaitPrimary(runId);
            flow.awaitShadow(runId);
            flow.pausePrimary(runId);
            store.transition(runId, "GATING", "VERIFYING");
            flow.verifyPhysical(runId);
            flow.requireEligible(runId);
            store.transition(runId, "VERIFYING", "CUTTING_OVER");
            failpoints.check(RebuildFailpoint.BEFORE_ALIAS_SWITCH);
            flow.cutover(runId);
            cutover = true;
            store.transition(runId, "CUTTING_OVER", "CUTOVER_COMMITTED");
            failpoints.check(RebuildFailpoint.AFTER_ALIAS_SWITCH_BEFORE_GATE_OPEN);
            completeForward(runId);
            return store.get(runId);
        } catch (RuntimeException primary) {
            handleFailure(runId, cutover, primary);
            throw primary;
        }
    }

    private void handleFailure(UUID runId, boolean cutoverReturned, RuntimeException primary) {
        RebuildStatus status = store.get(runId);
        if (cutoverReturned || "CUTOVER_COMMITTED".equals(status.status())) return;
        if ("CUTTING_OVER".equals(status.status())) {
            AliasTopology topology = flow.aliasTopology(runId);
            if (topology == AliasTopology.NEW) {
                store.transition(runId, "CUTTING_OVER", "CUTOVER_COMMITTED");
                return;
            }
            if (topology == AliasTopology.CONTRADICTORY) {
                flow.activateRebuildRequired(runId);
                return;
            }
        }
        cleanupBeforeCutover(runId, primary);
        suppress(primary, () -> flow.activateRebuildRequired(runId));
        store.fail(runId, primary);
    }

    private void completeForward(UUID runId) {
        flow.stopShadow(runId);
        flow.resumePrimary(runId);
        flow.clearLogGap(runId);
        flow.openGate(runId);
        store.transition(runId, "CUTOVER_COMMITTED", "COMPLETED");
    }

    private void cleanupBeforeCutover(UUID runId, RuntimeException primary) {
        suppress(primary, () -> flow.stopShadow(runId));
        suppress(primary, () -> flow.resumePrimary(runId));
        suppress(primary, () -> flow.openGate(runId));
    }

    private static void suppress(RuntimeException primary, Runnable cleanup) {
        try { cleanup.run(); } catch (RuntimeException cleanupFailure) {
            primary.addSuppressed(cleanupFailure);
        }
    }

    public RebuildStatus status(UUID runId) {
        RebuildStatus status = store.get(runId);
        String actual = flow.aliasTopology(runId).name();
        return new RebuildStatus(status.runId(),status.status(),status.generation(),
                status.failureMessage(),status.aliasSwapped(),status.startOffsets(),
                status.shadowOffsets(),status.barrierOffsets(),status.verificationRunId(),
                status.gateOwner(),actual);
    }
}
