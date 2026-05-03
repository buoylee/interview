package com.interview.financialconsistency.serviceprototype;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import com.interview.financialconsistency.serviceprototype.account.AccountRecord;
import com.interview.financialconsistency.serviceprototype.account.AccountRepository;
import com.interview.financialconsistency.serviceprototype.idempotency.IdempotencyRepository;
import com.interview.financialconsistency.serviceprototype.ledger.LedgerRepository;
import com.interview.financialconsistency.serviceprototype.outbox.OutboxRepository;
import com.interview.financialconsistency.serviceprototype.transfer.TransferRepository;
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
class RepositoryIntegrationTest {
    @Autowired
    private AccountRepository accountRepository;

    @Autowired
    private TransferRepository transferRepository;

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
    void accountRepositoryLocksAndUpdatesBalances() {
        AccountRecord account = accountRepository.findForUpdate("A-001");

        assertThat(account.availableBalance()).isEqualByComparingTo("1000.0000");

        accountRepository.applyBalanceDelta("A-001", new BigDecimal("-25.0000"));
        accountRepository.applyBalanceDelta("B-001", new BigDecimal("25.0000"));

        assertThat(accountRepository.findById("A-001"))
                .get()
                .extracting(AccountRecord::availableBalance)
                .isEqualTo(new BigDecimal("975.0000"));
        assertThat(accountRepository.findById("B-001"))
                .get()
                .extracting(AccountRecord::availableBalance)
                .isEqualTo(new BigDecimal("125.0000"));
    }

    @Test
    void applyBalanceDeltaRejectsMissingAccount() {
        assertThatThrownBy(() -> accountRepository.applyBalanceDelta("MISSING-001", new BigDecimal("1.0000")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Expected to update exactly one account")
                .hasMessageContaining("MISSING-001");
    }

    @Test
    void repositoriesWriteTransferLedgerIdempotencyAndOutboxFacts() {
        transferRepository.insert(
                "T-001",
                "REQ-001",
                "A-001",
                "B-001",
                "USD",
                new BigDecimal("25.0000"),
                "SUCCEEDED",
                null);
        ledgerRepository.insert("L-001", "T-001", "A-001", "DEBIT", "USD", new BigDecimal("25.0000"), "TRANSFER");
        ledgerRepository.insert("L-002", "T-001", "B-001", "CREDIT", "USD", new BigDecimal("25.0000"), "TRANSFER");
        idempotencyRepository.insertProcessing("KEY-001", "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef", "TRANSFER");
        idempotencyRepository.markCompleted("KEY-001", "T-001", "SUCCEEDED", 200, "{\"transferId\":\"T-001\"}");
        outboxRepository.insertPending("M-001", "TRANSFER", "T-001", "TransferSucceeded", "{\"transferId\":\"T-001\"}");

        assertThat(transferRepository.findStatus("T-001")).contains("SUCCEEDED");
        assertThat(ledgerRepository.countByTransferId("T-001")).isEqualTo(2);
        Map<String, Object> idempotencyRecord = idempotencyRepository.findForUpdate("KEY-001").orElseThrow();
        assertThat(idempotencyRecord)
                .containsEntry("business_id", "T-001")
                .containsEntry("status", "SUCCEEDED")
                .containsEntry("response_code", 200);
        assertThat(outboxRepository.countByAggregate("TRANSFER", "T-001")).isEqualTo(1);
    }

    @Test
    void markCompletedRejectsMissingIdempotencyKey() {
        assertThatThrownBy(() -> idempotencyRepository.markCompleted(
                        "MISSING-KEY", "T-001", "SUCCEEDED", 200, "{\"transferId\":\"T-001\"}"))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Expected to update exactly one idempotency record")
                .hasMessageContaining("MISSING-KEY");
    }
}
