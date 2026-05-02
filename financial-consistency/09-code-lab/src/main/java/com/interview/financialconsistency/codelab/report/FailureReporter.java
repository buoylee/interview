package com.interview.financialconsistency.codelab.report;

import com.interview.financialconsistency.codelab.model.HistoryItem;
import com.interview.financialconsistency.codelab.model.InvariantViolation;

public final class FailureReporter {
    private static final String NL = "\n";

    public String render(FailureReport report) {
        StringBuilder rendered = new StringBuilder();
        rendered.append("Experiment: ").append(report.experimentName()).append(NL);
        rendered.append("Scenario: ").append(report.scenario()).append(NL);
        rendered.append("Seed: ").append(report.seed()).append(NL);
        rendered.append("Expected to pass: ").append(report.expectedToPass()).append(NL);
        rendered.append("Result: ").append(report.violations().isEmpty() ? "PASS" : "FAILED").append(NL);

        for (InvariantViolation violation : report.violations()) {
            rendered.append(NL);
            rendered.append("Violated invariant: ").append(violation.invariant()).append(NL);
            rendered.append("Reason: ").append(violation.reason()).append(NL);
            rendered.append("Verifier: ").append(violation.verifier()).append(NL);
            rendered.append("Boundary: ").append(violation.boundary()).append(NL);
            rendered.append("Related items: ").append(String.join(", ", violation.relatedItemIds())).append(NL);
            rendered.append("Reduced history:");
            for (HistoryItem item : violation.reducedHistory().items()) {
                rendered.append(NL).append("- ").append(item.id());
            }
            rendered.append(NL);
        }

        return rendered.toString();
    }
}
