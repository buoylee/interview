package com.interview.mysqlescdc.verifier.status;

import java.time.Clock;
import java.time.Instant;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.stereotype.Service;

@Service
public final class PipelineStatusService {
    private final ConsumerLagReader lagReader;
    private final PipelineConditionStore store;
    private final PipelineStateEvaluator evaluator;
    private final ReconciliationMetrics metrics;
    private final Clock clock;

    @Autowired
    public PipelineStatusService(
            ConsumerLagReader lagReader,
            PipelineConditionStore store,
            PipelineStateEvaluator evaluator,
            ReconciliationMetrics metrics) {
        this(lagReader, store, evaluator, metrics, Clock.systemUTC());
    }

    PipelineStatusService(
            ConsumerLagReader lagReader, PipelineConditionStore store,
            PipelineStateEvaluator evaluator, ReconciliationMetrics metrics, Clock clock) {
        this.lagReader = lagReader;
        this.store = store;
        this.evaluator = evaluator;
        this.metrics = metrics;
        this.clock = clock;
    }

    public PipelineStatusReport current() {
        ConsumerLagSnapshot lag = lagReader.read();
        Instant now = clock.instant();
        var latest = store.latestVerification();
        var conclusive = store.latestConclusiveVerification();
        PipelineSignals signals = new PipelineSignals(
                store.activeConditions(), store.unresolvedDlqCount(),
                latest.map(PipelineConditionStore.LatestVerification::runId).orElse(null),
                latest.map(PipelineConditionStore.LatestVerification::status).orElse(null),
                latest.map(PipelineConditionStore.LatestVerification::differenceCount).orElse(0L),
                latest.map(PipelineConditionStore.LatestVerification::finishedAt).orElse(null),
                conclusive.map(PipelineConditionStore.LatestVerification::status).orElse(null),
                conclusive.map(PipelineConditionStore.LatestVerification::differenceCount).orElse(0L),
                conclusive.map(PipelineConditionStore.LatestVerification::finishedAt).orElse(null),
                lag, now);
        PipelineStatusReport report = evaluator.evaluate(signals);
        metrics.observe(report);
        return report;
    }
}
