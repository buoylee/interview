package com.interview.financialconsistency.codelab.model;

import java.util.List;
import java.util.Objects;

public record InvariantViolation(String invariant, String reason, String verifier, String boundary,
                                 List<String> relatedItemIds, History reducedHistory) {
    public InvariantViolation {
        Objects.requireNonNull(invariant);
        Objects.requireNonNull(reason);
        Objects.requireNonNull(verifier);
        Objects.requireNonNull(boundary);
        Objects.requireNonNull(reducedHistory);
        relatedItemIds = relatedItemIds == null ? List.of() : List.copyOf(relatedItemIds);
    }
}
