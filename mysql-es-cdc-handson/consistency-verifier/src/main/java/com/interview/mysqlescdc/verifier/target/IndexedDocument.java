package com.interview.mysqlescdc.verifier.target;

import java.time.Instant;

import com.interview.mysqlescdc.verifier.source.ExpectedDocument;

public record IndexedDocument(
        long productId,
        String sku,
        String name,
        String description,
        Long categoryId,
        String categoryName,
        Long priceCents,
        Integer availableQuantity,
        boolean searchable,
        long sourceRevision,
        Instant sourceUpdatedAt,
        long elasticsearchVersion,
        long sequenceNumber,
        long primaryTerm) {

    public IndexedDocument {
        if (productId < 1 || sourceRevision < 1 || elasticsearchVersion < 1
                || sequenceNumber < 0 || primaryTerm < 1) {
            throw new IllegalArgumentException("invalid indexed identity or Elasticsearch metadata");
        }
    }

    public static IndexedDocument fromExpected(
            ExpectedDocument expected,
            long elasticsearchVersion,
            long sequenceNumber,
            long primaryTerm) {
        return new IndexedDocument(
                expected.productId(), expected.sku(), expected.name(), expected.description(),
                expected.categoryId(), expected.categoryName(), expected.priceCents(),
                expected.availableQuantity(), expected.searchable(), expected.sourceRevision(),
                expected.sourceUpdatedAt(), elasticsearchVersion, sequenceNumber, primaryTerm);
    }
}
