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

public final class StateMachineVerifier implements ConsistencyVerifier {
    private static final Set<String> TERMINAL_STATES = Set.of("SUCCEEDED", "FAILED", "CANCELLED");

    @Override
    public String name() {
        return "StateMachineVerifier";
    }

    @Override
    public List<InvariantViolation> verify(History history) {
        List<InvariantViolation> violations = new ArrayList<>();
        violations.addAll(verifySingleTerminalState(history));
        violations.addAll(verifyUnknownDoesNotBecomeLocalFailure(history));
        return List.copyOf(violations);
    }

    private List<InvariantViolation> verifySingleTerminalState(History history) {
        Map<String, List<Fact>> terminalStatesByEntity = new LinkedHashMap<>();
        List<InvariantViolation> violations = new ArrayList<>();
        for (Fact fact : history.facts(FactType.LOCAL_STATE)) {
            String entity = fact.attr("entity");
            if (entity == null || entity.isBlank()) {
                violations.add(new InvariantViolation(
                        "LOCAL_STATE_ENTITY_REQUIRED",
                        "local state is missing entity",
                        name(),
                        "state-machine",
                        List.of(fact.id()),
                        history.reduceTo(Set.of(fact.id()))));
                continue;
            }

            String state = fact.attr("state");
            if (TERMINAL_STATES.contains(state)) {
                terminalStatesByEntity.computeIfAbsent(entity, ignored -> new ArrayList<>()).add(fact);
            }
        }

        for (Map.Entry<String, List<Fact>> entry : terminalStatesByEntity.entrySet()) {
            Set<String> distinctStates = new LinkedHashSet<>();
            for (Fact fact : entry.getValue()) {
                distinctStates.add(fact.requireAttr("state"));
            }
            if (distinctStates.size() > 1) {
                List<String> relatedIds = ids(entry.getValue());
                violations.add(new InvariantViolation(
                        "STATE_MACHINE_SINGLE_TERMINAL",
                        "entity " + entry.getKey() + " reached terminal states " + distinctStates,
                        name(),
                        "state-machine",
                        relatedIds,
                        history.reduceTo(new LinkedHashSet<>(relatedIds))));
            }
        }
        return violations;
    }

    private List<InvariantViolation> verifyUnknownDoesNotBecomeLocalFailure(History history) {
        List<InvariantViolation> violations = new ArrayList<>();
        for (Fact localState : history.facts(FactType.LOCAL_STATE)) {
            if (!"FAILED".equals(localState.attr("state"))) {
                continue;
            }

            List<Fact> unknownResults = unknownResultsForBusinessKey(history, localState.businessKey());
            if (!unknownResults.isEmpty()) {
                List<String> relatedIds = new ArrayList<>();
                relatedIds.add(localState.id());
                relatedIds.addAll(ids(unknownResults));
                violations.add(new InvariantViolation(
                        "UNKNOWN_NOT_LOCAL_FAILURE",
                        "businessKey=" + localState.businessKey() + " has UNKNOWN external result and local FAILED state",
                        name(),
                        "state-machine",
                        relatedIds,
                        history.reduceTo(new LinkedHashSet<>(relatedIds))));
            }
        }
        return violations;
    }

    private List<Fact> unknownResultsForBusinessKey(History history, String businessKey) {
        List<Fact> unknownResults = new ArrayList<>();
        for (Fact fact : history.factsByBusinessKey(businessKey)) {
            if ((fact.type() == FactType.EXTERNAL_RESULT || fact.type() == FactType.SUPPLIER_RESULT)
                    && "UNKNOWN".equals(fact.attr("result"))) {
                unknownResults.add(fact);
            }
        }
        return List.copyOf(unknownResults);
    }

    private List<String> ids(List<Fact> facts) {
        List<String> ids = new ArrayList<>();
        for (Fact fact : facts) {
            ids.add(fact.id());
        }
        return List.copyOf(ids);
    }
}
