package com.interview.financialconsistency.serviceprototype.outbox;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
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

        Map<String, Object> response = restTemplate.postForObject("/outbox/publish-once", null, Map.class);

        assertThat(response).containsEntry("published", 1);
        assertThat(outboxStatus(messageId)).isEqualTo("PUBLISHED");
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
}
