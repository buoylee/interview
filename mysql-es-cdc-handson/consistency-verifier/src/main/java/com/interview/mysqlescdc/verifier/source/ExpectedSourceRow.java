package com.interview.mysqlescdc.verifier.source;

import java.time.Instant;
import java.util.Objects;

public record ExpectedSourceRow(
        long productId,
        long revision,
        boolean active,
        String sku,
        String name,
        String description,
        Long categoryId,
        String categoryName,
        Long priceCents,
        Integer availableQuantity,
        Instant updatedAt) {

    public ExpectedSourceRow {
        if (productId < 1 || revision < 1) {
            throw new IllegalArgumentException("positive productId and revision required");
        }
        Objects.requireNonNull(updatedAt, "updatedAt");
        if (active) {
            requireNonBlank(sku, "active sku");
            requireNonBlank(name, "active name");
            Objects.requireNonNull(description, "active description");
            Objects.requireNonNull(categoryId, "active categoryId");
            requireNonBlank(categoryName, "active categoryName");
            Objects.requireNonNull(priceCents, "active priceCents");
            Objects.requireNonNull(availableQuantity, "active availableQuantity");
            if (categoryId < 1 || priceCents < 0 || availableQuantity < 0) {
                throw new IllegalArgumentException(
                        "active categoryId must be positive and numeric values non-negative");
            }
        } else if (sku != null || name != null || description != null || categoryId != null
                || categoryName != null || priceCents != null || availableQuantity != null) {
            throw new IllegalArgumentException("inactive source row must not contain business fields");
        }
    }

    public static ExpectedSourceRow inactive(long productId, long revision, Instant updatedAt) {
        return new ExpectedSourceRow(productId, revision, false,
                null, null, null, null, null, null, null, updatedAt);
    }

    private static void requireNonBlank(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }
}
