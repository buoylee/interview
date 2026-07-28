package com.interview.mysqlescdc.verifier.status;

import static org.assertj.core.api.Assertions.assertThat;

import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.Set;
import java.util.UUID;

import org.junit.jupiter.api.Test;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

class PipelineStateEvaluatorTest {
    private static final Instant NOW = Instant.parse("2026-07-22T12:00:00Z");
    private static final UUID RUN = UUID.fromString("00000000-0000-0000-0000-000000000055");
    private final PipelineStateEvaluator evaluator = new PipelineStateEvaluator(Duration.ofMinutes(10));

    @Test
    void locks_truthful_precedence() {
        assertThat(evaluate(Set.of("REBUILD_IN_PROGRESS"), 9, VerificationRunStatus.FAILED, 7, 8))
                .isEqualTo(PipelineStatus.REBUILDING);
        assertThat(evaluate(Set.of("LOG_GAP"), 9, VerificationRunStatus.FAILED, 7, 8))
                .isEqualTo(PipelineStatus.REBUILD_REQUIRED);
        assertThat(evaluate(Set.of("REBUILD_REQUIRED"), 0, VerificationRunStatus.PASS, 0, 0))
                .isEqualTo(PipelineStatus.REBUILD_REQUIRED);
        assertThat(evaluate(Set.of(), 1, VerificationRunStatus.PASS, 0, 8))
                .isEqualTo(PipelineStatus.DEGRADED);
        assertThat(evaluate(Set.of(), 0, VerificationRunStatus.DIFF, 2, 8))
                .isEqualTo(PipelineStatus.DEGRADED);
        assertThat(evaluate(Set.of(), 0, VerificationRunStatus.FAILED, 0, 8))
                .isEqualTo(PipelineStatus.DEGRADED);
        assertThat(evaluator.evaluate(signals(Set.of(), 0, null, 0, 8, true)).state())
                .isEqualTo(PipelineStatus.DEGRADED);
        assertThat(evaluate(Set.of(), 0, VerificationRunStatus.INCONCLUSIVE, 0, 8))
                .isEqualTo(PipelineStatus.CATCHING_UP);
        assertThat(evaluate(Set.of(), 0, VerificationRunStatus.PASS, 0, 8))
                .isEqualTo(PipelineStatus.CATCHING_UP);
        assertThat(evaluate(Set.of(), 0, VerificationRunStatus.PASS, 0, 0))
                .isEqualTo(PipelineStatus.HEALTHY);
    }

    @Test
    void missing_commit_is_not_healthy_even_when_numeric_lag_is_zero() {
        PipelineSignals signals = new PipelineSignals(Set.of(), 0, RUN,
                VerificationRunStatus.PASS, 0, NOW.minusSeconds(30),
                VerificationRunStatus.PASS, 0, NOW.minusSeconds(30),
                NOW.minusSeconds(30),
                new ConsumerLagSnapshot(0, false, List.of()), NOW);

        assertThat(evaluator.evaluate(signals).state()).isEqualTo(PipelineStatus.CATCHING_UP);
    }

    @Test
    void stale_pass_is_degraded_not_healthy() {
        PipelineSignals stale = new PipelineSignals(Set.of(), 0, RUN,
                VerificationRunStatus.PASS, 0, NOW.minus(Duration.ofMinutes(11)),
                VerificationRunStatus.PASS, 0, NOW.minus(Duration.ofMinutes(11)),
                NOW.minus(Duration.ofMinutes(11)),
                new ConsumerLagSnapshot(0, true, List.of()), NOW);

        assertThat(evaluator.evaluate(stale).state()).isEqualTo(PipelineStatus.DEGRADED);
    }

    @Test
    void newer_inconclusive_run_does_not_hide_latest_conclusive_diff() {
        PipelineSignals signals = new PipelineSignals(Set.of(), 0, RUN,
                VerificationRunStatus.INCONCLUSIVE, 0, NOW.minusSeconds(10),
                VerificationRunStatus.DIFF, 3, NOW.minusSeconds(20),
                null,
                new ConsumerLagSnapshot(0, true, List.of()), NOW);

        assertThat(evaluator.evaluate(signals).state()).isEqualTo(PipelineStatus.DEGRADED);
    }

    private PipelineStatus evaluate(Set<String> conditions, long dlq,
            VerificationRunStatus status, long differences, long lag) {
        return evaluator.evaluate(signals(conditions, dlq, status, differences, lag, true)).state();
    }

    private PipelineSignals signals(Set<String> conditions, long dlq,
            VerificationRunStatus status, long differences, long lag, boolean complete) {
        return new PipelineSignals(conditions, dlq, status == null ? null : RUN, status,
                differences, status == null ? null : NOW.minusSeconds(30),
                conclusive(status), differences,
                conclusive(status) == null ? null : NOW.minusSeconds(30),
                conclusive(status) == VerificationRunStatus.PASS
                        ? NOW.minusSeconds(30) : null,
                new ConsumerLagSnapshot(lag, complete, List.of()), NOW);
    }

    private VerificationRunStatus conclusive(VerificationRunStatus status) {
        if (status == null) return null;
        return status == VerificationRunStatus.PASS
                || status == VerificationRunStatus.DIFF
                || status == VerificationRunStatus.REPAIRED ? status : VerificationRunStatus.PASS;
    }
}
