package com.interview.mysqlescdc.product.api;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

public final class ProductRequests {
    private ProductRequests() {}

    public record CreateProductRequest(
            @Min(1) long id,
            @NotBlank String sku,
            @NotBlank String name,
            String description,
            @Min(1) long categoryId,
            @Min(0) long priceCents) {}

    public record ChangePriceRequest(@Min(0) long priceCents) {}

    public record ReplaceInventoryRequest(
            @Min(0) int availableQuantity,
            @Min(0) int reservedQuantity) {}

    public record RenameCategoryRequest(@NotBlank String name) {}

    public record RevisionResponse(long productId, long revision) {}
}
