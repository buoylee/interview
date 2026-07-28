package com.interview.mysqlescdc.consumer.canal;

import static org.assertj.core.api.Assertions.assertThat;

import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Statement;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.HashSet;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.Set;
import java.util.UUID;

import org.apache.kafka.clients.consumer.ConsumerConfig;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.apache.kafka.clients.consumer.KafkaConsumer;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class CanalPartitionContractIT {
    private static final String TOPIC = "product-search-revisions";
    private static final Set<Long> PRODUCT_IDS = Set.of(2101L, 2102L, 2103L);

    private final CanalRevisionParser parser =
            new CanalRevisionParser(JsonMapper.builder().build());

    @Test
    void canal_uses_null_keys_and_partition_hash_preserves_product_ordering() throws Exception {
        deleteContractProducts();
        try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(consumerProperties())) {
            consumer.subscribe(List.of(TOPIC));
            awaitAssignment(consumer);
            consumer.seekToEnd(consumer.assignment());
            consumer.assignment().forEach(consumer::position);
            createAndUpdateProductsThroughService();

            List<LocatedSignal> observed = awaitExpectedSignals(consumer);
            List<LocatedSignal> recordsFor2101 = observed.stream()
                    .filter(item -> item.signal().productId() == 2101L)
                    .toList();

            assertThat(recordsFor2101)
                    .extracting(item -> item.signal().eventRevision())
                    .contains(1L, 2L, 3L);
            assertThat(recordsFor2101)
                    .allSatisfy(item -> assertThat(item.record().key()).isNull());
            assertThat(recordsFor2101)
                    .extracting(item -> item.record().partition())
                    .containsOnly(recordsFor2101.getFirst().record().partition());

            Map<Long, Integer> productPartitions = new HashMap<>();
            observed.forEach(item -> productPartitions.putIfAbsent(
                    item.signal().productId(), item.record().partition()));
            assertThat(productPartitions).containsKeys(2101L, 2102L, 2103L);
            assertThat(new HashSet<>(productPartitions.values())).hasSizeGreaterThanOrEqualTo(2);
            assertThat(observed)
                    .allSatisfy(item -> assertThat(item.record().key()).isNull());
        }
    }

    private List<LocatedSignal> awaitExpectedSignals(KafkaConsumer<String, String> consumer) {
        Instant deadline = Instant.now().plusSeconds(45);
        List<LocatedSignal> observed = new ArrayList<>();
        while (Instant.now().isBefore(deadline)) {
            for (ConsumerRecord<String, String> record : consumer.poll(Duration.ofMillis(500))) {
                for (RevisionSignal signal : parser.parse(record.value())) {
                    if (PRODUCT_IDS.contains(signal.productId())) {
                        observed.add(new LocatedSignal(record, signal));
                    }
                }
            }
            if (hasExpectedSignals(observed)) {
                return observed;
            }
        }
        throw new AssertionError("timed out waiting for deterministic Canal partition signals: " + observed);
    }

    private static boolean hasExpectedSignals(List<LocatedSignal> observed) {
        Set<Long> revisions2101 = new HashSet<>();
        Set<Long> products = new HashSet<>();
        for (LocatedSignal item : observed) {
            products.add(item.signal().productId());
            if (item.signal().productId() == 2101L) {
                revisions2101.add(item.signal().eventRevision());
            }
        }
        return products.containsAll(PRODUCT_IDS)
                && revisions2101.containsAll(Set.of(1L, 2L, 3L));
    }

    private static void awaitAssignment(KafkaConsumer<String, String> consumer) {
        Instant deadline = Instant.now().plusSeconds(20);
        while (consumer.assignment().isEmpty() && Instant.now().isBefore(deadline)) {
            consumer.poll(Duration.ofMillis(250));
        }
        assertThat(consumer.assignment()).as("Kafka partition assignment").isNotEmpty();
    }

    private static Properties consumerProperties() {
        Properties properties = new Properties();
        properties.put(ConsumerConfig.BOOTSTRAP_SERVERS_CONFIG, "127.0.0.1:29092");
        properties.put(ConsumerConfig.GROUP_ID_CONFIG, "canal-partition-contract-" + UUID.randomUUID());
        properties.put(ConsumerConfig.ENABLE_AUTO_COMMIT_CONFIG, "false");
        properties.put(ConsumerConfig.AUTO_OFFSET_RESET_CONFIG, "earliest");
        properties.put(ConsumerConfig.ISOLATION_LEVEL_CONFIG, "read_committed");
        properties.put(ConsumerConfig.KEY_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        properties.put(ConsumerConfig.VALUE_DESERIALIZER_CLASS_CONFIG, StringDeserializer.class);
        return properties;
    }

    private static void deleteContractProducts() throws Exception {
        try (Connection connection = DriverManager.getConnection(
                "jdbc:mysql://127.0.0.1:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC",
                "product", "productpass");
                Statement statement = connection.createStatement()) {
            statement.executeUpdate("DELETE FROM product_search_revision WHERE product_id IN (2101,2102,2103)");
            statement.executeUpdate("DELETE FROM inventory WHERE product_id IN (2101,2102,2103)");
            statement.executeUpdate("DELETE FROM products WHERE id IN (2101,2102,2103)");
        }
    }

    private static void createAndUpdateProductsThroughService() throws Exception {
        HttpClient client = HttpClient.newHttpClient();
        post(client, "/api/products", """
                {"id":2101,"sku":"WIRE-2101","name":"Wire 2101",
                 "description":"partition contract","categoryId":10,"priceCents":1000}
                """, 201, "\"revision\":1");
        put(client, "/api/products/2101/price", "{\"priceCents\":1100}", 200, "\"revision\":2");
        put(client, "/api/products/2101/price", "{\"priceCents\":1200}", 200, "\"revision\":3");
        post(client, "/api/products", """
                {"id":2102,"sku":"WIRE-2102","name":"Wire 2102",
                 "description":"partition contract","categoryId":10,"priceCents":1000}
                """, 201, "\"revision\":1");
        post(client, "/api/products", """
                {"id":2103,"sku":"WIRE-2103","name":"Wire 2103",
                 "description":"partition contract","categoryId":10,"priceCents":1000}
                """, 201, "\"revision\":1");
    }

    private static void post(HttpClient client, String path, String body,
                             int expectedStatus, String expectedBodyFragment) throws Exception {
        request(client, "POST", path, body, expectedStatus, expectedBodyFragment);
    }

    private static void put(HttpClient client, String path, String body,
                            int expectedStatus, String expectedBodyFragment) throws Exception {
        request(client, "PUT", path, body, expectedStatus, expectedBodyFragment);
    }

    private static void request(HttpClient client, String method, String path, String body,
                                int expectedStatus, String expectedBodyFragment) throws Exception {
        HttpRequest request = HttpRequest.newBuilder(URI.create("http://127.0.0.1:8081" + path))
                .header("Content-Type", "application/json")
                .method(method, HttpRequest.BodyPublishers.ofString(body))
                .build();
        HttpResponse<String> response = client.send(request, HttpResponse.BodyHandlers.ofString());
        assertThat(response.statusCode()).isEqualTo(expectedStatus);
        assertThat(response.body()).contains(expectedBodyFragment);
    }

    private record LocatedSignal(ConsumerRecord<String, String> record, RevisionSignal signal) {
    }
}
