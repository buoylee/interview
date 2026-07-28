package com.interview.mysqlescdc.verifier.status;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.time.Clock;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneOffset;
import java.util.List;
import java.util.Optional;
import java.util.Set;
import java.util.UUID;

import org.junit.jupiter.api.Test;

import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

import io.micrometer.core.instrument.simple.SimpleMeterRegistry;

class PipelineStatusServiceTest {
    @Test
    void first_observation_restores_last_success_from_persisted_pass_history() {
        Instant passFinishedAt = Instant.parse("2026-07-22T11:58:00Z");
        Instant now = Instant.parse("2026-07-22T12:00:00Z");
        PipelineConditionStore store = mock(PipelineConditionStore.class);
        ConsumerLagReader lag = mock(ConsumerLagReader.class);
        UUID passRun = UUID.randomUUID();
        when(lag.read()).thenReturn(new ConsumerLagSnapshot(4, true, List.of()));
        when(store.activeConditions()).thenReturn(Set.of());
        when(store.unresolvedDlqCount()).thenReturn(0L);
        when(store.latestVerification()).thenReturn(Optional.of(
                new PipelineConditionStore.LatestVerification(UUID.randomUUID(),
                        VerificationRunStatus.INCONCLUSIVE, 0, now.minusSeconds(5))));
        var persistedPass = new PipelineConditionStore.LatestVerification(
                passRun, VerificationRunStatus.PASS, 0, passFinishedAt);
        when(store.latestConclusiveVerification()).thenReturn(Optional.of(persistedPass));
        when(store.latestSuccessfulPass()).thenReturn(Optional.of(persistedPass));
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        ReconciliationMetrics metrics = new ReconciliationMetrics(registry);
        PipelineStatusService service = new PipelineStatusService(
                lag, store, new PipelineStateEvaluator(Duration.ofMinutes(10)), metrics,
                Clock.fixed(now, ZoneOffset.UTC));

        PipelineStatusReport report = service.current();

        assertThat(report.state()).isEqualTo(PipelineStatus.CATCHING_UP);
        assertThat(report.latestSuccessfulPassFinishedAt()).isEqualTo(passFinishedAt);
        assertThat(registry.get("cdc_reconciliation_last_success_epoch_seconds")
                .gauge().value()).isEqualTo(passFinishedAt.getEpochSecond());
    }
}
