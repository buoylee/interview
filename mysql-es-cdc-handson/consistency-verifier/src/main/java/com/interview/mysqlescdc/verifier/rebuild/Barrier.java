package com.interview.mysqlescdc.verifier.rebuild;

import java.util.Set;
import java.util.UUID;

public record Barrier(UUID runId, Set<String> partitionTokens) {
    public Barrier { partitionTokens = Set.copyOf(partitionTokens); }
}
