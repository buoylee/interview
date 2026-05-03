package com.interview.financialconsistency.serviceprototype.verification;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.util.List;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(properties = "spring.kafka.listener.auto-startup=false")
@ActiveProfiles("test")
class TransferMysqlVerifierIntegrationTest {
    @Autowired
    private TransferService transferService;

    @Autowired
    private MysqlFactExtractor factExtractor;

    @Autowired
    private TransferMysqlVerifier verifier;

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
    void verifierFindsNoViolationsForSuccessfulTransfer() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "verifier-key-1", "A-001", "B-001", "USD", new BigDecimal("25.0000")));

        assertThat(response.status()).isEqualTo("SUCCEEDED");
        assertThat(verifyExtractedFacts()).isEmpty();
    }

    @Test
    void verifierFindsUnbalancedLedgerInsertedByFixture() {
        insertSuccessfulTransfer("T-UNBALANCED", "REQ-UNBALANCED", "50.0000");
        insertLedger("L-UNBALANCED-1", "T-UNBALANCED", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-UNBALANCED-2", "T-UNBALANCED", "B-001", "CREDIT", "USD", "49.0000");
        insertSucceededOutbox("M-UNBALANCED", "T-UNBALANCED");

        assertThat(verifyExtractedFacts())
                .singleElement()
                .satisfies(violation -> {
                    assertThat(violation.invariant()).isEqualTo("LEDGER_BALANCED");
                    assertThat(violation.relatedFactIds())
                            .contains("ledger_entry:L-UNBALANCED-1", "ledger_entry:L-UNBALANCED-2");
                });
    }

    @Test
    void verifierFindsLedgerRowsWithAmountsDifferentFromTransferAmount() {
        insertSuccessfulTransfer("T-WRONG-AMOUNT", "REQ-WRONG-AMOUNT", "50.0000");
        insertLedger("L-WRONG-AMOUNT-1", "T-WRONG-AMOUNT", "A-001", "DEBIT", "USD", "49.0000");
        insertLedger("L-WRONG-AMOUNT-2", "T-WRONG-AMOUNT", "B-001", "CREDIT", "USD", "49.0000");
        insertSucceededOutbox("M-WRONG-AMOUNT", "T-WRONG-AMOUNT");

        assertThat(verifyExtractedFacts()).extracting(DbInvariantViolation::invariant).containsExactly("LEDGER_BALANCED");
    }

    @Test
    void verifierFindsLedgerRowsWithCurrenciesDifferentFromTransferCurrency() {
        insertSuccessfulTransfer("T-WRONG-CURRENCY", "REQ-WRONG-CURRENCY", "50.0000");
        insertLedger("L-WRONG-CURRENCY-1", "T-WRONG-CURRENCY", "A-001", "DEBIT", "EUR", "50.0000");
        insertLedger("L-WRONG-CURRENCY-2", "T-WRONG-CURRENCY", "B-001", "CREDIT", "EUR", "50.0000");
        insertSucceededOutbox("M-WRONG-CURRENCY", "T-WRONG-CURRENCY");

        assertThat(verifyExtractedFacts()).extracting(DbInvariantViolation::invariant).containsExactly("LEDGER_BALANCED");
    }

    @Test
    void verifierFindsSuccessfulTransferWithOnlyOneLedgerRow() {
        insertSuccessfulTransfer("T-SINGLE-LEDGER", "REQ-SINGLE-LEDGER", "50.0000");
        insertLedger("L-SINGLE-LEDGER-1", "T-SINGLE-LEDGER", "A-001", "DEBIT", "USD", "50.0000");
        insertSucceededOutbox("M-SINGLE-LEDGER", "T-SINGLE-LEDGER");

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("LEDGER_DOUBLE_ENTRY_REQUIRED");
    }

    @Test
    void verifierFindsMissingOutboxForSuccessfulTransfer() {
        insertSuccessfulTransfer("T-MISSING-OUTBOX", "REQ-MISSING-OUTBOX", "50.0000");
        insertLedger("L-MISSING-OUTBOX-1", "T-MISSING-OUTBOX", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-MISSING-OUTBOX-2", "T-MISSING-OUTBOX", "B-001", "CREDIT", "USD", "50.0000");

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("TRANSFER_OUTBOX_REQUIRED");
    }

    @Test
    void verifierFindsDuplicateSucceededOutboxForSuccessfulTransfer() {
        insertSuccessfulTransfer("T-DUPLICATE-OUTBOX", "REQ-DUPLICATE-OUTBOX", "50.0000");
        insertLedger("L-DUPLICATE-OUTBOX-1", "T-DUPLICATE-OUTBOX", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-DUPLICATE-OUTBOX-2", "T-DUPLICATE-OUTBOX", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-DUPLICATE-OUTBOX-1", "T-DUPLICATE-OUTBOX");
        insertSucceededOutbox("M-DUPLICATE-OUTBOX-2", "T-DUPLICATE-OUTBOX");

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("TRANSFER_OUTBOX_SINGLE_SUCCEEDED_EVENT");
    }

    @Test
    void verifierRequiresTransferOutboxAggregateType() {
        insertSuccessfulTransfer("T-WRONG-OUTBOX-TYPE", "REQ-WRONG-OUTBOX-TYPE", "50.0000");
        insertLedger("L-WRONG-OUTBOX-TYPE-1", "T-WRONG-OUTBOX-TYPE", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-WRONG-OUTBOX-TYPE-2", "T-WRONG-OUTBOX-TYPE", "B-001", "CREDIT", "USD", "50.0000");
        insertOutbox("M-WRONG-OUTBOX-TYPE", "ORDER", "T-WRONG-OUTBOX-TYPE", "TransferSucceeded");

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("TRANSFER_OUTBOX_REQUIRED");
    }

    @Test
    void verifierFindsFailedTransferWithLedgerRows() {
        insertFailedTransfer("T-FAILED-WITH-LEDGER", "REQ-FAILED-WITH-LEDGER", "50.0000");
        insertLedger("L-FAILED-WITH-LEDGER-1", "T-FAILED-WITH-LEDGER", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-FAILED-WITH-LEDGER-2", "T-FAILED-WITH-LEDGER", "B-001", "CREDIT", "USD", "50.0000");

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly(
                        "FAILED_TRANSFER_HAS_NO_LEDGER",
                        "LEDGER_REQUIRES_SUCCEEDED_TRANSFER",
                        "LEDGER_REQUIRES_SUCCEEDED_TRANSFER");
    }

    @Test
    void verifierFindsLedgerRowsWithoutSucceededTransfer() {
        insertLedger("L-ORPHAN-1", "T-MISSING", "A-001", "DEBIT", "USD", "50.0000");
        insertInitiatedTransfer("T-INITIATED-WITH-LEDGER", "REQ-INITIATED-WITH-LEDGER", "50.0000");
        insertLedger("L-INITIATED-1", "T-INITIATED-WITH-LEDGER", "A-001", "DEBIT", "USD", "50.0000");

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("LEDGER_REQUIRES_SUCCEEDED_TRANSFER", "LEDGER_REQUIRES_SUCCEEDED_TRANSFER");
    }

    @Test
    void verifierFindsIdempotencyKeyWithMultipleSuccessfulBusinessIds() {
        DbHistory history = new DbHistory(List.of(
                new DbFact(
                        "idempotency_record",
                        "same-key",
                        "same-key",
                        Map.of("status", "SUCCEEDED", "business_id", "T-ONE")),
                new DbFact(
                        "idempotency_record",
                        "same-key-copy",
                        "same-key",
                        Map.of("status", "SUCCEEDED", "business_id", "T-TWO"))));

        assertThat(verifier.verify(history))
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("IDEMPOTENCY_KEY_SINGLE_SUCCESSFUL_BUSINESS_ID");
    }

    @Test
    void verifierFindsPublishedTransferEventWithoutConsumerProcessing() {
        insertSuccessfulTransfer("T-PUBLISHED-NOT-CONSUMED", "REQ-PUBLISHED-NOT-CONSUMED", "50.0000");
        insertLedger("L-PUBLISHED-NOT-CONSUMED-1", "T-PUBLISHED-NOT-CONSUMED", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger(
                "L-PUBLISHED-NOT-CONSUMED-2", "T-PUBLISHED-NOT-CONSUMED", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-PUBLISHED-NOT-CONSUMED", "T-PUBLISHED-NOT-CONSUMED");
        markOutboxStatus("M-PUBLISHED-NOT-CONSUMED", "PUBLISHED", 1);

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("CONSUMER_PROCESSED_PUBLISHED_EVENT");
    }

    @Test
    void verifierFindsPublishAttemptStillRetryable() {
        insertSuccessfulTransfer("T-PUBLISH-RETRY", "REQ-PUBLISH-RETRY", "50.0000");
        insertLedger("L-PUBLISH-RETRY-1", "T-PUBLISH-RETRY", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-PUBLISH-RETRY-2", "T-PUBLISH-RETRY", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-PUBLISH-RETRY", "T-PUBLISH-RETRY");
        markOutboxStatus("M-PUBLISH-RETRY", "FAILED_RETRYABLE", 1);

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("OUTBOX_PUBLISH_REQUIRED");
    }

    @Test
    void verifierFindsPublishingAttemptStillRequired() {
        insertSuccessfulTransfer("T-PUBLISHING", "REQ-PUBLISHING", "50.0000");
        insertLedger("L-PUBLISHING-1", "T-PUBLISHING", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-PUBLISHING-2", "T-PUBLISHING", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-PUBLISHING", "T-PUBLISHING");
        markOutboxStatus("M-PUBLISHING", "PUBLISHING", 1);

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("OUTBOX_PUBLISH_REQUIRED");
    }

    @Test
    void verifierDoesNotRequirePublishBeforeFirstFailedRetryableAttempt() {
        insertSuccessfulTransfer("T-PUBLISH-RETRY-NO-ATTEMPT", "REQ-PUBLISH-RETRY-NO-ATTEMPT", "50.0000");
        insertLedger("L-PUBLISH-RETRY-NO-ATTEMPT-1", "T-PUBLISH-RETRY-NO-ATTEMPT", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger(
                "L-PUBLISH-RETRY-NO-ATTEMPT-2", "T-PUBLISH-RETRY-NO-ATTEMPT", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-PUBLISH-RETRY-NO-ATTEMPT", "T-PUBLISH-RETRY-NO-ATTEMPT");
        markOutboxStatus("M-PUBLISH-RETRY-NO-ATTEMPT", "FAILED_RETRYABLE", 0);

        assertThat(verifyExtractedFacts()).isEmpty();
    }

    @Test
    void verifierDoesNotRequirePublishBeforeFirstPublishingAttempt() {
        insertSuccessfulTransfer("T-PUBLISHING-NO-ATTEMPT", "REQ-PUBLISHING-NO-ATTEMPT", "50.0000");
        insertLedger("L-PUBLISHING-NO-ATTEMPT-1", "T-PUBLISHING-NO-ATTEMPT", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-PUBLISHING-NO-ATTEMPT-2", "T-PUBLISHING-NO-ATTEMPT", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-PUBLISHING-NO-ATTEMPT", "T-PUBLISHING-NO-ATTEMPT");
        markOutboxStatus("M-PUBLISHING-NO-ATTEMPT", "PUBLISHING", 0);

        assertThat(verifyExtractedFacts()).isEmpty();
    }

    @Test
    void verifierFindsDuplicateConsumerProcessingFacts() {
        DbHistory history = new DbHistory(List.of(
                new DbFact(
                        "consumer_processed_event",
                        "row-1",
                        "M-DUPLICATE-CONSUMED",
                        Map.of(
                                "event_id",
                                "M-DUPLICATE-CONSUMED",
                                "consumer_group",
                                "funds-transfer-event-consumer",
                                "status",
                                "PROCESSED")),
                new DbFact(
                        "consumer_processed_event",
                        "row-2",
                        "M-DUPLICATE-CONSUMED",
                        Map.of(
                                "event_id",
                                "M-DUPLICATE-CONSUMED",
                                "consumer_group",
                                "funds-transfer-event-consumer",
                                "status",
                                "PROCESSED"))));

        assertThat(verifier.verify(history))
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("CONSUMER_IDEMPOTENT_PROCESSING");
    }

    @Test
    void verifierFindsPublishedTransferEventProcessedOnlyByDifferentConsumerGroup() {
        insertSuccessfulTransfer("T-PUBLISHED-OTHER-GROUP", "REQ-PUBLISHED-OTHER-GROUP", "50.0000");
        insertLedger("L-PUBLISHED-OTHER-GROUP-1", "T-PUBLISHED-OTHER-GROUP", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-PUBLISHED-OTHER-GROUP-2", "T-PUBLISHED-OTHER-GROUP", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-PUBLISHED-OTHER-GROUP", "T-PUBLISHED-OTHER-GROUP");
        markOutboxStatus("M-PUBLISHED-OTHER-GROUP", "PUBLISHED", 1);
        insertProcessedEvent("M-PUBLISHED-OTHER-GROUP", "T-PUBLISHED-OTHER-GROUP", "other-consumer-group");

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("CONSUMER_PROCESSED_PUBLISHED_EVENT");
    }

    @Test
    void verifierFindsNoViolationsAfterPublishAndConsume() {
        insertSuccessfulTransfer("T-PUBLISHED-CONSUMED", "REQ-PUBLISHED-CONSUMED", "50.0000");
        insertLedger("L-PUBLISHED-CONSUMED-1", "T-PUBLISHED-CONSUMED", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-PUBLISHED-CONSUMED-2", "T-PUBLISHED-CONSUMED", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-PUBLISHED-CONSUMED", "T-PUBLISHED-CONSUMED");
        markOutboxStatus("M-PUBLISHED-CONSUMED", "PUBLISHED", 1);
        insertProcessedEvent("M-PUBLISHED-CONSUMED", "T-PUBLISHED-CONSUMED");

        assertThat(verifyExtractedFacts()).isEmpty();
    }

    @Test
    void extractorUsesTransferBusinessIdentifiersForLedgerAndOutboxFactIds() {
        insertSuccessfulTransfer("T-FACT-ID", "REQ-FACT-ID", "50.0000");
        insertLedger("L-FACT-ID-1", "T-FACT-ID", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-FACT-ID-2", "T-FACT-ID", "B-001", "CREDIT", "USD", "50.0000");
        insertSucceededOutbox("M-FACT-ID", "T-FACT-ID");

        DbHistory history = factExtractor.extractAll();

        assertThat(facts(history, "ledger_entry"))
                .extracting(DbFact::factId)
                .containsExactly("T-FACT-ID", "T-FACT-ID");
        assertThat(facts(history, "ledger_entry"))
                .extracting(fact -> fact.attributes().get("entry_id"))
                .containsExactly("L-FACT-ID-1", "L-FACT-ID-2");
        assertThat(facts(history, "outbox_message"))
                .singleElement()
                .satisfies(fact -> {
                    assertThat(fact.factId()).isEqualTo("T-FACT-ID");
                    assertThat(fact.attributes()).containsEntry("message_id", "M-FACT-ID");
                });
    }

    @Test
    void extractorUsesConsumerGroupAndEventIdForConsumerProcessedFactId() {
        insertProcessedEvent("M-CONSUMER-FACT-ID", "T-CONSUMER-FACT-ID", "funds-transfer-event-consumer");
        insertProcessedEvent("M-CONSUMER-FACT-ID", "T-CONSUMER-FACT-ID", "other-consumer-group");

        DbHistory history = factExtractor.extractAll();

        assertThat(facts(history, "consumer_processed_event"))
                .extracting(DbFact::factId)
                .containsExactly("funds-transfer-event-consumer:M-CONSUMER-FACT-ID", "other-consumer-group:M-CONSUMER-FACT-ID");
        assertThat(facts(history, "consumer_processed_event"))
                .extracting(DbFact::businessId)
                .containsExactly("M-CONSUMER-FACT-ID", "M-CONSUMER-FACT-ID");
    }

    private List<DbInvariantViolation> verifyExtractedFacts() {
        return verifier.verify(factExtractor.extractAll());
    }

    private List<DbFact> facts(DbHistory history, String tableName) {
        return history.facts().stream().filter(fact -> tableName.equals(fact.tableName())).toList();
    }

    private void insertSuccessfulTransfer(String transferId, String requestId, String amount) {
        jdbcTemplate.update(
                """
                insert into transfer_order
                  (transfer_id, request_id, from_account_id, to_account_id, currency, amount, status)
                values (?, ?, 'A-001', 'B-001', 'USD', ?, 'SUCCEEDED')
                """,
                transferId,
                requestId,
                new BigDecimal(amount));
    }

    private void insertFailedTransfer(String transferId, String requestId, String amount) {
        jdbcTemplate.update(
                """
                insert into transfer_order
                  (transfer_id, request_id, from_account_id, to_account_id, currency, amount, status, failure_reason)
                values (?, ?, 'A-001', 'B-001', 'USD', ?, 'FAILED', 'FIXTURE_FAILURE')
                """,
                transferId,
                requestId,
                new BigDecimal(amount));
    }

    private void insertInitiatedTransfer(String transferId, String requestId, String amount) {
        jdbcTemplate.update(
                """
                insert into transfer_order
                  (transfer_id, request_id, from_account_id, to_account_id, currency, amount, status)
                values (?, ?, 'A-001', 'B-001', 'USD', ?, 'INITIATED')
                """,
                transferId,
                requestId,
                new BigDecimal(amount));
    }

    private void insertLedger(
            String entryId, String transferId, String accountId, String direction, String currency, String amount) {
        jdbcTemplate.update(
                """
                insert into ledger_entry
                  (entry_id, transfer_id, account_id, direction, currency, amount, entry_type)
                values (?, ?, ?, ?, ?, ?, 'TRANSFER')
                """,
                entryId,
                transferId,
                accountId,
                direction,
                currency,
                new BigDecimal(amount));
    }

    private void insertSucceededOutbox(String messageId, String transferId) {
        insertOutbox(messageId, "TRANSFER", transferId, "TransferSucceeded");
    }

    private void insertOutbox(String messageId, String aggregateType, String transferId, String eventType) {
        jdbcTemplate.update(
                """
                insert into outbox_message
                  (message_id, aggregate_type, aggregate_id, event_type, payload, status)
                values (?, ?, ?, ?, cast(? as json), 'PENDING')
                """,
                messageId,
                aggregateType,
                transferId,
                eventType,
                "{\"transferId\":\"" + transferId + "\"}");
    }

    private void markOutboxStatus(String messageId, String status, int attemptCount) {
        jdbcTemplate.update(
                """
                update outbox_message
                set status = ?,
                    attempt_count = ?,
                    published_at = case when ? = 'PUBLISHED' then current_timestamp(6) else published_at end
                where message_id = ?
                """,
                status,
                attemptCount,
                status,
                messageId);
    }

    private void insertProcessedEvent(String eventId, String transferId) {
        insertProcessedEvent(eventId, transferId, "funds-transfer-event-consumer");
    }

    private void insertProcessedEvent(String eventId, String transferId, String consumerGroup) {
        jdbcTemplate.update(
                """
                insert into consumer_processed_event (
                    event_id, transfer_id, topic, partition_id, offset_value,
                    consumer_group, status, processed_at
                )
                values (?, ?, 'funds.transfer.events', 0, 100, ?,
                        'PROCESSED', current_timestamp(6))
                """,
                eventId,
                transferId,
                consumerGroup);
    }
}
