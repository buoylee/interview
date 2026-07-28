package com.interview.mysqlescdc.verifier.status;

import java.time.Duration;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

@Component
public final class PipelineStateEvaluator {
    private final Duration recentPassMaxAge;

    public PipelineStateEvaluator(
            @Value("${verification.recent-pass-max-age:10m}") Duration recentPassMaxAge) {
        this.recentPassMaxAge = recentPassMaxAge;
    }

    public PipelineStatusReport evaluate(PipelineSignals signals) {
        PipelineStatus state = state(signals);
        return new PipelineStatusReport(
                state, signals.lag().totalLag(), signals.lag().allPartitionsCommitted(),
                signals.lag().partitions(), signals.unresolvedDlq(), signals.latestRunId(),
                signals.latestRunStatus(), signals.latestDifferenceCount(),
                signals.latestRunFinishedAt(), signals.activeConditions(), signals.evaluatedAt());
    }

    private PipelineStatus state(PipelineSignals signals) {
        if (signals.activeConditions().contains("REBUILD_IN_PROGRESS")) {
            return PipelineStatus.REBUILDING;
        }
        if (signals.activeConditions().contains("LOG_GAP")
                || signals.activeConditions().contains("REBUILD_REQUIRED")) {
            return PipelineStatus.REBUILD_REQUIRED;
        }
        VerificationRunStatus runStatus = signals.latestRunStatus();
        VerificationRunStatus conclusiveStatus = signals.latestConclusiveStatus();
        if (signals.unresolvedDlq() > 0
                || runStatus == VerificationRunStatus.FAILED
                || conclusiveStatus == null
                || conclusiveStatus == VerificationRunStatus.DIFF
                || conclusiveStatus == VerificationRunStatus.REPAIRED) {
            return PipelineStatus.DEGRADED;
        }
        if (signals.lag().totalLag() > 0
                || !signals.lag().allPartitionsCommitted()
                || runStatus == VerificationRunStatus.INCONCLUSIVE
                || runStatus == VerificationRunStatus.RUNNING) {
            return PipelineStatus.CATCHING_UP;
        }
        boolean recentPass = conclusiveStatus == VerificationRunStatus.PASS
                && signals.latestConclusiveDifferenceCount() == 0
                && signals.latestConclusiveFinishedAt() != null
                && !signals.latestConclusiveFinishedAt().isBefore(
                        signals.evaluatedAt().minus(recentPassMaxAge));
        return recentPass ? PipelineStatus.HEALTHY : PipelineStatus.DEGRADED;
    }
}
