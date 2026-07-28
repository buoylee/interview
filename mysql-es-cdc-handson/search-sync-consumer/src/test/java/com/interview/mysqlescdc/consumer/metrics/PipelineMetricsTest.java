package com.interview.mysqlescdc.consumer.metrics;

import static org.assertj.core.api.Assertions.*;
import io.micrometer.core.instrument.simple.SimpleMeterRegistry;
import java.lang.ref.WeakReference;
import java.util.function.LongSupplier;
import org.junit.jupiter.api.Test;
import com.interview.mysqlescdc.consumer.sink.BulkOutcome;

class PipelineMetricsTest {
    @Test void registers_locked_names_and_only_low_cardinality_labels() {
        var registry=new SimpleMeterRegistry();
        var metrics=new PipelineMetrics(registry,()->2L,()->3L);
        metrics.recordBulk(BulkOutcome.APPLIED); metrics.recordRetry(RetryFailureClass.TRANSPORT); metrics.recordSuccess();
        assertThat(registry.get("cdc_es_bulk_items_total").tag("outcome","APPLIED").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_retry_total").tag("failure_class","TRANSPORT").counter().count()).isEqualTo(1);
        assertThat(registry.get("cdc_product_dlq_unresolved").gauge().value()).isEqualTo(2);
        assertThat(registry.get("cdc_record_dlq_unresolved").gauge().value()).isEqualTo(3);
        assertThat(registry.getMeters()).allSatisfy(meter -> assertThat(meter.getId().getTags())
                .allSatisfy(tag -> assertThat(tag.getKey()).isIn("outcome","failure_class")));
        assertThat(registry.get("cdc_last_success_epoch_seconds").gauge().value()).isPositive();
    }

    @Test void rejects_null_labels_without_registering_new_meters() {
        var registry=new SimpleMeterRegistry();
        var metrics=new PipelineMetrics(registry,()->0L,()->0L);
        int before=registry.getMeters().size();
        assertThatThrownBy(() -> metrics.recordBulk(null)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> metrics.recordRetry(null)).isInstanceOf(IllegalArgumentException.class);
        assertThat(registry.getMeters()).hasSize(before);
    }

    @Test void keeps_dlq_gauge_suppliers_alive_for_the_application_lifetime() throws InterruptedException {
        var registry = new SimpleMeterRegistry();
        LongSupplier products = new FixedSupplier(2);
        LongSupplier records = new FixedSupplier(3);
        var productReference = new WeakReference<>(products);
        var recordReference = new WeakReference<>(records);
        var metrics = new PipelineMetrics(registry, products, records);
        products = null;
        records = null;

        for (int attempt = 0; attempt < 20; attempt++) {
            System.gc();
            Thread.sleep(10);
        }

        metrics.recordSuccess();
        assertThat(productReference.get()).isNotNull();
        assertThat(recordReference.get()).isNotNull();
        assertThat(registry.get("cdc_product_dlq_unresolved").gauge().value()).isEqualTo(2);
        assertThat(registry.get("cdc_record_dlq_unresolved").gauge().value()).isEqualTo(3);
    }

    private record FixedSupplier(long value) implements LongSupplier {
        @Override public long getAsLong() { return value; }
    }
}
