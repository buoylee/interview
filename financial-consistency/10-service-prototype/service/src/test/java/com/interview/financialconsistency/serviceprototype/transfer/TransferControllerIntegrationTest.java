package com.interview.financialconsistency.serviceprototype.transfer;

import static org.assertj.core.api.Assertions.assertThat;

import java.math.BigDecimal;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class TransferControllerIntegrationTest {
    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private JdbcTemplate jdbcTemplate;

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
    void postTransfersCreatesSuccessfulTransfer() {
        ResponseEntity<TransferResponse> response = postTransfer("api-key-1", new BigDecimal("25.0000"));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CREATED);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().status()).isEqualTo("SUCCEEDED");
    }

    @Test
    void postTransfersRequiresIdempotencyKeyHeader() {
        ResponseEntity<TransferResponse> response = postTransfer(null, new BigDecimal("25.0000"));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().status()).isEqualTo("REJECTED");
    }

    @Test
    void postTransfersReturnsConflictForSameKeyDifferentPayload() {
        postTransfer("api-key-2", new BigDecimal("25.0000"));

        ResponseEntity<TransferResponse> response = postTransfer("api-key-2", new BigDecimal("26.0000"));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.CONFLICT);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().status()).isEqualTo("REJECTED");
    }

    @Test
    void postTransfersReturnsBadRequestForMissingFields() {
        ResponseEntity<TransferResponse> response = postTransfer("api-key-3", Map.of());

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().status()).isEqualTo("REJECTED");
    }

    @Test
    void postTransfersReturnsBadRequestForNegativeAmount() {
        ResponseEntity<TransferResponse> response = postTransfer("api-key-4", new BigDecimal("-1.0000"));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().status()).isEqualTo("REJECTED");
    }

    @Test
    void postTransfersReturnsBadRequestForAmountWithTooManyDecimalPlaces() {
        ResponseEntity<TransferResponse> response = postTransfer("api-key-5", new BigDecimal("25.00001"));

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().status()).isEqualTo("REJECTED");
    }

    @Test
    void postTransfersReturnsBadRequestForMalformedCurrency() {
        Map<String, Object> body = Map.of(
                "fromAccountId", "A-001",
                "toAccountId", "B-001",
                "currency", "usd",
                "amount", new BigDecimal("25.0000"));

        ResponseEntity<TransferResponse> response = postTransfer("api-key-6", body);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
        assertThat(response.getBody()).isNotNull();
        assertThat(response.getBody().status()).isEqualTo("REJECTED");
    }

    private ResponseEntity<TransferResponse> postTransfer(String idempotencyKey, BigDecimal amount) {
        Map<String, Object> body = Map.of(
                "fromAccountId", "A-001",
                "toAccountId", "B-001",
                "currency", "USD",
                "amount", amount);
        return postTransfer(idempotencyKey, body);
    }

    private ResponseEntity<TransferResponse> postTransfer(String idempotencyKey, Map<String, Object> body) {
        HttpHeaders headers = new HttpHeaders();
        if (idempotencyKey != null) {
            headers.add("Idempotency-Key", idempotencyKey);
        }
        return restTemplate.postForEntity("/transfers", new HttpEntity<>(body, headers), TransferResponse.class);
    }
}
