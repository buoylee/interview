package com.interview.financialconsistency.serviceprototype.idempotency;

import java.util.Map;
import java.util.Optional;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class IdempotencyRepository {
    private final JdbcTemplate jdbcTemplate;

    public IdempotencyRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public int insertProcessing(String idempotencyKey, String requestHash, String businessType) {
        return jdbcTemplate.update(
                """
                insert into idempotency_record (
                    idempotency_key, request_hash, business_type, status
                )
                values (?, ?, ?, 'PROCESSING')
                """,
                idempotencyKey,
                requestHash,
                businessType);
    }

    public Optional<Map<String, Object>> findForUpdate(String idempotencyKey) {
        return jdbcTemplate.queryForList(
                        """
                        select idempotency_key, request_hash, business_type, business_id,
                               status, response_code, response_body, created_at, updated_at
                        from idempotency_record
                        where idempotency_key = ?
                        for update
                        """,
                        idempotencyKey)
                .stream()
                .findFirst();
    }

    public void markCompleted(
            String idempotencyKey,
            String businessId,
            String status,
            int responseCode,
            String responseBody) {
        jdbcTemplate.update(
                """
                update idempotency_record
                set business_id = ?,
                    status = ?,
                    response_code = ?,
                    response_body = ?
                where idempotency_key = ?
                """,
                businessId,
                status,
                responseCode,
                responseBody,
                idempotencyKey);
    }
}
