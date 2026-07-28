package com.interview.mysqlescdc.consumer.canal;

public record RevisionSignal(
        long productId,
        long eventRevision,
        boolean active,
        long canalMessageId,
        int rowIndex) {
}
