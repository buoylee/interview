package com.interview.mysqlescdc.verifier.source;

import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.Map;

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
        if (productId <= 0 || sourceRevision <= 0 || sourceUpdatedAt == null) {
            throw new IllegalArgumentException("expected document requires positive identity and UTC time");
        }
        Map<String, Object> managed = managedFields(
                sku, name, description, categoryId, categoryName, priceCents, availableQuantity);
        if (searchable) {
            verifySearchable(managed);
        } else if (managed.values().stream().anyMatch(value -> value != null)) {
            throw new IllegalArgumentException("verifier tombstone carries managed business data");
        }
    }

    public static ExpectedDocument tombstone(long productId, long revision, Instant updatedAt) {
        return new ExpectedDocument(productId, null, null, null, null, null, null, null,
                false, revision, updatedAt);
    }

    private static Map<String, Object> managedFields(
            String sku, String name, String description, Long categoryId,
            String categoryName, Long priceCents, Integer availableQuantity) {
        Map<String, Object> fields = new LinkedHashMap<>();
        fields.put("sku", sku);
        fields.put("name", name);
        fields.put("description", description);
        fields.put("category_id", categoryId);
        fields.put("category_name", categoryName);
        fields.put("price_cents", priceCents);
        fields.put("available_quantity", availableQuantity);
        return fields;
    }

    private static void verifySearchable(Map<String, Object> managed) {
        for (Map.Entry<String, Object> field : managed.entrySet()) {
            if (field.getValue() == null) {
                throw new IllegalArgumentException("missing expected field " + field.getKey());
            }
        }
        if (((String) managed.get("sku")).isBlank()
                || ((String) managed.get("name")).isBlank()
                || ((String) managed.get("category_name")).isBlank()) {
            throw new IllegalArgumentException("expected searchable names must be nonblank");
        }
        if ((Long) managed.get("category_id") <= 0
                || (Long) managed.get("price_cents") < 0
                || (Integer) managed.get("available_quantity") < 0) {
            throw new IllegalArgumentException("expected searchable numeric range violation");
        }
    }
}
