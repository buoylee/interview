package com.interview.financialconsistency.codelab.report;

import com.interview.financialconsistency.codelab.model.InvariantViolation;

import java.util.List;

public record FailureReport(String experimentName, String scenario, String seed, boolean expectedToPass,
                            List<InvariantViolation> violations) {
    public FailureReport {
        violations = violations == null ? List.of() : List.copyOf(violations);
    }
}
