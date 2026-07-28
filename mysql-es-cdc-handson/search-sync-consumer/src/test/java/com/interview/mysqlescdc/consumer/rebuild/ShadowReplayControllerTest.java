package com.interview.mysqlescdc.consumer.rebuild;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.*;
import java.util.Map;
import java.util.UUID;
import org.junit.jupiter.api.Test;

class ShadowReplayControllerTest {
    @Test void delegatesBoundedControlSurface() {
        ShadowReplayService service = mock(ShadowReplayService.class);
        var expected = new ShadowReplayStatus(UUID.randomUUID(), ShadowReplayState.RUNNING, Map.of(0, 7L), null);
        var request = new ShadowReplayRequest(expected.runId(), "product-search-revision", "products_v3_20260728123456_deadbeef", Map.of(0, 7L));
        when(service.start(request)).thenReturn(expected);
        assertThat(new ShadowReplayController(service).start(request)).isEqualTo(expected);
    }
}
