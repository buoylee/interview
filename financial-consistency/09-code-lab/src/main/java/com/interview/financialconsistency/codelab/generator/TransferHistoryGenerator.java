package com.interview.financialconsistency.codelab.generator;

import com.interview.financialconsistency.codelab.model.Command;
import com.interview.financialconsistency.codelab.model.Fact;
import com.interview.financialconsistency.codelab.model.FactType;
import com.interview.financialconsistency.codelab.model.History;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TransferHistoryGenerator {
    public List<ExperimentCase> cases() {
        return List.of(
                new ExperimentCase(
                        "transfer-normal-balanced",
                        "idempotent transfer with balanced debit and credit ledger postings",
                        History.of(
                                command("transfer-normal-command", "CreateTransfer", "T0"),
                                fact("transfer-normal-idempotency", FactType.IDEMPOTENCY_RECORD, "T0",
                                        "requestId", "REQ-T0", "entity", "transfer:T0"),
                                moneyFact("transfer-normal-debit", "T0", new BigDecimal("100.00"),
                                        "side", "DEBIT", "account", "source:A1"),
                                moneyFact("transfer-normal-credit", "T0", new BigDecimal("100.00"),
                                        "side", "CREDIT", "account", "destination:A2"),
                                fact("transfer-normal-state", FactType.LOCAL_STATE, "T0",
                                        "entity", "transfer:T0", "state", "SUCCEEDED")),
                        true),
                new ExperimentCase(
                        "transfer-duplicate-request",
                        "duplicate transfer request applies the same debit effect twice",
                        History.of(
                                fact("transfer-duplicate-effect-1", FactType.BUSINESS_EFFECT, "T1",
                                        "effectKey", "transfer:T1:debit"),
                                fact("transfer-duplicate-effect-2", FactType.BUSINESS_EFFECT, "T1",
                                        "effectKey", "transfer:T1:debit")),
                        false),
                new ExperimentCase(
                        "transfer-unbalanced-ledger",
                        "transfer records a debit without the matching credit",
                        History.of(
                                moneyFact("transfer-unbalanced-debit", "T2", new BigDecimal("100.00"),
                                        "side", "DEBIT", "account", "source:A1")),
                        false));
    }

    private static Command command(String id, String name, String businessKey, String... attrs) {
        return new Command(id, name, businessKey, Instant.EPOCH, attrs(attrs));
    }

    private static Fact fact(String id, FactType type, String businessKey, String... attrs) {
        return new Fact(id, type, businessKey, Instant.EPOCH, BigDecimal.ZERO, attrs(attrs));
    }

    private static Fact moneyFact(String id, String businessKey, BigDecimal amount, String... attrs) {
        return new Fact(id, FactType.LEDGER_POSTING, businessKey, Instant.EPOCH, amount, attrs(attrs));
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
}
