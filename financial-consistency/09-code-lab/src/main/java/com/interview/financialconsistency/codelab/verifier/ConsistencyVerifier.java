package com.interview.financialconsistency.codelab.verifier;

import com.interview.financialconsistency.codelab.model.History;
import com.interview.financialconsistency.codelab.model.InvariantViolation;

import java.util.List;

public interface ConsistencyVerifier {
    String name();

    List<InvariantViolation> verify(History history);
}
