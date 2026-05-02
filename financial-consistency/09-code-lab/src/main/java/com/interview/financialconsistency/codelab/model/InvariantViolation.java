package com.interview.financialconsistency.codelab.model;

import java.util.List;

public record InvariantViolation(String invariant, String reason, String verifier, String boundary,
                                 List<String> relatedItemIds, History reducedHistory) {
    public InvariantViolation {
        relatedItemIds = relatedItemIds == null ? List.of() : List.copyOf(relatedItemIds);
    }
}
