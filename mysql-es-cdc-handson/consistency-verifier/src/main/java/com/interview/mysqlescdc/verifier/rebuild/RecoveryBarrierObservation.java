package com.interview.mysqlescdc.verifier.rebuild;

import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

public record RecoveryBarrierObservation(String kind, UUID markerRunId,
        Map<Integer, Long> preOffsets, Map<Integer, Long> offsets,
        List<CanalRecoveryEvidence.Sentinel> events) {
    public RecoveryBarrierObservation {
        if (!Set.of("RESET_ANCHOR", "NORMAL_SENTINEL").contains(kind)
                || markerRunId == null || preOffsets == null || offsets == null || events == null
                || !preOffsets.keySet().equals(Set.of(0, 1, 2))
                || !offsets.keySet().equals(Set.of(0, 1, 2)) || events.size() != 3) {
            throw new IllegalArgumentException("exact recovery barrier observation required");
        }
        for (int partition : Set.of(0, 1, 2)) {
            if (offsets.get(partition) != preOffsets.get(partition) + 1) {
                throw new IllegalArgumentException("recovery barrier must be exactly next");
            }
        }
    }
}
