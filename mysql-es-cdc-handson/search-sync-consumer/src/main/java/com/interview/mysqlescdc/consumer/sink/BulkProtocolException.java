package com.interview.mysqlescdc.consumer.sink;

public class BulkProtocolException extends RuntimeException {
    public BulkProtocolException(String message) {
        super(message);
    }

    public BulkProtocolException(String message, Throwable cause) {
        super(message, cause);
    }
}
