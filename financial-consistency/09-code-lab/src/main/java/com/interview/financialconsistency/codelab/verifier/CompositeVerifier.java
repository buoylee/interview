package com.interview.financialconsistency.codelab.verifier;

import com.interview.financialconsistency.codelab.model.History;
import com.interview.financialconsistency.codelab.model.InvariantViolation;

import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

public final class CompositeVerifier implements ConsistencyVerifier {
    private final List<ConsistencyVerifier> verifiers;

    public CompositeVerifier(List<ConsistencyVerifier> verifiers) {
        Objects.requireNonNull(verifiers);
        this.verifiers = List.copyOf(verifiers);
    }

    @Override
    public String name() {
        return "CompositeVerifier";
    }

    @Override
    public List<InvariantViolation> verify(History history) {
        List<InvariantViolation> violations = new ArrayList<>();
        for (ConsistencyVerifier verifier : verifiers) {
            violations.addAll(verifier.verify(history));
        }
        return List.copyOf(violations);
    }
}
