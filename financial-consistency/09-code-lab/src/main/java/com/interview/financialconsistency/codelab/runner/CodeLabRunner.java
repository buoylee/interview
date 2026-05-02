package com.interview.financialconsistency.codelab.runner;

import com.interview.financialconsistency.codelab.generator.ExperimentCase;
import com.interview.financialconsistency.codelab.generator.OrderHistoryGenerator;
import com.interview.financialconsistency.codelab.generator.PaymentHistoryGenerator;
import com.interview.financialconsistency.codelab.generator.TransferHistoryGenerator;
import com.interview.financialconsistency.codelab.generator.TravelHistoryGenerator;
import com.interview.financialconsistency.codelab.model.InvariantViolation;
import com.interview.financialconsistency.codelab.report.FailureReport;
import com.interview.financialconsistency.codelab.report.FailureReporter;
import com.interview.financialconsistency.codelab.verifier.CompositeVerifier;
import com.interview.financialconsistency.codelab.verifier.ExternalFactVerifier;
import com.interview.financialconsistency.codelab.verifier.LedgerConsistencyVerifier;
import com.interview.financialconsistency.codelab.verifier.ManualRepairVerifier;
import com.interview.financialconsistency.codelab.verifier.PropagationVerifier;
import com.interview.financialconsistency.codelab.verifier.StateMachineVerifier;

import java.util.ArrayList;
import java.util.List;

public final class CodeLabRunner {
    private static final String NL = "\n";

    private CodeLabRunner() {
    }

    public static void main(String[] args) {
        System.out.println(run(args));
    }

    public static String run(String[] args) {
        String[] safeArgs = args == null ? new String[0] : args;
        if (safeArgs.length == 0) {
            return runCases(cases());
        }
        if ("list".equals(safeArgs[0]) && safeArgs.length == 1) {
            return listCases();
        }
        if ("run".equals(safeArgs[0])) {
            return runCommand(safeArgs);
        }
        return usage();
    }

    private static String runCommand(String[] args) {
        if (args.length == 1) {
            return runCases(cases());
        }
        if (args.length == 3 && "--case".equals(args[1])) {
            ExperimentCase experimentCase = findCase(args[2]);
            if (experimentCase == null) {
                return "Unknown case: " + args[2] + NL + usage();
            }
            return runCases(List.of(experimentCase));
        }
        return usage();
    }

    private static String listCases() {
        StringBuilder output = new StringBuilder();
        for (ExperimentCase experimentCase : cases()) {
            output.append(experimentCase.name())
                    .append(" [")
                    .append(experimentCase.scenario())
                    .append("] expected=")
                    .append(experimentCase.expectedToPass() ? "PASS" : "FAIL")
                    .append(NL);
        }
        return output.toString();
    }

    private static String runCases(List<ExperimentCase> selectedCases) {
        CompositeVerifier verifier = new CompositeVerifier(List.of(
                new LedgerConsistencyVerifier(),
                new StateMachineVerifier(),
                new ExternalFactVerifier(),
                new PropagationVerifier(),
                new ManualRepairVerifier()));
        FailureReporter reporter = new FailureReporter();

        StringBuilder output = new StringBuilder();
        int expectedPasses = 0;
        int expectedFailures = 0;
        int actualFailures = 0;
        for (ExperimentCase experimentCase : selectedCases) {
            if (experimentCase.expectedToPass()) {
                expectedPasses++;
            } else {
                expectedFailures++;
            }

            List<InvariantViolation> violations = verifier.verify(experimentCase.history());
            if (!violations.isEmpty()) {
                actualFailures++;
                FailureReport report = new FailureReport(
                        experimentCase.name(),
                        experimentCase.scenario(),
                        "fixed:" + experimentCase.name(),
                        experimentCase.expectedToPass(),
                        violations);
                output.append(reporter.render(report));
            } else {
                output.append("Experiment: ").append(experimentCase.name()).append(NL);
                output.append("Result: PASS").append(NL);
            }
            output.append(NL);
        }

        output.append("Summary:").append(NL);
        output.append("total=").append(selectedCases.size()).append(NL);
        output.append("expectedPasses=").append(expectedPasses).append(NL);
        output.append("expectedFailures=").append(expectedFailures).append(NL);
        output.append("actualFailures=").append(actualFailures).append(NL);
        return output.toString();
    }

    private static ExperimentCase findCase(String name) {
        for (ExperimentCase experimentCase : cases()) {
            if (experimentCase.name().equals(name)) {
                return experimentCase;
            }
        }
        return null;
    }

    private static List<ExperimentCase> cases() {
        List<ExperimentCase> cases = new ArrayList<>();
        cases.addAll(new TransferHistoryGenerator().cases());
        cases.addAll(new PaymentHistoryGenerator().cases());
        cases.addAll(new OrderHistoryGenerator().cases());
        cases.addAll(new TravelHistoryGenerator().cases());
        return List.copyOf(cases);
    }

    private static String usage() {
        return "Usage:" + NL
                + "  CodeLabRunner list" + NL
                + "  CodeLabRunner run" + NL
                + "  CodeLabRunner run --case <name>" + NL;
    }
}
