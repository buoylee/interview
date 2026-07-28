package com.interview.mysqlescdc.consumer.failpoint;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.util.concurrent.atomic.AtomicInteger;

import org.junit.jupiter.api.Test;

class FailpointRegistryTest {
    @Test
    void counters_are_noop_until_armed_and_consume_exactly_the_armed_hits() {
        AtomicInteger crashes = new AtomicInteger();
        CrashAction crash = code -> {
            assertThat(code).isEqualTo(86);
            crashes.incrementAndGet();
        };
        FailpointRegistry registry = new FailpointRegistry(crash);
        registry.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        assertThat(crashes).hasValue(0);
        registry.arm(Failpoint.AFTER_ES_BULK_SUCCESS, 2);
        assertThat(registry.remaining()).containsEntry(Failpoint.AFTER_ES_BULK_SUCCESS, 2);
        registry.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        assertThat(registry.remaining()).containsEntry(Failpoint.AFTER_ES_BULK_SUCCESS, 1);
        registry.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        registry.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        assertThat(crashes).hasValue(2);
        assertThat(registry.remaining()).containsEntry(Failpoint.AFTER_ES_BULK_SUCCESS, 0);
    }

    @Test
    void arm_rejects_out_of_contract_counts() {
        FailpointRegistry registry = new FailpointRegistry(code -> { });
        assertThatThrownBy(() -> registry.arm(Failpoint.AFTER_DLQ_PUBLISH, 0))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> registry.arm(Failpoint.AFTER_DLQ_PUBLISH, 101))
                .isInstanceOf(IllegalArgumentException.class);
    }
}
