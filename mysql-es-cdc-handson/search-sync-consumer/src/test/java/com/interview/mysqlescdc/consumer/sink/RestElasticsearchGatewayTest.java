package com.interview.mysqlescdc.consumer.sink;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.List;
import java.util.concurrent.atomic.AtomicReference;

import com.interview.mysqlescdc.consumer.projection.SearchDocument;
import com.sun.net.httpserver.HttpServer;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.params.ParameterizedTest;
import org.junit.jupiter.params.provider.ValueSource;
import tools.jackson.databind.json.JsonMapper;

class RestElasticsearchGatewayTest {
    @ParameterizedTest
    @ValueSource(strings = {"products_search", "PRODUCTS_WRITE", "products_write/path", "products_write?x=1", "products_v3_20260728123456_DEADBEEF", "products_v3_20260728123456_deadbeef/_doc"})
    void rejects_unsafe_explicit_targets(String target) {
        var gateway = new RestElasticsearchGateway(request -> new BulkHttpResponse(200, "{\"items\":[]}"),
                JsonMapper.builder().build(), "http://localhost:9200", Duration.ofSeconds(1));
        assertThatThrownBy(() -> gateway.write(target, List.of()))
                .isInstanceOf(IllegalArgumentException.class)
                .hasMessage("unsafe Elasticsearch target");
    }
    private HttpServer server;
    private final AtomicReference<Response> response = new AtomicReference<>();
    private final AtomicReference<String> requestBody = new AtomicReference<>();
    private final AtomicReference<String> requestQuery = new AtomicReference<>();
    private final AtomicReference<String> requestContentType = new AtomicReference<>();
    private String baseUrl;

    @BeforeEach
    void startServer() throws IOException {
        server = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
        server.createContext("/_bulk", exchange -> {
            requestBody.set(new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8));
            requestQuery.set(exchange.getRequestURI().getRawQuery());
            requestContentType.set(exchange.getRequestHeaders().getFirst("Content-Type"));
            Response next = response.get();
            byte[] body = next.body().getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(next.status(), body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        baseUrl = "http://127.0.0.1:" + server.getAddress().getPort();
    }

    @AfterEach
    void stopServer() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    void builds_exact_ordered_external_version_ndjson_and_classifies_every_item() {
        response.set(new Response(200, """
                {"errors":true,"items":[
                  {"index":{"_id":"1","status":201,"result":"created","_version":4}},
                  {"index":{"_id":"2","status":409,"error":{"type":"version_conflict_engine_exception","reason":"stale"}}},
                  {"index":{"_id":"3","status":400,"error":{"type":"mapper_parsing_exception","reason":"bad field"}}},
                  {"index":{"_id":"4","status":429,"error":{"type":"es_rejected_execution_exception","reason":"rejected"}}},
                  {"index":{"_id":"5","status":409,"error":{"type":"illegal_argument_exception","reason":"alias conflict"}}}
                ]}
                """));
        List<SearchDocument> documents = List.of(document(1, 4), document(2, 8), document(3, 3), document(4, 6), document(5, 7));

        BulkWriteResult result = gateway(baseUrl).write("products_write", documents);

        assertThat(result.items()).extracting(BulkItemResult::outcome).containsExactly(
                BulkOutcome.APPLIED, BulkOutcome.STALE, BulkOutcome.PERMANENT_FAILURE,
                BulkOutcome.RETRYABLE_FAILURE, BulkOutcome.PERMANENT_FAILURE);
        assertThat(result.items()).extracting(BulkItemResult::productId).containsExactly(1L, 2L, 3L, 4L, 5L);
        assertThat(result.items()).extracting(BulkItemResult::revision).containsExactly(4L, 8L, 3L, 6L, 7L);
        assertThat(requestQuery.get()).isNull();
        assertThat(requestContentType.get()).isEqualTo("application/x-ndjson");
        String[] lines = requestBody.get().split("\n", -1);
        assertThat(lines).hasSize(11);
        assertThat(lines[10]).isEmpty();
        for (int index = 0; index < documents.size(); index++) {
            assertThat(lines[index * 2]).isEqualTo("{\"index\":{\"_index\":\"products_write\",\"_id\":\""
                    + documents.get(index).productId() + "\",\"version\":" + documents.get(index).sourceRevision()
                    + ",\"version_type\":\"external\"}}");
            assertThat(lines[index * 2 + 1]).contains("\"product_id\":" + documents.get(index).productId());
        }
    }

    @Test
    void classifies_every_retryable_status_boundary() {
        response.set(new Response(200, """
                {"items":[
                  {"index":{"status":408,"error":{"type":"timeout_exception"}}},
                  {"index":{"status":429,"error":{"type":"es_rejected_execution_exception"}}},
                  {"index":{"status":500,"error":{"type":"internal_server_error"}}},
                  {"index":{"status":599,"error":{"type":"unknown_server_error"}}}
                ]}
                """));

        BulkWriteResult result = gateway(baseUrl).write("products_write",
                List.of(document(1, 1), document(2, 2), document(3, 3), document(4, 4)));

        assertThat(result.items()).extracting(BulkItemResult::outcome)
                .containsOnly(BulkOutcome.RETRYABLE_FAILURE);
        assertThat(result.hasRetryableFailure()).isTrue();
    }

    @Test
    void rejects_malformed_missing_non_array_and_wrong_count_responses() {
        assertProtocol("not-json");
        assertProtocol("{}");
        assertProtocol("{\"items\":{}}");
        assertProtocol("{\"items\":[]}");
    }

    @Test
    void rejects_missing_action_missing_status_and_unknown_success_status() {
        assertProtocol("{\"items\":[{}]}");
        assertProtocol("{\"items\":[{\"index\":{}}]}");
        assertProtocol("{\"items\":[{\"index\":{\"status\":202}}]}");
        assertProtocol("{\"items\":[{\"index\":{\"status\":399}}]}");
    }

    @Test
    void non_2xx_and_transport_failures_are_explicit_transport_failures() {
        response.set(new Response(503, "{\"error\":\"unavailable\"}"));
        assertThatThrownBy(() -> gateway(baseUrl).write("products_write", List.of(document(1, 1))))
                .isInstanceOf(BulkTransportException.class);

        server.stop(0);
        assertThatThrownBy(() -> gateway(baseUrl).write("products_write", List.of(document(1, 1))))
                .isInstanceOf(BulkTransportException.class);
    }

    @Test
    void request_timeout_fails_as_transport_error_within_a_bound() {
        server.removeContext("/_bulk");
        server.createContext("/_bulk", exchange -> {
            try {
                Thread.sleep(2_000);
            } catch (InterruptedException exception) {
                Thread.currentThread().interrupt();
            }
            exchange.close();
        });
        RestElasticsearchGateway gateway = new RestElasticsearchGateway(
                HttpClient.newBuilder().connectTimeout(Duration.ofMillis(200)).build(),
                JsonMapper.builder().build(), baseUrl + "/", Duration.ofMillis(150));

        long started = System.nanoTime();
        assertThatThrownBy(() -> gateway.write("products_write", List.of(document(1, 1))))
                .isInstanceOf(BulkTransportException.class);
        assertThat(Duration.ofNanos(System.nanoTime() - started)).isLessThan(Duration.ofSeconds(1));
    }

    @Test
    void interrupted_send_restores_interrupt_flag_and_is_transport_failure() {
        RestElasticsearchGateway gateway = new RestElasticsearchGateway(
                request -> { throw new InterruptedException("stop"); },
                JsonMapper.builder().build(), baseUrl, Duration.ofSeconds(1));
        try {
            assertThatThrownBy(() -> gateway.write("products_write", List.of(document(1, 1))))
                    .isInstanceOf(BulkTransportException.class);
            assertThat(Thread.currentThread().isInterrupted()).isTrue();
        } finally {
            Thread.interrupted();
        }
    }

    @Test
    void trailing_slash_is_normalized_before_building_bulk_uri() {
        AtomicReference<HttpRequest> captured = new AtomicReference<>();
        RestElasticsearchGateway gateway = new RestElasticsearchGateway(request -> {
            captured.set(request);
            return new BulkHttpResponse(200, "{\"items\":[{\"index\":{\"status\":201}}]}");
        }, JsonMapper.builder().build(), "http://localhost:9200/", Duration.ofSeconds(1));

        gateway.write("products_write", List.of(document(1, 1)));

        assertThat(captured.get().uri().toString())
                .isEqualTo("http://localhost:9200/_bulk");
    }

    private void assertProtocol(String payload) {
        response.set(new Response(200, payload));
        assertThatThrownBy(() -> gateway(baseUrl).write("products_write", List.of(document(1, 1))))
                .isInstanceOf(BulkProtocolException.class);
    }

    private RestElasticsearchGateway gateway(String url) {
        return new RestElasticsearchGateway(HttpClient.newHttpClient(), JsonMapper.builder().build(), url);
    }

    private SearchDocument document(long id, long revision) {
        return new SearchDocument(id, "SKU-" + id, "Keyboard", "Mechanical", 10L,
                "Accessories", 12999L, 8, true, revision, Instant.parse("2026-07-22T01:02:03Z"));
    }

    private record Response(int status, String body) {}
}
