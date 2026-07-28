package com.interview.mysqlescdc.product.application;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.interview.mysqlescdc.product.api.ProductRequests.CreateProductRequest;

@Service
public class ProductMutationService {
    private final JdbcClient jdbc;

    public ProductMutationService(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public long createProduct(CreateProductRequest request) {
        jdbc.sql("""
                INSERT INTO products
                    (id, sku, name, description, category_id, price_cents, status)
                VALUES
                    (:id, :sku, :name, :description, :categoryId, :priceCents, 'ACTIVE')
                """)
                .param("id", request.id())
                .param("sku", request.sku())
                .param("name", request.name())
                .param("description", request.description() == null ? "" : request.description())
                .param("categoryId", request.categoryId())
                .param("priceCents", request.priceCents())
                .update();
        jdbc.sql("""
                INSERT INTO inventory
                    (product_id, available_quantity, reserved_quantity)
                VALUES (:id, 0, 0)
                """).param("id", request.id()).update();
        jdbc.sql("""
                INSERT INTO product_search_revision (product_id, revision, active)
                VALUES (:id, 1, TRUE)
                """).param("id", request.id()).update();
        advanceSourceWatermark();
        return 1L;
    }

    @Transactional
    public long changePrice(long productId, long priceCents) {
        requireOne(jdbc.sql("""
                UPDATE products SET price_cents = :price
                WHERE id = :id AND status = 'ACTIVE'
                """).param("price", priceCents).param("id", productId).update(), productId);
        long revision = bump(productId);
        advanceSourceWatermark();
        return revision;
    }

    @Transactional
    public long replaceInventory(long productId, int available, int reserved) {
        requireOne(jdbc.sql("""
                UPDATE inventory i
                JOIN products p ON p.id = i.product_id
                SET i.available_quantity = :available, i.reserved_quantity = :reserved
                WHERE i.product_id = :id AND p.status = 'ACTIVE'
                """).param("available", available).param("reserved", reserved)
                .param("id", productId).update(), productId);
        long revision = bump(productId);
        advanceSourceWatermark();
        return revision;
    }

    @Transactional
    public int renameCategory(long categoryId, String name) {
        requireOne(jdbc.sql("UPDATE categories SET name = :name WHERE id = :id")
                .param("name", name).param("id", categoryId).update(), categoryId);
        int affectedProducts = jdbc.sql("""
                UPDATE product_search_revision r
                JOIN products p ON p.id = r.product_id
                SET r.revision = r.revision + 1,
                    r.updated_at = CURRENT_TIMESTAMP(6)
                WHERE p.category_id = :categoryId AND r.active = TRUE
                """).param("categoryId", categoryId).update();
        advanceSourceWatermark();
        return affectedProducts;
    }

    @Transactional
    public long deleteProduct(long productId) {
        requireOne(jdbc.sql("""
                UPDATE products SET status = 'DELETED'
                WHERE id = :id AND status = 'ACTIVE'
                """).param("id", productId).update(), productId);
        jdbc.sql("""
                UPDATE product_search_revision
                SET revision = revision + 1, active = FALSE
                WHERE product_id = :id
                """).param("id", productId).update();
        long revision = currentRevision(productId);
        advanceSourceWatermark();
        return revision;
    }

    @Transactional
    long changePriceAndFailForTest(long productId, long priceCents) {
        requireOne(jdbc.sql("""
                UPDATE products SET price_cents = :price
                WHERE id = :id AND status = 'ACTIVE'
                """).param("price", priceCents).param("id", productId).update(), productId);
        bump(productId);
        advanceSourceWatermark();
        throw new IllegalStateException("test-only rollback after watermark advance");
    }

    private long bump(long productId) {
        requireOne(jdbc.sql("""
                UPDATE product_search_revision
                SET revision = revision + 1
                WHERE product_id = :id AND active = TRUE
                """).param("id", productId).update(), productId);
        return currentRevision(productId);
    }

    private long currentRevision(long productId) {
        return jdbc.sql("""
                SELECT revision FROM product_search_revision WHERE product_id = :id
                """).param("id", productId).query(Long.class).single();
    }

    private void advanceSourceWatermark() {
        int changed = jdbc.sql("""
                UPDATE source_change_watermark
                SET value = value + 1
                WHERE singleton_id = 1
                """).update();
        if (changed != 1) {
            throw new IllegalStateException("source_change_watermark singleton is missing");
        }
    }

    private static void requireOne(int count, long id) {
        if (count != 1) {
            throw new IllegalArgumentException("resource not found or inactive: " + id);
        }
    }
}
