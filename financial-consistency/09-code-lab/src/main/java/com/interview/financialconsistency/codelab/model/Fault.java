package com.interview.financialconsistency.codelab.model;

import java.time.Instant;
import java.util.Map;
import java.util.Objects;

public record Fault(String id, String name, String businessKey, Instant occurredAt, Map<String, String> attributes)
        implements HistoryItem {
    public Fault {
        Objects.requireNonNull(id);
        Objects.requireNonNull(name);
        Objects.requireNonNull(businessKey);
        Objects.requireNonNull(occurredAt);
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }
}
