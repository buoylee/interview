package com.interview.mysqlescdc.consumer.sink;

public class BulkTransportException extends RuntimeException {
    public BulkTransportException(String message) {
        super(message);
    }

    public BulkTransportException(String message, Throwable cause) {
        super(message, cause);
    }
}
