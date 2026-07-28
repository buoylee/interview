package com.interview.mysqlescdc.verifier.repair;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.util.Objects;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.verifier.source.ExpectedDocument;
import com.interview.mysqlescdc.verifier.target.IndexedDocument;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;
import tools.jackson.databind.json.JsonMapper;

@Component
public final class RestRepairGateway implements RepairGateway {
    private static final Duration TIMEOUT = Duration.ofSeconds(10);
    private final HttpClient http;
    private final JsonMapper json;
    private final String baseUrl;

    @Autowired
    public RestRepairGateway(@Value("${verification.elasticsearch-url}") String baseUrl) {
        this(HttpClient.newBuilder().connectTimeout(TIMEOUT).build(),
                JsonMapper.builder().findAndAddModules().build(), baseUrl);
    }

    public RestRepairGateway(HttpClient http, JsonMapper json, String baseUrl) {
        this.http = Objects.requireNonNull(http, "http");
        this.json = Objects.requireNonNull(json, "json");
        this.baseUrl = Objects.requireNonNull(baseUrl, "baseUrl").replaceAll("/+$", "");
    }

    @Override
    public RepairOutcome write(
            String target, RepairActionType type, ExpectedDocument document) {
        if (type != RepairActionType.WRITE_EXTERNAL
                && type != RepairActionType.WRITE_EXTERNAL_GTE) {
            throw new IllegalArgumentException("write repair type required");
        }
        String versionType = type == RepairActionType.WRITE_EXTERNAL
                ? "external" : "external_gte";
        ObjectNode action = json.createObjectNode();
        ObjectNode index = action.putObject("index");
        index.put("_index", safeTarget(target));
        index.put("_id", Long.toString(document.productId()));
        index.put("version", document.sourceRevision());
        index.put("version_type", versionType);
        String body = serialize(action) + "\n" + serialize(documentBody(document)) + "\n";
        HttpResponse<String> response = send(HttpRequest.newBuilder(uri("/_bulk?require_alias=false"))
                .header("Content-Type", "application/x-ndjson")
                .timeout(TIMEOUT)
                .POST(HttpRequest.BodyPublishers.ofString(body)).build());
        requireHttpSuccess(response, "repair Bulk");
        JsonNode item = parse(response.body()).path("items").path(0).path("index");
        if (!item.isObject() || !item.path("status").isIntegralNumber()) {
            throw new IllegalStateException("repair Bulk item is malformed");
        }
        int status = item.path("status").intValue();
        if (status == 200 || status == 201) return RepairOutcome.APPLIED;
        if (status == 409 && type == RepairActionType.WRITE_EXTERNAL) return RepairOutcome.STALE;
        throw new IllegalStateException(
                "repair Bulk item failed with status " + status + " for " + versionType);
    }

    @Override
    public RepairOutcome deleteExtra(String target, IndexedDocument observed) {
        String path = "/" + safeTarget(target) + "/_doc/" + observed.productId()
                + "?if_seq_no=" + observed.sequenceNumber()
                + "&if_primary_term=" + observed.primaryTerm();
        HttpResponse<String> response = send(HttpRequest.newBuilder(uri(path))
                .timeout(TIMEOUT).DELETE().build());
        if (response.statusCode() == 200 || response.statusCode() == 404) {
            return RepairOutcome.APPLIED;
        }
        if (response.statusCode() == 409) {
            throw new IllegalStateException("conditional delete conflict requires new verification");
        }
        throw new IllegalStateException("conditional delete failed with HTTP " + response.statusCode());
    }

    private ObjectNode documentBody(ExpectedDocument document) {
        ObjectNode body = json.createObjectNode();
        body.put("product_id", document.productId());
        put(body, "sku", document.sku());
        put(body, "name", document.name());
        put(body, "description", document.description());
        put(body, "category_id", document.categoryId());
        put(body, "category_name", document.categoryName());
        put(body, "price_cents", document.priceCents());
        put(body, "available_quantity", document.availableQuantity());
        body.put("searchable", document.searchable());
        body.put("source_revision", document.sourceRevision());
        body.put("source_updated_at", document.sourceUpdatedAt().toString());
        return body;
    }

    private void put(ObjectNode body, String field, Object value) {
        if (value == null) body.putNull(field);
        else if (value instanceof String text) body.put(field, text);
        else if (value instanceof Long number) body.put(field, number);
        else if (value instanceof Integer number) body.put(field, number);
        else throw new IllegalArgumentException("unsupported repair scalar");
    }

    private String safeTarget(String target) {
        if (target == null || !target.matches("[a-z0-9._-]+") || "products_search".equals(target)) {
            throw new IllegalArgumentException("safe unfiltered repair target required");
        }
        return URLEncoder.encode(target, StandardCharsets.UTF_8);
    }

    private HttpResponse<String> send(HttpRequest request) {
        try {
            return http.send(request, HttpResponse.BodyHandlers.ofString());
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException("repair request interrupted", exception);
        } catch (IOException exception) {
            throw new IllegalStateException("repair request failed", exception);
        }
    }

    private void requireHttpSuccess(HttpResponse<String> response, String operation) {
        if (response.statusCode() < 200 || response.statusCode() >= 300) {
            throw new IllegalStateException(operation + " failed with HTTP " + response.statusCode());
        }
    }

    private JsonNode parse(String payload) {
        try {
            return json.readTree(payload);
        } catch (JacksonException exception) {
            throw new IllegalStateException("invalid repair response JSON", exception);
        }
    }

    private String serialize(Object value) {
        try {
            return json.writeValueAsString(value);
        } catch (JacksonException exception) {
            throw new IllegalArgumentException("cannot serialize repair request", exception);
        }
    }

    private URI uri(String path) {
        return URI.create(baseUrl + path);
    }
}
