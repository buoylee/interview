package com.interview.mysqlescdc.consumer.dlq;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import javax.sql.DataSource;

import java.util.Set;
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
        store.publish(record("permanent-two", "second"));

        assertThat(store.unresolvedCount()).isEqualTo(1);
        assertThat(store.findPending(EVENT_ID)).get().satisfies(row -> {
            assertThat(row.attempts()).isEqualTo(2);
            assertThat(row.failureClass()).isEqualTo("permanent-two");
            assertThat(row.lastError()).isEqualTo("second");
            assertThat(row.payload()).contains("\"productId\": 92101", "\"reason\": \"bad\"");
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
        assertThatThrownBy(() -> store.publish(new DlqRecord(
                EVENT_ID, "products.revision", 1, 42, 92101, 7,
                "not-json", "permanent", "bad")))
                .isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> store.publish(new DlqRecord(
                EVENT_ID, "products.revision", 1, 42, 92102, 7,
                "{}", "permanent", "bad")))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM sync_dlq_record WHERE product_id BETWEEN 92100 AND 92199")
                .query(Long.class).single()).isZero();
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

    private static DlqRecord record(String failureClass, String error) {
        return new DlqRecord(EVENT_ID, "products.revision", 1, 42, 92101, 7,
                "{\"productId\":92101,\"reason\":\"bad\"}", failureClass, error);
    }
}
