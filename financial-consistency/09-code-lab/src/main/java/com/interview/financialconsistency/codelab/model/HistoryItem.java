package com.interview.financialconsistency.codelab.model;

import java.time.Instant;
import java.util.Map;

public sealed interface HistoryItem permits Command, Event, Fact, Fault {
    String id();

    String businessKey();

    Instant occurredAt();

    Map<String, String> attributes();

    default String attr(String key) {
        return attributes().get(key);
    }

    default String requireAttr(String key) {
        String value = attributes().get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("Missing attribute " + key + " on " + id());
        }
        return value;
    }
}
