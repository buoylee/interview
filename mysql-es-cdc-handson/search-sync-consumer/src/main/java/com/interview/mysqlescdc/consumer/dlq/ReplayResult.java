package com.interview.mysqlescdc.consumer.dlq;

import com.interview.mysqlescdc.consumer.sink.BulkOutcome;

public record ReplayResult(String eventId, Long priorRevision, Long currentRevision,
        BulkOutcome outcome, boolean resolved, ReplayStatus status) {
    public static ReplayResult notFound(String id) {
        return new ReplayResult(id, null, null, null, false, ReplayStatus.NOT_FOUND);
    }
}
