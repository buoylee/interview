package com.interview.mysqlescdc.verifier.target;

import java.io.IOException;
import java.net.URI;
import java.net.URLEncoder;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Repository;

import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ArrayNode;
import tools.jackson.databind.node.ObjectNode;
import tools.jackson.databind.json.JsonMapper;

@Repository
public class RestIndexedDocumentReader implements IndexedDocumentReader {
    private static final Duration REQUEST_TIMEOUT = Duration.ofSeconds(10);
    private static final String KEEP_ALIVE = "1m";
    private static final int MAX_PAGE_SIZE = 1_000;

    private final HttpClient http;
    private final JsonMapper json;
    private final String baseUrl;

    @Autowired
    public RestIndexedDocumentReader(
            @Value("${verification.elasticsearch-url}") String baseUrl) {
        this(HttpClient.newBuilder().connectTimeout(REQUEST_TIMEOUT).build(),
                JsonMapper.builder().findAndAddModules().build(), baseUrl);
    }

    public RestIndexedDocumentReader(HttpClient http, JsonMapper json, String baseUrl) {
        this.http = Objects.requireNonNull(http, "http");
        this.json = Objects.requireNonNull(json, "json");
        this.baseUrl = Objects.requireNonNull(baseUrl, "baseUrl").replaceAll("/+$", "");
    }

    @Override
    public TargetCursor open(String indexOrAlias) {
        if (indexOrAlias == null || !indexOrAlias.matches("[a-z0-9._-]+")) {
            throw new IllegalArgumentException("safe Elasticsearch index or alias required");
        }
        if ("products_search".equals(indexOrAlias)) {
            throw new IllegalArgumentException("filtered serving alias cannot be verified");
        }
        String encoded = URLEncoder.encode(indexOrAlias, StandardCharsets.UTF_8);
        JsonNode response = exchange("Elasticsearch PIT open", HttpRequest.newBuilder(
                        uri("/" + encoded + "/_pit?keep_alive=" + KEEP_ALIVE))
                .timeout(REQUEST_TIMEOUT)
                .POST(HttpRequest.BodyPublishers.noBody())
                .build());
        String pitId = requiredText(response, "id", "PIT open response");
        return new TargetCursor(pitId, this::closePit);
    }

    @Override
    public IndexedPage readAfter(
            TargetCursor cursor, SearchAfterToken token, int pageSize) {
        Objects.requireNonNull(cursor, "cursor");
        try {
            if (pageSize < 1 || pageSize > MAX_PAGE_SIZE) {
                throw new IllegalArgumentException("pageSize must be between 1 and " + MAX_PAGE_SIZE);
            }
            ObjectNode body = searchBody(cursor.pitId(), token, pageSize);
            JsonNode response = exchange("Elasticsearch search", HttpRequest.newBuilder(uri("/_search"))
                    .header("Content-Type", "application/json")
                    .timeout(REQUEST_TIMEOUT)
                    .POST(HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body)))
                    .build());
            cursor.renew(textOrNull(response.get("pit_id")));
            JsonNode hits = response.path("hits").path("hits");
            if (!hits.isArray()) throw new IllegalStateException("Elasticsearch search hits missing");
            List<IndexedDocument> documents = new ArrayList<>(hits.size());
            SearchAfterToken next = null;
            for (JsonNode hit : hits) {
                documents.add(mapHit(hit));
                next = sortToken(hit);
            }
            return new IndexedPage(documents, next, documents.size() < pageSize);
        } catch (RuntimeException exception) {
            try {
                cursor.close();
            } catch (RuntimeException closeFailure) {
                exception.addSuppressed(closeFailure);
            }
            throw exception;
        }
    }

    private ObjectNode searchBody(String pitId, SearchAfterToken token, int pageSize) {
        ObjectNode body = json.createObjectNode();
        body.put("size", pageSize);
        body.put("track_total_hits", false);
        body.put("version", true);
        body.put("seq_no_primary_term", true);
        ObjectNode pit = body.putObject("pit");
        pit.put("id", pitId);
        pit.put("keep_alive", KEEP_ALIVE);
        ArrayNode sort = body.putArray("sort");
        sort.addObject().put("product_id", "asc");
        sort.addObject().put("_shard_doc", "asc");
        ArrayNode source = body.putArray("_source");
        for (String field : List.of(
                "product_id", "sku", "name", "description", "category_id", "category_name",
                "price_cents", "available_quantity", "searchable", "source_revision",
                "source_updated_at")) {
            source.add(field);
        }
        if (token != null) {
            ArrayNode searchAfter = body.putArray("search_after");
            token.sortValues().forEach(searchAfter::add);
        }
        return body;
    }

    private IndexedDocument mapHit(JsonNode hit) {
        JsonNode source = hit.path("_source");
        if (!source.isObject()) throw new IllegalStateException("Elasticsearch hit source missing");
        return new IndexedDocument(
                requiredLong(source, "product_id"),
                nullableText(source.get("sku")),
                nullableText(source.get("name")),
                nullableText(source.get("description")),
                nullableLong(source.get("category_id")),
                nullableText(source.get("category_name")),
                nullableLong(source.get("price_cents")),
                nullableInteger(source.get("available_quantity")),
                requiredBoolean(source, "searchable"),
                requiredLong(source, "source_revision"),
                nullableInstant(source.get("source_updated_at")),
                requiredLong(hit, "_version"),
                requiredLong(hit, "_seq_no"),
                requiredLong(hit, "_primary_term"));
    }

    private SearchAfterToken sortToken(JsonNode hit) {
        JsonNode sort = hit.get("sort");
        if (sort == null || !sort.isArray() || sort.isEmpty()) {
            throw new IllegalStateException("Elasticsearch hit sort token missing");
        }
        List<JsonNode> values = new ArrayList<>(sort.size());
        sort.forEach(value -> values.add(value.deepCopy()));
        return new SearchAfterToken(values);
    }

    private void closePit(String pitId) {
        ObjectNode body = json.createObjectNode().put("id", pitId);
        try {
            exchange("Elasticsearch PIT close", HttpRequest.newBuilder(uri("/_pit"))
                    .header("Content-Type", "application/json")
                    .timeout(REQUEST_TIMEOUT)
                    .method("DELETE", HttpRequest.BodyPublishers.ofString(json.writeValueAsString(body)))
                    .build());
        } catch (JacksonException exception) {
            throw new IllegalStateException("Elasticsearch PIT close serialization failed", exception);
        }
    }

    private JsonNode exchange(String operation, HttpRequest request) {
        try {
            HttpResponse<String> response = http.send(request, HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IllegalStateException(operation + " failed with HTTP " + response.statusCode());
            }
            JsonNode parsed = json.readTree(response.body());
            if (parsed == null || !parsed.isObject()) {
                throw new IllegalStateException(operation + " response is not an object");
            }
            return parsed;
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new IllegalStateException(operation + " interrupted", exception);
        } catch (IOException | JacksonException exception) {
            throw new IllegalStateException(operation + " failed", exception);
        }
    }

    private URI uri(String path) {
        return URI.create(baseUrl + path);
    }

    private static String requiredText(JsonNode object, String field, String context) {
        String value = textOrNull(object.get(field));
        if (value == null || value.isBlank()) throw new IllegalStateException(context + " lacks " + field);
        return value;
    }

    private static String textOrNull(JsonNode value) {
        return value != null && value.isTextual() ? value.textValue() : null;
    }

    private static String nullableText(JsonNode value) {
        return value == null || value.isNull() ? null : value.textValue();
    }

    private static Long nullableLong(JsonNode value) {
        return value == null || value.isNull() ? null : value.longValue();
    }

    private static Integer nullableInteger(JsonNode value) {
        return value == null || value.isNull() ? null : value.intValue();
    }

    private static Instant nullableInstant(JsonNode value) {
        return value == null || value.isNull() ? null : Instant.parse(value.textValue());
    }

    private static long requiredLong(JsonNode object, String field) {
        JsonNode value = object.get(field);
        if (value == null || !value.isIntegralNumber()) {
            throw new IllegalStateException("Elasticsearch hit lacks integral " + field);
        }
        return value.longValue();
    }

    private static boolean requiredBoolean(JsonNode object, String field) {
        JsonNode value = object.get(field);
        if (value == null || !value.isBoolean()) {
            throw new IllegalStateException("Elasticsearch hit lacks boolean " + field);
        }
        return value.booleanValue();
    }
}
