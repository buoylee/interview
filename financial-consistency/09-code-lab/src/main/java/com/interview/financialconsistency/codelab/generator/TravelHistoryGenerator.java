package com.interview.financialconsistency.codelab.generator;

import com.interview.financialconsistency.codelab.model.Fact;
import com.interview.financialconsistency.codelab.model.FactType;
import com.interview.financialconsistency.codelab.model.History;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public final class TravelHistoryGenerator {
    public List<ExperimentCase> cases() {
        return List.of(
                new ExperimentCase(
                        "travel-flight-success-hotel-failed",
                        "flight supplier succeeds but the trip is failed without repair",
                        History.of(
                                fact("travel-flight-success", FactType.SUPPLIER_RESULT, "TR1",
                                        "component", "flight", "supplier", "airline", "result", "SUCCEEDED"),
                                fact("travel-trip-failed", FactType.LOCAL_STATE, "TR1",
                                        "entity", "trip:TR1", "state", "FAILED")),
                        false),
                new ExperimentCase(
                        "travel-manual-repair-reviewed",
                        "supplier success is followed by approved manual repair evidence",
                        History.of(
                                fact("travel-repaired-supplier-success", FactType.SUPPLIER_RESULT, "TR2",
                                        "component", "flight", "supplier", "airline", "result", "SUCCEEDED"),
                                fact("travel-repair-approval", FactType.MANUAL_APPROVAL, "TR2",
                                        "repairKey", "R-TR2", "approver", "ops-lead"),
                                fact("travel-repair", FactType.MANUAL_REPAIR, "TR2",
                                        "repairKey", "R-TR2", "action", "mark-trip-reconciled"),
                                fact("travel-repair-review", FactType.MANUAL_REVIEW, "TR2",
                                        "repairKey", "R-TR2", "result", "APPROVED")),
                        true),
                new ExperimentCase(
                        "manual-repair-duplicate-submit",
                        "approved manual repair is submitted twice with the same repair key",
                        History.of(
                                fact("duplicate-repair-approval", FactType.MANUAL_APPROVAL, "R-DUP",
                                        "repairKey", "R-DUP"),
                                fact("duplicate-repair-1", FactType.MANUAL_REPAIR, "R-DUP",
                                        "repairKey", "R-DUP"),
                                fact("duplicate-repair-2", FactType.MANUAL_REPAIR, "R-DUP",
                                        "repairKey", "R-DUP"),
                                fact("duplicate-repair-review", FactType.MANUAL_REVIEW, "R-DUP",
                                        "repairKey", "R-DUP", "result", "APPROVED")),
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
