package com.interview.mysqlescdc.verifier.rebuild;

import java.util.Map;
import java.util.UUID;

public record RebuildStatus(UUID runId, String status, String generation, String failureMessage,
        boolean aliasSwapped, Map<Integer,Long> startOffsets, Map<Integer,Long> shadowOffsets,
        Map<Integer,Long> barrierOffsets, UUID verificationRunId, String gateOwner,
        String aliasState) {
    public RebuildStatus {
        startOffsets = startOffsets == null ? Map.of() : Map.copyOf(startOffsets);
        shadowOffsets = shadowOffsets == null ? Map.of() : Map.copyOf(shadowOffsets);
        barrierOffsets = barrierOffsets == null ? Map.of() : Map.copyOf(barrierOffsets);
    }
    public RebuildStatus(UUID runId, String status, String generation, String failureMessage,
            boolean aliasSwapped) {
        this(runId,status,generation,failureMessage,aliasSwapped,Map.of(),Map.of(),Map.of(),
                null,null,aliasSwapped?"NEW":"OLD");
    }
}
