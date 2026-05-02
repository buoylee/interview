package com.interview.financialconsistency.codelab.model;

import java.time.Instant;
import java.util.Map;

public record Event(String id, String name, String businessKey, Instant occurredAt, Map<String, String> attributes)
        implements HistoryItem {
    public Event {
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }
}
