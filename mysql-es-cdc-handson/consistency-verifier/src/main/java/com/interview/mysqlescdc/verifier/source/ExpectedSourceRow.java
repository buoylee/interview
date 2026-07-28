package com.interview.mysqlescdc.verifier.source;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

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
        List<String> violations = new ArrayList<>();
        if (productId <= 0) violations.add("product identity");
        if (revision <= 0) violations.add("revision identity");
        if (updatedAt == null) violations.add("revision time");

        if (active) {
            collectActiveViolations(
                    violations, sku, name, description, categoryId, categoryName,
                    priceCents, availableQuantity);
        } else {
            collectUnexpectedTombstoneValues(
                    violations, sku, name, description, categoryId, categoryName,
                    priceCents, availableQuantity);
        }
        if (!violations.isEmpty()) {
            throw new IllegalArgumentException(
                    "verifier source row violates: " + String.join(", ", violations));
        }
    }

    public static ExpectedSourceRow inactive(long productId, long revision, Instant updatedAt) {
        return new ExpectedSourceRow(productId, revision, false,
                null, null, null, null, null, null, null, updatedAt);
    }

    private static void collectActiveViolations(
            List<String> violations,
            String sku,
            String name,
            String description,
            Long categoryId,
            String categoryName,
            Long priceCents,
            Integer availableQuantity) {
        if (sku == null || sku.isBlank()) violations.add("active sku");
        if (name == null || name.isBlank()) violations.add("active name");
        if (description == null) violations.add("active description");
        if (categoryId == null || categoryId <= 0) violations.add("active category id");
        if (categoryName == null || categoryName.isBlank()) violations.add("active category name");
        if (priceCents == null || priceCents < 0) violations.add("active price");
        if (availableQuantity == null || availableQuantity < 0) {
            violations.add("active inventory");
        }
    }

    private static void collectUnexpectedTombstoneValues(
            List<String> violations,
            Object... businessValues) {
        for (Object value : businessValues) {
            if (value != null) {
                violations.add("inactive business payload");
                return;
            }
        }
    }
}
