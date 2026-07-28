package com.interview.mysqlescdc.consumer.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ShadowReplayControllerTest {
    @Test void delegatesBoundedControlSurface() {
        ShadowReplayService service = mock(ShadowReplayService.class);
        var expected = new ShadowReplayStatus(UUID.randomUUID(), "products_v3_20260728123456_deadbeef", java.util.Set.of(0,1,2), Map.of(0, 7L), true, ShadowReplayState.RUNNING, null);
        var request = new ShadowReplayRequest(expected.runId(), "product-search-revision", "products_v3_20260728123456_deadbeef", Map.of(0, 7L));
        when(service.start(request)).thenReturn(expected);
        assertThat(new ShadowReplayController(service).start(request)).isEqualTo(expected);
        when(service.status(expected.runId())).thenReturn(expected);
        when(service.stop(expected.runId())).thenReturn(expected);
        assertThat(new ShadowReplayController(service).status(expected.runId())).isEqualTo(expected);
        assertThat(new ShadowReplayController(service).stop(expected.runId())).isEqualTo(expected);
    }
}
