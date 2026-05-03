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

@SpringBootTest
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
    void verifierFindsFailedTransferWithLedgerRows() {
        insertFailedTransfer("T-FAILED-WITH-LEDGER", "REQ-FAILED-WITH-LEDGER", "50.0000");
        insertLedger("L-FAILED-WITH-LEDGER-1", "T-FAILED-WITH-LEDGER", "A-001", "DEBIT", "USD", "50.0000");
        insertLedger("L-FAILED-WITH-LEDGER-2", "T-FAILED-WITH-LEDGER", "B-001", "CREDIT", "USD", "50.0000");

        assertThat(verifyExtractedFacts())
                .extracting(DbInvariantViolation::invariant)
                .containsExactly("FAILED_TRANSFER_HAS_NO_LEDGER");
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
        jdbcTemplate.update(
                """
                insert into outbox_message
                  (message_id, aggregate_type, aggregate_id, event_type, payload, status)
                values (?, 'TRANSFER', ?, 'TransferSucceeded', cast(? as json), 'PENDING')
                """,
                messageId,
                transferId,
                "{\"transferId\":\"" + transferId + "\"}");
    }
}
