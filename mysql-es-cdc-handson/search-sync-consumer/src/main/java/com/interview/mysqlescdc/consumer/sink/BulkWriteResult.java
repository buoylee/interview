package com.interview.mysqlescdc.consumer.sink;

import java.util.List;

public record BulkWriteResult(List<BulkItemResult> items) {
    public BulkWriteResult {
        items = List.copyOf(items);
    }

    public boolean hasRetryableFailure() {
        return items.stream().anyMatch(item -> item.outcome() == BulkOutcome.RETRYABLE_FAILURE);
    }
}
