package com.interview.financialconsistency.serviceprototype.outbox;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.financialconsistency.serviceprototype.kafka.TransferEventEnvelope;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class OutboxPublisher {
    private final OutboxRepository outboxRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;
    private final String topic;
    private final String publisherId;

    public OutboxPublisher(
            OutboxRepository outboxRepository,
            KafkaTemplate<String, String> kafkaTemplate,
            ObjectMapper objectMapper,
            @Value("${app.kafka.transfer-events-topic}") String topic,
            @Value("${app.outbox.publisher-id}") String publisherId) {
        this.outboxRepository = outboxRepository;
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
        this.topic = topic;
        this.publisherId = publisherId;
    }

    public int publishBatch(int batchSize) {
        outboxRepository.claimPublishable(batchSize, publisherId);
        int published = 0;
        for (OutboxMessageRecord message : outboxRepository.findClaimedBy(publisherId)) {
            try {
                kafkaTemplate.send(topic, message.aggregateId(), envelopeJson(message)).get(10, TimeUnit.SECONDS);
                outboxRepository.markPublished(message.messageId());
                published++;
            } catch (Exception ex) {
                outboxRepository.markFailedRetryable(message.messageId(), ex.getMessage());
            }
        }
        return published;
    }

    private String envelopeJson(OutboxMessageRecord message) {
        try {
            return objectMapper.writeValueAsString(new TransferEventEnvelope(
                    message.messageId(),
                    message.aggregateType(),
                    message.aggregateId(),
                    message.eventType(),
                    message.payload()));
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to serialize outbox envelope " + message.messageId(), ex);
        }
    }
}
