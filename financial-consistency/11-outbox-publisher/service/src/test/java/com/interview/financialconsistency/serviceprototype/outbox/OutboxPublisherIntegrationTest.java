package com.interview.financialconsistency.serviceprototype.outbox;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.sql.Timestamp;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class OutboxPublisherIntegrationTest {
    @Autowired
    private TransferService transferService;

    @Autowired
    private OutboxPublisher outboxPublisher;

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
    void publisherMarksPendingOutboxAsPublishedAfterKafkaAck() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "outbox-publisher-key-1", "A-001", "B-001", "USD", new BigDecimal("25.0000")));

        String messageId = messageIdForTransfer(response.transferId());
        assertThat(outboxStatus(messageId)).isEqualTo("PENDING");

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);

        assertThat(outboxStatus(messageId)).isEqualTo("PUBLISHED");
        assertThat(publishedAt(messageId)).isNotNull();
        assertThat(attemptCount(messageId)).isEqualTo(1);
    }

    @Test
    void publisherDoesNotRecreateTransferFacts() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "outbox-publisher-key-2", "A-001", "B-001", "USD", new BigDecimal("25.0000")));

        assertThat(countRows("transfer_order")).isEqualTo(1);
        assertThat(countRows("ledger_entry")).isEqualTo(2);

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);

        assertThat(messageIdForTransfer(response.transferId())).isNotBlank();
        assertThat(countRows("transfer_order")).isEqualTo(1);
        assertThat(countRows("ledger_entry")).isEqualTo(2);
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

    private Timestamp publishedAt(String messageId) {
        return jdbcTemplate.queryForObject(
                "select published_at from outbox_message where message_id = ?",
                Timestamp.class,
                messageId);
    }

    private int attemptCount(String messageId) {
        Integer count = jdbcTemplate.queryForObject(
                "select attempt_count from outbox_message where message_id = ?",
                Integer.class,
                messageId);
        return count == null ? 0 : count;
    }

    private int countRows(String tableName) {
        Integer count = jdbcTemplate.queryForObject("select count(*) from " + tableName, Integer.class);
        return count == null ? 0 : count;
    }
}
