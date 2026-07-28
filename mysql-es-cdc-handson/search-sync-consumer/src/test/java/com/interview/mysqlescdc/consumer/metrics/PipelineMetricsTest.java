package com.interview.mysqlescdc.consumer.metrics;

import static org.assertj.core.api.Assertions.assertThat;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import org.junit.jupiter.api.Test;

class PipelineMetricsTest {
    @Test void registers_locked_names_and_only_low_cardinality_labels() {
        var registry=new SimpleMeterRegistry();
        var metrics=new PipelineMetrics(registry,()->2L,()->3L);
        metrics.recordBulk("applied"); metrics.recordRetry("transport"); metrics.recordSuccess();
        assertThat(registry.get("cdc_es_bulk_items_total").tag("outcome","applied").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_retry_total").tag("failure_class","transport").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_product_dlq_unresolved").gauge().value()).isEqualTo(2);
        assertThat(registry.get("cdc_record_dlq_unresolved").gauge().value()).isEqualTo(3);
        assertThat(registry.getMeters()).allSatisfy(meter -> assertThat(meter.getId().getTags())
                .allSatisfy(tag -> assertThat(tag.getKey()).isIn("outcome","failure_class")));
        assertThat(registry.get("cdc_last_success_epoch_seconds").gauge().value()).isPositive();
    }
}
