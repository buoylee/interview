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

    @Test
    void outboxPublisherConstraintsSupportPublishingStateAndConsumerGroupIdempotency() {
        assertThat(checkClause("outbox_message", "chk_outbox_status"))
                .contains("PUBLISHING");

        assertThat(indexColumns("consumer_processed_event", "PRIMARY"))
                .containsExactly("consumer_group", "event_id");
        assertThat(indexColumns("consumer_processed_event", "uk_consumer_group_topic_partition_offset"))
                .containsExactly("consumer_group", "topic", "partition_id", "offset_value");
        assertThat(indexColumns("consumer_processed_event", "idx_consumer_event_id"))
                .containsExactly("event_id");
    }

    @Test
    void consumerProcessedEventRequiredColumnsAreNotNullable() {
        assertThat(nullableColumns("consumer_processed_event", "event_id", "transfer_id", "topic",
                "partition_id", "offset_value", "consumer_group", "status"))
                .containsOnly("NO");
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

    private String checkClause(String tableName, String constraintName) {
        return jdbcTemplate.queryForObject(
                """
                select cc.check_clause
                from information_schema.table_constraints tc
                join information_schema.check_constraints cc
                  on cc.constraint_schema = tc.constraint_schema
                 and cc.constraint_name = tc.constraint_name
                where tc.table_schema = database()
                  and tc.table_name = ?
                  and tc.constraint_name = ?
                """,
                String.class,
                tableName,
                constraintName);
    }

    private List<String> indexColumns(String tableName, String indexName) {
        return jdbcTemplate.queryForList(
                """
                select column_name
                from information_schema.statistics
                where table_schema = database()
                  and table_name = ?
                  and index_name = ?
                order by seq_in_index
                """,
                String.class,
                tableName,
                indexName);
    }

    private List<String> nullableColumns(String tableName, String... columnNames) {
        return jdbcTemplate.queryForList(
                """
                select is_nullable
                from information_schema.columns
                where table_schema = database()
                  and table_name = ?
                  and column_name in (%s)
                order by field(column_name, %s)
                """.formatted(placeholders(columnNames.length), placeholders(columnNames.length)),
                String.class,
                parameters(tableName, columnNames));
    }

    private String placeholders(int count) {
        return String.join(", ", java.util.Collections.nCopies(count, "?"));
    }

    private Object[] parameters(String tableName, String[] columnNames) {
        Object[] parameters = new Object[1 + columnNames.length + columnNames.length];
        parameters[0] = tableName;
        System.arraycopy(columnNames, 0, parameters, 1, columnNames.length);
        System.arraycopy(columnNames, 0, parameters, 1 + columnNames.length, columnNames.length);
        return parameters;
    }
}
