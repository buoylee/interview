package com.interview.mysqlescdc.verifier.source;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.Connection;
import java.sql.DriverManager;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.concurrent.atomic.AtomicInteger;

import javax.sql.DataSource;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.AbstractDataSource;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

class JdbcExpectedDocumentReaderIT {
    private static final String URL = "jdbc:mysql://localhost:3308/product_catalog"
            + "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC";
    private static final long BASE_ID = 7_100_000L;

    private JdbcClient fixture;
    private CountingReadOnlyDataSource observedSource;
    private JdbcExpectedDocumentReader reader;
    private SourceWatermarkReader watermarkReader;

    @BeforeEach
    void setUp() {
        fixture = JdbcClient.create(dataSource("root", "rootpass"));
        observedSource = new CountingReadOnlyDataSource(dataSource("verifier", "verifierpass"));
        JdbcClient verifierJdbc = JdbcClient.create(observedSource);
        reader = new JdbcExpectedDocumentReader(verifierJdbc, new IndependentExpectedProjector());
        watermarkReader = new JdbcSourceWatermarkReader(verifierJdbc);
        cleanup();
        fixture.sql("""
                INSERT INTO categories(id, name, updated_at)
                VALUES (:id, 'Verifier Category', '2026-07-22 01:02:03.123456')
                ON DUPLICATE KEY UPDATE name = VALUES(name), updated_at = VALUES(updated_at)
                """).param("id", BASE_ID).update();
    }

    @AfterEach
    void cleanup() {
        if (fixture == null) {
            return;
        }
        fixture.sql("DELETE FROM product_search_revision WHERE product_id BETWEEN :first AND :last")
                .param("first", BASE_ID).param("last", BASE_ID + 999).update();
        fixture.sql("DELETE FROM inventory WHERE product_id BETWEEN :first AND :last")
                .param("first", BASE_ID).param("last", BASE_ID + 999).update();
        fixture.sql("DELETE FROM products WHERE id BETWEEN :first AND :last")
                .param("first", BASE_ID).param("last", BASE_ID + 999).update();
        fixture.sql("DELETE FROM categories WHERE id = :id").param("id", BASE_ID).update();
    }

    @Test
    void pages_205_revision_rows_as_100_100_5_without_duplicates_or_watermark_writes() {
        insertRows(205);
        deactivate(BASE_ID + 3, 9, "2026-07-22 05:06:07.234567");
        deactivate(BASE_ID + 203, 11, "2026-07-22 06:07:08.345678");
        long watermarkBefore = watermarkReader.current();
        observedSource.reset();

        List<ExpectedDocument> all = new ArrayList<>();
        long cursor = BASE_ID - 1;
        List<Integer> sizes = new ArrayList<>();
        List<Boolean> completion = new ArrayList<>();
        do {
            ExpectedPage page = reader.readAfter(cursor, 100);
            sizes.add(page.documents().size());
            completion.add(page.complete());
            all.addAll(page.documents());
            cursor = page.nextExclusiveProductId();
        } while (!completion.getLast());

        assertThat(sizes).containsExactly(100, 100, 5);
        assertThat(completion).containsExactly(false, false, true);
        assertThat(all).extracting(ExpectedDocument::productId)
                .doesNotHaveDuplicates().isSorted().hasSize(205);
        assertThat(all.get(3)).isEqualTo(ExpectedDocument.tombstone(
                BASE_ID + 3, 9, Instant.parse("2026-07-22T05:06:07.234567Z")));
        assertThat(all.get(203)).isEqualTo(ExpectedDocument.tombstone(
                BASE_ID + 203, 11, Instant.parse("2026-07-22T06:07:08.345678Z")));
        assertThat(watermarkReader.current()).isEqualTo(watermarkBefore);
        assertThat(observedSource.connections()).isEqualTo(4); // three pages plus final watermark
    }

    @Test
    void exact_boundary_uses_extra_row_rule_and_never_requires_an_empty_probe_page() {
        insertRows(201);
        observedSource.reset();

        ExpectedPage first = reader.readAfter(BASE_ID - 1, 100);
        ExpectedPage second = reader.readAfter(first.nextExclusiveProductId(), 100);
        ExpectedPage third = reader.readAfter(second.nextExclusiveProductId(), 100);

        assertThat(first.documents()).hasSize(100);
        assertThat(first.complete()).isFalse();
        assertThat(second.documents()).hasSize(100);
        assertThat(second.complete()).isFalse();
        assertThat(third.documents()).hasSize(1);
        assertThat(third.complete()).isTrue();
        assertThat(observedSource.connections()).isEqualTo(3);

        fixture.sql("DELETE FROM product_search_revision WHERE product_id = :id")
                .param("id", BASE_ID + 200).update();
        fixture.sql("DELETE FROM inventory WHERE product_id = :id")
                .param("id", BASE_ID + 200).update();
        fixture.sql("DELETE FROM products WHERE id = :id")
                .param("id", BASE_ID + 200).update();

        ExpectedPage exactFirst = reader.readAfter(BASE_ID - 1, 100);
        ExpectedPage exactSecond = reader.readAfter(exactFirst.nextExclusiveProductId(), 100);
        assertThat(exactFirst.complete()).isFalse();
        assertThat(exactSecond.documents()).hasSize(100);
        assertThat(exactSecond.complete()).isTrue();
    }

    @Test
    void load_distinguishes_missing_inactive_missing_joins_and_active_incomplete_aggregate() {
        insertRows(3);
        deactivate(BASE_ID + 1, 17, "2026-07-22 07:08:09.456789");
        removeBusinessRowsIgnoringForeignKeys(BASE_ID + 1);

        observedSource.reset();
        assertThat(reader.load(BASE_ID + 500)).isEmpty();
        assertThat(reader.load(BASE_ID + 1)).contains(ExpectedDocument.tombstone(
                BASE_ID + 1, 17, Instant.parse("2026-07-22T07:08:09.456789Z")));
        assertThat(observedSource.connections()).isEqualTo(2);

        fixture.sql("DELETE FROM inventory WHERE product_id = :id")
                .param("id", BASE_ID + 2).update();
        assertThatThrownBy(() -> reader.load(BASE_ID + 2))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("incomplete active expected source row")
                .hasMessageContaining(Long.toString(BASE_ID + 2));
    }

    @Test
    void each_reader_call_is_one_select_validates_arguments_and_preserves_utc_microseconds() {
        insertRows(1);
        fixture.sql("""
                UPDATE product_search_revision
                SET updated_at = '2026-07-22 08:09:10.567891'
                WHERE product_id = :id
                """).param("id", BASE_ID).update();
        fixture.sql("UPDATE products SET updated_at = '2026-07-22 08:09:10.567890' WHERE id = :id")
                .param("id", BASE_ID).update();
        observedSource.reset();

        ExpectedDocument loaded = reader.load(BASE_ID).orElseThrow();
        assertThat(loaded.sourceUpdatedAt())
                .isEqualTo(Instant.parse("2026-07-22T08:09:10.567891Z"));
        assertThat(observedSource.connections()).isOne();

        assertThatThrownBy(() -> reader.readAfter(-1, 100)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> reader.readAfter(0, 0)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> reader.readAfter(0, 1001)).isInstanceOf(IllegalArgumentException.class);
        assertThatThrownBy(() -> reader.load(0)).isInstanceOf(IllegalArgumentException.class);
    }

    @Test
    void concurrent_mutation_is_diagnostic_and_visible_through_the_external_watermark() {
        insertRows(101);
        long before = watermarkReader.current();
        ExpectedPage first = reader.readAfter(BASE_ID - 1, 100);
        fixture.sql("UPDATE source_change_watermark SET value = value + 1 WHERE singleton_id = 1").update();
        fixture.sql("UPDATE products SET price_cents = price_cents + 1 WHERE id = :id")
                .param("id", BASE_ID + 100).update();
        ExpectedPage second = reader.readAfter(first.nextExclusiveProductId(), 100);

        assertThat(second.documents()).singleElement()
                .extracting(ExpectedDocument::priceCents).isEqualTo(10_101L);
        assertThat(watermarkReader.current()).isEqualTo(before + 1);
        fixture.sql("UPDATE source_change_watermark SET value = :value WHERE singleton_id = 1")
                .param("value", before).update();
    }

    @Test
    void reader_statements_are_single_selects_and_verifier_credentials_are_read_only() {
        assertThat(JdbcExpectedDocumentReader.PAGE_STATEMENT.stripLeading()).startsWith("SELECT");
        assertThat(JdbcExpectedDocumentReader.LOAD_STATEMENT.stripLeading()).startsWith("SELECT");
        assertThat(JdbcExpectedDocumentReader.PAGE_STATEMENT).doesNotContain(";");
        assertThat(JdbcExpectedDocumentReader.LOAD_STATEMENT).doesNotContain(";");

        JdbcClient verifier = JdbcClient.create(dataSource("verifier", "verifierpass"));
        assertThatThrownBy(() -> verifier.sql(
                "UPDATE source_change_watermark SET value = value WHERE singleton_id = 1").update())
                .rootCause()
                .hasMessageContaining("UPDATE command denied");
    }

    private void insertRows(int count) {
        for (int offset = 0; offset < count; offset++) {
            long id = BASE_ID + offset;
            fixture.sql("""
                    INSERT INTO products(id, sku, name, description, category_id, price_cents, status, updated_at)
                    VALUES (:id, :sku, :name, :description, :category, :price, 'ACTIVE',
                            '2026-07-22 02:03:04.123456')
                    """).param("id", id).param("sku", "VERIFY-" + id)
                    .param("name", "Product " + id).param("description", "Verifier fixture")
                    .param("category", BASE_ID).param("price", 10_000L + offset).update();
            fixture.sql("""
                    INSERT INTO inventory(product_id, available_quantity, reserved_quantity, updated_at)
                    VALUES (:id, :quantity, 0, '2026-07-22 03:04:05.123456')
                    """).param("id", id).param("quantity", offset).update();
            fixture.sql("""
                    INSERT INTO product_search_revision(product_id, revision, active, updated_at)
                    VALUES (:id, 1, TRUE, '2026-07-22 04:05:06.123456')
                    """).param("id", id).update();
        }
    }

    private void deactivate(long id, long revision, String timestamp) {
        fixture.sql("""
                UPDATE product_search_revision
                SET revision = :revision, active = FALSE, updated_at = :updatedAt
                WHERE product_id = :id
                """).param("revision", revision).param("updatedAt", timestamp).param("id", id).update();
    }

    private void removeBusinessRowsIgnoringForeignKeys(long productId) {
        try (Connection connection = DriverManager.getConnection(URL, "root", "rootpass")) {
            connection.createStatement().execute("SET FOREIGN_KEY_CHECKS = 0");
            try {
                try (var inventory = connection.prepareStatement(
                        "DELETE FROM inventory WHERE product_id = ?")) {
                    inventory.setLong(1, productId);
                    inventory.executeUpdate();
                }
                try (var product = connection.prepareStatement(
                        "DELETE FROM products WHERE id = ?")) {
                    product.setLong(1, productId);
                    product.executeUpdate();
                }
            } finally {
                connection.createStatement().execute("SET FOREIGN_KEY_CHECKS = 1");
            }
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }

    private DataSource dataSource(String username, String password) {
        return new DriverManagerDataSource(URL, username, password);
    }

    private static final class CountingReadOnlyDataSource extends AbstractDataSource {
        private final DataSource delegate;
        private final AtomicInteger connections = new AtomicInteger();

        private CountingReadOnlyDataSource(DataSource delegate) { this.delegate = delegate; }
        int connections() { return connections.get(); }
        void reset() { connections.set(0); }

        @Override public Connection getConnection() throws java.sql.SQLException {
            connections.incrementAndGet();
            return delegate.getConnection();
        }
        @Override public Connection getConnection(String username, String password) throws java.sql.SQLException {
            connections.incrementAndGet();
            return delegate.getConnection(username, password);
        }
    }
}
