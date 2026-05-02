package com.interview.financialconsistency.codelab.model;

import java.time.Instant;
import java.util.Map;
import java.util.Objects;

public record Command(String id, String name, String businessKey, Instant occurredAt, Map<String, String> attributes)
        implements HistoryItem {
    public Command {
        Objects.requireNonNull(id);
        Objects.requireNonNull(name);
        Objects.requireNonNull(businessKey);
        Objects.requireNonNull(occurredAt);
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }
}
