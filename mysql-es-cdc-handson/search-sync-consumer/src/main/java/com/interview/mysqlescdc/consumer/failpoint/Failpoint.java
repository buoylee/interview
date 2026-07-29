package com.interview.mysqlescdc.consumer.failpoint;

public enum Failpoint {
    BEFORE_ES_BULK,
    AFTER_ES_BULK_SUCCESS,
    AFTER_DLQ_PUBLISH,
    BEFORE_KAFKA_OFFSET_COMMIT
}
