package com.interview.mysqlescdc.consumer.source;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.sql.Connection;
import java.lang.reflect.InvocationTargetException;
import java.lang.reflect.Proxy;
import java.time.Instant;
import java.util.concurrent.atomic.AtomicInteger;

import javax.sql.DataSource;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DelegatingDataSource;
import org.springframework.jdbc.datasource.SimpleDriverDataSource;

import com.mysql.cj.jdbc.Driver;

class JdbcSourceSnapshotRepositoryIT {
    private static final long PRODUCT_ID = 22101L;
    private static final long CATEGORY_ID = 22100L;
    private static final String JDBC_URL =
            "jdbc:mysql://127.0.0.1:3308/product_catalog"
                    + "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC";

    private JdbcClient jdbc;
    private SourceSnapshotRepository repository;
    private DataSource dataSource;

    @BeforeEach
    void setUp() throws Exception {
        dataSource = new SimpleDriverDataSource(
                new Driver(), JDBC_URL, "product", "productpass");
        jdbc = JdbcClient.create(dataSource);
        repository = new JdbcSourceSnapshotRepository(jdbc);
        clean();
        jdbc.sql("""
                INSERT INTO categories (id, name, updated_at)
                VALUES (:id, 'Accessories', '2026-07-22 01:00:00.111111')
                """).param("id", CATEGORY_ID).update();
    }

    @AfterEach
    void tearDown() {
        clean();
    }

    @Test
    void loads_every_active_field_and_observes_category_and_inventory_changes() {
        insertActiveProduct();

        assertThat(repository.load(PRODUCT_ID)).contains(SourceProductSnapshot.active(
                PRODUCT_ID, "SKU-22101", "Keyboard", "Mechanical",
                CATEGORY_ID, "Accessories", 12999L, 8, 1L,
                Instant.parse("2026-07-22T01:02:03.444444Z")));

        jdbc.sql("UPDATE categories SET name = 'Computer Accessories', "
                + "updated_at = '2026-07-22 01:04:05.555555' WHERE id = :id")
                .param("id", CATEGORY_ID).update();
        jdbc.sql("UPDATE inventory SET available_quantity = 13, "
                + "updated_at = '2026-07-22 01:05:06.666666' WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();
        jdbc.sql("UPDATE product_search_revision SET revision = 2, "
                + "updated_at = '2026-07-22 01:05:06.777777' WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();

        assertThat(repository.load(PRODUCT_ID)).contains(SourceProductSnapshot.active(
                PRODUCT_ID, "SKU-22101", "Keyboard", "Mechanical",
                CATEGORY_ID, "Computer Accessories", 12999L, 13, 2L,
                Instant.parse("2026-07-22T01:05:06.777777Z")));
    }

    @Test
    void maps_an_inactive_row_to_a_timestamp_exact_tombstone_source() {
        insertActiveProduct();
        jdbc.sql("UPDATE products SET status = 'DELETED', "
                + "updated_at = '2026-07-22 02:03:04.111111' WHERE id = :id")
                .param("id", PRODUCT_ID).update();
        jdbc.sql("UPDATE product_search_revision SET active = FALSE, revision = 3, "
                + "updated_at = '2026-07-22 02:03:04.123456' WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();

        assertThat(repository.load(PRODUCT_ID)).contains(SourceProductSnapshot.inactive(
                PRODUCT_ID, 3L, Instant.parse("2026-07-22T02:03:04.123456Z")));
    }

    @Test
    void inactive_snapshot_uses_revision_timestamp_when_a_business_join_is_missing() {
        insertActiveProduct();
        jdbc.sql("UPDATE product_search_revision SET active = FALSE, revision = 3, "
                + "updated_at = '2026-07-22 02:03:04.123456' WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();
        jdbc.sql("DELETE FROM inventory WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();

        assertThat(repository.load(PRODUCT_ID)).contains(SourceProductSnapshot.inactive(
                PRODUCT_ID, 3L, Instant.parse("2026-07-22T02:03:04.123456Z")));
    }

    @Test
    void inactive_snapshot_ignores_later_business_timestamps() {
        insertActiveProduct();
        jdbc.sql("UPDATE product_search_revision SET active = FALSE, revision = 3, "
                + "updated_at = '2026-07-22 02:03:04.123456' WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();
        jdbc.sql("UPDATE products SET updated_at = '2026-07-22 03:04:05.654321' WHERE id = :id")
                .param("id", PRODUCT_ID).update();

        assertThat(repository.load(PRODUCT_ID)).contains(SourceProductSnapshot.inactive(
                PRODUCT_ID, 3L, Instant.parse("2026-07-22T02:03:04.123456Z")));
    }

    @Test
    void returns_empty_when_the_revision_row_is_truly_missing() {
        assertThat(repository.load(PRODUCT_ID)).isEmpty();
    }

    @Test
    void fails_closed_when_an_active_revision_has_an_incomplete_join() {
        insertActiveProduct();
        jdbc.sql("DELETE FROM inventory WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();

        assertThatThrownBy(() -> repository.load(PRODUCT_ID))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("incomplete active source snapshot")
                .hasMessageContaining(Long.toString(PRODUCT_ID));
    }

    @Test
    void load_executes_exactly_one_select_statement() {
        insertActiveProduct();
        AtomicInteger selectCount = new AtomicInteger();
        SourceSnapshotRepository countedRepository = new JdbcSourceSnapshotRepository(
                JdbcClient.create(countingDataSource(dataSource, selectCount)));
        assertThat(JdbcSourceSnapshotRepository.SELECT_STATEMENT)
                .as("one statement, without semicolon-separated query assembly")
                .startsWith("SELECT")
                .doesNotContain(";");
        assertThat(countedRepository.load(PRODUCT_ID)).isPresent();
        assertThat(selectCount).hasValue(1);
    }

    private void insertActiveProduct() {
        jdbc.sql("""
                INSERT INTO products
                    (id, sku, name, description, category_id, price_cents, status, updated_at)
                VALUES
                    (:id, 'SKU-22101', 'Keyboard', 'Mechanical', :categoryId, 12999,
                     'ACTIVE', '2026-07-22 01:02:03.222222')
                """).param("id", PRODUCT_ID).param("categoryId", CATEGORY_ID).update();
        jdbc.sql("""
                INSERT INTO inventory
                    (product_id, available_quantity, reserved_quantity, updated_at)
                VALUES (:id, 8, 0, '2026-07-22 01:02:03.333333')
                """).param("id", PRODUCT_ID).update();
        jdbc.sql("""
                INSERT INTO product_search_revision (product_id, revision, active, updated_at)
                VALUES (:id, 1, TRUE, '2026-07-22 01:02:03.444444')
                """).param("id", PRODUCT_ID).update();
    }

    private void clean() {
        if (jdbc == null) {
            return;
        }
        jdbc.sql("DELETE FROM product_search_revision WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();
        jdbc.sql("DELETE FROM inventory WHERE product_id = :id")
                .param("id", PRODUCT_ID).update();
        jdbc.sql("DELETE FROM products WHERE id = :id")
                .param("id", PRODUCT_ID).update();
        jdbc.sql("DELETE FROM categories WHERE id = :id")
                .param("id", CATEGORY_ID).update();
    }

    private static DataSource countingDataSource(DataSource delegate, AtomicInteger selectCount) {
        return new DelegatingDataSource(delegate) {
            @Override
            public Connection getConnection() throws java.sql.SQLException {
                Connection connection = super.getConnection();
                return (Connection) Proxy.newProxyInstance(
                        Connection.class.getClassLoader(),
                        new Class<?>[] {Connection.class},
                        (proxy, method, arguments) -> {
                            if ("prepareStatement".equals(method.getName())
                                    && arguments != null
                                    && arguments.length > 0
                                    && arguments[0] instanceof String sql
                                    && sql.stripLeading().startsWith("SELECT")) {
                                selectCount.incrementAndGet();
                            }
                            try {
                                return method.invoke(connection, arguments);
                            } catch (InvocationTargetException exception) {
                                throw exception.getCause();
                            }
                        });
            }
        };
    }
}
