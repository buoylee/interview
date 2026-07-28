package com.interview.mysqlescdc.consumer.metrics;

import java.time.Instant;
import java.util.concurrent.atomic.AtomicLong;
import java.util.function.LongSupplier;
import org.springframework.stereotype.Component;
import org.springframework.beans.factory.annotation.Autowired;
import io.micrometer.core.instrument.*;
import com.interview.mysqlescdc.consumer.dlq.*;

@Component
public class PipelineMetrics {
    private final MeterRegistry registry; private final AtomicLong lastSuccess=new AtomicLong();
    @Autowired
    public PipelineMetrics(MeterRegistry registry, DlqStore products, RecordDlqStore records) {
        this(registry,products::unresolvedCount,records::unresolvedCount);
    }
    public PipelineMetrics(MeterRegistry registry, LongSupplier products, LongSupplier records) {
        this.registry=registry;
        Counter.builder("cdc_consumer_records_total").register(registry);
        Counter.builder("cdc_consumer_signals_total").register(registry);
        Counter.builder("cdc_stale_revision_total").register(registry);
        Gauge.builder("cdc_product_dlq_unresolved",products,LongSupplier::getAsLong).register(registry);
        Gauge.builder("cdc_record_dlq_unresolved",records,LongSupplier::getAsLong).register(registry);
        Gauge.builder("cdc_last_success_epoch_seconds",lastSuccess,AtomicLong::get).register(registry);
    }
    public void recordConsumerRecord(){registry.get("cdc_consumer_records_total").counter().increment();}
    public void recordSignal(){registry.get("cdc_consumer_signals_total").counter().increment();}
    public void recordBulk(String outcome){Counter.builder("cdc_es_bulk_items_total").tag("outcome",outcome).register(registry).increment();}
    public void recordRetry(String failureClass){Counter.builder("cdc_retry_total").tag("failure_class",failureClass).register(registry).increment();}
    public void recordStale(){registry.get("cdc_stale_revision_total").counter().increment();}
    public void recordSuccess(){lastSuccess.set(Instant.now().getEpochSecond());}
}
