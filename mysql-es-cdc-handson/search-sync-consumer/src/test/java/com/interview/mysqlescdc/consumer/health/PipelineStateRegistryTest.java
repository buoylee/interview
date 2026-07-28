package com.interview.mysqlescdc.consumer.health;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;
import org.junit.jupiter.api.Test;
import org.springframework.boot.health.contributor.Status;
import com.interview.mysqlescdc.consumer.dlq.*;

class PipelineStateRegistryTest {
    private final DlqStore products=mock(DlqStore.class);
    private final RecordDlqStore records=mock(RecordDlqStore.class);
    private final PipelineStateRegistry registry=new PipelineStateRegistry(products,records);

    @Test void unresolved_rows_force_degraded_and_cannot_be_masked_by_catching_up() {
        when(products.unresolvedCount()).thenReturn(1L);
        registry.setCatchingUp(true);
        assertThat(registry.current()).isEqualTo(PipelineState.DEGRADED);
        assertThat(new PipelineHealthIndicator(registry).health().getStatus()).isEqualTo(Status.DOWN);
    }
    @Test void catching_up_is_unknown_and_clean_idle_is_up() {
        registry.setCatchingUp(true);
        assertThat(new PipelineHealthIndicator(registry).health().getStatus()).isEqualTo(Status.UNKNOWN);
        registry.setCatchingUp(false);
        assertThat(new PipelineHealthIndicator(registry).health().getStatus()).isEqualTo(Status.UP);
    }
}
