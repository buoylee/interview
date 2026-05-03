package com.interview.financialconsistency.serviceprototype.verification;

import java.util.Map;
import java.util.Objects;

public record DbFact(String tableName, String factId, String businessId, Map<String, String> attributes) {
    public DbFact {
        tableName = Objects.requireNonNull(tableName);
        factId = Objects.requireNonNull(factId);
        businessId = Objects.requireNonNull(businessId);
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }
}
