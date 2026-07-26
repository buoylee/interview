package com.interview.mysqlescdc.product.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;

import com.interview.mysqlescdc.product.api.ProductRequests.CreateProductRequest;

@SpringBootTest
@ActiveProfiles("integration")
class ProductMutationServiceIT {
    @Autowired ProductMutationService service;
    @Autowired JdbcClient jdbc;

    @BeforeEach
    void cleanProducts() {
        jdbc.sql("DELETE FROM product_search_revision").update();
        jdbc.sql("DELETE FROM inventory").update();
        jdbc.sql("DELETE FROM products").update();
    }

    @Test
    void all_search_relevant_changes_advance_one_revision() {
        assertThat(service.createProduct(new CreateProductRequest(
                1001L, "SKU-1001", "Keyboard", "Mechanical", 10L, 12999L))).isEqualTo(1L);
        assertThat(service.createProduct(new CreateProductRequest(
                1002L, "SKU-1002", "Mouse", "Wireless", 10L, 4999L))).isEqualTo(1L);
        assertThat(service.createProduct(new CreateProductRequest(
                2001L, "SKU-2001", "SSD", "NVMe", 20L, 15999L))).isEqualTo(1L);
        assertThat(service.replaceInventory(1001L, 8, 2)).isEqualTo(2L);
        assertThat(service.changePrice(1001L, 11999L)).isEqualTo(3L);
        assertThat(service.renameCategory(10L, "Computer Accessories")).isEqualTo(2);
        assertThat(revision(1001L)).isEqualTo(4L);
        assertThat(revision(1002L)).isEqualTo(2L);
        assertThat(revision(2001L)).isEqualTo(1L);
        assertThat(service.deleteProduct(1001L)).isEqualTo(5L);
        assertThat(active(1001L)).isFalse();
    }

    @Test
    void a_failed_business_write_rolls_back_its_revision() {
        service.createProduct(new CreateProductRequest(
                1001L, "DUPLICATE", "Keyboard", "Mechanical", 10L, 12999L));

        assertThatThrownBy(() -> service.createProduct(new CreateProductRequest(
                1002L, "DUPLICATE", "Mouse", "Wireless", 10L, 4999L)))
                .isInstanceOf(RuntimeException.class);

        assertThat(jdbc.sql("SELECT COUNT(*) FROM products WHERE id = 1002")
                .query(Long.class).single()).isZero();
        assertThat(jdbc.sql("SELECT COUNT(*) FROM product_search_revision WHERE product_id = 1002")
                .query(Long.class).single()).isZero();
    }

    @Test
    void inventory_mutation_after_delete_rolls_back_without_advancing_revision() {
        service.createProduct(new CreateProductRequest(
                1001L, "SKU-1001", "Keyboard", "Mechanical", 10L, 12999L));
        assertThat(service.deleteProduct(1001L)).isEqualTo(2L);

        assertThatThrownBy(() -> service.replaceInventory(1001L, 8, 2))
                .isInstanceOf(RuntimeException.class);

        assertThat(availableInventory(1001L)).isZero();
        assertThat(reservedInventory(1001L)).isZero();
        assertThat(revision(1001L)).isEqualTo(2L);
    }

    private long revision(long productId) {
        return jdbc.sql("SELECT revision FROM product_search_revision WHERE product_id = :id")
                .param("id", productId).query(Long.class).single();
    }

    private boolean active(long productId) {
        return jdbc.sql("SELECT active FROM product_search_revision WHERE product_id = :id")
                .param("id", productId).query(Boolean.class).single();
    }

    private int availableInventory(long productId) {
        return jdbc.sql("SELECT available_quantity FROM inventory WHERE product_id = :id")
                .param("id", productId).query(Integer.class).single();
    }

    private int reservedInventory(long productId) {
        return jdbc.sql("SELECT reserved_quantity FROM inventory WHERE product_id = :id")
                .param("id", productId).query(Integer.class).single();
    }
}
