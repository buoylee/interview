package com.interview.financialconsistency.serviceprototype.consumer;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.financialconsistency.serviceprototype.kafka.TransferEventEnvelope;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

@Component
public class TransferEventConsumer {
    private final ConsumerProcessedEventRepository repository;
    private final ObjectMapper objectMapper;
    private final String consumerGroup;

    public TransferEventConsumer(
            ConsumerProcessedEventRepository repository,
            ObjectMapper objectMapper,
            @Value("${spring.kafka.consumer.group-id}") String consumerGroup) {
        this.repository = repository;
        this.objectMapper = objectMapper;
        this.consumerGroup = consumerGroup;
    }

    @KafkaListener(topics = "${app.kafka.transfer-events-topic}")
    public void consume(ConsumerRecord<String, String> record, Acknowledgment acknowledgment) throws Exception {
        TransferEventEnvelope envelope = readEnvelope(record);
        String messageId = requireText(envelope.messageId(), "messageId is required", record, null);
        String payloadJson = requireText(envelope.payload(), "payload is required", record, messageId);
        JsonNode payload = readPayload(payloadJson, record, messageId);
        String transferId = requireText(payload.path("transferId").asText(null),
                "payload.transferId is required", record, messageId);

        repository.insertProcessed(
                messageId,
                transferId,
                record.topic(),
                record.partition(),
                record.offset(),
                consumerGroup);
        acknowledgment.acknowledge();
    }

    private TransferEventEnvelope readEnvelope(ConsumerRecord<String, String> record) {
        try {
            TransferEventEnvelope envelope = objectMapper.readValue(record.value(), TransferEventEnvelope.class);
            if (envelope == null) {
                throw invalid("Invalid transfer event envelope", record, null, null);
            }
            return envelope;
        } catch (Exception ex) {
            if (ex instanceof IllegalArgumentException illegalArgumentException) {
                throw illegalArgumentException;
            }
            throw invalid("Invalid transfer event envelope", record, null, ex);
        }
    }

    private JsonNode readPayload(String payloadJson, ConsumerRecord<String, String> record, String messageId) {
        try {
            return objectMapper.readTree(payloadJson);
        } catch (Exception ex) {
            throw invalid("Invalid transfer event payload", record, messageId, ex);
        }
    }

    private String requireText(
            String value,
            String failure,
            ConsumerRecord<String, String> record,
            String messageId) {
        if (value == null || value.isBlank()) {
            throw invalid(failure, record, messageId, null);
        }
        return value;
    }

    private IllegalArgumentException invalid(
            String failure,
            ConsumerRecord<String, String> record,
            String messageId,
            Exception cause) {
        String message = failure + " at topic=" + record.topic()
                + ", partition=" + record.partition()
                + ", offset=" + record.offset();
        if (messageId != null && !messageId.isBlank()) {
            message += ", messageId=" + messageId;
        }
        if (cause == null) {
            return new IllegalArgumentException(message);
        }
        return new IllegalArgumentException(message, cause);
    }
}
