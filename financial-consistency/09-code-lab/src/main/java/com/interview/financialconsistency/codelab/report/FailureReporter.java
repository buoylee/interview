package com.interview.financialconsistency.codelab.report;

import com.interview.financialconsistency.codelab.model.HistoryItem;
import com.interview.financialconsistency.codelab.model.InvariantViolation;

public final class FailureReporter {
    public String render(FailureReport report) {
        StringBuilder rendered = new StringBuilder();
        rendered.append("Experiment: ").append(report.experimentName()).append(System.lineSeparator());
        rendered.append("Scenario: ").append(report.scenario()).append(System.lineSeparator());
        rendered.append("Seed: ").append(report.seed()).append(System.lineSeparator());
        rendered.append("Expected to pass: ").append(report.expectedToPass()).append(System.lineSeparator());
        rendered.append("Result: ").append(report.violations().isEmpty() ? "PASS" : "FAILED").append(System.lineSeparator());

        for (InvariantViolation violation : report.violations()) {
            rendered.append(System.lineSeparator());
            rendered.append("Violated invariant: ").append(violation.invariant()).append(System.lineSeparator());
            rendered.append("Reason: ").append(violation.reason()).append(System.lineSeparator());
            rendered.append("Verifier: ").append(violation.verifier()).append(System.lineSeparator());
            rendered.append("Boundary: ").append(violation.boundary()).append(System.lineSeparator());
            rendered.append("Related items: ").append(String.join(", ", violation.relatedItemIds())).append(System.lineSeparator());
            rendered.append("Reduced history:");
            for (HistoryItem item : violation.reducedHistory().items()) {
                rendered.append(System.lineSeparator()).append("- ").append(item.id());
            }
            rendered.append(System.lineSeparator());
        }

        return rendered.toString();
    }
}
