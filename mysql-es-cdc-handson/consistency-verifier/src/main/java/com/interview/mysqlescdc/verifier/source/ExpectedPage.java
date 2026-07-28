package com.interview.mysqlescdc.verifier.source;

import java.util.List;

public record ExpectedPage(
        List<ExpectedDocument> documents,
        long nextExclusiveProductId,
        boolean complete) {

    public ExpectedPage {
        documents = List.copyOf(documents);
        long previous = 0;
        for (ExpectedDocument document : documents) {
            if (document.productId() <= previous) {
                throw new IllegalArgumentException("documents must be strictly ordered by productId");
            }
            previous = document.productId();
        }
        if (documents.isEmpty()) {
            if (!complete) {
                throw new IllegalArgumentException("empty page must be complete");
            }
        } else if (nextExclusiveProductId != previous) {
            throw new IllegalArgumentException("nextExclusiveProductId must equal the final productId");
        }
    }
}
