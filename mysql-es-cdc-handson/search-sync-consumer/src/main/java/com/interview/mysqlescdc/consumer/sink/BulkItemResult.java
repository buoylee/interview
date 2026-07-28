package com.interview.mysqlescdc.consumer.sink;

public record BulkItemResult(
        long productId,
        long revision,
        BulkOutcome outcome,
        int status,
        String errorType,
        String reason) {

    public boolean settled() {
        return outcome != BulkOutcome.RETRYABLE_FAILURE;
    }
}
