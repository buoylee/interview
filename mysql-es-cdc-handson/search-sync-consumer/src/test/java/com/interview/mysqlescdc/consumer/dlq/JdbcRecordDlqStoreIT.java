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

        assertThatThrownBy(() -> store.publish(new RecordDlqRecord(
                RECORD_ID, "products.revision", 7, 94202, key, "raw", "parse", "bad")))
                .isInstanceOf(IllegalArgumentException.class);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM sync_record_dlq WHERE partition_no=7")
                .query(Long.class).single()).isEqualTo(1);
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

    private static RecordDlqRecord record(
            String key, String raw, String failureClass, String error) {
        return new RecordDlqRecord(RECORD_ID, "products.revision", 7, 94201,
                key, raw, failureClass, error);
    }
}
