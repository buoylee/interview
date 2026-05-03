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
        TransferEventEnvelope envelope = objectMapper.readValue(record.value(), TransferEventEnvelope.class);
        JsonNode payload = objectMapper.readTree(envelope.payload());
        String transferId = payload.get("transferId").asText();

        repository.insertProcessed(
                envelope.messageId(),
                transferId,
                record.topic(),
                record.partition(),
                record.offset(),
                consumerGroup);
        acknowledgment.acknowledge();
    }
}
