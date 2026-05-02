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

public final class PropagationVerifier implements ConsistencyVerifier {
    @Override
    public String name() {
        return "PropagationVerifier";
    }

    @Override
    public List<InvariantViolation> verify(History history) {
        List<InvariantViolation> violations = new ArrayList<>();
        violations.addAll(verifyCommittedOutboxPublished(history));
        violations.addAll(verifyMessageEffectIdempotency(history));
        return List.copyOf(violations);
    }

    private List<InvariantViolation> verifyCommittedOutboxPublished(History history) {
        Set<String> publishedMessageIds = new LinkedHashSet<>();
        for (Fact fact : history.facts(FactType.OUTBOX_PUBLISHED)) {
            String messageId = fact.attr("messageId");
            if (messageId != null && !messageId.isBlank()) {
                publishedMessageIds.add(messageId);
            }
        }

        List<InvariantViolation> violations = new ArrayList<>();
        for (Fact fact : history.facts(FactType.OUTBOX_RECORD)) {
            String messageId = fact.attr("messageId");
            if (!"COMMITTED".equals(fact.attr("status"))) {
                continue;
            }
            if (messageId == null || messageId.isBlank()) {
                violations.add(new InvariantViolation(
                        "OUTBOX_MESSAGE_ID_REQUIRED",
                        "committed outbox record is missing messageId",
                        name(),
                        "propagation",
                        List.of(fact.id()),
                        history.reduceTo(Set.of(fact.id()))));
                continue;
            }
            if (!publishedMessageIds.contains(messageId)) {
                violations.add(new InvariantViolation(
                        "OUTBOX_COMMITTED_NOT_PUBLISHED",
                        "committed outbox messageId=" + messageId + " was not published",
                        name(),
                        "propagation",
                        List.of(fact.id()),
                        history.reduceTo(Set.of(fact.id()))));
            }
        }
        return violations;
    }

    private List<InvariantViolation> verifyMessageEffectIdempotency(History history) {
        Map<String, List<Fact>> effectsByMessageId = new LinkedHashMap<>();
        for (Fact fact : history.facts(FactType.BUSINESS_EFFECT)) {
            String messageId = fact.attr("messageId");
            if (messageId == null || messageId.isBlank()) {
                continue;
            }
            effectsByMessageId.computeIfAbsent(messageId, ignored -> new ArrayList<>()).add(fact);
        }

        List<InvariantViolation> violations = new ArrayList<>();
        for (Map.Entry<String, List<Fact>> entry : effectsByMessageId.entrySet()) {
            if (entry.getValue().size() > 1) {
                List<String> relatedIds = ids(entry.getValue());
                violations.add(new InvariantViolation(
                        "MESSAGE_EFFECT_IDEMPOTENT",
                        "messageId=" + entry.getKey() + " created " + entry.getValue().size()
                                + " business effects",
                        name(),
                        "propagation",
                        relatedIds,
                        history.reduceTo(new LinkedHashSet<>(relatedIds))));
            }
        }
        return violations;
    }

    private List<String> ids(List<Fact> facts) {
        List<String> ids = new ArrayList<>();
        for (Fact fact : facts) {
            ids.add(fact.id());
        }
        return List.copyOf(ids);
    }
}
