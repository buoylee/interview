package com.interview.financialconsistency.codelab.generator;

import com.interview.financialconsistency.codelab.model.Fact;
import com.interview.financialconsistency.codelab.model.FactType;
import com.interview.financialconsistency.codelab.model.History;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class OrderHistoryGenerator {
    public List<ExperimentCase> cases() {
        return List.of(
                new ExperimentCase(
                        "order-paid-inventory-failed",
                        "payment succeeds externally while inventory records a local failure",
                        History.of(
                                fact("order-payment-success", FactType.LOCAL_STATE, "P3",
                                        "entity", "payment:P3", "state", "SUCCEEDED"),
                                fact("order-external-success", FactType.EXTERNAL_RESULT, "P3",
                                        "provider", "payment-gateway", "result", "SUCCEEDED"),
                                fact("order-inventory-failed", FactType.LOCAL_STATE, "P3",
                                        "entity", "inventory:I3", "state", "FAILED")),
                        false),
                new ExperimentCase(
                        "tcc-cancel-confirm-race",
                        "TCC participant records both confirm and cancel terminal outcomes",
                        History.of(
                                fact("tcc-confirmed", FactType.LOCAL_STATE, "TCC1",
                                        "entity", "tcc:TCC1", "state", "SUCCEEDED"),
                                fact("tcc-cancelled", FactType.LOCAL_STATE, "TCC1",
                                        "entity", "tcc:TCC1", "state", "CANCELLED")),
                        false));
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
