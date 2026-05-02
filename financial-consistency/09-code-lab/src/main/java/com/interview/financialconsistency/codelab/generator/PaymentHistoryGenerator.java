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

public final class PaymentHistoryGenerator {
    public List<ExperimentCase> cases() {
        return List.of(
                new ExperimentCase(
                        "payment-timeout-unknown-then-success",
                        "payment timeout is held as unknown until the external success is reconciled locally",
                        History.of(
                                command("payment-unknown-command", "ChargePayment", "P0"),
                                fact("payment-unknown-state", FactType.LOCAL_STATE, "P0",
                                        "entity", "payment:P0", "state", "UNKNOWN"),
                                fact("payment-unknown-external-success", FactType.EXTERNAL_RESULT, "P0",
                                        "provider", "card-network", "result", "SUCCEEDED"),
                                fact("payment-unknown-local-success", FactType.LOCAL_STATE, "P0",
                                        "entity", "payment:P0", "state", "SUCCEEDED")),
                        true),
                new ExperimentCase(
                        "payment-timeout-late-success",
                        "payment is marked failed before a late external success arrives",
                        History.of(
                                command("payment-late-command", "ChargePayment", "P1"),
                                fact("payment-late-local-failed", FactType.LOCAL_STATE, "P1",
                                        "entity", "payment:P1", "state", "FAILED"),
                                fact("payment-late-external-success", FactType.EXTERNAL_RESULT, "P1",
                                        "provider", "card-network", "result", "SUCCEEDED")),
                        false),
                new ExperimentCase(
                        "outbox-committed-not-published",
                        "committed outbox message is never published",
                        History.of(
                                fact("outbox-local-success", FactType.LOCAL_STATE, "P-outbox",
                                        "entity", "payment:P-outbox", "state", "SUCCEEDED"),
                                fact("outbox-record", FactType.OUTBOX_RECORD, "P-outbox",
                                        "messageId", "M1", "status", "COMMITTED")),
                        false),
                new ExperimentCase(
                        "consumer-duplicate-message-effect",
                        "consumer applies multiple business effects from the same delivered message",
                        History.of(
                                fact("consumer-effect-1", FactType.BUSINESS_EFFECT, "P2",
                                        "messageId", "M2", "effectKey", "payment:P2:settled:attempt-1"),
                                fact("consumer-effect-2", FactType.BUSINESS_EFFECT, "P2",
                                        "messageId", "M2", "effectKey", "payment:P2:settled:attempt-2")),
                        false));
    }

    private static Command command(String id, String name, String businessKey, String... attrs) {
        return new Command(id, name, businessKey, Instant.EPOCH, attrs(attrs));
    }

    private static Fact fact(String id, FactType type, String businessKey, String... attrs) {
        return new Fact(id, type, businessKey, Instant.EPOCH, BigDecimal.ZERO, attrs(attrs));
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
