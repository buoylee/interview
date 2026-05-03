package com.interview.financialconsistency.serviceprototype.verification;

import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Component;

@Component
public class MysqlFactExtractor {
    private final JdbcTemplate jdbcTemplate;

    public MysqlFactExtractor(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public DbHistory extractAll() {
        List<DbFact> facts = new ArrayList<>();
        facts.addAll(extractTransferOrders());
        facts.addAll(extractLedgerEntries());
        facts.addAll(extractIdempotencyRecords());
        facts.addAll(extractOutboxMessages());
        facts.addAll(extractConsumerProcessedEvents());
        facts.addAll(extractAccounts());
        return new DbHistory(facts);
    }

    private List<DbFact> extractTransferOrders() {
        return jdbcTemplate
                .queryForList(
                        """
                        select transfer_id, request_id, from_account_id, to_account_id, currency, amount,
                               status, failure_reason, created_at, updated_at
                        from transfer_order
                        order by transfer_id
                        """)
                .stream()
                .map(row -> fact("transfer_order", row, "transfer_id", "transfer_id"))
                .toList();
    }

    private List<DbFact> extractLedgerEntries() {
        return jdbcTemplate
                .queryForList(
                        """
                        select entry_id, transfer_id, account_id, direction, currency, amount, entry_type, created_at
                        from ledger_entry
                        order by entry_id
                        """)
                .stream()
                .map(row -> fact("ledger_entry", row, "transfer_id", "transfer_id"))
                .toList();
    }

    private List<DbFact> extractIdempotencyRecords() {
        return jdbcTemplate
                .queryForList(
                        """
                        select idempotency_key, request_hash, business_type, business_id, status,
                               response_code, response_body, created_at, updated_at
                        from idempotency_record
                        order by idempotency_key
                        """)
                .stream()
                .map(row -> fact("idempotency_record", row, "idempotency_key", "idempotency_key"))
                .toList();
    }

    private List<DbFact> extractOutboxMessages() {
        return jdbcTemplate
                .queryForList(
                        """
                        select message_id, aggregate_type, aggregate_id, event_type, payload, status,
                               published_at, attempt_count, created_at, updated_at
                        from outbox_message
                        order by message_id
                        """)
                .stream()
                .map(row -> fact("outbox_message", row, "aggregate_id", "aggregate_id"))
                .toList();
    }

    private List<DbFact> extractConsumerProcessedEvents() {
        return jdbcTemplate
                .queryForList(
                        """
                        select event_id, transfer_id, topic, partition_id, offset_value,
                               consumer_group, status, processed_at, failure_reason, created_at, updated_at
                        from consumer_processed_event
                        order by event_id, consumer_group
                        """)
                .stream()
                .map(this::consumerProcessedEventFact)
                .toList();
    }

    private List<DbFact> extractAccounts() {
        return jdbcTemplate
                .queryForList(
                        """
                        select account_id, currency, available_balance, frozen_balance, version, created_at, updated_at
                        from account
                        order by account_id
                        """)
                .stream()
                .map(row -> fact("account", row, "account_id", "account_id"))
                .toList();
    }

    private DbFact fact(String tableName, Map<String, Object> row, String factIdColumn, String businessIdColumn) {
        String factId = value(row.get(factIdColumn));
        String businessId = value(row.get(businessIdColumn));
        Map<String, String> attributes = new LinkedHashMap<>();
        row.forEach((column, columnValue) -> attributes.put(column, value(columnValue)));
        return new DbFact(tableName, factId, businessId, attributes);
    }

    private DbFact consumerProcessedEventFact(Map<String, Object> row) {
        String eventId = value(row.get("event_id"));
        String consumerGroup = value(row.get("consumer_group"));
        Map<String, String> attributes = new LinkedHashMap<>();
        row.forEach((column, columnValue) -> attributes.put(column, value(columnValue)));
        return new DbFact("consumer_processed_event", consumerGroup + ":" + eventId, eventId, attributes);
    }

    private String value(Object value) {
        return value == null ? "" : value.toString();
    }
}
