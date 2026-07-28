package com.interview.mysqlescdc.consumer.dlq;

import static org.assertj.core.api.Assertions.*;
import static org.mockito.Mockito.*;
import java.util.*;
import org.junit.jupiter.api.Test;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;

class DlqControllerTest {
    @Test void exposes_explicit_counts_lists_not_found_pending_and_resolved_outcomes() {
        DlqStore products=mock(DlqStore.class); RecordDlqStore records=mock(RecordDlqStore.class);
        DlqReplayService productReplay=mock(DlqReplayService.class);
        RecordDlqReplayService recordReplay=mock(RecordDlqReplayService.class);
        when(products.unresolvedCount()).thenReturn(2L); when(records.unresolvedCount()).thenReturn(3L);
        when(products.listPending()).thenReturn(List.of()); when(records.listPending()).thenReturn(List.of());
        when(productReplay.replay("t:0:1:7")).thenReturn(ReplayResult.notFound("t:0:1:7"));
        var controller=new DlqController(products,records,productReplay,recordReplay);
        assertThat(controller.productCount()).containsEntry("unresolved",2L);
        assertThat(controller.recordCount()).containsEntry("unresolved",3L);
        assertThat(controller.products("PENDING")).isEmpty();
        assertThat(controller.records("PENDING")).isEmpty();
        assertThat(controller.replayProduct("t:0:1:7").status()).isEqualTo(ReplayStatus.NOT_FOUND);
        assertThatThrownBy(() -> controller.products("RESOLVED"))
                .isInstanceOfSatisfying(ResponseStatusException.class,
                        failure -> assertThat(failure.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST));
    }
}
