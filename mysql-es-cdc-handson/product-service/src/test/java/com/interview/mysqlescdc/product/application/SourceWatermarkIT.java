package com.interview.mysqlescdc.product.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;

import com.interview.mysqlescdc.product.api.ProductRequests.CreateProductRequest;

@SpringBootTest
class SourceWatermarkIT {
    @Autowired ProductMutationService service;
    @Autowired JdbcClient jdbc;

    @BeforeEach
    void resetFactsAndWatermark() {
        jdbc.sql("DELETE FROM product_search_revision").update();
        jdbc.sql("DELETE FROM inventory").update();
        jdbc.sql("DELETE FROM products").update();
        jdbc.sql("UPDATE categories SET name = 'Accessories' WHERE id = 10").update();
        jdbc.sql("""
                INSERT INTO source_change_watermark(singleton_id, value)
                VALUES (1, 0)
                ON DUPLICATE KEY UPDATE value = 0
                """).update();
    }

    @Test
    void every_supported_committed_mutation_advances_exactly_once() {
        assertAdvanceOnce(() -> service.createProduct(product(1001L, "SKU-1001")));
        assertAdvanceOnce(() -> service.changePrice(1001L, 11998L));
        assertAdvanceOnce(() -> service.replaceInventory(1001L, 8, 2));
        assertAdvanceOnce(() -> service.deleteProduct(1001L));
    }

    @Test
    void category_fan_out_advances_once_for_the_whole_transaction() {
        service.createProduct(product(1001L, "SKU-1001"));
        service.createProduct(product(1002L, "SKU-1002"));
        long revisionOne = revision(1001L);
        long revisionTwo = revision(1002L);

        assertAdvanceOnce(() -> assertThat(service.renameCategory(10L, "Input Devices")).isEqualTo(2));

        assertThat(revision(1001L)).isEqualTo(revisionOne + 1);
        assertThat(revision(1002L)).isEqualTo(revisionTwo + 1);
    }

    @Test
    void explicit_failure_rolls_back_fact_revision_and_watermark() {
        service.createProduct(product(1001L, "SKU-1001"));
        long beforeWatermark = watermark();
        long beforeRevision = revision(1001L);
        long beforePrice = price(1001L);

        assertThatThrownBy(() -> service.changePriceAndFailForTest(1001L, 11997L))
                .isInstanceOf(IllegalStateException.class);

        assertThat(watermark()).isEqualTo(beforeWatermark);
        assertThat(revision(1001L)).isEqualTo(beforeRevision);
        assertThat(price(1001L)).isEqualTo(beforePrice);
    }

    @Test
    void missing_singleton_fails_and_rolls_back_the_business_transaction() {
        service.createProduct(product(1001L, "SKU-1001"));
        long beforeRevision = revision(1001L);
        long beforePrice = price(1001L);
        jdbc.sql("DELETE FROM source_change_watermark WHERE singleton_id = 1").update();

        assertThatThrownBy(() -> service.changePrice(1001L, 11996L))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("source_change_watermark singleton");

        assertThat(revision(1001L)).isEqualTo(beforeRevision);
        assertThat(price(1001L)).isEqualTo(beforePrice);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM source_change_watermark")
                .query(Long.class).single()).isZero();
    }

    private void assertAdvanceOnce(Runnable mutation) {
        long before = watermark();
        mutation.run();
        assertThat(watermark()).isEqualTo(before + 1L);
    }

    private CreateProductRequest product(long id, String sku) {
        return new CreateProductRequest(id, sku, "Keyboard", "Mechanical", 10L, 12999L);
    }

    private long watermark() {
        return jdbc.sql("SELECT value FROM source_change_watermark WHERE singleton_id = 1")
                .query(Long.class).single();
    }

    private long revision(long productId) {
        return jdbc.sql("SELECT revision FROM product_search_revision WHERE product_id = :id")
                .param("id", productId).query(Long.class).single();
    }

    private long price(long productId) {
        return jdbc.sql("SELECT price_cents FROM products WHERE id = :id")
                .param("id", productId).query(Long.class).single();
    }
}
