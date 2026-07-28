package com.interview.mysqlescdc.consumer.failpoint;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;

import org.junit.jupiter.api.Test;

class FailpointRegistryTest {
    @Test
    void counters_are_noop_until_armed_and_consume_exactly_the_armed_hits() {
        CrashAction crash = mock(CrashAction.class);
        FailpointRegistry registry = new FailpointRegistry(crash);
        registry.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        verify(crash, never()).crash(86);
        registry.arm(Failpoint.AFTER_ES_BULK_SUCCESS, 2);
        registry.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        registry.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        registry.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        verify(crash, times(2)).crash(86);
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
