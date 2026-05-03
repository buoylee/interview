package com.interview.financialconsistency.serviceprototype.account;

import java.math.BigDecimal;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.stereotype.Repository;

@Repository
public class AccountRepository {
    private static final RowMapper<AccountRecord> ACCOUNT_ROW_MAPPER = (rs, rowNum) -> new AccountRecord(
            rs.getString("account_id"),
            rs.getString("currency"),
            rs.getBigDecimal("available_balance"),
            rs.getBigDecimal("frozen_balance"),
            rs.getLong("version"));

    private final JdbcTemplate jdbcTemplate;

    public AccountRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public Optional<AccountRecord> findById(String accountId) {
        return jdbcTemplate.query(
                        """
                        select account_id, currency, available_balance, frozen_balance, version
                        from account
                        where account_id = ?
                        """,
                        ACCOUNT_ROW_MAPPER,
                        accountId)
                .stream()
                .findFirst();
    }

    public AccountRecord findForUpdate(String accountId) {
        return jdbcTemplate.queryForObject(
                """
                select account_id, currency, available_balance, frozen_balance, version
                from account
                where account_id = ?
                for update
                """,
                ACCOUNT_ROW_MAPPER,
                accountId);
    }

    public void applyBalanceDelta(String accountId, BigDecimal delta) {
        int rowsUpdated = jdbcTemplate.update(
                """
                update account
                set available_balance = available_balance + ?,
                    version = version + 1
                where account_id = ?
                """,
                delta,
                accountId);
        if (rowsUpdated != 1) {
            throw new IllegalStateException(
                    "Expected to update exactly one account for accountId " + accountId + " but updated " + rowsUpdated);
        }
    }
}
