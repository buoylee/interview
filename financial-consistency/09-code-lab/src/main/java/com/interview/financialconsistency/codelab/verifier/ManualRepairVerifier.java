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
import java.util.Set;

public final class ManualRepairVerifier implements ConsistencyVerifier {
    @Override
    public String name() {
        return "ManualRepairVerifier";
    }

    @Override
    public List<InvariantViolation> verify(History history) {
        Map<String, List<Fact>> repairsByKey = new LinkedHashMap<>();
        Map<String, List<Fact>> approvalsByKey = new LinkedHashMap<>();
        Map<String, List<Fact>> reviewsByKey = new LinkedHashMap<>();
        Map<String, List<Fact>> approvedReviewsByKey = new LinkedHashMap<>();
        List<InvariantViolation> violations = new ArrayList<>();

        for (Fact fact : history.facts()) {
            if (!isManualRepairFact(fact)) {
                continue;
            }

            String repairKey = fact.attr("repairKey");
            if (repairKey == null || repairKey.isBlank()) {
                if (fact.type() == FactType.MANUAL_REPAIR) {
                    violations.add(new InvariantViolation(
                            "MANUAL_REPAIR_KEY_REQUIRED",
                            "manual repair is missing repairKey",
                            name(),
                            "manual-repair",
                            List.of(fact.id()),
                            history.reduceTo(Set.of(fact.id()))));
                } else {
                    violations.add(new InvariantViolation(
                            "MANUAL_REPAIR_EVIDENCE_KEY_REQUIRED",
                            "manual repair evidence is missing repairKey",
                            name(),
                            "manual-repair",
                            List.of(fact.id()),
                            history.reduceTo(Set.of(fact.id()))));
                }
                continue;
            }

            if (fact.type() == FactType.MANUAL_REPAIR) {
                repairsByKey.computeIfAbsent(repairKey, ignored -> new ArrayList<>()).add(fact);
            } else if (fact.type() == FactType.MANUAL_APPROVAL) {
                approvalsByKey.computeIfAbsent(repairKey, ignored -> new ArrayList<>()).add(fact);
            } else if (fact.type() == FactType.MANUAL_REVIEW) {
                reviewsByKey.computeIfAbsent(repairKey, ignored -> new ArrayList<>()).add(fact);
                if ("APPROVED".equals(fact.attr("result"))) {
                    approvedReviewsByKey.computeIfAbsent(repairKey, ignored -> new ArrayList<>()).add(fact);
                }
            }
        }

        for (Map.Entry<String, List<Fact>> entry : repairsByKey.entrySet()) {
            String repairKey = entry.getKey();
            List<Fact> approvals = approvalsByKey.getOrDefault(repairKey, List.of());
            List<Fact> approvedReviews = approvedReviewsByKey.getOrDefault(repairKey, List.of());
            if (approvals.isEmpty() || approvedReviews.isEmpty()) {
                for (Fact repair : entry.getValue()) {
                    List<String> relatedIds = new ArrayList<>();
                    relatedIds.add(repair.id());
                    relatedIds.addAll(ids(approvals));
                    relatedIds.addAll(ids(reviewsByKey.getOrDefault(repairKey, List.of())));
                    violations.add(new InvariantViolation(
                            "MANUAL_REPAIR_REQUIRES_APPROVAL_AND_REVIEW",
                            "manual repair repairKey=" + repairKey + " is missing approval or approved review",
                            name(),
                            "manual-repair",
                            relatedIds,
                            history.reduceTo(new LinkedHashSet<>(relatedIds))));
                }
            }

            if (entry.getValue().size() > 1) {
                List<String> relatedIds = ids(entry.getValue());
                violations.add(new InvariantViolation(
                        "MANUAL_REPAIR_IDEMPOTENT",
                        "manual repair repairKey=" + repairKey + " appears " + entry.getValue().size() + " times",
                        name(),
                        "manual-repair",
                        relatedIds,
                        history.reduceTo(new LinkedHashSet<>(relatedIds))));
            }
        }
        return List.copyOf(violations);
    }

    private boolean isManualRepairFact(Fact fact) {
        return fact.type() == FactType.MANUAL_REPAIR
                || fact.type() == FactType.MANUAL_APPROVAL
                || fact.type() == FactType.MANUAL_REVIEW;
    }

    private List<String> ids(List<Fact> facts) {
        List<String> ids = new ArrayList<>();
        for (Fact fact : facts) {
            ids.add(fact.id());
        }
        return List.copyOf(ids);
    }
}
