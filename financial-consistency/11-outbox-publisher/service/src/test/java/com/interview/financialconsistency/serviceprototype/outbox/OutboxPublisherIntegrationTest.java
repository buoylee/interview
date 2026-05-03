package com.interview.financialconsistency.serviceprototype.outbox;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.sql.Timestamp;
import java.time.Duration;
import java.util.List;
import java.util.Properties;
import java.util.UUID;
import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
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

    @Autowired
    private OutboxRepository outboxRepository;

    @Autowired
    private ObjectMapper objectMapper;

    @Value("${spring.kafka.bootstrap-servers}")
    private String bootstrapServers;

    @Value("${app.kafka.transfer-events-topic}")
    private String topic;

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

    @Test
    void repositoryClaimFindUsesDistinctOwnerTokens() {
        insertOutboxMessage("message-owner-1", "transfer-owner-1");
        insertOutboxMessage("message-owner-2", "transfer-owner-2");

        assertThat(outboxRepository.claimPublishable(1, "local-publisher:owner-a")).isEqualTo(1);
        assertThat(outboxRepository.claimPublishable(1, "local-publisher:owner-b")).isEqualTo(1);

        List<OutboxMessageRecord> ownerA = outboxRepository.findClaimedBy("local-publisher:owner-a");
        List<OutboxMessageRecord> ownerB = outboxRepository.findClaimedBy("local-publisher:owner-b");

        assertThat(ownerA).hasSize(1);
        assertThat(ownerB).hasSize(1);
        assertThat(ownerA.get(0).messageId()).isNotEqualTo(ownerB.get(0).messageId());
    }

    @Test
    void staleOwnerCannotMarkPublishedOrRetryableAfterOwnershipChanged() {
        insertOutboxMessage("message-stale-owner", "transfer-stale-owner");

        assertThat(outboxRepository.claimPublishable(1, "local-publisher:owner-a")).isEqualTo(1);
        jdbcTemplate.update(
                "update outbox_message set locked_by = ? where message_id = ?",
                "local-publisher:owner-b",
                "message-stale-owner");

        assertThatThrownBy(() -> outboxRepository.markPublished("message-stale-owner", "local-publisher:owner-a"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("updated 0");
        assertThat(outboxStatus("message-stale-owner")).isEqualTo("PUBLISHING");

        outboxRepository.markFailedRetryable("message-stale-owner", "local-publisher:owner-b", "boom");
        assertThat(outboxStatus("message-stale-owner")).isEqualTo("FAILED_RETRYABLE");

        assertThatThrownBy(() -> outboxRepository.markFailedRetryable("message-stale-owner", "local-publisher:owner-b", "late"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("updated 0");
    }

    @Test
    void publisherWritesTransferEnvelopeToKafkaTopic() throws Exception {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "outbox-publisher-key-3", "A-001", "B-001", "USD", new BigDecimal("25.0000")));
        String messageId = messageIdForTransfer(response.transferId());

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);

        ConsumerRecord<String, String> record = readRecordForKey(response.transferId());
        assertThat(record.key()).isEqualTo(response.transferId());

        JsonNode envelope = objectMapper.readTree(record.value());
        assertThat(envelope.get("messageId").asText()).isEqualTo(messageId);
        assertThat(envelope.get("aggregateType").asText()).isEqualTo("TRANSFER");
        assertThat(envelope.get("aggregateId").asText()).isEqualTo(response.transferId());
        assertThat(envelope.get("eventType").asText()).isEqualTo("TransferSucceeded");
        assertThat(envelope.get("payload").asText()).contains(response.transferId());
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

    private void insertOutboxMessage(String messageId, String transferId) {
        outboxRepository.insertPending(
                messageId,
                "TRANSFER",
                transferId,
                "TransferSucceeded",
                "{\"transferId\":\"" + transferId + "\"}");
    }

    private ConsumerRecord<String, String> readRecordForKey(String key) {
        Properties properties = new Properties();
        properties.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, bootstrapServers);
        properties.put(ConsumerConfig.GROUP_ID_CONFIG, "outbox-publisher-test-" + UUID.randomUUID());
        properties.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        properties.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class.getName());
        properties.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");

        try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(properties)) {
            consumer.subscribe(List.of(topic));
            long deadline = System.nanoTime() + Duration.ofSeconds(10).toNanos();
            while (System.nanoTime() < deadline) {
                for (ConsumerRecord<String, String> record : consumer.poll(Duration.ofMillis(250))) {
                    if (key.equals(record.key())) {
                        return record;
                    }
                }
            }
        }
        throw new AssertionError("Did not find Kafka record with key " + key);
    }
}
