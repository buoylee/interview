package com.interview.mysqlescdc.verifier.source;

import java.time.Instant;
import java.util.Objects;

public record ExpectedDocument(
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
        Instant sourceUpdatedAt) {

    public ExpectedDocument {
        if (productId < 1 || sourceRevision < 1) {
            throw new IllegalArgumentException("positive productId and sourceRevision required");
        }
        Objects.requireNonNull(sourceUpdatedAt, "sourceUpdatedAt");
        if (searchable) {
            requireNonBlank(sku, "searchable sku");
            requireNonBlank(name, "searchable name");
            Objects.requireNonNull(description, "searchable description");
            Objects.requireNonNull(categoryId, "searchable categoryId");
            requireNonBlank(categoryName, "searchable categoryName");
            Objects.requireNonNull(priceCents, "searchable priceCents");
            Objects.requireNonNull(availableQuantity, "searchable availableQuantity");
            if (categoryId < 1 || priceCents < 0 || availableQuantity < 0) {
                throw new IllegalArgumentException(
                        "searchable categoryId must be positive and numeric values non-negative");
            }
        } else if (sku != null || name != null || description != null || categoryId != null
                || categoryName != null || priceCents != null || availableQuantity != null) {
            throw new IllegalArgumentException("tombstone must not contain business fields");
        }
    }

    public static ExpectedDocument tombstone(long productId, long revision, Instant updatedAt) {
        return new ExpectedDocument(productId, null, null, null, null, null, null, null,
                false, revision, updatedAt);
    }

    private static void requireNonBlank(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }
}
