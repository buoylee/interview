package com.interview.financialconsistency.codelab.model;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;

public record Fact(String id, FactType type, String businessKey, Instant occurredAt, BigDecimal amount,
                   Map<String, String> attributes) implements HistoryItem {
    public Fact {
        amount = amount == null ? BigDecimal.ZERO : amount;
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }
}
