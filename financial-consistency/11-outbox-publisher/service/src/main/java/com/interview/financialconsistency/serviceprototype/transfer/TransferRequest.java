package com.interview.financialconsistency.serviceprototype.transfer;

import java.math.BigDecimal;

public record TransferRequest(
        String idempotencyKey,
        String fromAccountId,
        String toAccountId,
        String currency,
        BigDecimal amount) {
}
