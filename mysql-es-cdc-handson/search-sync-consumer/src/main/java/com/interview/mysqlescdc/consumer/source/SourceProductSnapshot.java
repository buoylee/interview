package com.interview.mysqlescdc.consumer.source;

import java.time.Instant;
import java.util.Objects;

public record SourceProductSnapshot(
        long productId,
        String sku,
        String name,
        String description,
        Long categoryId,
        String categoryName,
        Long priceCents,
        Integer availableQuantity,
        boolean active,
        long revision,
        Instant updatedAt) {

    public SourceProductSnapshot {
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
        } else if (sku != null || name != null || description != null
                || categoryId != null || categoryName != null || priceCents != null
                || availableQuantity != null) {
            throw new IllegalArgumentException("inactive source must not contain business fields");
        }
    }

    private static void requireNonBlank(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }

    public static SourceProductSnapshot active(
            long productId,
            String sku,
            String name,
            String description,
            long categoryId,
            String categoryName,
            long priceCents,
            int availableQuantity,
            long revision,
            Instant updatedAt) {
        return new SourceProductSnapshot(
                productId, sku, name, description, categoryId, categoryName,
                priceCents, availableQuantity, true, revision, updatedAt);
    }

    public static SourceProductSnapshot inactive(long productId, long revision, Instant updatedAt) {
        return new SourceProductSnapshot(
                productId, null, null, null, null, null, null, null,
                false, revision, updatedAt);
    }
}
