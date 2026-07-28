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
    }

    public static SearchDocument tombstone(
            long productId, long sourceRevision, Instant sourceUpdatedAt) {
        return new SearchDocument(
                productId, null, null, null, null, null, null, null,
                false, sourceRevision, sourceUpdatedAt);
    }
}
