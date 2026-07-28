package com.interview.mysqlescdc.product.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.server.LocalServerPort;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;
import com.interview.mysqlescdc.product.api.ProductRequests.CreateProductRequest;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("integration")
class ProductWriteGateIT {
    @Autowired ProductMutationService mutations;
    @Autowired JdbcClient jdbc;
    @LocalServerPort int port;

    @BeforeEach void reset() {
        jdbc.sql("UPDATE product_write_gate SET closed=FALSE,owner_run_id=NULL,reason=NULL WHERE singleton_id=1").update();
        jdbc.sql("DELETE FROM product_search_revision").update();
        jdbc.sql("DELETE FROM inventory").update();
        jdbc.sql("DELETE FROM products").update();
    }
    @AfterEach void reopen() {
        jdbc.sql("UPDATE product_write_gate SET closed=FALSE,owner_run_id=NULL,reason=NULL WHERE singleton_id=1").update();
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
    @Test void every_http_mutation_returns_exact_503_body_and_changes_no_related_fact() throws Exception {
        mutations.createProduct(new CreateProductRequest(88002,"M5-2","x","",10,10));
        String before=snapshot();
        jdbc.sql("UPDATE product_write_gate SET closed=TRUE,owner_run_id=UUID_TO_BIN(UUID()),reason='cutover' WHERE singleton_id=1").update();
        HttpClient client=HttpClient.newHttpClient();
        for (HttpRequest request : new HttpRequest[]{
                request("POST","/api/products","{\"id\":88003,\"sku\":\"M5-3\",\"name\":\"x\",\"description\":\"\",\"categoryId\":10,\"priceCents\":1}"),
                request("PUT","/api/products/88002/price","{\"priceCents\":99}"),
                request("PUT","/api/products/88002/inventory","{\"availableQuantity\":5,\"reservedQuantity\":1}"),
                request("PUT","/api/categories/10","{\"name\":\"changed\"}"),
                request("DELETE","/api/products/88002",null)}) {
            HttpResponse<String> response=client.send(request,HttpResponse.BodyHandlers.ofString());
            assertThat(response.statusCode()).isEqualTo(503);
            assertThat(response.body()).contains("\"code\":\"PRODUCT_WRITES_PAUSED\"").contains("\"retryable\":true");
            assertThat(snapshot()).isEqualTo(before);
        }
    }
    private HttpRequest request(String method,String path,String body) {
        HttpRequest.BodyPublisher publisher=body==null?HttpRequest.BodyPublishers.noBody():HttpRequest.BodyPublishers.ofString(body);
        return HttpRequest.newBuilder(URI.create("http://127.0.0.1:"+port+path)).header("Content-Type","application/json").method(method,publisher).build();
    }
    private String snapshot() {
        return jdbc.sql("""
                SELECT CONCAT_WS('|',
                  (SELECT COUNT(*) FROM products),(SELECT COALESCE(SUM(price_cents),0) FROM products),
                  (SELECT COUNT(*) FROM inventory),(SELECT COALESCE(SUM(available_quantity+reserved_quantity),0) FROM inventory),
                  (SELECT COUNT(*) FROM categories),(SELECT GROUP_CONCAT(name ORDER BY id) FROM categories),
                  (SELECT COUNT(*) FROM product_search_revision),(SELECT COALESCE(SUM(revision),0) FROM product_search_revision),
                  (SELECT value FROM source_change_watermark WHERE singleton_id=1))
                """).query(String.class).single();
    }
}
