package com.interview.financialconsistency.serviceprototype.account;

import java.math.BigDecimal;

public record AccountRecord(
        String accountId,
        String currency,
        BigDecimal availableBalance,
        BigDecimal frozenBalance,
        long version) {
}
