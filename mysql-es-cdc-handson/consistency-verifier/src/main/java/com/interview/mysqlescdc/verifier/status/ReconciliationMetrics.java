package com.interview.mysqlescdc.verifier.status;

import java.util.EnumMap;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.atomic.AtomicLong;

import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.verifier.diff.DifferenceType;
import com.interview.mysqlescdc.verifier.repair.RepairActionType;
import com.interview.mysqlescdc.verifier.repair.RepairOutcome;
import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

import io.micrometer.core.instrument.Counter;
import io.micrometer.core.instrument.Gauge;
import io.micrometer.core.instrument.MeterRegistry;

@Component
public final class ReconciliationMetrics {
    private static final Set<VerificationRunStatus> RUN_OUTCOMES = Set.of(
            VerificationRunStatus.PASS, VerificationRunStatus.DIFF,
            VerificationRunStatus.INCONCLUSIVE, VerificationRunStatus.FAILED);
    private static final Set<RepairOutcome> REPAIR_OUTCOMES = Set.of(
            RepairOutcome.APPLIED, RepairOutcome.STALE, RepairOutcome.FAILED);
    private final Map<PipelineStatus, AtomicLong> states = new EnumMap<>(PipelineStatus.class);
    private final AtomicLong lag = new AtomicLong();
    private final AtomicLong unresolvedDlq = new AtomicLong();
    private final AtomicLong lastSuccessEpochSeconds = new AtomicLong();
    private final Map<VerificationRunStatus, Counter> runCounters =
            new EnumMap<>(VerificationRunStatus.class);
    private final Map<DifferenceType, AtomicLong> differences =
            new EnumMap<>(DifferenceType.class);
    private final Map<RepairActionType, Map<RepairOutcome, Counter>> repairCounters =
            new EnumMap<>(RepairActionType.class);

    public ReconciliationMetrics(MeterRegistry registry) {
        for (PipelineStatus state : PipelineStatus.values()) {
            AtomicLong value = new AtomicLong();
            states.put(state, value);
            Gauge.builder("cdc_pipeline_state", value, AtomicLong::get)
                    .tag("state", state.name()).register(registry);
        }
        Gauge.builder("cdc_consumer_lag", lag, AtomicLong::get).register(registry);
        Gauge.builder("cdc_unresolved_dlq", unresolvedDlq, AtomicLong::get).register(registry);
        Gauge.builder("cdc_reconciliation_last_success_epoch_seconds",
                lastSuccessEpochSeconds, AtomicLong::get).register(registry);
        for (VerificationRunStatus outcome : RUN_OUTCOMES) {
            runCounters.put(outcome, Counter.builder("cdc_reconciliation_runs_total")
                    .tag("outcome", outcome.name()).register(registry));
        }
        for (DifferenceType type : DifferenceType.values()) {
            AtomicLong value = new AtomicLong();
            differences.put(type, value);
            Gauge.builder("cdc_reconciliation_differences", value, AtomicLong::get)
                    .tag("type", type.name()).register(registry);
        }
        for (RepairActionType action : RepairActionType.values()) {
            Map<RepairOutcome, Counter> outcomes = new EnumMap<>(RepairOutcome.class);
            for (RepairOutcome outcome : REPAIR_OUTCOMES) {
                outcomes.put(outcome, Counter.builder("cdc_repair_actions_total")
                        .tags("action", action.name(), "outcome", outcome.name())
                        .register(registry));
            }
            repairCounters.put(action, outcomes);
        }
    }

    public void recordRun(
            VerificationRunStatus outcome, Map<DifferenceType, Long> observedDifferences) {
        runCounters.get(outcome).increment();
        differences.forEach((type, value) -> value.set(observedDifferences.getOrDefault(type, 0L)));
    }

    public void recordRepair(RepairActionType action, RepairOutcome outcome) {
        repairCounters.get(action).get(outcome).increment();
    }

    public void observe(PipelineStatusReport report) {
        states.forEach((state, value) -> value.set(state == report.state() ? 1 : 0));
        lag.set(report.kafkaLag());
        unresolvedDlq.set(report.unresolvedDlq());
        if (report.latestSuccessfulPassFinishedAt() != null) {
            lastSuccessEpochSeconds.set(
                    report.latestSuccessfulPassFinishedAt().getEpochSecond());
        }
    }
}
