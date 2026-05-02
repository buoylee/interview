package com.interview.financialconsistency.codelab.verifier;

import com.interview.financialconsistency.codelab.model.Fact;
import com.interview.financialconsistency.codelab.model.FactType;
import com.interview.financialconsistency.codelab.model.History;
import com.interview.financialconsistency.codelab.model.InvariantViolation;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

public final class LedgerConsistencyVerifier implements ConsistencyVerifier {
    @Override
    public String name() {
        return "LedgerConsistencyVerifier";
    }

    @Override
    public List<InvariantViolation> verify(History history) {
        List<InvariantViolation> violations = new ArrayList<>();
        violations.addAll(verifyBalancedLedger(history));
        violations.addAll(verifyBusinessEffectIdempotency(history));
        return List.copyOf(violations);
    }

    private List<InvariantViolation> verifyBalancedLedger(History history) {
        Map<String, List<Fact>> postingsByBusinessKey = new LinkedHashMap<>();
        List<InvariantViolation> violations = new ArrayList<>();
        for (Fact fact : history.facts(FactType.LEDGER_POSTING)) {
            String side = fact.attr("side");
            if (side == null || side.isBlank()) {
                violations.add(new InvariantViolation(
                        "LEDGER_POSTING_SIDE_REQUIRED",
                        "ledger posting is missing side",
                        name(),
                        "ledger",
                        List.of(fact.id()),
                        history.reduceTo(Set.of(fact.id()))));
                continue;
            }
            if (!"DEBIT".equals(side) && !"CREDIT".equals(side)) {
                violations.add(new InvariantViolation(
                        "LEDGER_POSTING_SIDE_KNOWN",
                        "ledger posting has unknown side " + side,
                        name(),
                        "ledger",
                        List.of(fact.id()),
                        history.reduceTo(Set.of(fact.id()))));
                continue;
            }
            postingsByBusinessKey.computeIfAbsent(fact.businessKey(), ignored -> new ArrayList<>()).add(fact);
        }

        for (Map.Entry<String, List<Fact>> entry : postingsByBusinessKey.entrySet()) {
            BigDecimal signedSum = BigDecimal.ZERO;
            for (Fact posting : entry.getValue()) {
                signedSum = signedSum.add(signedAmount(posting));
            }
            if (signedSum.compareTo(BigDecimal.ZERO) != 0) {
                List<String> relatedIds = ids(entry.getValue());
                violations.add(new InvariantViolation(
                        "LEDGER_BALANCED",
                        "ledger postings for businessKey=" + entry.getKey() + " have signed sum " + signedSum,
                        name(),
                        "ledger",
                        relatedIds,
                        history.reduceTo(new LinkedHashSet<>(relatedIds))));
            }
        }
        return violations;
    }

    private List<InvariantViolation> verifyBusinessEffectIdempotency(History history) {
        Map<String, List<Fact>> effectsByKey = new LinkedHashMap<>();
        for (Fact fact : history.facts(FactType.BUSINESS_EFFECT)) {
            String effectKey = fact.attr("effectKey");
            if (effectKey != null) {
                effectsByKey.computeIfAbsent(effectKey, ignored -> new ArrayList<>()).add(fact);
            }
        }

        List<InvariantViolation> violations = new ArrayList<>();
        for (Map.Entry<String, List<Fact>> entry : effectsByKey.entrySet()) {
            if (entry.getValue().size() > 1) {
                List<String> relatedIds = ids(entry.getValue());
                violations.add(new InvariantViolation(
                        "BUSINESS_EFFECT_IDEMPOTENT",
                        "business effect key " + entry.getKey() + " appears " + entry.getValue().size() + " times",
                        name(),
                        "idempotency",
                        relatedIds,
                        history.reduceTo(new LinkedHashSet<>(relatedIds))));
            }
        }
        return violations;
    }

    private BigDecimal signedAmount(Fact posting) {
        String side = posting.attr("side");
        if ("DEBIT".equals(side)) {
            return posting.amount().negate();
        }
        if ("CREDIT".equals(side)) {
            return posting.amount();
        }
        throw new IllegalStateException("validated ledger side became invalid on " + posting.id());
    }

    private List<String> ids(List<Fact> facts) {
        List<String> ids = new ArrayList<>();
        for (Fact fact : facts) {
            ids.add(fact.id());
        }
        return List.copyOf(ids);
    }
}
