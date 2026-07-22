# MySQL ES CDC Hands-on M2-M3 Reliable Consumer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox - [ ] syntax for tracking.

**Goal:** Replace the Adapter baseline with a custom Spring Boot consumer that turns Canal revision signals into exact multi-table Elasticsearch documents and survives duplicate delivery, old events, Bulk partial failure, process crashes, poison data, and replay.

**Architecture:** Canal continues to publish flat messages to product-search-revisions. The consumer parses product_id from each data row, reloads the current aggregate with one MySQL statement, projects a deterministic active document or tombstone, and writes through the products_write alias using strict external versioning. A Kafka record is acknowledged only after every represented product has either reached Elasticsearch, been rejected as an older/equal version, or been durably persisted in the MySQL DLQ table.

**Tech Stack:** Java 21, Spring Boot 4.1.0, Spring Kafka 4.1.0 as managed by Spring Boot, Spring JDBC JdbcClient, Spring RestClient, Jackson 3 JsonMapper, MySQL 8.4.8, Kafka 4.1.2, Elasticsearch 8.17.0, Micrometer, JUnit 5, AssertJ.

## Global Constraints

- Execute only after the M0 and M1 completion gates pass.
- Work only in branch codex/mysql-es-cdc-handson and its isolated worktree.
- product-service remains MySQL-only; all downstream code belongs to search-sync-consumer.
- Canal 1.1.8 record key is null. product_id is the partitionHash input and is parsed from flat-message data.
- Same-product ordering is a partition contract, not a Kafka record-key contract.
- Use Kafka manual immediate acknowledgment with enable.auto.commit=false.
- Never acknowledge before every row in the Kafka record is settled.
- Use Elasticsearch version_type=external, not external_gte. Only a 409 whose item error type is version_conflict_engine_exception is settled as duplicate/stale; every other 409 is a permanent protocol/data failure.
- Active and deleted products are both indexed; deleted products are tombstones with searchable=false and the latest source_revision.
- Inspect every Elasticsearch Bulk item. Top-level HTTP 200 is not sufficient.
- A transient dependency failure keeps the Kafka offset uncommitted. A deterministic data failure may enter the durable DLQ.
- DLQ identity is topic:partition:offset:productId and publication is idempotent.
- The consumer projector must not be imported by consistency-verifier.
- No exactly-once claim. The implemented contract is at-least-once plus deterministic projection, external revision fencing, durable DLQ, and later reconciliation.
- Command context: run build, Compose, script, and Git commands from `mysql-es-cdc-handson/`; file lists in this plan remain repository-worktree-relative.

## Locked Interfaces

~~~text
CanalRevisionParser.parse(String) -> List<RevisionSignal>
SourceSnapshotRepository.load(long) -> Optional<SourceProductSnapshot>
SearchDocumentProjector.project(SourceProductSnapshot) -> SearchDocument
ElasticsearchGateway.write(String, List<SearchDocument>) -> BulkWriteResult
DlqStore.publish(DlqRecord) -> void
DlqStore.findPending(String) -> Optional<DlqRecord>
DlqStore.resolve(String) -> void
RecordDlqStore.publish(RecordDlqRecord) -> void
RecordDlqStore.findPending(String) -> Optional<RecordDlqRecord>
RecordDlqStore.resolve(String) -> void
SyncRecordProcessor.process(ConsumerRecord<String,String>) -> ProcessingResult
~~~

The verifier will define different projector and gateway types in M4 even where the field names match.

---

### Task 1: Add consumer dependencies and lock the real Canal wire contract

**Files:**

- Modify: mysql-es-cdc-handson/search-sync-consumer/pom.xml
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/resources/application.yaml
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/canal/CanalFlatMessage.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/canal/RevisionSignal.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/canal/CanalRevisionParser.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/canal/CanalRevisionParserTest.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/canal/CanalPartitionContractIT.java
- Modify: mysql-es-cdc-handson/infra/compose.yaml

**Interfaces:**

- Consumes: Canal 1.1.8 flat JSON for product_catalog.product_search_revision.
- Produces: RevisionSignal(productId, eventRevision, active, canalMessageId, rowIndex); unrelated tables and DDL return an empty list.

- [ ] **Step 1: Write parser tests before adding dependencies**

Create CanalRevisionParserTest.java:

~~~java
package com.interview.mysqlescdc.consumer.canal;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import tools.jackson.databind.json.JsonMapper;

class CanalRevisionParserTest {
    private final CanalRevisionParser parser =
            new CanalRevisionParser(JsonMapper.builder().build());

    @Test
    void parses_every_revision_row_from_a_flat_message() {
        String payload = """
                {
                  "id": 91,
                  "database": "product_catalog",
                  "table": "product_search_revision",
                  "isDdl": false,
                  "type": "UPDATE",
                  "data": [
                    {"product_id":"1001","revision":"4","active":"1"},
                    {"product_id":"1002","revision":"8","active":"0"}
                  ]
                }
                """;

        assertThat(parser.parse(payload)).containsExactly(
                new RevisionSignal(1001L, 4L, true, 91L, 0),
                new RevisionSignal(1002L, 8L, false, 91L, 1));
    }

    @Test
    void ignores_ddl_and_unrelated_tables() {
        assertThat(parser.parse("""
                {"id":92,"database":"product_catalog","table":"products",
                 "isDdl":false,"type":"UPDATE","data":[{"id":"1001"}]}
                """)).isEmpty();
        assertThat(parser.parse("""
                {"id":93,"database":"product_catalog",
                 "table":"product_search_revision","isDdl":true,
                 "type":"ALTER","data":[]}
                """)).isEmpty();
    }
}
~~~

- [ ] **Step 2: Run the parser test and verify the red state**

Run:

~~~bash
./mvnw -pl search-sync-consumer -Dtest=CanalRevisionParserTest test
~~~

Expected: FAIL because JsonMapper, CanalRevisionParser, and RevisionSignal do not exist.

- [ ] **Step 3: Add exact consumer dependencies**

Add these dependencies to search-sync-consumer/pom.xml:

~~~xml
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-webmvc</artifactId>
</dependency>
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-jdbc</artifactId>
</dependency>
<dependency>
  <groupId>org.springframework.boot</groupId>
  <artifactId>spring-boot-starter-kafka</artifactId>
</dependency>
<dependency>
  <groupId>com.mysql</groupId>
  <artifactId>mysql-connector-j</artifactId>
  <scope>runtime</scope>
</dependency>
~~~

Retain actuator and test dependencies from M0.

- [ ] **Step 4: Add configuration with manual acknowledgment**

Create application.yaml:

~~~yaml
spring:
  application:
    name: search-sync-consumer
  datasource:
    url: jdbc:mysql://mysql:3306/product_catalog?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
    username: product
    password: productpass
  kafka:
    bootstrap-servers: toxiproxy:8667
    consumer:
      group-id: product-search-sync-v1
      enable-auto-commit: false
      auto-offset-reset: earliest
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      properties:
        isolation.level: read_committed
    listener:
      ack-mode: manual_immediate
      immediate-stop: true

server:
  port: 8082

pipeline:
  source-topic: product-search-revisions
  target-alias: products_write
  elasticsearch-base-url: http://toxiproxy:8666
  retry-attempts: 3
  retry-backoff: 250ms

lab:
  failpoints:
    enabled: ${LAB_FAILPOINTS_ENABLED:false}

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
~~~

- [ ] **Step 5: Implement the wire records and parser**

Create CanalFlatMessage.java:

~~~java
package com.interview.mysqlescdc.consumer.canal;

import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.annotation.JsonIgnoreProperties;

@JsonIgnoreProperties(ignoreUnknown = true)
public record CanalFlatMessage(
        long id,
        String database,
        String table,
        Boolean isDdl,
        String type,
        List<Map<String, String>> data) {
}
~~~

Create RevisionSignal.java:

~~~java
package com.interview.mysqlescdc.consumer.canal;

public record RevisionSignal(
        long productId,
        long eventRevision,
        boolean active,
        long canalMessageId,
        int rowIndex) {
}
~~~

Create CanalRevisionParser.java:

~~~java
package com.interview.mysqlescdc.consumer.canal;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import org.springframework.stereotype.Component;
import tools.jackson.core.JacksonException;
import tools.jackson.databind.json.JsonMapper;

@Component
public class CanalRevisionParser {
    private final JsonMapper json;

    public CanalRevisionParser(JsonMapper json) {
        this.json = json;
    }

    public List<RevisionSignal> parse(String payload) {
        try {
            CanalFlatMessage message = json.readValue(payload, CanalFlatMessage.class);
            if (Boolean.TRUE.equals(message.isDdl())
                    || !"product_catalog".equals(message.database())
                    || !"product_search_revision".equals(message.table())
                    || message.data() == null) {
                return List.of();
            }

            List<RevisionSignal> signals = new ArrayList<>();
            for (int index = 0; index < message.data().size(); index++) {
                Map<String, String> row = message.data().get(index);
                signals.add(new RevisionSignal(
                        Long.parseLong(required(row, "product_id")),
                        Long.parseLong(required(row, "revision")),
                        parseBoolean(required(row, "active")),
                        message.id(),
                        index));
            }
            return List.copyOf(signals);
        } catch (JacksonException | NumberFormatException exception) {
            throw new IllegalArgumentException("invalid Canal flat message", exception);
        }
    }

    private static String required(Map<String, String> row, String key) {
        String value = row.get(key);
        if (value == null || value.isBlank()) {
            throw new IllegalArgumentException("missing Canal field: " + key);
        }
        return value;
    }

    private static boolean parseBoolean(String value) {
        if ("1".equals(value) || "true".equalsIgnoreCase(value)) {
            return true;
        }
        if ("0".equals(value) || "false".equalsIgnoreCase(value)) {
            return false;
        }
        throw new IllegalArgumentException("invalid Canal boolean: " + value);
    }
}
~~~

- [ ] **Step 6: Verify the parser is green**

Run:

~~~bash
./mvnw -pl search-sync-consumer -Dtest=CanalRevisionParserTest test
~~~

Expected: 2 tests PASS.

- [ ] **Step 7: Add a live compatibility test for null record key and partitionHash**

CanalPartitionContractIT must:

1. Start with the M0 Compose stack.
2. Create product 2101 and update its price twice.
3. Consume the matching Canal records with a unique group and no auto commit.
4. Assert every matching ConsumerRecord.key() is null.
5. Assert every data row for product 2101 arrived on one identical partition.
6. Create products 2102 and 2103. With `canal.mq.database.hash=false`, the Java string hashes of `"2101"`, `"2102"`, and `"2103"` map across the three configured partitions; assert at least two are observed so the test cannot pass on a fixed partition.

Its core assertions are:

~~~java
assertThat(recordsFor2101)
        .allSatisfy(record -> assertThat(record.key()).isNull());
assertThat(recordsFor2101)
        .extracting(ConsumerRecord::partition)
        .containsOnly(recordsFor2101.getFirst().partition());
assertThat(allObservedPartitions).hasSizeGreaterThanOrEqualTo(2);
~~~

Run:

~~~bash
./mvnw -pl search-sync-consumer \
  -Dtest=CanalPartitionContractIT test
~~~

Expected: PASS against Canal 1.1.8. If record key is not null or same-product rows span partitions, stop and update the design before continuing.

- [ ] **Step 8: Add consumer service to Compose and commit**

Add this service to `infra/compose.yaml`:

~~~yaml
  search-sync-consumer:
    build:
      context: ../search-sync-consumer
    depends_on:
      mysql:
        condition: service_healthy
      kafka-init:
        condition: service_completed_successfully
      toxiproxy:
        condition: service_started
    environment:
      SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/product_catalog?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
      SPRING_DATASOURCE_USERNAME: product
      SPRING_DATASOURCE_PASSWORD: productpass
      SPRING_KAFKA_BOOTSTRAP_SERVERS: toxiproxy:8667
      PIPELINE_ELASTICSEARCH_BASE_URL: http://toxiproxy:8666
    ports: ["8082:8082"]
~~~

Run:

~~~bash
./mvnw -pl search-sync-consumer test
docker compose -f infra/compose.yaml config --quiet
git add .
git commit -m "feat(cdc-lab): parse Canal revision signals"
~~~

---

### Task 2: Rehydrate one current MySQL snapshot and project active documents or tombstones

**Files:**

- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/source/SourceProductSnapshot.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/source/SourceSnapshotRepository.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/source/JdbcSourceSnapshotRepository.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/projection/SearchDocument.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/projection/SearchDocumentProjector.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/projection/SearchDocumentProjectorTest.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/source/JdbcSourceSnapshotRepositoryIT.java

**Interfaces:**

- Consumes: product_id.
- Produces: one source revision and one deterministic SearchDocument. Inactive sources produce a persisted tombstone, never an Elasticsearch DELETE.

- [ ] **Step 1: Write active and tombstone projection tests**

The active fixture must assert every managed field. The deleted fixture must assert only identity, searchable=false, revision, and timestamp are populated:

~~~java
@Test
void projects_a_complete_active_document() {
    SourceProductSnapshot source = SourceProductSnapshot.active(
            2101L, "SKU-2101", "Keyboard", "Mechanical",
            10L, "Accessories", 12999L, 8, 4L,
            Instant.parse("2026-07-22T01:02:03Z"));

    assertThat(projector.project(source)).isEqualTo(new SearchDocument(
            2101L, "SKU-2101", "Keyboard", "Mechanical",
            10L, "Accessories", 12999L, 8, true, 4L,
            Instant.parse("2026-07-22T01:02:03Z")));
}

@Test
void projects_an_inactive_source_as_a_versioned_tombstone() {
    SourceProductSnapshot source = SourceProductSnapshot.inactive(
            2101L, 5L, Instant.parse("2026-07-22T02:00:00Z"));

    SearchDocument document = projector.project(source);

    assertThat(document.productId()).isEqualTo(2101L);
    assertThat(document.searchable()).isFalse();
    assertThat(document.sourceRevision()).isEqualTo(5L);
    assertThat(document.sku()).isNull();
    assertThat(document.name()).isNull();
}
~~~

- [ ] **Step 2: Run the tests and verify the red state**

Run:

~~~bash
./mvnw -pl search-sync-consumer -Dtest=SearchDocumentProjectorTest test
~~~

Expected: FAIL because source and projection types do not exist.

- [ ] **Step 3: Define immutable source and target records**

Create `SourceProductSnapshot.java`:

~~~java
package com.interview.mysqlescdc.consumer.source;

import java.time.Instant;
import java.util.Objects;

public record SourceProductSnapshot(
        long productId,
        String sku,
        String name,
        String description,
        Long categoryId,
        String categoryName,
        Long priceCents,
        Integer availableQuantity,
        boolean active,
        long revision,
        Instant updatedAt) {

    public SourceProductSnapshot {
        if (productId < 1 || revision < 1) {
            throw new IllegalArgumentException("positive productId and revision required");
        }
        Objects.requireNonNull(updatedAt, "updatedAt");
    }

    public static SourceProductSnapshot active(
            long productId,
            String sku,
            String name,
            String description,
            long categoryId,
            String categoryName,
            long priceCents,
            int availableQuantity,
            long revision,
            Instant updatedAt) {
        return new SourceProductSnapshot(
                productId, sku, name, description, categoryId, categoryName,
                priceCents, availableQuantity, true, revision, updatedAt);
    }

    public static SourceProductSnapshot inactive(
            long productId, long revision, Instant updatedAt) {
        return new SourceProductSnapshot(
                productId, null, null, null, null, null,
                null, null, false, revision, updatedAt);
    }
}
~~~

Create `SearchDocument.java` with the complete wire names:

~~~java
package com.interview.mysqlescdc.consumer.projection;

import java.time.Instant;
import java.util.Objects;

import com.fasterxml.jackson.annotation.JsonProperty;

public record SearchDocument(
        @JsonProperty("product_id") long productId,
        @JsonProperty("sku") String sku,
        @JsonProperty("name") String name,
        @JsonProperty("description") String description,
        @JsonProperty("category_id") Long categoryId,
        @JsonProperty("category_name") String categoryName,
        @JsonProperty("price_cents") Long priceCents,
        @JsonProperty("available_quantity") Integer availableQuantity,
        @JsonProperty("searchable") boolean searchable,
        @JsonProperty("source_revision") long sourceRevision,
        @JsonProperty("source_updated_at") Instant sourceUpdatedAt) {

    public SearchDocument {
        if (productId < 1 || sourceRevision < 1) {
            throw new IllegalArgumentException("positive productId and sourceRevision required");
        }
        Objects.requireNonNull(sourceUpdatedAt, "sourceUpdatedAt");
    }

    public static SearchDocument tombstone(
            long productId, long sourceRevision, Instant sourceUpdatedAt) {
        return new SearchDocument(
                productId, null, null, null, null, null, null, null,
                false, sourceRevision, sourceUpdatedAt);
    }
}
~~~

- [ ] **Step 4: Implement one-statement source rehydration**

SourceSnapshotRepository.java:

~~~java
package com.interview.mysqlescdc.consumer.source;

import java.util.Optional;

public interface SourceSnapshotRepository {
    Optional<SourceProductSnapshot> load(long productId);
}
~~~

JdbcSourceSnapshotRepository uses one SQL statement:

~~~sql
SELECT
  r.product_id,
  r.revision,
  r.active,
  p.sku,
  p.name,
  p.description,
  p.category_id,
  c.name AS category_name,
  p.price_cents,
  i.available_quantity,
  GREATEST(
    r.updated_at,
    p.updated_at,
    c.updated_at,
    i.updated_at
  ) AS source_updated_at
FROM product_search_revision r
JOIN products p ON p.id = r.product_id
JOIN categories c ON c.id = p.category_id
JOIN inventory i ON i.product_id = p.id
WHERE r.product_id = :productId
~~~

Map active=false to SourceProductSnapshot.inactive even though the joined business columns still exist. One SQL statement gives one MySQL statement snapshot; do not perform four independent selects.

- [ ] **Step 5: Implement the deterministic projector**

~~~java
package com.interview.mysqlescdc.consumer.projection;

import org.springframework.stereotype.Component;

import com.interview.mysqlescdc.consumer.source.SourceProductSnapshot;

@Component
public class SearchDocumentProjector {
    public SearchDocument project(SourceProductSnapshot source) {
        if (!source.active()) {
            return SearchDocument.tombstone(
                    source.productId(), source.revision(), source.updatedAt());
        }
        return new SearchDocument(
                source.productId(),
                source.sku(),
                source.name(),
                source.description(),
                source.categoryId(),
                source.categoryName(),
                source.priceCents(),
                source.availableQuantity(),
                true,
                source.revision(),
                source.updatedAt());
    }
}
~~~

- [ ] **Step 6: Verify projection and real MySQL rehydration**

Run:

~~~bash
./mvnw -pl search-sync-consumer \
  -Dtest=SearchDocumentProjectorTest,JdbcSourceSnapshotRepositoryIT test
~~~

Expected: active and inactive fixtures pass; the integration test observes category and inventory changes through the single query.

- [ ] **Step 7: Commit source rehydration**

~~~bash
git add search-sync-consumer
git commit -m "feat(cdc-lab): rehydrate deterministic search documents"
~~~

---

### Task 3: Write exact Bulk items through versioned aliases

**Files:**

- Create: mysql-es-cdc-handson/infra/elasticsearch/bootstrap-products-v2.sh
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/BulkOutcome.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/BulkItemResult.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/BulkWriteResult.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/ElasticsearchGateway.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/sink/RestElasticsearchGateway.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/sink/RestElasticsearchGatewayTest.java

**Interfaces:**

- Consumes: target alias and ordered SearchDocument list.
- Produces: one BulkItemResult per input document, preserving input order.

- [ ] **Step 1: Write Bulk classification tests**

The test server returns one success, one version conflict, one mapper error, one throttling error, and one non-version 409:

~~~json
{
  "errors": true,
  "items": [
    {"index":{"_id":"1","status":201,"result":"created","_version":4}},
    {"index":{"_id":"2","status":409,"error":{"type":"version_conflict_engine_exception","reason":"current version [8] is higher"}}},
    {"index":{"_id":"3","status":400,"error":{"type":"mapper_parsing_exception","reason":"failed to parse field"}}},
    {"index":{"_id":"4","status":429,"error":{"type":"es_rejected_execution_exception","reason":"rejected"}}},
    {"index":{"_id":"5","status":409,"error":{"type":"illegal_argument_exception","reason":"alias contract conflict"}}}
  ]
}
~~~

Assert outcomes APPLIED, STALE, PERMANENT_FAILURE, RETRYABLE_FAILURE, and PERMANENT_FAILURE in that order. Also assert the request body contains version_type external for all five items and ends with a newline.

- [ ] **Step 2: Run the test and verify the red state**

Run:

~~~bash
./mvnw -pl search-sync-consumer -Dtest=RestElasticsearchGatewayTest test
~~~

Expected: FAIL because sink types do not exist.

- [ ] **Step 3: Define Bulk result types**

~~~java
public enum BulkOutcome {
    APPLIED,
    STALE,
    PERMANENT_FAILURE,
    RETRYABLE_FAILURE
}
~~~

~~~java
public record BulkItemResult(
        long productId,
        long revision,
        BulkOutcome outcome,
        int status,
        String errorType,
        String reason) {
    public boolean settled() {
        return outcome != BulkOutcome.RETRYABLE_FAILURE;
    }
}
~~~

~~~java
public record BulkWriteResult(List<BulkItemResult> items) {
    public boolean hasRetryableFailure() {
        return items.stream().anyMatch(
                item -> item.outcome() == BulkOutcome.RETRYABLE_FAILURE);
    }
}
~~~

ElasticsearchGateway:

~~~java
public interface ElasticsearchGateway {
    BulkWriteResult write(String targetAlias, List<SearchDocument> documents);
}
~~~

- [ ] **Step 4: Implement NDJSON with strict external versions**

RestElasticsearchGateway must build exactly two NDJSON lines per document:

~~~json
{"index":{"_index":"products_write","_id":"2101","version":4,"version_type":"external"}}
{"product_id":2101,"sku":"SKU-2101","name":"Keyboard","description":"Mechanical","category_id":10,"category_name":"Accessories","price_cents":12999,"available_quantity":8,"searchable":true,"source_revision":4,"source_updated_at":"2026-07-22T01:02:03Z"}
~~~

Its request builder is explicit and always appends the final newline:

~~~java
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
            body.append(json.writeValueAsString(document)).append('\n');
        } catch (JacksonException exception) {
            throw new IllegalArgumentException("cannot serialize Bulk document", exception);
        }
    }
    return body.toString();
}
~~~

Use:

~~~java
restClient.post()
        .uri("/_bulk?require_alias=true")
        .contentType(MediaType.parseMediaType("application/x-ndjson"))
        .body(ndjson)
        .retrieve()
        .body(String.class);
~~~

Classification rules are exact:

- 200 or 201 → APPLIED;
- 409 with error.type=version_conflict_engine_exception → STALE and settled;
- any other 409 → PERMANENT_FAILURE;
- 408, 429, or any 5xx → RETRYABLE_FAILURE;
- every other 4xx → PERMANENT_FAILURE.

Top-level transport exceptions become a BulkTransportException and are retryable by the processor. A response item count different from the request count is a protocol error and must not be acknowledged.

Parse each item independently; never branch only on top-level `errors`:

~~~java
private BulkWriteResult parseResponse(String payload, List<SearchDocument> documents) {
    try {
        JsonNode items = json.readTree(payload).path("items");
        if (!items.isArray() || items.size() != documents.size()) {
            throw new BulkProtocolException("Bulk item count does not match request");
        }
        List<BulkItemResult> results = new ArrayList<>(documents.size());
        for (int index = 0; index < documents.size(); index++) {
            SearchDocument document = documents.get(index);
            JsonNode item = items.get(index).path("index");
            int status = item.path("status").asInt(-1);
            JsonNode error = item.path("error");
            String errorType = error.path("type").asText(null);
            BulkOutcome outcome = classify(status, errorType);
            results.add(new BulkItemResult(
                    document.productId(),
                    document.sourceRevision(),
                    outcome,
                    status,
                    errorType,
                    error.path("reason").asText(null)));
        }
        return new BulkWriteResult(List.copyOf(results));
    } catch (JacksonException exception) {
        throw new BulkProtocolException("invalid Elasticsearch Bulk response", exception);
    }
}

private static BulkOutcome classify(int status, String errorType) {
    if (status == 200 || status == 201) return BulkOutcome.APPLIED;
    if (status == 409 && "version_conflict_engine_exception".equals(errorType)) {
        return BulkOutcome.STALE;
    }
    if (status == 408 || status == 429 || status >= 500) {
        return BulkOutcome.RETRYABLE_FAILURE;
    }
    if (status >= 400 && status < 500) return BulkOutcome.PERMANENT_FAILURE;
    throw new BulkProtocolException("unexpected Bulk item status: " + status);
}
~~~

- [ ] **Step 5: Bootstrap the physical index and aliases**

Create bootstrap-products-v2.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

curl -fsS -X PUT http://localhost:9200/_index_template/products-search \
  -H 'Content-Type: application/json' \
  --data-binary @infra/elasticsearch/index-template.json

curl -fsS -X PUT http://localhost:9200/products_v2 \
  -H 'Content-Type: application/json' \
  -d '{
    "mappings": {
      "_meta": {
        "schema_version": 1,
        "deletion_mode": "tombstone",
        "generation": "products_v2"
      }
    }
  }'

curl -fsS -X POST http://localhost:9200/_aliases \
  -H 'Content-Type: application/json' \
  -d '{
    "actions": [
      {"add":{"index":"products_v2","alias":"products_write","is_write_index":true}},
      {"add":{"index":"products_v2","alias":"products_search","filter":{"term":{"searchable":true}}}}
    ]
  }'
~~~

- [ ] **Step 6: Verify all item classes and aliases**

Run:

~~~bash
./mvnw -pl search-sync-consumer -Dtest=RestElasticsearchGatewayTest test
bash infra/elasticsearch/bootstrap-products-v2.sh
curl -fsS http://localhost:9200/_alias/products_write | jq -e 'has("products_v2")'
curl -fsS http://localhost:9200/_alias/products_search | jq -e 'has("products_v2")'
~~~

Expected: all tests pass and both aliases point only to products_v2.

- [ ] **Step 7: Commit the versioned sink**

~~~bash
git add infra/elasticsearch search-sync-consumer
git commit -m "feat(cdc-lab): add revision-fenced Elasticsearch bulk writes"
~~~

---

### Task 4: Persist an idempotent DLQ before offsets can advance

**Files:**

- Create: mysql-es-cdc-handson/infra/mysql/init/03-pipeline-control.sql
- Create: mysql-es-cdc-handson/infra/mysql/apply-pipeline-control.sh
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/DlqStatus.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/DlqRecord.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/DlqStore.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/JdbcDlqStore.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/RecordDlqRecord.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/RecordDlqStore.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/JdbcRecordDlqStore.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/dlq/JdbcDlqStoreIT.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/dlq/JdbcRecordDlqStoreIT.java

**Interfaces:**

- Consumes: either a deterministic product event ID and permanent item failure, or a record ID topic:partition:offset and an unparseable raw Kafka value.
- Produces: one durable PENDING row in the corresponding DLQ table; duplicate publication updates attempts and last_error without creating a second logical item.

- [ ] **Step 1: Write the failing DLQ idempotency test**

The test publishes the same event twice and asserts:

~~~java
assertThat(store.unresolvedCount()).isEqualTo(1);
assertThat(store.findPending("topic:1:42:2101"))
        .get()
        .extracting(DlqRecord::attempts)
        .isEqualTo(2);
~~~

Then resolve it and assert unresolvedCount is zero and resolved_at is non-null.

Add a second test that publishes the same malformed record twice with ID topic:1:42. Assert one `sync_record_dlq` row, attempts=2, the original raw value is byte-for-byte unchanged, and product_id/source_revision are not required.

- [ ] **Step 2: Add the durable control table**

Create 03-pipeline-control.sql:

~~~sql
USE product_catalog;

CREATE TABLE IF NOT EXISTS sync_dlq_record (
  event_id VARCHAR(300) NOT NULL,
  topic_name VARCHAR(200) NOT NULL,
  partition_no INT NOT NULL,
  offset_no BIGINT NOT NULL,
  product_id BIGINT NOT NULL,
  source_revision BIGINT NOT NULL,
  payload JSON NOT NULL,
  failure_class VARCHAR(100) NOT NULL,
  last_error TEXT NOT NULL,
  status VARCHAR(20) NOT NULL,
  attempts INT NOT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  resolved_at TIMESTAMP(6) NULL,
  PRIMARY KEY (event_id),
  KEY ix_dlq_status_created (status, created_at),
  CONSTRAINT ck_dlq_status CHECK (status IN ('PENDING', 'RESOLVED'))
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS sync_record_dlq (
  record_id VARCHAR(300) NOT NULL,
  topic_name VARCHAR(200) NOT NULL,
  partition_no INT NOT NULL,
  offset_no BIGINT NOT NULL,
  raw_key TEXT NULL,
  raw_payload MEDIUMTEXT NOT NULL,
  failure_class VARCHAR(100) NOT NULL,
  last_error TEXT NOT NULL,
  status VARCHAR(20) NOT NULL,
  attempts INT NOT NULL,
  created_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  resolved_at TIMESTAMP(6) NULL,
  PRIMARY KEY (record_id),
  UNIQUE KEY uk_record_dlq_source (topic_name, partition_no, offset_no),
  KEY ix_record_dlq_status_created (status, created_at),
  CONSTRAINT ck_record_dlq_status CHECK (status IN ('PENDING', 'RESOLVED'))
) ENGINE=InnoDB;
~~~

Create apply-pipeline-control.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
docker compose -f infra/compose.yaml exec -T mysql \
  mysql -uroot -prootpass \
  < infra/mysql/init/03-pipeline-control.sql
~~~

- [ ] **Step 3: Implement the DLQ store**

DlqStore:

~~~java
public interface DlqStore {
    void publish(DlqRecord record);
    Optional<DlqRecord> findPending(String eventId);
    void resolve(String eventId);
    long unresolvedCount();
}
~~~

RecordDlqStore has the same lifecycle but never requires parsed business identifiers:

~~~java
public interface RecordDlqStore {
    void publish(RecordDlqRecord record);
    Optional<RecordDlqRecord> findPending(String recordId);
    void resolve(String recordId);
    long unresolvedCount();
}
~~~

JdbcRecordDlqStore uses record_id=topic:partition:offset and the same idempotent reopen-on-recurrence rule. Store raw_payload as text, not JSON, because invalid JSON is a supported poison case.

JdbcDlqStore.publish uses this idempotent statement:

~~~sql
INSERT INTO sync_dlq_record (
  event_id, topic_name, partition_no, offset_no, product_id,
  source_revision, payload, failure_class, last_error, status, attempts
) VALUES (
  :eventId, :topic, :partition, :offset, :productId,
  :revision, CAST(:payload AS JSON), :failureClass, :lastError, 'PENDING', 1
)
ON DUPLICATE KEY UPDATE
  attempts = attempts + 1,
  failure_class = VALUES(failure_class),
  last_error = VALUES(last_error),
  status = 'PENDING',
  resolved_at = NULL,
  updated_at = CURRENT_TIMESTAMP(6)
~~~

resolve updates only PENDING rows to RESOLVED and sets resolved_at. A later permanent publication of the same deterministic event reopens the row instead of hiding a recurring failure. It must not delete evidence.

- [ ] **Step 4: Run migration and integration test**

Run:

~~~bash
bash infra/mysql/apply-pipeline-control.sh
./mvnw -pl search-sync-consumer -Dtest=JdbcDlqStoreIT,JdbcRecordDlqStoreIT test
~~~

Expected: PASS; duplicate product and record publications each remain one row with attempts=2.

- [ ] **Step 5: Commit the durable DLQ**

~~~bash
git add infra/mysql search-sync-consumer
git commit -m "feat(cdc-lab): persist idempotent consumer DLQ records"
~~~

---

### Task 5: Process and acknowledge Kafka records at the Elasticsearch-or-durable-DLQ boundary

**Files:**

- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/pipeline/ProcessingResult.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/pipeline/RetryablePipelineException.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/pipeline/SyncRecordProcessor.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/pipeline/SearchRevisionListener.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/config/KafkaListenerConfiguration.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/failpoint/Failpoint.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/failpoint/CrashAction.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/failpoint/ProcessCrashAction.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/failpoint/FailpointRegistry.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/pipeline/SyncRecordProcessorTest.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/pipeline/SearchRevisionListenerTest.java

**Interfaces:**

- Consumes: one ConsumerRecord with zero or more revision rows.
- Produces: ProcessingResult only when every unique product in the record is settled. Any retryable item throws and leaves the record unacknowledged.

- [ ] **Step 1: Write the four settlement tests**

SyncRecordProcessorTest must cover:

1. APPLIED → no DLQ, result settled.
2. version_conflict_engine_exception 409 → no DLQ, result settled.
3. non-version 409 or other PERMANENT_FAILURE → product DLQ publish succeeds, result settled.
4. RETRYABLE_FAILURE after three attempts → throws RetryablePipelineException and does not publish DLQ.
5. invalid JSON or a revision row missing product_id is attempted three times, persisted to record DLQ, and only then settled.
6. record-DLQ publication failure leaves the Kafka record unacknowledged.

SearchRevisionListenerTest must verify call order:

~~~text
processor.process
failpoint AFTER_ES_BULK_SUCCESS
failpoint BEFORE_KAFKA_OFFSET_COMMIT
acknowledgment.acknowledge
~~~

and verify acknowledge is never called when process throws.

- [ ] **Step 2: Run tests and verify the red state**

Run:

~~~bash
./mvnw -pl search-sync-consumer \
  -Dtest=SyncRecordProcessorTest,SearchRevisionListenerTest test
~~~

Expected: FAIL because pipeline classes do not exist.

- [ ] **Step 3: Implement record processing**

SyncRecordProcessor must:

1. Parse the record value. On invalid JSON, unsupported required fields, or a revision row without product_id, make exactly three bounded parse attempts; then publish the original raw record to `sync_record_dlq` with ID topic:partition:offset and invoke AFTER_DLQ_PUBLISH only after commit.
2. Deduplicate repeated product IDs within that record, keeping the highest eventRevision.
3. Load current MySQL source snapshots.
4. Reject a missing source row as a permanent contract failure.
5. Reject source.revision < eventRevision as a retryable source-read race.
6. Project documents and submit one Bulk request.
7. Retry only when the result contains RETRYABLE_FAILURE, up to pipeline.retry-attempts.
8. Publish each PERMANENT_FAILURE to DLQ with event ID topic:partition:offset:productId, then invoke the `AFTER_DLQ_PUBLISH` failpoint only after the DLQ transaction has committed.
9. Return only after every result is APPLIED, STALE, or durably in the product or record DLQ.

The public method is:

~~~java
public ProcessingResult process(ConsumerRecord<String, String> record)
~~~

ProcessingResult records:

~~~java
public record ProcessingResult(
        int signalCount,
        int appliedCount,
        int staleCount,
        int productDlqCount,
        int recordDlqCount,
        long highestSourceRevision) {
}
~~~

Do not catch Error or process-termination exceptions.

- [ ] **Step 4: Implement listener and container error behavior**

Create the checkpoint types before compiling the listener:

~~~java
public enum Failpoint {
    AFTER_ES_BULK_SUCCESS,
    AFTER_DLQ_PUBLISH,
    BEFORE_KAFKA_OFFSET_COMMIT
}
~~~

~~~java
@FunctionalInterface
public interface CrashAction {
    void crash(int exitCode);
}
~~~

~~~java
@Component
public final class ProcessCrashAction implements CrashAction {
    private final boolean enabled;

    public ProcessCrashAction(
            @Value("${lab.failpoints.enabled:false}") boolean enabled) {
        this.enabled = enabled;
    }

    @Override
    public void crash(int exitCode) {
        if (!enabled) {
            throw new IllegalStateException("process failpoints are disabled");
        }
        Runtime.getRuntime().halt(exitCode);
    }
}
~~~

~~~java
@Component
public final class FailpointRegistry {
    private final Map<Failpoint, AtomicInteger> counters =
            new EnumMap<>(Failpoint.class);
    private final CrashAction crashAction;

    public FailpointRegistry(CrashAction crashAction) {
        this.crashAction = crashAction;
        for (Failpoint failpoint : Failpoint.values()) {
            counters.put(failpoint, new AtomicInteger());
        }
    }

    public void arm(Failpoint failpoint, int hits) {
        if (hits < 1 || hits > 100) {
            throw new IllegalArgumentException("hits must be in 1..100");
        }
        counters.get(failpoint).set(hits);
    }

    public void clear() {
        counters.values().forEach(counter -> counter.set(0));
    }

    public void hit(Failpoint failpoint) {
        int previous = counters.get(failpoint)
                .getAndUpdate(value -> value > 0 ? value - 1 : 0);
        if (previous > 0) {
            crashAction.crash(86);
        }
    }
}
~~~

With every counter initially zero, normal execution is a no-op.

SearchRevisionListener:

~~~java
@Component
public class SearchRevisionListener {
    private final SyncRecordProcessor processor;
    private final FailpointRegistry failpoints;

    public SearchRevisionListener(
            SyncRecordProcessor processor,
            FailpointRegistry failpoints) {
        this.processor = processor;
        this.failpoints = failpoints;
    }

    @KafkaListener(
            topics = "product-search-revisions",
            groupId = "product-search-sync-v1",
            ackMode = "MANUAL_IMMEDIATE")
    public void onRevision(
            ConsumerRecord<String, String> record,
            Acknowledgment acknowledgment) {
        ProcessingResult result = processor.process(record);
        if (result.appliedCount() > 0) {
            failpoints.hit(Failpoint.AFTER_ES_BULK_SUCCESS);
        }
        failpoints.hit(Failpoint.BEFORE_KAFKA_OFFSET_COMMIT);
        acknowledgment.acknowledge();
    }
}
~~~

KafkaListenerConfiguration creates this handler and a manual-immediate container factory:

~~~java
@Bean
DefaultErrorHandler pipelineErrorHandler() {
    DefaultErrorHandler handler =
            new DefaultErrorHandler(new FixedBackOff(1_000L, Long.MAX_VALUE));
    handler.setAckAfterHandle(false);
    handler.setCommitRecovered(false);
    return handler;
}
~~~

The processor performs three immediate attempts per listener delivery. If a transient dependency is still down, the handler redelivers at one-second intervals without acknowledging or skipping; this is an offset-holding recovery loop, not an unbounded tight in-method retry. Permanent data errors do not enter this loop because they are durably published to DLQ. Set `syncCommits=true` on the consumer factory.

- [ ] **Step 5: Run settlement tests**

Run:

~~~bash
./mvnw -pl search-sync-consumer \
  -Dtest=SyncRecordProcessorTest,SearchRevisionListenerTest test
~~~

Expected: all six processor paths and both listener ACK paths pass.

- [ ] **Step 6: Prove an M2 happy path**

Run the stack, bootstrap products_v2, create product 2201, then update inventory and category. Poll conditions, never fixed sleeps:

~~~bash
curl -fsS http://localhost:9200/products_search/_doc/2201 \
  | jq -e '
      ._source.product_id == 2201
      and ._source.category_name == "Computer Accessories"
      and ._source.available_quantity == 8
      and ._source.source_revision == 3
      and ._source.searchable == true
    '
~~~

Delete product 2201 and verify the write alias contains `searchable=false` at revision 4. Verify exclusion through `_search`, because Elasticsearch alias filters are search filters and must not be tested with the direct GET-by-ID API:

~~~bash
curl -fsS http://localhost:9200/products_search/_search \
  -H 'Content-Type: application/json' \
  -d '{"query":{"ids":{"values":["2201"]}}}' \
  | jq -e '.hits.total.value == 0'
~~~

- [ ] **Step 7: Commit the acknowledgment boundary**

~~~bash
git add search-sync-consumer
git commit -m "feat(cdc-lab): ack only after ES or durable DLQ"
~~~

---

### Task 6: Add deterministic crash failpoints and prove duplicate delivery is harmless

**Files:**

- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/failpoint/FailpointController.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/failpoint/FailpointRegistryTest.java
- Create: mysql-es-cdc-handson/scenarios/definitions/m3-after-es-before-offset.json
- Create: mysql-es-cdc-handson/scenarios/definitions/m3-after-dlq-before-offset.json
- Create: mysql-es-cdc-handson/scenarios/scripts/run-m3-after-es-before-offset.sh
- Create: mysql-es-cdc-handson/scenarios/scripts/run-m3-after-dlq-before-offset.sh

**Interfaces:**

- Consumes: one armed failpoint with a remaining hit count.
- Produces: deterministic process exit code 86 at AFTER_ES_BULK_SUCCESS or AFTER_DLQ_PUBLISH.

- [ ] **Step 1: Write failpoint tests**

Test that:

- an unarmed point does nothing;
- arm(point, 1) calls the fake CrashAction exactly once;
- the second hit does nothing;
- production ProcessCrashAction delegates to Runtime.halt only under the lab Spring profile.

- [ ] **Step 2: Expose the Task 5 failpoint state only through the lab API**

Reuse the `Failpoint`, `CrashAction`, `ProcessCrashAction`, and `FailpointRegistry` types created before the listener in Task 5. Do not create a second checkpoint mechanism.

Annotate `FailpointController` with `@ConditionalOnProperty(name="lab.failpoints.enabled", havingValue="true")` and expose:

~~~text
POST /internal/failpoints/{name}/arm?hits=1
DELETE /internal/failpoints
GET /internal/failpoints
~~~

Reject hits outside 1..100.

- [ ] **Step 3: Insert the DLQ failpoint at the correct boundary**

In SyncRecordProcessor, call:

~~~java
dlqStore.publish(record);
failpoints.hit(Failpoint.AFTER_DLQ_PUBLISH);
~~~

The call must be after the MySQL DLQ transaction commits and before ProcessingResult is returned.

- [ ] **Step 4: Implement after-ES-before-offset scenario**

The scenario runner must:

1. Start with lag zero and product 2301 at revision 1.
2. Arm AFTER_ES_BULK_SUCCESS for one hit.
3. Change price, producing revision 2.
4. Wait until the consumer container exits with code 86.
5. Query products_write directly and capture revision 2.
6. Capture committed consumer-group offset and prove it has not passed the record.
7. Restart the consumer.
8. Wait until group lag is zero.
9. Verify the document remains exactly revision 2 and no DLQ exists.
10. Record the second processing attempt as APPLIED or STALE, both acceptable settled outcomes.

- [ ] **Step 5: Implement after-DLQ-before-offset scenario**

Create an incompatible mapping for one field, arm AFTER_DLQ_PUBLISH, and produce revision 2. Verify:

- the consumer exits 86;
- exactly one PENDING DLQ row exists;
- the source offset was not committed;
- after restart, DLQ attempts increments but unresolvedCount remains 1;
- after restoring mapping and replaying, status becomes RESOLVED and ES reaches revision 2.

- [ ] **Step 6: Run both scenarios twice**

Run:

~~~bash
bash scenarios/scripts/run-m3-after-es-before-offset.sh
bash scenarios/scripts/run-m3-after-es-before-offset.sh
bash scenarios/scripts/run-m3-after-dlq-before-offset.sh
bash scenarios/scripts/run-m3-after-dlq-before-offset.sh
~~~

Expected: all four runs converge without duplicate DLQ identities or revision regression.

- [ ] **Step 7: Commit deterministic crash coverage**

~~~bash
git add search-sync-consumer scenarios
git commit -m "test(cdc-lab): prove crash-window replay semantics"
~~~

---

### Task 7: Add DLQ replay, pipeline state, metrics, and the M3 verification gate

**Files:**

- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/DlqReplayService.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/RecordDlqReplayService.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/dlq/DlqController.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/health/PipelineState.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/health/PipelineStateRegistry.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/health/PipelineHealthIndicator.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/metrics/PipelineMetrics.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/dlq/DlqReplayServiceTest.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/test/java/com/interview/mysqlescdc/consumer/dlq/RecordDlqReplayServiceTest.java
- Create: mysql-es-cdc-handson/scenarios/scripts/run-m3-matrix.sh
- Create: mysql-es-cdc-handson/docs/02-reliable-pipeline.md
- Create: mysql-es-cdc-handson/docs/03-failure-model.md
- Modify: mysql-es-cdc-handson/Makefile
- Modify: mysql-es-cdc-handson/README.md

**Interfaces:**

- Consumes: a pending product or record DLQ ID after the dependency, mapping, parser, or wire-compatibility defect is fixed.
- Produces: RESOLVED only after the record can be parsed and every resulting product reaches APPLIED or STALE; pipeline states HEALTHY, CATCHING_UP, and DEGRADED.

- [ ] **Step 1: Write DLQ replay tests**

Tests must prove:

- missing event ID returns not found;
- retryable ES failure leaves status PENDING;
- permanent ES failure leaves status PENDING and increments attempts;
- APPLIED marks RESOLVED;
- STALE marks RESOLVED because an equal or newer source revision is already present.
- record replay reparses the stored raw payload, rehydrates current MySQL state for every product, and stays PENDING if parsing or settlement still fails;
- a permanently malformed raw value cannot be administratively marked RESOLVED without a successful independent reconciliation run recorded by M4.

- [ ] **Step 2: Implement replay from current MySQL state**

DlqReplayService.replay(eventId):

1. Load the PENDING DLQ row.
2. Reload current source by productId; never reuse the stale payload as the target document.
3. Project the current document.
4. Write to products_write with the current revision.
5. Resolve only for APPLIED or STALE.
6. Return a ReplayResult containing eventId, priorRevision, currentRevision, outcome, and resolved.

DlqController exposes:

~~~text
GET /internal/dlq?status=PENDING
GET /internal/dlq/count
POST /internal/dlq/{eventId}/replay
GET /internal/record-dlq?status=PENDING
GET /internal/record-dlq/count
POST /internal/record-dlq/{recordId}/replay
~~~

- [ ] **Step 3: Add explicit state and low-cardinality metrics**

PipelineState:

~~~java
public enum PipelineState {
    HEALTHY,
    CATCHING_UP,
    DEGRADED,
    REBUILD_REQUIRED,
    REBUILDING
}
~~~

M2-M3 may set only HEALTHY, CATCHING_UP, and DEGRADED. M4-M5 will activate the other states.

Metrics:

~~~text
cdc_consumer_records_total
cdc_consumer_signals_total
cdc_es_bulk_items_total{outcome}
cdc_retry_total{failure_class}
cdc_product_dlq_unresolved
cdc_record_dlq_unresolved
cdc_stale_revision_total
cdc_last_success_epoch_seconds
~~~

Do not use product_id, event_id, topic offset, or error message as a metric label.

PipelineHealthIndicator returns DOWN for DEGRADED, UNKNOWN for CATCHING_UP, and UP for HEALTHY. A PENDING row in either DLQ forces DEGRADED.

- [ ] **Step 4: Build the M3 scenario matrix**

run-m3-matrix.sh runs these deterministic scenarios:

~~~text
m3-consumer-restart
m3-after-es-before-offset
m3-bulk-partial
m3-duplicate-record
m3-late-old-revision
m3-mapping-conflict
m3-record-parse-dlq
m3-after-dlq-before-offset
m3-delete-then-old-replay
~~~

For every scenario it waits for the consumer group lag to reach zero or for an expected DEGRADED state. It never uses a fixed sleep as a success condition.

- [ ] **Step 5: Write mechanism documents**

docs/02-reliable-pipeline.md must include:

- Canal null record key versus product_id partitionHash;
- parse → rehydrate → project → Bulk item inspect → DLQ/ACK sequence;
- record-level poison handling before product_id exists, including raw-payload preservation and replay after parser correction;
- version_type=external semantics for greater, equal, and lower revisions;
- why a persisted tombstone is required;
- why rehydrating current MySQL state lets an old signal refresh to a newer state.

docs/03-failure-model.md must include:

- transient, replay, permanent data, stale, log-gap, projection-drift, and source-loss classes;
- exact crash-window table;
- why unresolved DLQ means DEGRADED;
- why M3 still cannot detect binlog/Kafka gaps or independent projection bugs.

- [ ] **Step 6: Add M2-M3 commands**

Add to Makefile:

~~~make
.PHONY: bootstrap-index verify-m3 scenario-m3

bootstrap-index:
	bash infra/elasticsearch/bootstrap-products-v2.sh

verify-m3:
	./mvnw -q -pl search-sync-consumer test
	bash scenarios/scripts/run-m3-matrix.sh

scenario-m3:
	bash scenarios/scripts/run-m3-matrix.sh
~~~

- [ ] **Step 7: Run the full M2-M3 gate**

Run:

~~~bash
make reset
make up
bash infra/mysql/apply-pipeline-control.sh
make bootstrap-index
make verify-m3
curl -fsS http://localhost:8082/actuator/metrics/cdc_es_bulk_items_total
curl -fsS http://localhost:8082/internal/dlq/count | jq -e '.unresolved == 0'
curl -fsS http://localhost:8082/internal/record-dlq/count | jq -e '.unresolved == 0'
git diff --check
~~~

Expected:

- unit and integration tests pass;
- all matrix scenarios reach their declared terminal state;
- no scenario advances an offset before ES or durable DLQ;
- final unresolved DLQ is zero;
- active documents and tombstones retain the latest revision.

- [ ] **Step 8: Commit M2-M3**

~~~bash
git add .
git commit -m "feat(cdc-lab): complete reliable CDC consumer semantics"
~~~

## M2-M3 Completion Gate

Do not start M4 until:

- the live compatibility test proves Canal record key is null and product_id partitionHash is stable;
- multi-table rehydration uses one source SQL statement;
- every Bulk item is classified;
- equal/lower external versions cannot overwrite newer documents;
- all deleted products have versioned tombstones;
- retryable failure leaves offsets uncommitted;
- permanent data failure is durably and idempotently stored before ACK;
- malformed or structurally invalid Canal records are durably stored by topic/partition/offset before ACK, without requiring product_id or source_revision;
- both crash failpoints demonstrate replay without regression;
- DLQ replay reads current MySQL state and reaches RESOLVED only after APPLIED or STALE;
- M3 matrix passes twice from a reset environment;
- git status is clean.
