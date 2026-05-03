package com.interview.financialconsistency.serviceprototype.transfer;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.financialconsistency.serviceprototype.account.AccountRecord;
import com.interview.financialconsistency.serviceprototype.account.AccountRepository;
import com.interview.financialconsistency.serviceprototype.idempotency.IdempotencyRepository;
import com.interview.financialconsistency.serviceprototype.ledger.LedgerRepository;
import com.interview.financialconsistency.serviceprototype.outbox.OutboxRepository;
import java.math.BigDecimal;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class TransferServiceIntegrationTest {
    @Autowired
    private TransferService transferService;

    @Autowired
    private AccountRepository accountRepository;

    @Autowired
    private LedgerRepository ledgerRepository;

    @Autowired
    private IdempotencyRepository idempotencyRepository;

    @Autowired
    private OutboxRepository outboxRepository;

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
    void successfulTransferWritesAllFactsInOneTransaction() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "transfer-key-1", "A-001", "B-001", "USD", new BigDecimal("25.0000")));

        assertThat(response.status()).isEqualTo("SUCCEEDED");
        assertThat(response.transferId()).isNotBlank();
        assertThat(accountRepository.findById("A-001"))
                .get()
                .extracting(AccountRecord::availableBalance)
                .isEqualTo(new BigDecimal("975.0000"));
        assertThat(accountRepository.findById("B-001"))
                .get()
                .extracting(AccountRecord::availableBalance)
                .isEqualTo(new BigDecimal("125.0000"));
        assertThat(countRows("transfer_order")).isEqualTo(1);
        assertThat(ledgerRepository.countByTransferId(response.transferId())).isEqualTo(2);

        Map<String, Object> idempotency = idempotencyRepository.findForUpdate("transfer-key-1").orElseThrow();
        assertThat(idempotency)
                .containsEntry("business_id", response.transferId())
                .containsEntry("status", "SUCCEEDED");
        assertThat(outboxRepository.countByAggregate("TRANSFER", response.transferId())).isEqualTo(1);
        assertThat(outboxStatus(response.transferId())).isEqualTo("PENDING");
    }

    @Test
    void duplicateRequestReturnsSameResultWithoutDuplicateLedger() {
        TransferRequest request =
                new TransferRequest("transfer-key-2", "A-001", "B-001", "USD", new BigDecimal("25.0000"));

        TransferResponse first = transferService.transfer(request);
        TransferResponse duplicate = transferService.transfer(request);

        assertThat(duplicate.status()).isEqualTo("SUCCEEDED");
        assertThat(duplicate.transferId()).isEqualTo(first.transferId());
        assertThat(ledgerRepository.countByTransferId(first.transferId())).isEqualTo(2);
        assertThat(outboxRepository.countByAggregate("TRANSFER", first.transferId())).isEqualTo(1);
    }

    @Test
    void sameIdempotencyKeyWithDifferentPayloadIsRejected() {
        TransferResponse first = transferService.transfer(new TransferRequest(
                "transfer-key-3", "A-001", "B-001", "USD", new BigDecimal("25.0000")));

        TransferResponse rejected = transferService.transfer(new TransferRequest(
                "transfer-key-3", "A-001", "B-001", "USD", new BigDecimal("26.0000")));

        assertThat(rejected.status()).isEqualTo("REJECTED");
        assertThat(ledgerRepository.countByTransferId(first.transferId())).isEqualTo(2);
        assertThat(countRows("ledger_entry")).isEqualTo(2);
        assertThat(outboxRepository.countByAggregate("TRANSFER", first.transferId())).isEqualTo(1);
    }

    @Test
    void insufficientFundsDoesNotWriteLedgerOrOutbox() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "transfer-key-4", "A-001", "B-001", "USD", new BigDecimal("1000.0001")));

        assertThat(response.status()).isEqualTo("FAILED");
        assertThat(response.transferId()).isNotBlank();
        assertThat(countRows("transfer_order")).isEqualTo(1);
        assertThat(ledgerRepository.countByTransferId(response.transferId())).isZero();
        assertThat(outboxRepository.countByAggregate("TRANSFER", response.transferId())).isZero();
        assertThat(accountRepository.findById("A-001"))
                .get()
                .extracting(AccountRecord::availableBalance)
                .isEqualTo(new BigDecimal("1000.0000"));
        assertThat(accountRepository.findById("B-001"))
                .get()
                .extracting(AccountRecord::availableBalance)
                .isEqualTo(new BigDecimal("100.0000"));

        Map<String, Object> idempotency = idempotencyRepository.findForUpdate("transfer-key-4").orElseThrow();
        assertThat(idempotency)
                .containsEntry("business_id", response.transferId())
                .containsEntry("status", "FAILED");
    }

    @Test
    void currencyMismatchReturnsRejectedWithoutWritingBusinessFacts() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "transfer-key-5", "A-001", "B-001", "EUR", new BigDecimal("25.0000")));

        assertThat(response.status()).isEqualTo("REJECTED");
        assertNoBusinessFactsOrBalanceChanges();
    }

    @Test
    void missingSourceAccountReturnsRejectedWithoutWritingBusinessFacts() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "transfer-key-6", "MISSING-001", "B-001", "USD", new BigDecimal("25.0000")));

        assertThat(response.status()).isEqualTo("REJECTED");
        assertNoBusinessFactsOrBalanceChanges();
    }

    @Test
    void missingTargetAccountReturnsRejectedWithoutWritingBusinessFacts() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "transfer-key-7", "A-001", "MISSING-001", "USD", new BigDecimal("25.0000")));

        assertThat(response.status()).isEqualTo("REJECTED");
        assertNoBusinessFactsOrBalanceChanges();
    }

    private void assertNoBusinessFactsOrBalanceChanges() {
        assertThat(countRows("transfer_order")).isZero();
        assertThat(countRows("ledger_entry")).isZero();
        assertThat(countRows("outbox_message")).isZero();
        assertThat(accountRepository.findById("A-001"))
                .get()
                .extracting(AccountRecord::availableBalance)
                .isEqualTo(new BigDecimal("1000.0000"));
        assertThat(accountRepository.findById("B-001"))
                .get()
                .extracting(AccountRecord::availableBalance)
                .isEqualTo(new BigDecimal("100.0000"));
    }

    private int countRows(String tableName) {
        Integer count = jdbcTemplate.queryForObject("select count(*) from " + tableName, Integer.class);
        return count == null ? 0 : count;
    }

    private String outboxStatus(String transferId) {
        return jdbcTemplate.queryForObject(
                """
                select status
                from outbox_message
                where aggregate_type = 'TRANSFER'
                  and aggregate_id = ?
                """,
                String.class,
                transferId);
    }
}
