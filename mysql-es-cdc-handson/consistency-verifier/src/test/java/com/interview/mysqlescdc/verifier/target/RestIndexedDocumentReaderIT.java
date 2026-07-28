package com.interview.mysqlescdc.verifier.target;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.UUID;

import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import com.interview.mysqlescdc.verifier.diff.ConsistencyReport;
import com.interview.mysqlescdc.verifier.diff.DifferenceType;
import com.interview.mysqlescdc.verifier.diff.DocumentDifference;
import com.interview.mysqlescdc.verifier.diff.ReconciliationEngine;
import com.interview.mysqlescdc.verifier.diff.VerificationInput;
import com.interview.mysqlescdc.verifier.source.ExpectedDocument;

import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;

class RestIndexedDocumentReaderIT {
    private static final String ES = "http://127.0.0.1:9200";
    private static final String INDEX = "products_reconcile_it";
    private final HttpClient http = HttpClient.newHttpClient();
    private final JsonMapper json = JsonMapper.builder().findAndAddModules().build();
    private RestIndexedDocumentReader reader;

    @BeforeEach
    void setUp() {
        request("DELETE", "/" + INDEX, null, 200, 404);
        request("PUT", "/" + INDEX, """
                {"mappings":{"properties":{
                  "product_id":{"type":"long"},
                  "source_revision":{"type":"long"},
                  "source_updated_at":{"type":"date_nanos"},
                  "searchable":{"type":"boolean"}
                }}}
                """, 200);
        reader = new RestIndexedDocumentReader(http, json, ES);
    }

    @AfterEach
    void tearDown() {
        request("DELETE", "/" + INDEX, null, 200, 404);
    }

    @Test
    void pit_search_after_pages_of_two_feed_all_exact_classifications_and_close_on_success() {
        ExpectedDocument missing = expected(1, 1, true);
        ExpectedDocument modified = expected(3, 3, true);
        ExpectedDocument stale = expected(4, 4, true);
        ExpectedDocument future = expected(5, 5, true);
        ExpectedDocument tombstone = expected(6, 6, false);
        ExpectedDocument versionMismatch = expected(7, 7, true);
        ExpectedDocument exact = expected(8, 8, true);

        index(expected(2, 2, true), 2, null);
        index(modified, 3, "Wrong category");
        index(expected(4, 3, true), 3, null);
        index(expected(5, 6, true), 6, null);
        index(expected(6, 6, true), 6, null);
        index(versionMismatch, 99, null);
        index(exact, 8, null);
        request("POST", "/" + INDEX + "/_refresh", null, 200);

        long baselineContexts = openPitContexts();
        List<IndexedDocument> actual = new ArrayList<>();
        List<SearchAfterToken> tokens = new ArrayList<>();
        try (TargetCursor cursor = reader.open(INDEX)) {
            assertThat(openPitContexts()).isEqualTo(baselineContexts + 1);
            SearchAfterToken token = null;
            boolean complete;
            do {
                IndexedPage page = reader.readAfter(cursor, token, 2);
                actual.addAll(page.documents());
                token = page.nextToken();
                if (token != null) tokens.add(token);
                complete = page.complete();
            } while (!complete);
        }
        assertThat(openPitContexts()).isEqualTo(baselineContexts);
        assertThat(actual).extracting(IndexedDocument::productId)
                .containsExactly(2L, 3L, 4L, 5L, 6L, 7L, 8L);
        assertThat(tokens).allSatisfy(token -> assertThat(token.sortValues()).hasSize(2));
        assertThat(actual.getFirst().elasticsearchVersion()).isEqualTo(2);
        assertThat(actual.getFirst().sequenceNumber()).isNotNegative();
        assertThat(actual.getFirst().primaryTerm()).isPositive();

        List<DocumentDifference> differences = new ArrayList<>();
        ConsistencyReport report = new ReconciliationEngine().compare(new VerificationInput(
                UUID.randomUUID(), 77, 77,
                List.of(missing, modified, stale, future, tombstone, versionMismatch, exact).iterator(),
                actual.iterator(), differences::add));

        assertThat(differences).extracting(DocumentDifference::type).containsExactly(
                DifferenceType.MISSING,
                DifferenceType.EXTRA,
                DifferenceType.MODIFIED,
                DifferenceType.STALE,
                DifferenceType.FUTURE_REVISION,
                DifferenceType.TOMBSTONE_MISMATCH,
                DifferenceType.VERSION_METADATA_MISMATCH);
        assertThat(report.differenceCount()).isEqualTo(7);
    }

    @Test
    void search_failure_closes_the_real_pit_before_propagating() {
        index(expected(10, 10, true), 10, null);
        request("POST", "/" + INDEX + "/_refresh", null, 200);
        long baselineContexts = openPitContexts();
        TargetCursor cursor = reader.open(INDEX);
        assertThat(openPitContexts()).isEqualTo(baselineContexts + 1);
        SearchAfterToken invalidArity = new SearchAfterToken(
                List.of(json.valueToTree(10L)));

        assertThatThrownBy(() -> reader.readAfter(cursor, invalidArity, 2))
                .isInstanceOf(IllegalStateException.class)
                .hasMessageContaining("Elasticsearch search");

        assertThat(openPitContexts()).isEqualTo(baselineContexts);
        assertThat(cursor.closed()).isTrue();
    }

    @Test
    void filtered_serving_alias_is_rejected_before_opening_a_pit() {
        long baselineContexts = openPitContexts();

        assertThatThrownBy(() -> reader.open("products_search"))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessageContaining("filtered serving alias");

        assertThat(openPitContexts()).isEqualTo(baselineContexts);
    }

    private ExpectedDocument expected(long id, long revision, boolean searchable) {
        Instant updatedAt = Instant.parse("2026-07-22T03:04:05.123456Z");
        if (!searchable) return ExpectedDocument.tombstone(id, revision, updatedAt);
        return new ExpectedDocument(
                id, "SKU-" + id, "Product " + id, "Description " + id,
                10L, "Category 10", 1000L + id, 4, true, revision, updatedAt);
    }

    private void index(ExpectedDocument document, long version, String categoryNameOverride) {
        var body = json.createObjectNode();
        body.put("product_id", document.productId());
        putNullable(body, "sku", document.sku());
        putNullable(body, "name", document.name());
        putNullable(body, "description", document.description());
        putNullable(body, "category_id", document.categoryId());
        putNullable(body, "category_name",
                categoryNameOverride == null ? document.categoryName() : categoryNameOverride);
        putNullable(body, "price_cents", document.priceCents());
        putNullable(body, "available_quantity", document.availableQuantity());
        body.put("searchable", document.searchable());
        body.put("source_revision", document.sourceRevision());
        body.put("source_updated_at", document.sourceUpdatedAt().toString());
        request("PUT", "/" + INDEX + "/_doc/" + document.productId()
                + "?version=" + version + "&version_type=external", body.toString(), 200, 201);
    }

    private void putNullable(tools.jackson.databind.node.ObjectNode body, String field, Object value) {
        if (value == null) body.putNull(field);
        else if (value instanceof String text) body.put(field, text);
        else if (value instanceof Long number) body.put(field, number);
        else if (value instanceof Integer number) body.put(field, number);
        else throw new IllegalArgumentException("unsupported fixture scalar");
    }

    private long openPitContexts() {
        JsonNode root = json.readTree(request("GET", "/_nodes/stats/indices/search", null, 200));
        long total = 0;
        for (JsonNode node : root.path("nodes")) {
            total += node.path("indices").path("search").path("open_contexts").longValue();
        }
        return total;
    }

    private String request(String method, String path, String body, int... expectedStatuses) {
        try {
            HttpRequest.Builder builder = HttpRequest.newBuilder(URI.create(ES + path));
            if (body != null) builder.header("Content-Type", "application/json");
            builder.method(method, body == null
                    ? HttpRequest.BodyPublishers.noBody()
                    : HttpRequest.BodyPublishers.ofString(body));
            HttpResponse<String> response = http.send(builder.build(), HttpResponse.BodyHandlers.ofString());
            assertThat(expectedStatuses).contains(response.statusCode());
            return response.body();
        } catch (Exception exception) {
            throw new IllegalStateException(exception);
        }
    }
}
