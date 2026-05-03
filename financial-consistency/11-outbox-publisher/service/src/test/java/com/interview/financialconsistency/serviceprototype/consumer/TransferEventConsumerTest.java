package com.interview.financialconsistency.serviceprototype.consumer;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.junit.jupiter.api.Test;
import org.springframework.kafka.support.Acknowledgment;

class TransferEventConsumerTest {
    private final ConsumerProcessedEventRepository repository = mock(ConsumerProcessedEventRepository.class);
    private final TransferEventConsumer consumer =
            new TransferEventConsumer(repository, new ObjectMapper(), "funds-transfer-event-consumer");

    @Test
    void invalidEnvelopeJsonThrowsWithRecordContextAndDoesNotAck() {
        Acknowledgment acknowledgment = mock(Acknowledgment.class);

        assertThatThrownBy(() -> consumer.consume(record("not-json"), acknowledgment))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Invalid transfer event envelope")
                .hasMessageContaining("topic=funds.transfer.events")
                .hasMessageContaining("partition=2")
                .hasMessageContaining("offset=42");

        verifyNoProcessingOrAck(acknowledgment);
    }

    @Test
    void blankMessageIdThrowsWithRecordContextAndDoesNotAck() {
        Acknowledgment acknowledgment = mock(Acknowledgment.class);

        assertThatThrownBy(() -> consumer.consume(
                        record("""
                                {"messageId":" ","aggregateType":"TRANSFER","aggregateId":"T-1","eventType":"TransferSucceeded","payload":"{\\"transferId\\":\\"T-1\\"}"}
                                """),
                        acknowledgment))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("messageId is required")
                .hasMessageContaining("topic=funds.transfer.events")
                .hasMessageContaining("partition=2")
                .hasMessageContaining("offset=42");

        verifyNoProcessingOrAck(acknowledgment);
    }

    @Test
    void invalidPayloadJsonThrowsWithRecordContextAndMessageIdAndDoesNotAck() {
        Acknowledgment acknowledgment = mock(Acknowledgment.class);

        assertThatThrownBy(() -> consumer.consume(
                        record("""
                                {"messageId":"message-1","aggregateType":"TRANSFER","aggregateId":"T-1","eventType":"TransferSucceeded","payload":"not-json"}
                                """),
                        acknowledgment))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("Invalid transfer event payload")
                .hasMessageContaining("topic=funds.transfer.events")
                .hasMessageContaining("partition=2")
                .hasMessageContaining("offset=42")
                .hasMessageContaining("messageId=message-1");

        verifyNoProcessingOrAck(acknowledgment);
    }

    @Test
    void blankPayloadThrowsWithRecordContextAndMessageIdAndDoesNotAck() {
        Acknowledgment acknowledgment = mock(Acknowledgment.class);

        assertThatThrownBy(() -> consumer.consume(
                        record("""
                                {"messageId":"message-blank-payload","aggregateType":"TRANSFER","aggregateId":"T-1","eventType":"TransferSucceeded","payload":" "}
                                """),
                        acknowledgment))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("payload is required")
                .hasMessageContaining("topic=funds.transfer.events")
                .hasMessageContaining("partition=2")
                .hasMessageContaining("offset=42")
                .hasMessageContaining("messageId=message-blank-payload");

        verifyNoProcessingOrAck(acknowledgment);
    }

    @Test
    void blankTransferIdThrowsWithRecordContextAndMessageIdAndDoesNotAck() {
        Acknowledgment acknowledgment = mock(Acknowledgment.class);

        assertThatThrownBy(() -> consumer.consume(
                        record("""
                                {"messageId":"message-2","aggregateType":"TRANSFER","aggregateId":"T-1","eventType":"TransferSucceeded","payload":"{\\"transferId\\":\\" \\"}"}
                                """),
                        acknowledgment))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("payload.transferId is required")
                .hasMessageContaining("topic=funds.transfer.events")
                .hasMessageContaining("partition=2")
                .hasMessageContaining("offset=42")
                .hasMessageContaining("messageId=message-2");

        verifyNoProcessingOrAck(acknowledgment);
    }

    @Test
    void duplicateProcessedEventIsStillAcknowledged() throws Exception {
        Acknowledgment acknowledgment = mock(Acknowledgment.class);
        when(repository.insertProcessed(anyString(), anyString(), anyString(), anyInt(), anyLong(), anyString()))
                .thenReturn(false);

        consumer.consume(
                record("""
                        {"messageId":"message-3","aggregateType":"TRANSFER","aggregateId":"T-1","eventType":"TransferSucceeded","payload":"{\\"transferId\\":\\"T-1\\"}"}
                        """),
                acknowledgment);

        verify(repository).insertProcessed(
                "message-3", "T-1", "funds.transfer.events", 2, 42L, "funds-transfer-event-consumer");
        verify(acknowledgment).acknowledge();
    }

    private ConsumerRecord<String, String> record(String value) {
        return new ConsumerRecord<>("funds.transfer.events", 2, 42L, "T-1", value);
    }

    private void verifyNoProcessingOrAck(Acknowledgment acknowledgment) {
        verify(repository, never())
                .insertProcessed(anyString(), anyString(), anyString(), anyInt(), anyLong(), anyString());
        verify(acknowledgment, never()).acknowledge();
    }
}
