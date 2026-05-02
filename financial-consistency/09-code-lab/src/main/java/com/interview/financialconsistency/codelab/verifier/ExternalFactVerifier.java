package com.interview.financialconsistency.codelab.verifier;

import com.interview.financialconsistency.codelab.model.Fact;
import com.interview.financialconsistency.codelab.model.FactType;
import com.interview.financialconsistency.codelab.model.History;
import com.interview.financialconsistency.codelab.model.InvariantViolation;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;

public final class ExternalFactVerifier implements ConsistencyVerifier {
    @Override
    public String name() {
        return "ExternalFactVerifier";
    }

    @Override
    public List<InvariantViolation> verify(History history) {
        Map<String, List<Fact>> successesByBusinessKey = new LinkedHashMap<>();
        Map<String, List<Fact>> failuresByBusinessKey = new LinkedHashMap<>();

        for (Fact fact : history.facts()) {
            if (isExternalSuccess(fact)) {
                successesByBusinessKey.computeIfAbsent(fact.businessKey(), ignored -> new ArrayList<>()).add(fact);
            } else if (isLocalFailure(fact)) {
                failuresByBusinessKey.computeIfAbsent(fact.businessKey(), ignored -> new ArrayList<>()).add(fact);
            }
        }

        List<InvariantViolation> violations = new ArrayList<>();
        for (Map.Entry<String, List<Fact>> entry : successesByBusinessKey.entrySet()) {
            List<Fact> failures = failuresByBusinessKey.get(entry.getKey());
            if (failures == null || failures.isEmpty()) {
                continue;
            }

            List<String> relatedIds = new ArrayList<>();
            relatedIds.addAll(ids(entry.getValue()));
            relatedIds.addAll(ids(failures));
            violations.add(new InvariantViolation(
                    "EXTERNAL_SUCCESS_NOT_EXPLAINED_BY_LOCAL_FAILURE",
                    "businessKey=" + entry.getKey() + " has external success and local FAILED state",
                    name(),
                    "external-fact",
                    relatedIds,
                    history.reduceTo(new LinkedHashSet<>(relatedIds))));
        }
        return List.copyOf(violations);
    }

    private boolean isExternalSuccess(Fact fact) {
        return (fact.type() == FactType.EXTERNAL_RESULT || fact.type() == FactType.SUPPLIER_RESULT)
                && "SUCCEEDED".equals(fact.attr("result"));
    }

    private boolean isLocalFailure(Fact fact) {
        return fact.type() == FactType.LOCAL_STATE && "FAILED".equals(fact.attr("state"));
    }

    private List<String> ids(List<Fact> facts) {
        List<String> ids = new ArrayList<>();
        for (Fact fact : facts) {
            ids.add(fact.id());
        }
        return List.copyOf(ids);
    }
}
