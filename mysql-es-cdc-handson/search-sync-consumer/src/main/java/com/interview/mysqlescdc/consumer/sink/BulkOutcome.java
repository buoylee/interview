package com.interview.mysqlescdc.consumer.sink;

public enum BulkOutcome {
    APPLIED,
    STALE,
    PERMANENT_FAILURE,
    RETRYABLE_FAILURE
}
