package com.interview.financialconsistency.codelab.report;

import com.interview.financialconsistency.codelab.model.HistoryItem;
import com.interview.financialconsistency.codelab.model.InvariantViolation;

public final class FailureReporter {
    private static final String NL = "\n";

    public String render(FailureReport report) {
        StringBuilder rendered = new StringBuilder();
        appendLine(rendered, "Experiment: " + report.experimentName());
        appendLine(rendered, "Scenario: " + report.scenario());
        appendLine(rendered, "Seed: " + report.seed());
        appendLine(rendered, "Expected to pass: " + report.expectedToPass());
        appendLine(rendered, "Result: " + (report.violations().isEmpty() ? "PASS" : "FAILED"));

        for (InvariantViolation violation : report.violations()) {
            rendered.append(NL);
            appendLine(rendered, "Violated invariant: " + violation.invariant());
            appendLine(rendered, "Reason: " + violation.reason());
            appendLine(rendered, "Verifier: " + violation.verifier());
            appendLine(rendered, "Boundary: " + violation.boundary());
            appendLine(rendered, "Related items: " + String.join(", ", violation.relatedItemIds()));
            rendered.append("Reduced history:");
            for (HistoryItem item : violation.reducedHistory().items()) {
                rendered.append(NL).append("- ").append(item.id());
            }
            rendered.append(NL);
        }

        return rendered.toString();
    }

    private void appendLine(StringBuilder rendered, String line) {
        rendered.append(line).append(NL);
    }
}
