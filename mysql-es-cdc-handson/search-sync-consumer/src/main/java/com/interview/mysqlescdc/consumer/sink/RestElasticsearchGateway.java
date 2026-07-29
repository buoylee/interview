package com.interview.mysqlescdc.consumer.sink;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.List;
import java.util.Objects;

import com.interview.mysqlescdc.consumer.projection.SearchDocument;
import com.interview.mysqlescdc.consumer.lab.ProjectionFaultMode;
import com.interview.mysqlescdc.consumer.lab.ProjectionFaultRegistry;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.node.ObjectNode;
import tools.jackson.databind.json.JsonMapper;

public class RestElasticsearchGateway implements ElasticsearchGateway {
    private final BulkHttpSender sender;
    private final JsonMapper json;
    private final URI bulkUri;
    private final Duration requestTimeout;
    private final ProjectionFaultRegistry faults;

    public RestElasticsearchGateway(HttpClient client, JsonMapper json, String baseUrl) {
        this(client, json, baseUrl, Duration.ofSeconds(5));
    }

    public RestElasticsearchGateway(
            HttpClient client, JsonMapper json, String baseUrl, Duration requestTimeout) {
        this(client, json, baseUrl, requestTimeout, new ProjectionFaultRegistry());
    }

    public RestElasticsearchGateway(
            HttpClient client, JsonMapper json, String baseUrl, Duration requestTimeout,
            ProjectionFaultRegistry faults) {
        this(request -> {
            HttpResponse<String> response = Objects.requireNonNull(client, "client")
                    .send(request, HttpResponse.BodyHandlers.ofString());
            return new BulkHttpResponse(response.statusCode(), response.body());
        }, json, baseUrl, requestTimeout, faults);
    }

    RestElasticsearchGateway(
            BulkHttpSender sender, JsonMapper json, String baseUrl, Duration requestTimeout) {
        this(sender, json, baseUrl, requestTimeout, new ProjectionFaultRegistry());
    }

    RestElasticsearchGateway(
            BulkHttpSender sender, JsonMapper json, String baseUrl, Duration requestTimeout,
            ProjectionFaultRegistry faults) {
        this.sender = Objects.requireNonNull(sender, "sender");
        this.json = Objects.requireNonNull(json, "json");
        this.requestTimeout = requirePositive(requestTimeout);
        this.faults = Objects.requireNonNull(faults, "faults");
        String normalizedBaseUrl = Objects.requireNonNull(baseUrl, "baseUrl").replaceAll("/+$", "");
        this.bulkUri = URI.create(normalizedBaseUrl + "/_bulk");
    }

    @Override
    public BulkWriteResult write(String targetAlias, List<SearchDocument> documents) {
        ElasticsearchTargets.requireSafe(targetAlias);
        List<SearchDocument> orderedDocuments = List.copyOf(documents);
        String ndjson = buildNdjson(targetAlias, orderedDocuments);
        HttpRequest request = HttpRequest.newBuilder(bulkUri)
                .header("Content-Type", "application/x-ndjson")
                .timeout(requestTimeout)
                .POST(HttpRequest.BodyPublishers.ofString(ndjson))
                .build();
        final BulkHttpResponse response;
        try {
            response = sender.send(request);
        } catch (InterruptedException exception) {
            Thread.currentThread().interrupt();
            throw new BulkTransportException("Elasticsearch Bulk request interrupted", exception);
        } catch (IOException | RuntimeException exception) {
            throw new BulkTransportException("Elasticsearch Bulk request failed", exception);
        }
        if (response.status() < 200 || response.status() >= 300) {
            throw new BulkTransportException("Elasticsearch Bulk HTTP status " + response.status());
        }
        return parseResponse(response.body(), orderedDocuments);
    }

    URI bulkUri() {
        return bulkUri;
    }

    Duration requestTimeout() {
        return requestTimeout;
    }

    private static Duration requirePositive(Duration timeout) {
        Objects.requireNonNull(timeout, "requestTimeout");
        if (timeout.isZero() || timeout.isNegative()) {
            throw new IllegalArgumentException("requestTimeout must be positive");
        }
        return timeout;
    }

    private String buildNdjson(String targetAlias, List<SearchDocument> documents) {
        StringBuilder body = new StringBuilder();
        for (SearchDocument document : documents) {
            ObjectNode action = json.createObjectNode();
            ObjectNode index = action.putObject("index");
            index.put("_index", targetAlias);
            index.put("_id", Long.toString(document.productId()));
            index.put("version", document.sourceRevision());
            index.put("version_type", "external");
            try {
                body.append(json.writeValueAsString(action)).append('\n');
                ObjectNode source = json.valueToTree(document);
                if (!document.searchable()) {
                    for (String field : List.of("sku", "name", "description", "category_id",
                            "category_name", "price_cents", "available_quantity")) {
                        source.remove(field);
                    }
                }
                if (document.searchable()
                        && faults.matches(ProjectionFaultMode.PRICE_CENTS_AS_STRING, document.productId())) {
                    source.put("price_cents", document.priceCents() + "-invalid");
                }
                body.append(json.writeValueAsString(source)).append('\n');
            } catch (JacksonException exception) {
                throw new IllegalArgumentException("cannot serialize Bulk document", exception);
            }
        }
        return body.toString();
    }

    private BulkWriteResult parseResponse(String payload, List<SearchDocument> documents) {
        final JsonNode root;
        try {
            root = json.readTree(payload);
        } catch (JacksonException exception) {
            throw new BulkProtocolException("invalid Elasticsearch Bulk response", exception);
        }
        if (root == null || !root.isObject()) {
            throw new BulkProtocolException("Bulk response must be an object");
        }
        JsonNode items = root.get("items");
        if (items == null || !items.isArray() || items.size() != documents.size()) {
            throw new BulkProtocolException("Bulk item count does not match request");
        }
        List<BulkItemResult> results = new ArrayList<>(documents.size());
        for (int position = 0; position < documents.size(); position++) {
            SearchDocument document = documents.get(position);
            JsonNode wrapper = items.get(position);
            JsonNode item = wrapper == null || !wrapper.isObject() ? null : wrapper.get("index");
            if (item == null || !item.isObject()) {
                throw new BulkProtocolException("Bulk item " + position + " is missing index action");
            }
            JsonNode statusNode = item.get("status");
            if (statusNode == null || !statusNode.isIntegralNumber()) {
                throw new BulkProtocolException("Bulk item " + position + " is missing numeric status");
            }
            int status = statusNode.intValue();
            JsonNode error = item.get("error");
            String errorType = error != null && error.isObject() ? textOrNull(error.get("type")) : null;
            String reason = error != null && error.isObject() ? textOrNull(error.get("reason")) : null;
            results.add(new BulkItemResult(document.productId(), document.sourceRevision(),
                    classify(status, errorType), status, errorType, reason));
        }
        return new BulkWriteResult(results);
    }

    private static String textOrNull(JsonNode node) {
        return node != null && node.isTextual() ? node.textValue() : null;
    }

    private static BulkOutcome classify(int status, String errorType) {
        if (status == 200 || status == 201) {
            return BulkOutcome.APPLIED;
        }
        if (status == 409 && "version_conflict_engine_exception".equals(errorType)) {
            return BulkOutcome.STALE;
        }
        if (status == 408 || status == 429 || status >= 500 && status <= 599) {
            return BulkOutcome.RETRYABLE_FAILURE;
        }
        if (status >= 400 && status <= 499) {
            return BulkOutcome.PERMANENT_FAILURE;
        }
        throw new BulkProtocolException("unexpected Bulk item status: " + status);
    }
}
