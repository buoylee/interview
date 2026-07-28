package com.interview.mysqlescdc.verifier.target;

import java.util.List;

public record IndexedPage(
        List<IndexedDocument> documents,
        SearchAfterToken nextToken,
        boolean complete) {
    public IndexedPage {
        documents = List.copyOf(documents);
        long previous = 0;
        for (IndexedDocument document : documents) {
            if (document.productId() <= previous) {
                throw new IllegalArgumentException("indexed page must be ordered by productId");
            }
            previous = document.productId();
        }
        if (documents.isEmpty() && !complete) {
            throw new IllegalArgumentException("empty indexed page must be complete");
        }
        if (!documents.isEmpty() && nextToken == null) {
            throw new IllegalArgumentException("non-empty indexed page requires next token");
        }
    }
}
