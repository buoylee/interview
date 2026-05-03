package com.interview.financialconsistency.serviceprototype.verification;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.math.BigDecimal;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class VerificationControllerIntegrationTest {
    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @BeforeEach
    void resetData() {
        jdbcTemplate.update("delete from outbox_message");
        jdbcTemplate.update("delete from ledger_entry");
        jdbcTemplate.update("delete from transfer_order");
        jdbcTemplate.update("delete from idempotency_record");
        jdbcTemplate.update(
                "update account set available_balance = 1000.0000, frozen_balance = 0.0000, version = 0 where account_id = 'A-001'");
        jdbcTemplate.update(
                "update account set available_balance = 100.0000, frozen_balance = 0.0000, version = 0 where account_id = 'B-001'");
    }

    @Test
    void verificationEndpointReturnsNoViolationsForCleanDatabase() throws Exception {
        ResponseEntity<String> response = restTemplate.getForEntity("/verification/violations", String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(readViolations(response)).isEmpty();
    }

    @Test
    void verificationEndpointReturnsViolationsAfterBadFixture() throws Exception {
        insertBadLedgerFixture();

        ResponseEntity<String> response = restTemplate.getForEntity("/verification/violations", String.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat(readViolations(response))
                .extracting(DbInvariantViolation::invariant)
                .contains(TransferMysqlVerifier.LEDGER_DOUBLE_ENTRY_REQUIRED);
    }

    private DbInvariantViolation[] readViolations(ResponseEntity<String> response) throws Exception {
        assertThat(response.getBody()).isNotNull();
        return objectMapper.readValue(response.getBody(), DbInvariantViolation[].class);
    }

    private void insertBadLedgerFixture() {
        jdbcTemplate.update(
                """
                insert into transfer_order
                  (transfer_id, request_id, from_account_id, to_account_id, currency, amount, status)
                values ('BAD-LEDGER-1', 'manual-bad-ledger', 'A-001', 'B-001', 'USD', ?, 'SUCCEEDED')
                """,
                new BigDecimal("10.0000"));
        jdbcTemplate.update(
                """
                insert into ledger_entry
                  (entry_id, transfer_id, account_id, direction, currency, amount, entry_type)
                values ('BAD-LEDGER-1-DEBIT', 'BAD-LEDGER-1', 'A-001', 'DEBIT', 'USD', ?, 'TRANSFER')
                """,
                new BigDecimal("10.0000"));
    }
}
