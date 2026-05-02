package com.interview.financialconsistency.codelab;

import com.interview.financialconsistency.codelab.model.Command;
import com.interview.financialconsistency.codelab.model.Event;
import com.interview.financialconsistency.codelab.model.Fact;
import com.interview.financialconsistency.codelab.model.FactType;
import com.interview.financialconsistency.codelab.model.History;
import com.interview.financialconsistency.codelab.model.HistoryItem;
import com.interview.financialconsistency.codelab.model.InvariantViolation;
import com.interview.financialconsistency.codelab.runner.CodeLabRunner;
import com.interview.financialconsistency.codelab.report.FailureReport;
import com.interview.financialconsistency.codelab.report.FailureReporter;
import com.interview.financialconsistency.codelab.verifier.LedgerConsistencyVerifier;
import com.interview.financialconsistency.codelab.verifier.StateMachineVerifier;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.*;

public final class CodeLabSelfTest {
    private CodeLabSelfTest() {
    }

    public static void main(String[] args) {
        CodeLabRunner.main(new String[0]);
        testHistoryFiltersFacts();
        testReducedHistoryKeepsSelectedItems();
        testFactAttributesAreDefensiveCopies();
        testModelRejectsNullRequiredFields();
        testLedgerVerifierRejectsUnbalancedTransfer();
        testLedgerVerifierRejectsDuplicateBusinessEffect();
        testStateMachineVerifierRejectsDualTerminalStates();
        testFailureReporterPrintsViolationDetails();
        testLedgerVerifierReportsMissingSide();
        testLedgerVerifierReportsUnknownSide();
        testStateMachineVerifierReportsMissingEntity();
        testFailureReporterUsesDeterministicNewlines();
        System.out.println("SELF_TEST_PASS");
    }

    private static void testHistoryFiltersFacts() {
        History history = History.of(
                command("cmd-1", "CreateTransfer", "T1"),
                fact("fact-1", FactType.LEDGER_POSTING, "T1", "side", "DEBIT", "account", "A"),
                fact("fact-2", FactType.LOCAL_STATE, "T1", "state", "SUCCEEDED", "entity", "transfer:T1"));

        assertEquals(2, history.facts().size(), "history should expose two facts");
        assertEquals(1, history.facts(FactType.LEDGER_POSTING).size(), "history should filter ledger facts");
    }

    private static void testReducedHistoryKeepsSelectedItems() {
        History history = History.of(
                command("cmd-1", "CreateTransfer", "T1"),
                fact("fact-1", FactType.LEDGER_POSTING, "T1", "side", "DEBIT"),
                fact("fact-2", FactType.LEDGER_POSTING, "T1", "side", "CREDIT"));

        History reduced = history.reduceTo(Set.of("cmd-1", "fact-2"));
        assertEquals(2, reduced.items().size(), "reduced history should keep selected items");
        assertEquals("fact-2", reduced.items().get(1).id(), "reduced history should preserve original order");
    }

    private static void testFactAttributesAreDefensiveCopies() {
        Map<String, String> attributes = new LinkedHashMap<>();
        attributes.put("side", "DEBIT");
        Fact fact = new Fact("fact-1", FactType.LEDGER_POSTING, "T1", Instant.EPOCH, BigDecimal.TEN, attributes);
        attributes.put("side", "CREDIT");
        assertEquals("DEBIT", fact.requireAttr("side"), "fact should copy attributes at construction");
    }

    private static void testModelRejectsNullRequiredFields() {
        assertThrows(NullPointerException.class,
                () -> new Command(null, "CreateTransfer", "T1", Instant.EPOCH, Map.of()),
                "command should reject null id");
        assertThrows(NullPointerException.class,
                () -> new Fact("fact-1", null, "T1", Instant.EPOCH, BigDecimal.ZERO, Map.of()),
                "fact should reject null type");
        assertThrows(NullPointerException.class,
                () -> new Fact("fact-1", FactType.LEDGER_POSTING, null, Instant.EPOCH, BigDecimal.ZERO, Map.of()),
                "fact should reject null business key");
        assertThrows(NullPointerException.class,
                () -> History.of((HistoryItem) null),
                "history should reject null items");
    }

    private static void testLedgerVerifierRejectsUnbalancedTransfer() {
        History history = History.of(
                moneyFact("posting-1", FactType.LEDGER_POSTING, "T1", new BigDecimal("100.00"), "side", "DEBIT"));

        List<InvariantViolation> violations = new LedgerConsistencyVerifier().verify(history);

        assertEquals(1, violations.size(), "unbalanced transfer should create one violation");
        assertEquals("LEDGER_BALANCED", violations.get(0).invariant(), "violation should identify ledger balance invariant");
    }

    private static void testLedgerVerifierRejectsDuplicateBusinessEffect() {
        History history = History.of(
                fact("effect-1", FactType.BUSINESS_EFFECT, "T1", "effectKey", "transfer:T1:debit"),
                fact("effect-2", FactType.BUSINESS_EFFECT, "T1", "effectKey", "transfer:T1:debit"));

        List<InvariantViolation> violations = new LedgerConsistencyVerifier().verify(history);

        assertAnyViolation(violations, "BUSINESS_EFFECT_IDEMPOTENT", "duplicate business effect should violate idempotency");
    }

    private static void testStateMachineVerifierRejectsDualTerminalStates() {
        History history = History.of(
                fact("state-1", FactType.LOCAL_STATE, "P1", "entity", "payment:P1", "state", "SUCCEEDED"),
                fact("state-2", FactType.LOCAL_STATE, "P1", "entity", "payment:P1", "state", "FAILED"));

        List<InvariantViolation> violations = new StateMachineVerifier().verify(history);

        assertEquals(1, violations.size(), "dual terminal states should create one violation");
        assertEquals("STATE_MACHINE_SINGLE_TERMINAL", violations.get(0).invariant(), "violation should identify state machine invariant");
    }

    private static void testFailureReporterPrintsViolationDetails() {
        History reducedHistory = History.of(
                fact("posting-1", FactType.LEDGER_POSTING, "T1", "side", "DEBIT"));
        InvariantViolation violation = new InvariantViolation(
                "LEDGER_BALANCED",
                "ledger postings do not balance",
                "LedgerConsistencyVerifier",
                "ledger",
                List.of("posting-1"),
                reducedHistory);
        FailureReport report = new FailureReport("core consistency", "unbalanced transfer", "seed-1", false, List.of(violation));

        String rendered = new FailureReporter().render(report);

        assertContains(rendered, "Violated invariant:", "report should include invariant heading");
        assertContains(rendered, "LedgerConsistencyVerifier", "report should include verifier name");
        assertContains(rendered, "posting-1", "report should include related fact id");
    }

    private static void testLedgerVerifierReportsMissingSide() {
        History history = History.of(
                moneyFact("posting-1", FactType.LEDGER_POSTING, "T1", new BigDecimal("100.00")));

        List<InvariantViolation> violations = new LedgerConsistencyVerifier().verify(history);

        assertEquals(1, violations.size(), "missing ledger side should create one violation");
        assertEquals("LEDGER_POSTING_SIDE_REQUIRED", violations.get(0).invariant(), "violation should identify missing side");
    }

    private static void testLedgerVerifierReportsUnknownSide() {
        History history = History.of(
                moneyFact("posting-1", FactType.LEDGER_POSTING, "T1", new BigDecimal("100.00"), "side", "HOLD"));

        List<InvariantViolation> violations = new LedgerConsistencyVerifier().verify(history);

        assertEquals(1, violations.size(), "unknown ledger side should create one violation");
        assertEquals("LEDGER_POSTING_SIDE_KNOWN", violations.get(0).invariant(), "violation should identify unknown side");
    }

    private static void testStateMachineVerifierReportsMissingEntity() {
        History history = History.of(
                fact("state-1", FactType.LOCAL_STATE, "P1", "state", "SUCCEEDED"));

        List<InvariantViolation> violations = new StateMachineVerifier().verify(history);

        assertEquals(1, violations.size(), "missing state entity should create one violation");
        assertEquals("LOCAL_STATE_ENTITY_REQUIRED", violations.get(0).invariant(), "violation should identify missing entity");
    }

    private static void testFailureReporterUsesDeterministicNewlines() {
        History reducedHistory = History.of(
                fact("posting-1", FactType.LEDGER_POSTING, "T1", "side", "DEBIT"));
        InvariantViolation violation = new InvariantViolation(
                "LEDGER_BALANCED",
                "ledger postings do not balance",
                "LedgerConsistencyVerifier",
                "ledger",
                List.of("posting-1"),
                reducedHistory);
        FailureReport report = new FailureReport("core consistency", "unbalanced transfer", "seed-1", false, List.of(violation));

        String expected = ""
                + "Experiment: core consistency\n"
                + "Scenario: unbalanced transfer\n"
                + "Seed: seed-1\n"
                + "Expected to pass: false\n"
                + "Result: FAILED\n"
                + "\n"
                + "Violated invariant: LEDGER_BALANCED\n"
                + "Reason: ledger postings do not balance\n"
                + "Verifier: LedgerConsistencyVerifier\n"
                + "Boundary: ledger\n"
                + "Related items: posting-1\n"
                + "Reduced history:\n"
                + "- posting-1\n";

        assertEquals(expected, new FailureReporter().render(report), "report should use deterministic newlines");
    }

    private static Command command(String id, String name, String businessKey, String... attrs) {
        return new Command(id, name, businessKey, Instant.EPOCH, attrs(attrs));
    }

    private static Event event(String id, String name, String businessKey, String... attrs) {
        return new Event(id, name, businessKey, Instant.EPOCH, attrs(attrs));
    }

    private static Fact fact(String id, FactType type, String businessKey, String... attrs) {
        return new Fact(id, type, businessKey, Instant.EPOCH, BigDecimal.ZERO, attrs(attrs));
    }

    private static Fact moneyFact(String id, FactType type, String businessKey, BigDecimal amount, String... attrs) {
        return new Fact(id, type, businessKey, Instant.EPOCH, amount, attrs(attrs));
    }

    private static Map<String, String> attrs(String... values) {
        if (values.length % 2 != 0) {
            throw new IllegalArgumentException("attributes must be key/value pairs");
        }
        Map<String, String> result = new LinkedHashMap<>();
        for (int i = 0; i < values.length; i += 2) {
            result.put(values[i], values[i + 1]);
        }
        return result;
    }

    private static void assertEquals(Object expected, Object actual, String message) {
        if (!Objects.equals(expected, actual)) {
            throw new AssertionError(message + " expected=" + expected + " actual=" + actual);
        }
    }

    private static void assertTrue(boolean condition, String message) {
        if (!condition) {
            throw new AssertionError(message);
        }
    }

    private static void assertContains(String text, String expected, String message) {
        if (!text.contains(expected)) {
            throw new AssertionError(message + " expected to contain=" + expected + " actual=" + text);
        }
    }

    private static void assertAnyViolation(List<InvariantViolation> violations, String invariant, String message) {
        for (InvariantViolation violation : violations) {
            if (violation.invariant().equals(invariant)) {
                return;
            }
        }
        throw new AssertionError(message + " invariant=" + invariant + " violations=" + violations);
    }

    private static void assertThrows(Class<? extends Throwable> expectedType, Runnable action, String message) {
        try {
            action.run();
        } catch (Throwable actual) {
            if (expectedType.isInstance(actual)) {
                return;
            }
            throw new AssertionError(message + " expected=" + expectedType.getSimpleName() + " actual=" + actual.getClass().getSimpleName(), actual);
        }
        throw new AssertionError(message + " expected=" + expectedType.getSimpleName());
    }
}
