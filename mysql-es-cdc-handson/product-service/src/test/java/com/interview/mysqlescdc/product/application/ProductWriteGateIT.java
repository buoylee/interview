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
class ProductWriteGateIT {
    @Autowired ProductMutationService mutations;
    @Autowired JdbcClient jdbc;

    @BeforeEach void reset() {
        jdbc.sql("UPDATE product_write_gate SET closed=FALSE,owner_run_id=NULL,reason=NULL WHERE singleton_id=1").update();
        jdbc.sql("DELETE FROM product_search_revision").update();
        jdbc.sql("DELETE FROM inventory").update();
        jdbc.sql("DELETE FROM products").update();
    }
    @Test void closed_gate_fails_before_facts_revision_or_watermark_change() {
        long before = jdbc.sql("SELECT value FROM source_change_watermark WHERE singleton_id=1").query(Long.class).single();
        jdbc.sql("UPDATE product_write_gate SET closed=TRUE,owner_run_id=UUID_TO_BIN(UUID()),reason='cutover' WHERE singleton_id=1").update();
        assertThatThrownBy(() -> mutations.createProduct(new CreateProductRequest(88001,"M5-1","x","",10,1)))
                .isInstanceOf(WriteGateClosedException.class);
        assertThat(jdbc.sql("SELECT COUNT(*) FROM products WHERE id=88001").query(Long.class).single()).isZero();
        assertThat(jdbc.sql("SELECT COUNT(*) FROM product_search_revision WHERE product_id=88001").query(Long.class).single()).isZero();
        assertThat(jdbc.sql("SELECT value FROM source_change_watermark WHERE singleton_id=1").query(Long.class).single()).isEqualTo(before);
    }
}
