package com.interview.mysqlescdc.consumer.canal;

import static org.assertj.core.api.Assertions.assertThat;

import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.sql.Connection;
import java.sql.DriverManager;
import java.sql.Statement;
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
import org.apache.kafka.common.TopicPartition;
import org.apache.kafka.common.serialization.StringDeserializer;
import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class CanalPartitionContractIT {
    private static final String TOPIC = "product-search-revisions";
    private static final Set<Long> PRODUCT_IDS = Set.of(2101L, 2102L, 2103L);
    private static final Set<ExpectedSignal> CLEANUP_BARRIER = Set.of(
            new ExpectedSignal(2101L, 92101L, "DELETE"),
            new ExpectedSignal(2102L, 92102L, "DELETE"),
            new ExpectedSignal(2103L, 92103L, "DELETE"));
    private static final Set<ExpectedSignal> EXPECTED_CURRENT_SIGNALS = Set.of(
            new ExpectedSignal(2101L, 1L, "INSERT"),
            new ExpectedSignal(2101L, 2L, "UPDATE"),
            new ExpectedSignal(2101L, 3L, "UPDATE"),
            new ExpectedSignal(2102L, 1L, "INSERT"),
            new ExpectedSignal(2103L, 1L, "INSERT"));

    private final JsonMapper json = JsonMapper.builder().build();
    private final CanalRevisionParser parser = new CanalRevisionParser(json);

    @Test
    void canal_uses_null_keys_and_partition_hash_preserves_product_ordering() throws Exception {
        try (KafkaConsumer<String, String> consumer = new KafkaConsumer<>(consumerProperties())) {
            consumer.subscribe(List.of(TOPIC));
            awaitAssignment(consumer);
            consumer.seekToEnd(consumer.assignment());
            consumer.assignment().forEach(consumer::position);

            writeAndDeleteCleanupBarrier();
            awaitCleanupBarrier(consumer);
            Map<Integer, Long> baselineOffsets = captureBaselineOffsets(consumer);

            createAndUpdateProductsThroughService();
            List<LocatedSignal> observed = awaitExpectedSignals(consumer, baselineOffsets);
            assertThat(observed)
                    .extracting(LocatedSignal::expected)
                    .containsExactlyInAnyOrderElementsOf(EXPECTED_CURRENT_SIGNALS);

            List<LocatedSignal> recordsFor2101 = observed.stream()
                    .filter(item -> item.signal().productId() == 2101L)
                    .toList();
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
            assertThat(observed).allSatisfy(item -> {
                assertThat(item.record().key()).isNull();
                assertThat(item.record().offset())
                        .isGreaterThanOrEqualTo(baselineOffsets.get(item.record().partition()));
            });
        }
    }

    private void awaitCleanupBarrier(KafkaConsumer<String, String> consumer) {
        Instant deadline = Instant.now().plusSeconds(45);
        Set<ExpectedSignal> observed = new HashSet<>();
        while (Instant.now().isBefore(deadline)) {
            for (ConsumerRecord<String, String> record : consumer.poll(Duration.ofMillis(500))) {
                observed.addAll(locatedSignals(record).stream()
                        .map(LocatedSignal::expected)
                        .filter(CLEANUP_BARRIER::contains)
                        .toList());
            }
            if (observed.equals(CLEANUP_BARRIER)) {
                return;
            }
        }
        throw new AssertionError("timed out waiting for observable Canal cleanup barrier: " + observed);
    }

    private static Map<Integer, Long> captureBaselineOffsets(KafkaConsumer<String, String> consumer) {
        Map<Integer, Long> baselineOffsets = new HashMap<>();
        for (TopicPartition partition : consumer.assignment()) {
            baselineOffsets.put(partition.partition(), consumer.position(partition));
        }
        return Map.copyOf(baselineOffsets);
    }

    private List<LocatedSignal> awaitExpectedSignals(
            KafkaConsumer<String, String> consumer, Map<Integer, Long> baselineOffsets) {
        Instant deadline = Instant.now().plusSeconds(45);
        List<LocatedSignal> observed = new ArrayList<>();
        Set<ExpectedSignal> settled = new HashSet<>();
        while (Instant.now().isBefore(deadline)) {
            for (ConsumerRecord<String, String> record : consumer.poll(Duration.ofMillis(500))) {
                if (record.offset() < baselineOffsets.get(record.partition())) {
                    continue;
                }
                for (LocatedSignal item : locatedSignals(record)) {
                    if (!PRODUCT_IDS.contains(item.signal().productId())) {
                        continue;
                    }
                    assertThat(item.expected())
                            .as("only exact current-run product signals are accepted")
                            .isIn(EXPECTED_CURRENT_SIGNALS);
                    observed.add(item);
                    settled.add(item.expected());
                }
            }
            if (settled.equals(EXPECTED_CURRENT_SIGNALS)) {
                return observed;
            }
        }
        throw new AssertionError("timed out waiting for exact baseline-bound Canal signals: " + observed);
    }

    private List<LocatedSignal> locatedSignals(ConsumerRecord<String, String> record) {
        try {
            CanalFlatMessage message = json.readValue(record.value(), CanalFlatMessage.class);
            return parser.parse(record.value()).stream()
                    .map(signal -> new LocatedSignal(
                            record, signal,
                            new ExpectedSignal(signal.productId(), signal.eventRevision(), message.type())))
                    .toList();
        } catch (Exception exception) {
            throw new IllegalArgumentException("invalid live Canal record", exception);
        }
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

    private static void writeAndDeleteCleanupBarrier() throws Exception {
        try (Connection connection = DriverManager.getConnection(
                "jdbc:mysql://127.0.0.1:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC",
                "product", "productpass");
                Statement statement = connection.createStatement()) {
            statement.executeUpdate("DELETE FROM product_search_revision WHERE product_id IN (2101,2102,2103)");
            statement.executeUpdate("DELETE FROM inventory WHERE product_id IN (2101,2102,2103)");
            statement.executeUpdate("DELETE FROM products WHERE id IN (2101,2102,2103)");
            statement.executeUpdate("""
                    INSERT INTO products
                      (id, sku, name, description, category_id, price_cents, status)
                    VALUES
                      (2101, 'BARRIER-2101', 'Barrier 2101', 'cleanup barrier', 10, 1, 'ACTIVE'),
                      (2102, 'BARRIER-2102', 'Barrier 2102', 'cleanup barrier', 10, 1, 'ACTIVE'),
                      (2103, 'BARRIER-2103', 'Barrier 2103', 'cleanup barrier', 10, 1, 'ACTIVE')
                    """);
            statement.executeUpdate("""
                    INSERT INTO inventory (product_id, available_quantity, reserved_quantity)
                    VALUES (2101,0,0),(2102,0,0),(2103,0,0)
                    """);
            statement.executeUpdate("""
                    INSERT INTO product_search_revision (product_id, revision, active)
                    VALUES (2101,92101,1),(2102,92102,1),(2103,92103,1)
                    """);
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

    private record ExpectedSignal(long productId, long revision, String type) {
    }

    private record LocatedSignal(
            ConsumerRecord<String, String> record, RevisionSignal signal, ExpectedSignal expected) {
    }
}
