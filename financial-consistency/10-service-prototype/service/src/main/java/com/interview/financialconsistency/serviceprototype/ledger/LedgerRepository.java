package com.interview.financialconsistency.serviceprototype.ledger;

import java.math.BigDecimal;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class LedgerRepository {
    private final JdbcTemplate jdbcTemplate;

    public LedgerRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void insert(
            String entryId,
            String transferId,
            String accountId,
            String direction,
            String currency,
            BigDecimal amount,
            String entryType) {
        jdbcTemplate.update(
                """
                insert into ledger_entry (
                    entry_id, transfer_id, account_id, direction,
                    currency, amount, entry_type
                )
                values (?, ?, ?, ?, ?, ?, ?)
                """,
                entryId,
                transferId,
                accountId,
                direction,
                currency,
                amount,
                entryType);
    }

    public int countByTransferId(String transferId) {
        Integer count = jdbcTemplate.queryForObject(
                """
                select count(*)
                from ledger_entry
                where transfer_id = ?
                """,
                Integer.class,
                transferId);
        return count == null ? 0 : count;
    }
}
