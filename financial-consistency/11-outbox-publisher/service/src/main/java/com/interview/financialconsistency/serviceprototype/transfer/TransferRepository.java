package com.interview.financialconsistency.serviceprototype.transfer;

import java.math.BigDecimal;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class TransferRepository {
    private final JdbcTemplate jdbcTemplate;

    public TransferRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public void insert(
            String transferId,
            String requestId,
            String fromAccountId,
            String toAccountId,
            String currency,
            BigDecimal amount,
            String status,
            String failureReason) {
        jdbcTemplate.update(
                """
                insert into transfer_order (
                    transfer_id, request_id, from_account_id, to_account_id,
                    currency, amount, status, failure_reason
                )
                values (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                transferId,
                requestId,
                fromAccountId,
                toAccountId,
                currency,
                amount,
                status,
                failureReason);
    }

    public Optional<String> findStatus(String transferId) {
        return jdbcTemplate.queryForList(
                        """
                        select status
                        from transfer_order
                        where transfer_id = ?
                        """,
                        String.class,
                        transferId)
                .stream()
                .findFirst();
    }
}
