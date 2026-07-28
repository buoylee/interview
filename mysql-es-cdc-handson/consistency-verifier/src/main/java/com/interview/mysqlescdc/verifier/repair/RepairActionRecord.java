package com.interview.mysqlescdc.verifier.repair;

import java.util.UUID;

public record RepairActionRecord(
        UUID actionId,
        long productId,
        RepairActionType type,
        RepairOutcome outcome) {}
