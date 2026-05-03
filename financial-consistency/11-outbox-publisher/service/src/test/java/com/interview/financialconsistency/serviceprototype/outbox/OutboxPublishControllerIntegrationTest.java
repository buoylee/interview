package com.interview.financialconsistency.serviceprototype.outbox;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.time.Duration;
import java.util.Map;
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
class OutboxPublishControllerIntegrationTest {
    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private TransferService transferService;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void cleanBusinessTables() {
        jdbcTemplate.update("delete from consumer_processed_event");
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
    @SuppressWarnings("unchecked")
    void publishOncePublishesPendingOutbox() {
        TransferResponse transfer = transferService.transfer(new TransferRequest(
                "outbox-api-key-1", "A-001", "B-001", "USD", new BigDecimal("25.0000")));
        String messageId = messageIdForTransfer(transfer.transferId());

        ResponseEntity<Map> response = restTemplate.postForEntity("/outbox/publish-once", null, Map.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat((Map<String, Object>) response.getBody()).containsEntry("published", 1);
        assertThat(outboxStatus(messageId)).isEqualTo("PUBLISHED");
        awaitProcessed(messageId);
    }

    @Test
    @SuppressWarnings("unchecked")
    void publishOnceHonorsExplicitBatchSize() {
        TransferResponse first = transferService.transfer(new TransferRequest(
                "outbox-api-key-2", "A-001", "B-001", "USD", new BigDecimal("25.0000")));
        TransferResponse second = transferService.transfer(new TransferRequest(
                "outbox-api-key-3", "A-001", "B-001", "USD", new BigDecimal("25.0000")));
        String firstMessageId = messageIdForTransfer(first.transferId());
        String secondMessageId = messageIdForTransfer(second.transferId());

        ResponseEntity<Map> response = restTemplate.postForEntity("/outbox/publish-once?batchSize=1", null, Map.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat((Map<String, Object>) response.getBody()).containsEntry("published", 1);
        assertThat(countPublished(firstMessageId, secondMessageId)).isEqualTo(1);
        awaitAnyProcessed(firstMessageId, secondMessageId);
    }

    @Test
    @SuppressWarnings("unchecked")
    void publishOnceReturnsZeroForEmptyOutbox() {
        ResponseEntity<Map> response = restTemplate.postForEntity("/outbox/publish-once", null, Map.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.OK);
        assertThat((Map<String, Object>) response.getBody()).containsEntry("published", 0);
    }

    @Test
    void publishOnceRejectsZeroBatchSize() {
        assertInvalidBatchSize(0);
    }

    @Test
    void publishOnceRejectsNegativeBatchSize() {
        assertInvalidBatchSize(-1);
    }

    @Test
    void publishOnceRejectsTooLargeBatchSize() {
        assertInvalidBatchSize(101);
    }

    private String messageIdForTransfer(String transferId) {
        return jdbcTemplate.queryForObject(
                "select message_id from outbox_message where aggregate_id = ?",
                String.class,
                transferId);
    }

    private String outboxStatus(String messageId) {
        return jdbcTemplate.queryForObject(
                "select status from outbox_message where message_id = ?",
                String.class,
                messageId);
    }

    private int countPublished(String firstMessageId, String secondMessageId) {
        Integer count = jdbcTemplate.queryForObject(
                """
                select count(*)
                from outbox_message
                where message_id in (?, ?) and status = 'PUBLISHED'
                """,
                Integer.class,
                firstMessageId,
                secondMessageId);
        return count == null ? 0 : count;
    }

    private void assertInvalidBatchSize(int batchSize) {
        ResponseEntity<Map> response = restTemplate.postForEntity(
                "/outbox/publish-once?batchSize=" + batchSize,
                null,
                Map.class);

        assertThat(response.getStatusCode()).isEqualTo(HttpStatus.BAD_REQUEST);
    }

    private void awaitProcessed(String messageId) {
        long deadline = System.nanoTime() + Duration.ofSeconds(5).toNanos();
        while (System.nanoTime() < deadline) {
            if (processedCount(messageId) > 0) {
                return;
            }
            sleepBriefly();
        }
        throw new AssertionError("Timed out waiting for consumer_processed_event " + messageId);
    }

    private void awaitAnyProcessed(String firstMessageId, String secondMessageId) {
        long deadline = System.nanoTime() + Duration.ofSeconds(5).toNanos();
        while (System.nanoTime() < deadline) {
            if (processedCount(firstMessageId) + processedCount(secondMessageId) > 0) {
                return;
            }
            sleepBriefly();
        }
        throw new AssertionError(
                "Timed out waiting for consumer_processed_event " + firstMessageId + " or " + secondMessageId);
    }

    private int processedCount(String messageId) {
        Integer count = jdbcTemplate.queryForObject(
                "select count(*) from consumer_processed_event where event_id = ?",
                Integer.class,
                messageId);
        return count == null ? 0 : count;
    }

    private void sleepBriefly() {
        try {
            Thread.sleep(50);
        } catch (InterruptedException ex) {
            Thread.currentThread().interrupt();
            throw new AssertionError("Interrupted while waiting for consumer_processed_event", ex);
        }
    }
}
