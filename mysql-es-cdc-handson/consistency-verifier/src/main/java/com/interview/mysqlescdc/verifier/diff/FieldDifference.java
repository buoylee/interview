package com.interview.mysqlescdc.verifier.diff;

import java.util.Objects;

import tools.jackson.databind.JsonNode;

public record FieldDifference(String field, JsonNode expectedValue, JsonNode actualValue) {
    public FieldDifference {
        if (field == null || field.isBlank()) {
            throw new IllegalArgumentException("field name required");
        }
        Objects.requireNonNull(expectedValue, "expectedValue");
        Objects.requireNonNull(actualValue, "actualValue");
    }
}
