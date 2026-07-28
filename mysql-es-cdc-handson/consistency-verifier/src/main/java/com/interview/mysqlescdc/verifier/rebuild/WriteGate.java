package com.interview.mysqlescdc.verifier.rebuild;

import java.util.UUID;

public interface WriteGate {
    WriteGateLease close(UUID runId, String reason);
    void open(UUID runId);
    record WriteGateLease(UUID runId, String reason) {}
}
