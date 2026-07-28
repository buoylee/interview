package com.interview.mysqlescdc.product.application;

public final class WriteGateClosedException extends RuntimeException {
    public WriteGateClosedException(String ownerRunId, String reason) {
        super("product writes paused by " + ownerRunId + (reason == null ? "" : ": " + reason));
    }
}
