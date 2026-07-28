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

class JdbcDlqStoreIT {
    private static final String JDBC_URL = "jdbc:mysql://127.0.0.1:3308/product_catalog"
            + "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC";
    private static final String EVENT_ID = "products.revision:1:42:92101";

    private JdbcClient jdbc;
    private DlqStore store;

    @BeforeEach
    void setUp() throws Exception {
        DataSource dataSource = new SimpleDriverDataSource(
                new Driver(), JDBC_URL, "product", "productpass");
        jdbc = JdbcClient.create(dataSource);
        clean();
        store = new JdbcDlqStore(dataSource);
    }

    @AfterEach
    void tearDown() {
        clean();
    }

    @Test
    void duplicate_publish_is_atomic_and_resolved_failure_reopens_without_losing_history() {
        store.publish(record("permanent-one", "first"));
        store.publish(DlqRecord.newPending(
                EVENT_ID, "products.revision", 1, 42, 92101, 7,
                "{ \"reason\": \"bad\", \"source_revision\": 7, \"product_id\": 92101 }",
                "permanent-two", "second"));

        assertThat(store.unresolvedCount()).isEqualTo(1);
        assertThat(store.findPending(EVENT_ID)).get().satisfies(row -> {
            assertThat(row.attempts()).isEqualTo(2);
            assertThat(row.failureClass()).isEqualTo("permanent-two");
            assertThat(row.lastError()).isEqualTo("second");
            assertThat(row.payload()).contains(
                    "\"product_id\": 92101", "\"source_revision\": 7", "\"reason\": \"bad\"");
        });

        store.resolve(EVENT_ID);
        Object resolvedAt = jdbc.sql("SELECT resolved_at FROM sync_dlq_record WHERE event_id=:id")
                .param("id", EVENT_ID).query().singleRow().get("resolved_at");
        store.resolve(EVENT_ID);
        store.resolve("products.revision:1:999:92101");
        assertThat(store.findPending(EVENT_ID)).isEmpty();
        assertThat(store.unresolvedCount()).isZero();
        assertThat(jdbc.sql("SELECT resolved_at IS NOT NULL FROM sync_dlq_record WHERE event_id=:id")
                .param("id", EVENT_ID).query(Boolean.class).single()).isTrue();
        assertThat(jdbc.sql("SELECT resolved_at FROM sync_dlq_record WHERE event_id=:id")
                .param("id", EVENT_ID).query().singleRow().get("resolved_at"))
                .isEqualTo(resolvedAt);

        store.publish(record("permanent-three", "third"));
        assertThat(store.findPending(EVENT_ID)).get().satisfies(row -> {
            assertThat(row.attempts()).isEqualTo(3);
            assertThat(row.status()).isEqualTo(DlqStatus.PENDING);
            assertThat(row.resolvedAt()).isNull();
        });
    }

    @Test
    void rejects_invalid_json_and_identity_mismatches_before_writing() {
        assertThatThrownBy(() -> store.publish(DlqRecord.newPending(
                EVENT_ID, "products.revision", 1, 42, 92101, 7,
                "not-json", "permanent", "bad")))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> store.publish(DlqRecord.newPending(
                EVENT_ID, "products.revision", 1, 42, 92102, 7,
                payload(92102, 7), "permanent", "bad")))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM sync_dlq_record WHERE product_id BETWEEN 92100 AND 92199")
                .query(Long.class).single()).isZero();
    }

    @Test
    void rejects_non_object_empty_or_mismatched_product_payload_contracts() {
        for (String invalid : new String[] {
                "null", "[]", "42", "\"scalar\"", "{}",
                "{\"product_id\":92101}",
                "{\"source_revision\":7}",
                "{\"product_id\":\"92101\",\"source_revision\":7}",
                "{\"product_id\":92101,\"source_revision\":7.0}",
                "{\"product_id\":92102,\"source_revision\":7}",
                "{\"product_id\":92101,\"source_revision\":8}"
        }) {
            assertThatThrownBy(() -> store.publish(DlqRecord.newPending(
                    EVENT_ID, "products.revision", 1, 42, 92101, 7,
                    invalid, "permanent", "bad")))
                    .as("payload must be a matching product failure object: %s", invalid)
                    .isInstanceOf(IllegalArgumentException.class);
        }
        assertThat(store.unresolvedCount()).isZero();
    }

    @Test
    void immutable_product_evidence_conflict_fails_without_mutating_or_reopening() {
        store.publish(record("first-class", "first-error"));
        store.resolve(EVENT_ID);

        assertThatThrownBy(() -> store.publish(DlqRecord.newPending(
                EVENT_ID, "products.revision", 1, 42, 92101, 8,
                payload(92101, 8), "conflict-class", "conflict-error")))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("immutable");
        assertThat(jdbc.sql("""
                SELECT attempts, source_revision, failure_class, last_error, status,
                       resolved_at IS NOT NULL AS has_resolved_at
                FROM sync_dlq_record WHERE event_id=:id
                """).param("id", EVENT_ID).query().singleRow())
                .containsEntry("attempts", 1)
                .containsEntry("source_revision", 7L)
                .containsEntry("failure_class", "first-class")
                .containsEntry("last_error", "first-error")
                .containsEntry("status", "RESOLVED")
                .containsEntry("has_resolved_at", 1L);
    }

    @Test
    void concurrent_compatible_and_conflicting_product_publications_are_atomic() {
        store.publish(record("baseline", "baseline"));
        AtomicInteger conflicts = new AtomicInteger();
        IntStream.range(0, 12).parallel().forEach(attempt -> {
            try {
                long revision = attempt % 2 == 0 ? 7 : 8;
                store.publish(DlqRecord.newPending(
                        EVENT_ID, "products.revision", 1, 42, 92101, revision,
                        payload(92101, revision), "attempt", "attempt-" + attempt));
            } catch (IllegalStateException expected) {
                conflicts.incrementAndGet();
            }
        });
        assertThat(conflicts).hasValue(6);
        assertThat(store.findPending(EVENT_ID)).get().satisfies(row -> {
            assertThat(row.attempts()).isEqualTo(7);
            assertThat(row.sourceRevision()).isEqualTo(7);
            assertThat(row.payload()).contains("\"product_id\": 92101", "\"source_revision\": 7");
        });
    }

    @Test
    void live_catalog_enforces_identity_lifecycle_and_required_indexes() {
        assertThat(jdbc.sql("""
                SELECT CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS
                WHERE TABLE_SCHEMA='product_catalog' AND TABLE_NAME='sync_dlq_record'
                """).query(String.class).list()).contains(
                        "PRIMARY", "uk_dlq_source_product", "ck_dlq_identity",
                        "ck_dlq_coordinates", "ck_dlq_attempts", "ck_dlq_lifecycle");
        assertThat(Set.copyOf(jdbc.sql("""
                SELECT DISTINCT INDEX_NAME FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA='product_catalog' AND TABLE_NAME='sync_dlq_record'
                """).query(String.class).list())).contains(
                        "PRIMARY", "uk_dlq_source_product", "ix_dlq_status_created");
        assertThat(indexShape("sync_dlq_record")).containsExactlyInAnyOrder(
                "PRIMARY:0:1:event_id",
                "uk_dlq_source_product:0:1:topic_name",
                "uk_dlq_source_product:0:2:partition_no",
                "uk_dlq_source_product:0:3:offset_no",
                "uk_dlq_source_product:0:4:product_id",
                "ix_dlq_status_created:1:1:status",
                "ix_dlq_status_created:1:2:created_at");
        assertThat(checkClauses("sync_dlq_record")).containsExactlyInAnyOrderEntriesOf(Map.of(
                "ck_dlq_attempts", "(attempts>0)",
                "ck_dlq_coordinates", "((partition_no>=0)and(offset_no>=0)and(product_id>0)and(source_revision>0))",
                "ck_dlq_identity", "(event_id=concat(topic_name,':',partition_no,':',offset_no,':',product_id))",
                "ck_dlq_lifecycle", "(((status='pending')and(resolved_atisnull))or((status='resolved')and(resolved_atisnotnull)))"));
        assertThatThrownBy(() -> jdbc.sql("""
                INSERT INTO sync_dlq_record
                  (event_id, topic_name, partition_no, offset_no, product_id,
                   source_revision, payload, failure_class, last_error, status,
                   attempts, resolved_at)
                VALUES ('wrong', 'products.revision', 1, 42, 92101, 1,
                        JSON_OBJECT(), 'test', 'bad', 'PENDING', 1, NULL)
                """).update()).isInstanceOf(RuntimeException.class);
    }

    @Test
    void concurrent_duplicate_publications_increment_attempts_without_lost_updates() {
        IntStream.range(0, 12).parallel()
                .forEach(attempt -> store.publish(record("concurrent", "attempt-" + attempt)));

        assertThat(store.findPending(EVENT_ID)).get()
                .extracting(DlqRecord::attempts).isEqualTo(12);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM sync_dlq_record WHERE event_id=:id")
                .param("id", EVENT_ID).query(Long.class).single()).isEqualTo(1);
    }

    private void clean() {
        if (jdbc != null) {
            jdbc.sql("DELETE FROM sync_dlq_record").update();
        }
    }

    private java.util.List<String> indexShape(String table) {
        return jdbc.sql("""
                SELECT CONCAT(INDEX_NAME, ':', NON_UNIQUE, ':', SEQ_IN_INDEX, ':', COLUMN_NAME)
                FROM information_schema.STATISTICS
                WHERE TABLE_SCHEMA='product_catalog' AND TABLE_NAME=:table
                """).param("table", table).query(String.class).list();
    }

    private Map<String, String> checkClauses(String table) {
        return jdbc.sql("""
                SELECT tc.CONSTRAINT_NAME, cc.CHECK_CLAUSE
                FROM information_schema.TABLE_CONSTRAINTS tc
                JOIN information_schema.CHECK_CONSTRAINTS cc
                  ON cc.CONSTRAINT_SCHEMA=tc.CONSTRAINT_SCHEMA
                 AND cc.CONSTRAINT_NAME=tc.CONSTRAINT_NAME
                WHERE tc.CONSTRAINT_SCHEMA='product_catalog' AND tc.TABLE_NAME=:table
                """).param("table", table).query().listOfRows().stream().collect(Collectors.toMap(
                        row -> row.get("CONSTRAINT_NAME").toString(),
                        row -> normalizeClause(row.get("CHECK_CLAUSE").toString())));
    }

    private static String normalizeClause(String clause) {
        return clause.toLowerCase().replace("`", "").replace("_latin1", "")
                .replace("\\", "").replaceAll("\\s+", "");
    }

    private static DlqRecord record(String failureClass, String error) {
        return DlqRecord.newPending(EVENT_ID, "products.revision", 1, 42, 92101, 7,
                payload(92101, 7), failureClass, error);
    }

    private static String payload(long productId, long revision) {
        return "{\"product_id\":" + productId + ",\"source_revision\":" + revision
                + ",\"reason\":\"bad\"}";
    }
}
