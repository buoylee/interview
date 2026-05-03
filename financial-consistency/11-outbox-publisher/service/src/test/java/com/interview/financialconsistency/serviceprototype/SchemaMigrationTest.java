package com.interview.financialconsistency.serviceprototype;

import static org.assertj.core.api.Assertions.assertThat;

import java.util.List;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class SchemaMigrationTest {
    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Test
    void flywayCreatesFundsCoreTablesAndSeedAccounts() {
        List<String> tableNames = jdbcTemplate.queryForList(
                """
                select table_name
                from information_schema.tables
                where table_schema = database()
                  and table_name in (
                    'account',
                    'transfer_order',
                    'ledger_entry',
                    'idempotency_record',
                    'outbox_message'
                  )
                """,
                String.class);

        assertThat(tableNames)
                .containsExactlyInAnyOrder(
                        "account",
                        "transfer_order",
                        "ledger_entry",
                        "idempotency_record",
                        "outbox_message");

        List<String> accountIds = jdbcTemplate.queryForList(
                "select account_id from account where account_id in ('A-001', 'B-001')",
                String.class);

        assertThat(accountIds).containsExactlyInAnyOrder("A-001", "B-001");
    }

    @Test
    void outboxPublisherColumnsAndConsumerTableExist() {
        assertThat(columnNames("outbox_message"))
                .contains("locked_at", "locked_by", "last_error");
        assertThat(columnNames("consumer_processed_event"))
                .contains("event_id", "transfer_id", "topic", "partition_id",
                        "offset_value", "consumer_group", "status", "processed_at", "failure_reason");
    }

    private List<String> columnNames(String tableName) {
        return jdbcTemplate.queryForList(
                """
                select column_name
                from information_schema.columns
                where table_schema = database()
                  and table_name = ?
                order by ordinal_position
                """,
                String.class,
                tableName);
    }
}
