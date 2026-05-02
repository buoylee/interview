package com.interview.financialconsistency.codelab;

import com.interview.financialconsistency.codelab.generator.ExperimentCase;
import com.interview.financialconsistency.codelab.generator.OrderHistoryGenerator;
import com.interview.financialconsistency.codelab.generator.PaymentHistoryGenerator;
import com.interview.financialconsistency.codelab.generator.TransferHistoryGenerator;
import com.interview.financialconsistency.codelab.generator.TravelHistoryGenerator;
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
import com.interview.financialconsistency.codelab.verifier.ExternalFactVerifier;
import com.interview.financialconsistency.codelab.verifier.LedgerConsistencyVerifier;
import com.interview.financialconsistency.codelab.verifier.ManualRepairVerifier;
import com.interview.financialconsistency.codelab.verifier.PropagationVerifier;
import com.interview.financialconsistency.codelab.verifier.CompositeVerifier;
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
        testExternalFactVerifierRejectsLateSuccessAfterLocalFailure();
        testPropagationVerifierRejectsCommittedOutboxWithoutPublication();
        testPropagationVerifierReportsCommittedOutboxMissingMessageId();
        testPropagationVerifierRejectsDuplicateMessageEffect();
        testPropagationVerifierDoesNotCollideMessageEffectKeys();
        testManualRepairVerifierRejectsRepairWithoutApprovalAndReview();
        testManualRepairVerifierRejectsDuplicateRepair();
        testManualRepairVerifierReportsRepairMissingRepairKey();
        testManualRepairVerifierReportsEvidenceMissingRepairKey();
        testGeneratorsExposeAtLeastEightCases();
        testGeneratedFailureCasesProduceViolations();
        testGeneratedPassingCasesProduceNoViolations();
        testOrderPaidInventoryFailedCaseIncludesInventoryFailure();
        testRunnerListsCases();
        testRunnerRunsOneCase();
        testRunnerRunsAllCases();
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

    private static void testExternalFactVerifierRejectsLateSuccessAfterLocalFailure() {
        History history = History.of(
                fact("state-1", FactType.LOCAL_STATE, "P1", "state", "FAILED", "entity", "payment:P1"),
                fact("external-1", FactType.EXTERNAL_RESULT, "P1", "result", "SUCCEEDED", "provider", "card-network"));

        List<InvariantViolation> violations = new ExternalFactVerifier().verify(history);

        assertAnyViolation(violations, "EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE",
                "external success after local failure should violate external fact consistency");
    }

    private static void testPropagationVerifierRejectsCommittedOutboxWithoutPublication() {
        History history = History.of(
                fact("outbox-1", FactType.OUTBOX_RECORD, "T1", "messageId", "M1", "status", "COMMITTED"));

        List<InvariantViolation> violations = new PropagationVerifier().verify(history);

        assertAnyViolation(violations, "OUTBOX_COMMITTED_NOT_PUBLISHED",
                "committed outbox record should require publication");
    }

    private static void testPropagationVerifierReportsCommittedOutboxMissingMessageId() {
        History history = History.of(
                fact("outbox-1", FactType.OUTBOX_RECORD, "T1", "status", "COMMITTED"));

        List<InvariantViolation> violations = new PropagationVerifier().verify(history);

        assertAnyViolation(violations, "OUTBOX_MESSAGE_ID_REQUIRED",
                "committed outbox record should require messageId");
    }

    private static void testPropagationVerifierRejectsDuplicateMessageEffect() {
        History history = History.of(
                fact("effect-1", FactType.BUSINESS_EFFECT, "T1", "messageId", "M1", "effectKey", "transfer:T1:debit"),
                fact("effect-2", FactType.BUSINESS_EFFECT, "T1", "messageId", "M1", "effectKey", "transfer:T1:debit"));

        List<InvariantViolation> violations = new PropagationVerifier().verify(history);

        assertAnyViolation(violations, "MESSAGE_EFFECT_IDEMPOTENT",
                "duplicate message effect should violate message idempotency");
    }

    private static void testPropagationVerifierDoesNotCollideMessageEffectKeys() {
        History history = History.of(
                fact("effect-1", FactType.BUSINESS_EFFECT, "T1", "messageId", "A:B", "effectKey", "C"),
                fact("effect-2", FactType.BUSINESS_EFFECT, "T1", "messageId", "A", "effectKey", "B:C"));

        List<InvariantViolation> violations = new PropagationVerifier().verify(history);

        assertNoViolation(violations, "MESSAGE_EFFECT_IDEMPOTENT",
                "distinct message/effect pairs should not collide");
    }

    private static void testManualRepairVerifierRejectsRepairWithoutApprovalAndReview() {
        History history = History.of(
                fact("repair-1", FactType.MANUAL_REPAIR, "R1", "repairKey", "R1"));

        List<InvariantViolation> violations = new ManualRepairVerifier().verify(history);

        assertAnyViolation(violations, "MANUAL_REPAIR_REQUIRES_APPROVAL_AND_REVIEW",
                "manual repair should require approval and approved review");
    }

    private static void testManualRepairVerifierRejectsDuplicateRepair() {
        History history = History.of(
                fact("repair-1", FactType.MANUAL_REPAIR, "R1", "repairKey", "R1"),
                fact("repair-2", FactType.MANUAL_REPAIR, "R1", "repairKey", "R1"));

        List<InvariantViolation> violations = new ManualRepairVerifier().verify(history);

        assertAnyViolation(violations, "MANUAL_REPAIR_IDEMPOTENT",
                "duplicate manual repair should violate repair idempotency");
    }

    private static void testManualRepairVerifierReportsRepairMissingRepairKey() {
        History history = History.of(
                fact("repair-1", FactType.MANUAL_REPAIR, "R1"));

        List<InvariantViolation> violations = new ManualRepairVerifier().verify(history);

        assertAnyViolation(violations, "MANUAL_REPAIR_KEY_REQUIRED",
                "manual repair should require repairKey");
    }

    private static void testManualRepairVerifierReportsEvidenceMissingRepairKey() {
        History history = History.of(
                fact("approval-1", FactType.MANUAL_APPROVAL, "R1"),
                fact("review-1", FactType.MANUAL_REVIEW, "R1", "result", "APPROVED"));

        List<InvariantViolation> violations = new ManualRepairVerifier().verify(history);

        assertAnyViolation(violations, "MANUAL_REPAIR_EVIDENCE_KEY_REQUIRED",
                "manual repair evidence should require repairKey");
    }

    private static void testGeneratorsExposeAtLeastEightCases() {
        List<ExperimentCase> cases = generatedCases();
        Set<String> names = new LinkedHashSet<>();
        for (ExperimentCase experimentCase : cases) {
            names.add(experimentCase.name());
        }

        assertTrue(cases.size() >= 8, "generators should expose at least eight experiment cases");
        assertTrue(names.contains("transfer-duplicate-request"), "transfer duplicate case should exist");
        assertTrue(names.contains("transfer-unbalanced-ledger"), "transfer unbalanced case should exist");
        assertTrue(names.contains("payment-timeout-late-success"), "payment late success case should exist");
        assertTrue(names.contains("outbox-committed-not-published"), "outbox unpublished case should exist");
        assertTrue(names.contains("consumer-duplicate-message-effect"), "consumer duplicate case should exist");
        assertTrue(names.contains("tcc-cancel-confirm-race"), "tcc race case should exist");
        assertTrue(names.contains("travel-flight-success-hotel-failed"), "travel failure case should exist");
        assertTrue(names.contains("manual-repair-duplicate-submit"), "manual repair duplicate case should exist");
    }

    private static void testGeneratedFailureCasesProduceViolations() {
        CompositeVerifier verifier = compositeVerifier();
        Map<String, Set<String>> expectedInvariants = expectedFailureInvariantsByCaseName();
        for (ExperimentCase experimentCase : generatedCases()) {
            if (experimentCase.expectedToPass()) {
                continue;
            }
            List<InvariantViolation> violations = verifier.verify(experimentCase.history());
            Set<String> actualInvariants = new LinkedHashSet<>();
            for (InvariantViolation violation : violations) {
                actualInvariants.add(violation.invariant());
            }
            Set<String> expectedInvariantsForCase = expectedInvariants.get(experimentCase.name());
            assertTrue(expectedInvariantsForCase != null,
                    "failing generator case should declare expected invariants name=" + experimentCase.name());
            assertEquals(expectedInvariantsForCase, actualInvariants,
                    "failing generator case should produce intended invariants name=" + experimentCase.name()
                            + " expected=" + expectedInvariantsForCase + " actual=" + actualInvariants);
        }
    }

    private static void testGeneratedPassingCasesProduceNoViolations() {
        CompositeVerifier verifier = compositeVerifier();
        for (ExperimentCase experimentCase : generatedCases()) {
            if (!experimentCase.expectedToPass()) {
                continue;
            }
            List<InvariantViolation> violations = verifier.verify(experimentCase.history());
            assertEquals(List.of(), violations,
                    "passing generator case should produce no violations name=" + experimentCase.name());
        }
    }

    private static void testOrderPaidInventoryFailedCaseIncludesInventoryFailure() {
        ExperimentCase experimentCase = findGeneratedCase("order-paid-inventory-failed");
        for (Fact fact : experimentCase.history().facts(FactType.LOCAL_STATE)) {
            if ("inventory:I3".equals(fact.attr("entity")) && "FAILED".equals(fact.attr("state"))) {
                return;
            }
        }
        throw new AssertionError("order-paid-inventory-failed should include inventory:I3 FAILED local state");
    }

    private static void testRunnerListsCases() {
        String output = CodeLabRunner.run(new String[]{"list"});

        assertContains(output, "transfer-duplicate-request", "runner list should include transfer duplicate case");
        assertContains(output, "manual-repair-duplicate-submit", "runner list should include manual repair duplicate case");
    }

    private static void testRunnerRunsOneCase() {
        String output = CodeLabRunner.run(new String[]{"run", "--case", "payment-timeout-late-success"});

        assertContains(output, "Experiment: payment-timeout-late-success", "runner should render selected experiment");
        assertContains(output, "Result: FAILED", "runner should report selected failing case");
        assertContains(output, "ExternalFactVerifier", "runner should include verifier details for selected failing case");
    }

    private static void testRunnerRunsAllCases() {
        String output = CodeLabRunner.run(new String[]{"run"});

        assertContains(output, "Summary:", "runner should print summary when running all cases");
        assertContains(output, "expectedFailures=9", "runner summary should count expected failures");
        assertContains(output, "actualFailures=9", "runner summary should count actual failures");
    }

    private static Map<String, Set<String>> expectedFailureInvariantsByCaseName() {
        Map<String, Set<String>> expected = new LinkedHashMap<>();
        expected.put("transfer-duplicate-request", Set.of("BUSINESS_EFFECT_IDEMPOTENT"));
        expected.put("transfer-unbalanced-ledger", Set.of("LEDGER_BALANCED"));
        expected.put("payment-timeout-late-success", Set.of("EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE"));
        expected.put("outbox-committed-not-published", Set.of("OUTBOX_COMMITTED_NOT_PUBLISHED"));
        expected.put("consumer-duplicate-message-effect", Set.of("MESSAGE_EFFECT_IDEMPOTENT"));
        expected.put("order-paid-inventory-failed", Set.of("EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE"));
        expected.put("tcc-cancel-confirm-race", Set.of("STATE_MACHINE_SINGLE_TERMINAL"));
        expected.put("travel-flight-success-hotel-failed", Set.of("EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE"));
        expected.put("manual-repair-duplicate-submit", Set.of("MANUAL_REPAIR_IDEMPOTENT"));
        return Map.copyOf(expected);
    }

    private static ExperimentCase findGeneratedCase(String name) {
        for (ExperimentCase experimentCase : generatedCases()) {
            if (experimentCase.name().equals(name)) {
                return experimentCase;
            }
        }
        throw new AssertionError("generated case should exist name=" + name);
    }

    private static List<ExperimentCase> generatedCases() {
        List<ExperimentCase> cases = new ArrayList<>();
        cases.addAll(new TransferHistoryGenerator().cases());
        cases.addAll(new PaymentHistoryGenerator().cases());
        cases.addAll(new OrderHistoryGenerator().cases());
        cases.addAll(new TravelHistoryGenerator().cases());
        return List.copyOf(cases);
    }

    private static CompositeVerifier compositeVerifier() {
        return new CompositeVerifier(List.of(
                new LedgerConsistencyVerifier(),
                new StateMachineVerifier(),
                new ExternalFactVerifier(),
                new PropagationVerifier(),
                new ManualRepairVerifier()));
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

    private static void assertNoViolation(List<InvariantViolation> violations, String invariant, String message) {
        for (InvariantViolation violation : violations) {
            if (violation.invariant().equals(invariant)) {
                throw new AssertionError(message + " invariant=" + invariant + " violations=" + violations);
            }
        }
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
