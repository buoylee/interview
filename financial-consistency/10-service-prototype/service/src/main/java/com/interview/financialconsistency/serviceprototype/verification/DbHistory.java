package com.interview.financialconsistency.serviceprototype.verification;

import java.util.List;
import java.util.Objects;

public record DbHistory(List<DbFact> facts) {
    public DbHistory {
        facts = List.copyOf(Objects.requireNonNull(facts));
    }
}
