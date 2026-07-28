package com.interview.mysqlescdc.consumer.dlq;

import java.util.List;
import com.interview.mysqlescdc.consumer.sink.BulkOutcome;

public record RecordReplayResult(String recordId, List<BulkOutcome> productOutcomes,
        boolean resolved, ReplayStatus status) {
    public RecordReplayResult { productOutcomes = List.copyOf(productOutcomes); }
    public static RecordReplayResult notFound(String id) {
        return new RecordReplayResult(id, List.of(), false, ReplayStatus.NOT_FOUND);
    }
}
