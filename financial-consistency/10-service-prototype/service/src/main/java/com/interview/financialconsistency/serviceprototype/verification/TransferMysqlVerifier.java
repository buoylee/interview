package com.interview.financialconsistency.serviceprototype.verification;

import java.math.BigDecimal;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;
import org.springframework.stereotype.Component;

@Component
public class TransferMysqlVerifier {
    public static final String LEDGER_DOUBLE_ENTRY_REQUIRED = "LEDGER_DOUBLE_ENTRY_REQUIRED";
    public static final String LEDGER_BALANCED = "LEDGER_BALANCED";
    public static final String TRANSFER_OUTBOX_REQUIRED = "TRANSFER_OUTBOX_REQUIRED";
    public static final String FAILED_TRANSFER_HAS_NO_LEDGER = "FAILED_TRANSFER_HAS_NO_LEDGER";
    public static final String LEDGER_REQUIRES_SUCCEEDED_TRANSFER = "LEDGER_REQUIRES_SUCCEEDED_TRANSFER";
    public static final String IDEMPOTENCY_KEY_SINGLE_SUCCESSFUL_BUSINESS_ID =
            "IDEMPOTENCY_KEY_SINGLE_SUCCESSFUL_BUSINESS_ID";

    public List<DbInvariantViolation> verify(DbHistory history) {
        Map<String, List<DbFact>> factsByTable = history.facts().stream()
                .collect(Collectors.groupingBy(DbFact::tableName, LinkedHashMap::new, Collectors.toList()));
        List<DbFact> transfers = factsByTable.getOrDefault("transfer_order", List.of());
        List<DbFact> ledgers = factsByTable.getOrDefault("ledger_entry", List.of());
        List<DbFact> outboxMessages = factsByTable.getOrDefault("outbox_message", List.of());
        List<DbFact> idempotencyRecords = factsByTable.getOrDefault("idempotency_record", List.of());

        Map<String, List<DbFact>> ledgersByTransferId = ledgers.stream()
                .collect(Collectors.groupingBy(DbFact::businessId, LinkedHashMap::new, Collectors.toList()));
        Map<String, List<DbFact>> outboxByAggregateId = outboxMessages.stream()
                .collect(Collectors.groupingBy(DbFact::businessId, LinkedHashMap::new, Collectors.toList()));
        Map<String, DbFact> transfersById = transfers.stream()
                .collect(Collectors.toMap(DbFact::businessId, transfer -> transfer, (left, right) -> left, LinkedHashMap::new));

        List<DbInvariantViolation> violations = new ArrayList<>();
        for (DbFact transfer : transfers) {
            String transferId = transfer.businessId();
            List<DbFact> transferLedgers = ledgersByTransferId.getOrDefault(transferId, List.of());
            String status = transfer.attributes().get("status");
            if ("SUCCEEDED".equals(status)) {
                verifySuccessfulTransferLedger(violations, transfer, transferLedgers);
                verifySuccessfulTransferOutbox(violations, transfer, outboxByAggregateId.getOrDefault(transferId, List.of()));
            }
            if ("FAILED".equals(status) && !transferLedgers.isEmpty()) {
                violations.add(new DbInvariantViolation(
                        FAILED_TRANSFER_HAS_NO_LEDGER,
                        "Failed transfer " + transferId + " has ledger rows",
                        relatedFactIds(transfer, transferLedgers)));
            }
        }
        verifyLedgersHaveSucceededTransfer(violations, ledgers, transfersById);
        verifyIdempotencyRecords(violations, idempotencyRecords);
        return List.copyOf(violations);
    }

    private void verifySuccessfulTransferLedger(
            List<DbInvariantViolation> violations, DbFact transfer, List<DbFact> transferLedgers) {
        List<DbFact> debits = transferLedgers.stream()
                .filter(ledger -> "DEBIT".equals(ledger.attributes().get("direction")))
                .toList();
        List<DbFact> credits = transferLedgers.stream()
                .filter(ledger -> "CREDIT".equals(ledger.attributes().get("direction")))
                .toList();

        if (transferLedgers.size() != 2 || debits.size() != 1 || credits.size() != 1) {
            violations.add(new DbInvariantViolation(
                    LEDGER_DOUBLE_ENTRY_REQUIRED,
                    "Successful transfer " + transfer.businessId() + " requires exactly one debit and one credit",
                    relatedFactIds(transfer, transferLedgers)));
            return;
        }

        DbFact debit = debits.get(0);
        DbFact credit = credits.get(0);
        if (!sameAmount(debit, credit)
                || !sameAmount(debit, transfer)
                || !sameAmount(credit, transfer)
                || !sameCurrency(debit, credit)
                || !sameCurrency(debit, transfer)
                || !sameCurrency(credit, transfer)) {
            violations.add(new DbInvariantViolation(
                    LEDGER_BALANCED,
                    "Successful transfer " + transfer.businessId()
                            + " requires ledger rows to match each other and the transfer amount and currency",
                    relatedFactIds(transfer, List.of(debit, credit))));
        }
    }

    private void verifySuccessfulTransferOutbox(
            List<DbInvariantViolation> violations, DbFact transfer, List<DbFact> outboxMessages) {
        boolean hasSucceededEvent = outboxMessages.stream()
                .anyMatch(message -> "TRANSFER".equals(message.attributes().get("aggregate_type"))
                        && "TransferSucceeded".equals(message.attributes().get("event_type")));
        if (!hasSucceededEvent) {
            violations.add(new DbInvariantViolation(
                    TRANSFER_OUTBOX_REQUIRED,
                    "Successful transfer " + transfer.businessId() + " requires a TransferSucceeded outbox message",
                    relatedFactIds(transfer, outboxMessages)));
        }
    }

    private void verifyLedgersHaveSucceededTransfer(
            List<DbInvariantViolation> violations, List<DbFact> ledgers, Map<String, DbFact> transfersById) {
        for (DbFact ledger : ledgers) {
            DbFact transfer = transfersById.get(ledger.businessId());
            if (transfer == null || !"SUCCEEDED".equals(transfer.attributes().get("status"))) {
                String reason = transfer == null
                        ? "Ledger row " + physicalFactId(ledger) + " references missing transfer " + ledger.businessId()
                        : "Ledger row " + physicalFactId(ledger) + " references non-succeeded transfer "
                                + ledger.businessId();
                violations.add(new DbInvariantViolation(
                        LEDGER_REQUIRES_SUCCEEDED_TRANSFER,
                        reason,
                        transfer == null ? List.of(physicalFactId(ledger)) : relatedFactIds(transfer, List.of(ledger))));
            }
        }
    }

    private void verifyIdempotencyRecords(
            List<DbInvariantViolation> violations, List<DbFact> idempotencyRecords) {
        Map<String, Set<String>> successfulBusinessIdsByKey = new LinkedHashMap<>();
        for (DbFact record : idempotencyRecords) {
            if (!"SUCCEEDED".equals(record.attributes().get("status"))) {
                continue;
            }
            String businessId = record.attributes().get("business_id");
            if (businessId == null || businessId.isBlank()) {
                continue;
            }
            successfulBusinessIdsByKey
                    .computeIfAbsent(record.businessId(), ignored -> new LinkedHashSet<>())
                    .add(businessId);
        }

        for (Map.Entry<String, Set<String>> entry : successfulBusinessIdsByKey.entrySet()) {
            if (entry.getValue().size() > 1) {
                List<String> relatedFactIds = idempotencyRecords.stream()
                        .filter(record -> entry.getKey().equals(record.businessId()))
                        .map(this::physicalFactId)
                        .toList();
                violations.add(new DbInvariantViolation(
                        IDEMPOTENCY_KEY_SINGLE_SUCCESSFUL_BUSINESS_ID,
                        "Idempotency key " + entry.getKey() + " has multiple successful business ids",
                        relatedFactIds));
            }
        }
    }

    private BigDecimal amount(DbFact ledger) {
        return new BigDecimal(ledger.attributes().get("amount"));
    }

    private boolean sameAmount(DbFact left, DbFact right) {
        return amount(left).compareTo(amount(right)) == 0;
    }

    private boolean sameCurrency(DbFact left, DbFact right) {
        return left.attributes().get("currency").equals(right.attributes().get("currency"));
    }

    private List<String> relatedFactIds(DbFact primaryFact, List<DbFact> relatedFacts) {
        List<String> factIds = new ArrayList<>();
        factIds.add(physicalFactId(primaryFact));
        relatedFacts.stream().map(this::physicalFactId).forEach(factIds::add);
        return factIds;
    }

    private String physicalFactId(DbFact fact) {
        return switch (fact.tableName()) {
            case "ledger_entry" -> fact.tableName() + ":" + fact.attributes().getOrDefault("entry_id", fact.factId());
            case "outbox_message" -> fact.tableName() + ":" + fact.attributes().getOrDefault("message_id", fact.factId());
            case "transfer_order" -> fact.tableName() + ":" + fact.attributes().getOrDefault("transfer_id", fact.factId());
            case "idempotency_record" -> fact.tableName() + ":"
                    + fact.attributes().getOrDefault("idempotency_key", fact.factId());
            case "account" -> fact.tableName() + ":" + fact.attributes().getOrDefault("account_id", fact.factId());
            default -> fact.tableName() + ":" + fact.factId();
        };
    }
}
