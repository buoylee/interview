package com.interview.mysqlescdc.verifier.status;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import org.junit.jupiter.api.Test;

import io.micrometer.core.instrument.Meter;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import com.interview.mysqlescdc.verifier.diff.DifferenceType;
import com.interview.mysqlescdc.verifier.repair.RepairActionType;
import com.interview.mysqlescdc.verifier.repair.RepairOutcome;
import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;

class ReconciliationMetricsTest {
    private static final Set<String> ALLOWED_LABELS = Set.of("state", "outcome", "type", "action");

    @Test
    void registers_only_fixed_low_cardinality_label_keys_and_values() {
        SimpleMeterRegistry registry = new SimpleMeterRegistry();
        ReconciliationMetrics metrics = new ReconciliationMetrics(registry);
        metrics.recordRun(VerificationRunStatus.DIFF, Map.of(DifferenceType.MISSING, 2L));
        metrics.recordRepair(RepairActionType.WRITE_EXTERNAL_GTE, RepairOutcome.APPLIED);

        assertThat(registry.getMeters()).extracting(meter -> meter.getId().getName())
                .contains("cdc_pipeline_state", "cdc_consumer_lag", "cdc_unresolved_dlq",
                        "cdc_reconciliation_runs_total", "cdc_reconciliation_differences",
                        "cdc_reconciliation_last_success_epoch_seconds",
                        "cdc_repair_actions_total");
        assertThat(registry.getMeters().stream()
                .flatMap(meter -> meter.getId().getTags().stream())
                .map(tag -> tag.getKey()).collect(Collectors.toSet()))
                .isSubsetOf(ALLOWED_LABELS);
        for (Meter meter : registry.getMeters()) {
            Map<String, String> tags = meter.getId().getTags().stream()
                    .collect(Collectors.toMap(tag -> tag.getKey(), tag -> tag.getValue()));
            assertThat(tags.values()).allMatch(value -> value.matches("[A-Z_]+"));
        }
        assertThat(registry.get("cdc_reconciliation_runs_total")
                .tag("outcome", "DIFF").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_reconciliation_differences")
                .tag("type", "MISSING").gauge().value()).isEqualTo(2);
        assertThat(registry.get("cdc_repair_actions_total")
                .tags("action", "WRITE_EXTERNAL_GTE", "outcome", "APPLIED")
                .counter().count()).isEqualTo(1);
    }
}
