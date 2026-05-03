package com.interview.financialconsistency.serviceprototype.consumer;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.financialconsistency.serviceprototype.kafka.TransferEventEnvelope;
import com.interview.financialconsistency.serviceprototype.outbox.OutboxPublisher;
import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class TransferEventConsumerIntegrationTest {
    @Autowired
    private TransferService transferService;

    @Autowired
    private OutboxPublisher outboxPublisher;

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Autowired
    private ConsumerProcessedEventRepository repository;

    @Value("${app.kafka.transfer-events-topic}")
    private String topic;

    @Value("${spring.kafka.consumer.group-id}")
    private String consumerGroup;

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
    void consumerWritesProcessedEventAfterPublishedTransferEvent() throws Exception {
        TransferResponse response = createTransfer("consumer-key-1");
        String messageId = messageIdForTransfer(response.transferId());

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);

        awaitProcessedEventCount(messageId, 1);
        assertThat(processedStatus(messageId)).isEqualTo("PROCESSED");
    }

    @Test
    void duplicatePublishedEventIsProcessedOnlyOnce() throws Exception {
        TransferResponse response = createTransfer("consumer-key-2");
        String messageId = messageIdForTransfer(response.transferId());
        String envelopeJson = envelopeJson(messageId);

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);
        awaitProcessedEventCount(messageId, 1);

        kafkaTemplate.send(topic, response.transferId(), envelopeJson).get(10, TimeUnit.SECONDS);
        kafkaTemplate.send(topic, response.transferId(), envelopeJson).get(10, TimeUnit.SECONDS);
        Thread.sleep(1500);

        assertThat(processedEventCount(messageId)).isEqualTo(1);
    }

    @Test
    void processedEventIdempotencyIsScopedByConsumerGroup() {
        assertThat(repository.insertProcessed(
                "message-per-group", "transfer-per-group", topic, 0, 100L, consumerGroup))
                .isTrue();
        assertThat(repository.insertProcessed(
                "message-per-group", "transfer-per-group", topic, 0, 100L, consumerGroup))
                .isFalse();

        assertThat(repository.insertProcessed(
                "message-per-group", "transfer-per-group", topic, 0, 100L, consumerGroup + "-other"))
                .isTrue();

        assertThat(processedEventCount(consumerGroup, "message-per-group")).isEqualTo(1);
        assertThat(processedEventCount(consumerGroup + "-other", "message-per-group")).isEqualTo(1);
    }

    private TransferResponse createTransfer(String idempotencyKey) {
        return transferService.transfer(new TransferRequest(
                idempotencyKey, "A-001", "B-001", "USD", new BigDecimal("25.0000")));
    }

    private String messageIdForTransfer(String transferId) {
        return jdbcTemplate.queryForObject(
                "select message_id from outbox_message where aggregate_id = ?",
                String.class,
                transferId);
    }

    private String envelopeJson(String messageId) throws Exception {
        Map<String, Object> row = jdbcTemplate.queryForMap(
                """
                select message_id, aggregate_type, aggregate_id, event_type, cast(payload as char) as payload
                from outbox_message
                where message_id = ?
                """,
                messageId);
        return objectMapper.writeValueAsString(new TransferEventEnvelope(
                (String) row.get("message_id"),
                (String) row.get("aggregate_type"),
                (String) row.get("aggregate_id"),
                (String) row.get("event_type"),
                (String) row.get("payload")));
    }

    private void awaitProcessedEventCount(String eventId, int expected) throws InterruptedException {
        for (int attempt = 0; attempt < 60; attempt++) {
            if (processedEventCount(eventId) == expected) {
                return;
            }
            Thread.sleep(500);
        }
        assertThat(processedEventCount(eventId)).isEqualTo(expected);
    }

    private int processedEventCount(String eventId) {
        return processedEventCount(consumerGroup, eventId);
    }

    private int processedEventCount(String group, String eventId) {
        Integer count = jdbcTemplate.queryForObject(
                "select count(*) from consumer_processed_event where consumer_group = ? and event_id = ?",
                Integer.class,
                group,
                eventId);
        return count == null ? 0 : count;
    }

    private String processedStatus(String eventId) {
        return jdbcTemplate.queryForObject(
                "select status from consumer_processed_event where consumer_group = ? and event_id = ?",
                String.class,
                consumerGroup,
                eventId);
    }
}
