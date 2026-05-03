package com.interview.financialconsistency.serviceprototype.verification;

import java.util.List;
import java.util.Objects;

public record DbInvariantViolation(String invariant, String reason, List<String> relatedFactIds) {
    public DbInvariantViolation {
        invariant = Objects.requireNonNull(invariant);
        reason = Objects.requireNonNull(reason);
        relatedFactIds = relatedFactIds == null ? List.of() : List.copyOf(relatedFactIds);
    }
}
