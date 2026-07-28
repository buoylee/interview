package com.interview.mysqlescdc.consumer.dlq;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import javax.sql.DataSource;

import java.util.Set;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.IntStream;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.SimpleDriverDataSource;

import com.mysql.cj.jdbc.Driver;

class JdbcRecordDlqStoreIT {
    private static final String JDBC_URL = "jdbc:mysql://127.0.0.1:3308/product_catalog"
            + "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC";
    private static final String RECORD_ID = "products.revision:7:94201";

    private JdbcClient jdbc;
    private RecordDlqStore store;

    @BeforeEach
    void setUp() throws Exception {
        DataSource dataSource = new SimpleDriverDataSource(
                new Driver(), JDBC_URL, "product", "productpass");
        jdbc = JdbcClient.create(dataSource);
        clean();
        store = new JdbcRecordDlqStore(dataSource);
    }

    @AfterEach
    void tearDown() {
        clean();
    }

    @Test
    void malformed_payload_and_nullable_key_round_trip_while_duplicates_resolve_and_reopen() {
        String raw = "{invalid-json\n\u0000tail";
        store.publish(record(null, raw, "parse-one", "first"));
        store.publish(record(null, raw, "parse-two", "second"));

        assertThat(store.unresolvedCount()).isEqualTo(1);
        assertThat(store.findPending(RECORD_ID)).get().satisfies(row -> {
            assertThat(row.attempts()).isEqualTo(2);
            assertThat(row.rawKey()).isNull();
            assertThat(row.rawPayload()).isEqualTo(raw);
            assertThat(row.failureClass()).isEqualTo("parse-two");
            assertThat(row.lastError()).isEqualTo("second");
        });

        store.resolve(RECORD_ID);
        Object resolvedAt = jdbc.sql("SELECT resolved_at FROM sync_record_dlq WHERE record_id=:id")
                .param("id", RECORD_ID).query().singleRow().get("resolved_at");
        store.resolve(RECORD_ID);
        store.resolve("products.revision:7:99999");
        assertThat(jdbc.sql("SELECT resolved_at FROM sync_record_dlq WHERE record_id=:id")
                .param("id", RECORD_ID).query().singleRow().get("resolved_at"))
                .isEqualTo(resolvedAt);
        store.publish(record(null, raw, "parse-three", "third"));
        assertThat(store.findPending(RECORD_ID)).get().satisfies(row -> {
            assertThat(row.attempts()).isEqualTo(3);
            assertThat(row.rawPayload()).isEqualTo(raw);
            assertThat(row.resolvedAt()).isNull();
        });
    }

    @Test
    void non_null_raw_key_round_trips_and_identity_mismatch_fails_closed() {
        String key = "key\u0000with\nbytes";
        store.publish(record(key, "not json", "parse", "bad"));
        assertThat(store.findPending(RECORD_ID)).get().extracting(RecordDlqRecord::rawKey)
                .isEqualTo(key);

        assertThatThrownBy(() -> store.publish(RecordDlqRecord.newPending(
                RECORD_ID, "products.revision", 7, 94202, key, "raw", "parse", "bad")))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM sync_record_dlq WHERE partition_no=7")
                .query(Long.class).single()).isEqualTo(1);
    }

    @Test
    void immutable_raw_evidence_conflicts_do_not_increment_overwrite_or_reopen() {
        store.publish(record(null, "first\u0000payload", "first-class", "first-error"));
        store.resolve(RECORD_ID);

        assertThatThrownBy(() -> store.publish(record(
                "new-key", "first\u0000payload", "conflict", "key-conflict")))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("immutable");
        assertThatThrownBy(() -> store.publish(record(
                null, "changed", "conflict", "payload-conflict")))
                .isInstanceOf(IllegalStateException.class).hasMessageContaining("immutable");
        assertThat(jdbc.sql("""
                SELECT attempts, raw_key, raw_payload, failure_class, last_error, status,
                       resolved_at IS NOT NULL AS has_resolved_at
                FROM sync_record_dlq WHERE record_id=:id
                """).param("id", RECORD_ID).query().singleRow())
                .containsEntry("attempts", 1)
                .containsEntry("raw_key", null)
                .containsEntry("raw_payload", "first\u0000payload")
                .containsEntry("failure_class", "first-class")
                .containsEntry("last_error", "first-error")
                .containsEntry("status", "RESOLVED")
                .containsEntry("has_resolved_at", 1L);
    }

    @Test
    void raw_key_identity_is_null_safe_binary_exact_under_case_accent_and_space_variants() {
        for (String[] variant : new String[][] {
                {"A", "a"},
                {"e", "é"},
                {"key", "key "}
        }) {
            store.publish(record(variant[0], "same-payload", "first", "first"));
            store.resolve(RECORD_ID);

            assertThatThrownBy(() -> store.publish(record(
                    variant[1], "same-payload", "conflict", "conflict")))
                    .as("raw keys must differ by binary value: <%s> vs <%s>", variant[0], variant[1])
                    .isInstanceOf(IllegalStateException.class)
                    .hasMessageContaining("immutable");
            assertThat(jdbc.sql("""
                    SELECT attempts, raw_key, raw_payload, failure_class, last_error, status,
                           resolved_at IS NOT NULL AS has_resolved_at
                    FROM sync_record_dlq WHERE record_id=:id
                    """).param("id", RECORD_ID).query().singleRow())
                    .containsEntry("attempts", 1)
                    .containsEntry("raw_key", variant[0])
                    .containsEntry("raw_payload", "same-payload")
                    .containsEntry("failure_class", "first")
                    .containsEntry("last_error", "first")
                    .containsEntry("status", "RESOLVED")
                    .containsEntry("has_resolved_at", 1L);
            clean();
        }

        store.publish(record(null, "same-payload", "first", "first"));
        store.publish(record(null, "same-payload", "second", "second"));
        assertThat(store.findPending(RECORD_ID)).get().satisfies(row -> {
            assertThat(row.rawKey()).isNull();
            assertThat(row.attempts()).isEqualTo(2);
        });
    }

    @Test
    void concurrent_compatible_and_conflicting_raw_publications_are_atomic() {
        store.publish(record(null, "original\u0000raw", "baseline", "baseline"));
        AtomicInteger conflicts = new AtomicInteger();
        IntStream.range(0, 12).parallel().forEach(attempt -> {
            try {
                String raw = attempt % 2 == 0 ? "original\u0000raw" : "changed";
                store.publish(record(null, raw, "attempt", "attempt-" + attempt));
            } catch (IllegalStateException expected) {
                conflicts.incrementAndGet();
            }
        });
        assertThat(conflicts).hasValue(6);
        assertThat(store.findPending(RECORD_ID)).get().satisfies(row -> {
            assertThat(row.attempts()).isEqualTo(7);
            assertThat(row.rawPayload()).isEqualTo("original\u0000raw");
        });
    }

    @Test
    void empty_poison_payload_round_trips_and_live_catalog_has_lifecycle_constraints() {
        store.publish(record(null, "", "empty-value", "empty"));
        assertThat(store.findPending(RECORD_ID)).get()
                .extracting(RecordDlqRecord::rawPayload).isEqualTo("");
        assertThat(jdbc.sql("""
                SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA='product_catalog' AND TABLE_NAME='sync_record_dlq'
                """).query(String.class).list()).contains(
                        "PRIMARY", "uk_record_dlq_source", "ck_record_dlq_identity",
                        "ck_record_dlq_coordinates", "ck_record_dlq_attempts",
                        "ck_record_dlq_lifecycle");
        assertThat(Set.copyOf(jdbc.sql("""
                SELECT DISTINCT INDEX_NAME FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA='product_catalog' AND TABLE_NAME='sync_record_dlq'
                """).query(String.class).list())).contains(
                        "PRIMARY", "uk_record_dlq_source", "ix_record_dlq_status_created");
        assertThat(indexShape()).containsExactlyInAnyOrder(
                "PRIMARY:0:1:record_id",
                "uk_record_dlq_source:0:1:topic_name",
                "uk_record_dlq_source:0:2:partition_no",
                "uk_record_dlq_source:0:3:offset_no",
                "ix_record_dlq_status_created:1:1:status",
                "ix_record_dlq_status_created:1:2:created_at");
        assertThat(checkClauses()).containsExactlyInAnyOrderEntriesOf(Map.of(
                "ck_record_dlq_attempts", "(attempts>0)",
                "ck_record_dlq_coordinates", "((partition_no>=0)and(offset_no>=0))",
                "ck_record_dlq_identity", "(record_id=concat(topic_name,':',partition_no,':',offset_no))",
                "ck_record_dlq_lifecycle", "(((status='pending')and(resolved_atisnull))or((status='resolved')and(resolved_atisnotnull)))"));
    }

    @Test
    void concurrent_duplicate_raw_records_increment_attempts_without_lost_updates() {
        IntStream.range(0, 12).parallel()
                .forEach(attempt -> store.publish(record(
                        null, "poison\u0000payload", "concurrent", "attempt-" + attempt)));

        assertThat(store.findPending(RECORD_ID)).get().satisfies(row -> {
            assertThat(row.attempts()).isEqualTo(12);
            assertThat(row.rawPayload()).isEqualTo("poison\u0000payload");
        });
        assertThat(jdbc.sql("SELECT COUNT(*) FROM sync_record_dlq WHERE record_id=:id")
                .param("id", RECORD_ID).query(Long.class).single()).isEqualTo(1);
    }

    private void clean() {
        if (jdbc != null) {
            jdbc.sql("DELETE FROM sync_record_dlq").update();
        }
    }

    private java.util.List<String> indexShape() {
        return jdbc.sql("""
                SELECT CONCAT(INDEX_NAME, ':', NON_UNIQUE, ':', SEQ_IN_INDEX, ':', COLUMN_NAME)
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA='product_catalog' AND TABLE_NAME='sync_record_dlq'
                """).query(String.class).list();
    }

    private Map<String, String> checkClauses() {
        return jdbc.sql("""
                SELECT tc.CONSTRAINT_NAME, cc.CHECK_CLAUSE
                FROM information_schema.TABLE_CONSTRAINTS tc
                JOIN information_schema.CHECK_CONSTRAINTS cc
                  ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA
                 AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_SCHEMA='product_catalog'
                  AND tc.TABLE_NAME='sync_record_dlq'
                """).query().listOfRows().stream().collect(Collectors.toMap(
                        row -> row.get("CONSTRAINT_NAME").toString(),
                        row -> normalizeClause(row.get("CHECK_CLAUSE").toString())));
    }

    private static String normalizeClause(String clause) {
        return clause.toLowerCase().replace("`", "").replace("_latin1", "")
                .replace("\\", "").replaceAll("\\s+", "");
    }

    private static RecordDlqRecord record(
            String key, String raw, String failureClass, String error) {
        return RecordDlqRecord.newPending(RECORD_ID, "products.revision", 7, 94201,
                key, raw, failureClass, error);
    }
}
