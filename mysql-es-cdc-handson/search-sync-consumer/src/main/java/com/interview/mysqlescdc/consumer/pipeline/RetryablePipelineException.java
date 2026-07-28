package com.interview.mysqlescdc.consumer.pipeline;

public class RetryablePipelineException extends RuntimeException {
    public RetryablePipelineException(String message) {
        super(message);
    }

    public RetryablePipelineException(String message, Throwable cause) {
        super(message, cause);
    }
}
