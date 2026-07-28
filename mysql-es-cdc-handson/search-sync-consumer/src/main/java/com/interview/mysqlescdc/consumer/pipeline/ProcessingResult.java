package com.interview.mysqlescdc.consumer.pipeline;

public record ProcessingResult(
        int signalCount,
        int appliedCount,
        int staleCount,
        int productDlqCount,
        int recordDlqCount,
        long highestSourceRevision) {
}
