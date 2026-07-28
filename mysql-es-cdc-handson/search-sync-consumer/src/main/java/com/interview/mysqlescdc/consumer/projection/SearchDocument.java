package com.interview.mysqlescdc.consumer.projection;

import java.time.Instant;
import java.util.Objects;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SearchDocument(
        @JsonProperty("product_id") long productId,
        @JsonProperty("sku") String sku,
        @JsonProperty("name") String name,
        @JsonProperty("description") String description,
        @JsonProperty("category_id") Long categoryId,
        @JsonProperty("category_name") String categoryName,
        @JsonProperty("price_cents") Long priceCents,
        @JsonProperty("available_quantity") Integer availableQuantity,
        @JsonProperty("searchable") boolean searchable,
        @JsonProperty("source_revision") long sourceRevision,
        @JsonProperty("source_updated_at") Instant sourceUpdatedAt) {

    public SearchDocument {
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
        } else if (sku != null || name != null || description != null
                || categoryId != null || categoryName != null || priceCents != null
                || availableQuantity != null) {
            throw new IllegalArgumentException(
                    "non-searchable document must not contain business fields");
        }
    }

    private static void requireNonBlank(String value, String field) {
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException(field + " must not be blank");
        }
    }

    public static SearchDocument tombstone(
            long productId, long sourceRevision, Instant sourceUpdatedAt) {
        return new SearchDocument(
                productId, null, null, null, null, null, null, null,
                false, sourceRevision, sourceUpdatedAt);
    }
}
