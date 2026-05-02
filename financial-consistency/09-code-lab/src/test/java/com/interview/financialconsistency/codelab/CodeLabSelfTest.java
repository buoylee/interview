package com.interview.financialconsistency.codelab;

import com.interview.financialconsistency.codelab.model.Command;
import com.interview.financialconsistency.codelab.model.Event;
import com.interview.financialconsistency.codelab.model.Fact;
import com.interview.financialconsistency.codelab.model.FactType;
import com.interview.financialconsistency.codelab.model.History;
import com.interview.financialconsistency.codelab.runner.CodeLabRunner;

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
}
