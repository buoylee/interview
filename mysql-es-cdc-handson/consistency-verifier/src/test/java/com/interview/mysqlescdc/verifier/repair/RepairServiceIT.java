package com.interview.mysqlescdc.verifier.repair;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;

import javax.sql.DataSource;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.jdbc.datasource.DriverManagerDataSource;

import com.interview.mysqlescdc.verifier.diff.ReconciliationEngine;
import com.interview.mysqlescdc.verifier.run.JdbcVerificationRunStore;
import com.interview.mysqlescdc.verifier.run.VerificationRequest;
import com.interview.mysqlescdc.verifier.run.VerificationRunReport;
import com.interview.mysqlescdc.verifier.run.VerificationRunService;
import com.interview.mysqlescdc.verifier.run.VerificationRunStatus;
import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.source.IndependentExpectedProjector;
import com.interview.mysqlescdc.verifier.source.JdbcExpectedDocumentReader;
import com.interview.mysqlescdc.verifier.source.JdbcSourceWatermarkReader;
import com.interview.mysqlescdc.verifier.target.RestIndexedDocumentReader;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;
import tools.jackson.databind.json.JsonMapper;

class RepairServiceIT {
    private static final String MYSQL = "jdbc:mysql://localhost:3308/product_catalog"
            + "?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC";
    private static final String ES = "http://127.0.0.1:9200";
    private static final String INDEX = "products_repair_it";
    private static final long BASE = 7_200_000L;

    private final HttpClient http = HttpClient.newHttpClient();
    private final JsonMapper json = JsonMapper.builder().findAndAddModules().build();
    private JdbcClient fixture;
    private JdbcClient verifierJdbc;
    private VerificationRunService runs;
    private RepairService repairs;

    @BeforeEach
    void setUp() {
        fixture = JdbcClient.create(dataSource("root", "rootpass"));
        verifierJdbc = JdbcClient.create(dataSource("verifier", "verifierpass"));
        cleanupDatabase();
        deleteIndex();
        request("PUT", "/" + INDEX, """
                {"mappings":{"properties":{
                  "product_id":{"type":"long"},
                  "source_revision":{"type":"long"},
                  "source_updated_at":{"type":"date_nanos"},
                  "searchable":{"type":"boolean"}
                }}}
                """, 200);
        indexExistingSourceFacts();
        fixture.sql("""
                INSERT INTO categories(id, name, updated_at)
                VALUES (:id, 'Repair Category', '2026-07-22 01:00:00.123456')
                """).param("id", BASE).update();
        insertSource(BASE + 1, 2, true);
        insertSource(BASE + 2, 3, false);
        insertSource(BASE + 3, 4, true);
        insertSource(BASE + 4, 5, false);

        index(activeDocument(BASE + 2, 2), 2);
        ObjectNode wrongCategory = activeDocument(BASE + 3, 4);
        wrongCategory.put("category_name", "Wrong Category");
        index(wrongCategory, 4);
        index(activeDocument(BASE + 4, 5), 5);
        index(activeDocument(BASE + 99, 1), 1);
        request("POST", "/" + INDEX + "/_refresh", null, 200);

        JdbcVerificationRunStore store = new JdbcVerificationRunStore(verifierJdbc);
        var sourceReader = new JdbcExpectedDocumentReader(
                verifierJdbc, new IndependentExpectedProjector());
        var watermark = new JdbcSourceWatermarkReader(verifierJdbc);
        runs = new VerificationRunService(
                watermark, sourceReader,
                new RestIndexedDocumentReader(http, json, ES),
                new ReconciliationEngine(), store);
        repairs = new RepairService(
                store, watermark, sourceReader,
                new RestRepairGateway(http, json, ES), 100);
    }

    @AfterEach
    void tearDown() {
        if (fixture != null) cleanupDatabase();
        deleteIndex();
    }

    @Test
    void repairs_five_bounded_drift_classes_then_fresh_verification_passes_with_exact_versions() {
        VerificationRunReport drift = runs.run(new VerificationRequest(INDEX, 2));

        assertThat(drift.status()).isEqualTo(VerificationRunStatus.DIFF);
        assertThat(drift.differenceCount()).isEqualTo(5);
        RepairReport repaired = repairs.repair(drift.runId());

        assertThat(repaired.repaired()).isTrue();
        assertThat(repaired.applied()).isEqualTo(5);
        assertThat(fixture.sql("""
                SELECT status FROM verification_run WHERE run_id = UUID_TO_BIN(:runId)
                """).param("runId", drift.runId().toString()).query(String.class).single())
                .isEqualTo("REPAIRED");
        assertThat(fixture.sql("""
                SELECT COUNT(*) FROM repair_action
                WHERE run_id = UUID_TO_BIN(:runId) AND outcome = 'APPLIED'
                """).param("runId", drift.runId().toString()).query(Long.class).single())
                .isEqualTo(5);

        request("POST", "/" + INDEX + "/_refresh", null, 200);
        VerificationRunReport fresh = runs.run(new VerificationRequest(INDEX, 2));
        assertThat(fresh.status()).isEqualTo(VerificationRunStatus.PASS);
        assertThat(fresh.differenceCount()).isZero();
        assertVersion(BASE + 1, 2);
        assertVersion(BASE + 2, 3);
        assertVersion(BASE + 3, 4);
        assertVersion(BASE + 4, 5);
        assertThat(request("GET", "/" + INDEX + "/_doc/" + (BASE + 99), null, 200, 404))
                .contains("\"found\":false");
    }

    private void insertSource(long id, long revision, boolean active) {
        fixture.sql("""
                INSERT INTO products(id, sku, name, description, category_id, price_cents, status, updated_at)
                VALUES (:id, :sku, :name, 'Repair fixture', :category, :price,
                        :status, '2026-07-22 02:00:00.123456')
                """).param("id", id).param("sku", "REPAIR-" + id)
                .param("name", "Repair " + id).param("category", BASE)
                .param("price", 10_000L + id - BASE)
                .param("status", active ? "ACTIVE" : "DELETED").update();
        fixture.sql("""
                INSERT INTO inventory(product_id, available_quantity, reserved_quantity, updated_at)
                VALUES (:id, 7, 0, '2026-07-22 03:00:00.123456')
                """).param("id", id).update();
        fixture.sql("""
                INSERT INTO product_search_revision(product_id, revision, active, updated_at)
                VALUES (:id, :revision, :active, '2026-07-22 04:00:00.123456')
                """).param("id", id).param("revision", revision).param("active", active).update();
    }

    private ObjectNode activeDocument(long id, long revision) {
        ObjectNode body = json.createObjectNode();
        body.put("product_id", id);
        body.put("sku", "REPAIR-" + id);
        body.put("name", "Repair " + id);
        body.put("description", "Repair fixture");
        body.put("category_id", BASE);
        body.put("category_name", "Repair Category");
        body.put("price_cents", 10_000L + id - BASE);
        body.put("available_quantity", 7);
        body.put("searchable", true);
        body.put("source_revision", revision);
        body.put("source_updated_at", Instant.parse("2026-07-22T04:00:00.123456Z").toString());
        return body;
    }

    private void indexExistingSourceFacts() {
        var reader = new JdbcExpectedDocumentReader(
                verifierJdbc, new IndependentExpectedProjector());
        long cursor = 0;
        while (true) {
            var page = reader.readAfter(cursor, 100);
            for (ExpectedDocument document : page.documents()) {
                index(documentBody(document), document.sourceRevision());
            }
            if (page.complete()) return;
            cursor = page.nextExclusiveProductId();
        }
    }

    private ObjectNode documentBody(ExpectedDocument document) {
        ObjectNode body = json.createObjectNode();
        body.put("product_id", document.productId());
        if (document.searchable()) {
            body.put("sku", document.sku());
            body.put("name", document.name());
            body.put("description", document.description());
            body.put("category_id", document.categoryId());
            body.put("category_name", document.categoryName());
            body.put("price_cents", document.priceCents());
            body.put("available_quantity", document.availableQuantity());
        }
        body.put("searchable", document.searchable());
        body.put("source_revision", document.sourceRevision());
        body.put("source_updated_at", document.sourceUpdatedAt().toString());
        return body;
    }

    private void index(ObjectNode body, long version) {
        request("PUT", "/" + INDEX + "/_doc/" + body.path("product_id").longValue()
                + "?version=" + version + "&version_type=external", body.toString(), 200, 201);
    }

    private void assertVersion(long productId, long revision) {
        JsonNode hit = json.readTree(request(
                "GET", "/" + INDEX + "/_doc/" + productId, null, 200));
        assertThat(hit.path("_version").longValue()).isEqualTo(revision);
        assertThat(hit.path("_source").path("source_revision").longValue()).isEqualTo(revision);
    }

    private void cleanupDatabase() {
        fixture.sql("""
                DELETE ra FROM repair_action ra JOIN verification_run vr ON vr.run_id = ra.run_id
                WHERE vr.target_name = :target
                """).param("target", INDEX).update();
        fixture.sql("""
                DELETE vd FROM verification_difference vd JOIN verification_run vr ON vr.run_id = vd.run_id
                WHERE vr.target_name = :target
                """).param("target", INDEX).update();
        fixture.sql("DELETE FROM verification_run WHERE target_name = :target")
                .param("target", INDEX).update();
        fixture.sql("DELETE FROM product_search_revision WHERE product_id BETWEEN :first AND :last")
                .param("first", BASE).param("last", BASE + 200).update();
        fixture.sql("DELETE FROM inventory WHERE product_id BETWEEN :first AND :last")
                .param("first", BASE).param("last", BASE + 200).update();
        fixture.sql("DELETE FROM products WHERE id BETWEEN :first AND :last")
                .param("first", BASE).param("last", BASE + 200).update();
        fixture.sql("DELETE FROM categories WHERE id = :id").param("id", BASE).update();
    }

    private void deleteIndex() {
        request("DELETE", "/" + INDEX, null, 200, 404);
    }

    private DataSource dataSource(String user, String password) {
        return new DriverManagerDataSource(MYSQL, user, password);
    }

    private String request(String method, String path, String body, int... statuses) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(ES + path));
            if (body != null) builder.header("Content-Type", "application/json");
            builder.method(method, body == null
                    ? HttpRequest.BodyPublishers.noBody()
                    : HttpRequest.BodyPublishers.ofString(body));
            HttpResponse<String> response = http.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            assertThat(statuses).contains(response.statusCode());
            return response.body();
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }
}
