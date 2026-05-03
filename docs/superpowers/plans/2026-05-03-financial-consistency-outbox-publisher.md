# Financial Consistency Outbox Publisher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `financial-consistency/11-outbox-publisher/`, a Spring Boot + MySQL + Kafka continuation of chapter 10 that publishes committed Outbox rows to Kafka, consumes events idempotently, and verifies event propagation facts.

**Architecture:** Start from the chapter 10 Funds Core Service and keep `TransferService` inside a single MySQL local transaction. Add Kafka only after commit through an explicit `OutboxPublisher`, then consume `TransferSucceeded` events into a local `consumer_processed_event` table. Extend the independent verifier so correctness is judged from database facts, not service self-reporting or Kafka offsets.

**Tech Stack:** Java 17, Spring Boot 3.5.9, Maven, Spring Web, Spring JDBC, Spring Kafka, Flyway, MySQL Connector/J, MySQL 8.0 via Docker Compose, Apache Kafka via Docker Compose, JUnit 5.

---

## Documentation Basis

Current Spring Kafka and Kafka Docker documentation was checked with ctx7 before writing this plan.

Relevant Spring Kafka guidance:

- Spring Boot Kafka configuration uses `spring.kafka.bootstrap-servers`, producer/consumer serializers, consumer group id, and listener ack mode.
- Producer configuration can use `acks=all`, `retries`, and `enable.idempotence=true`.
- Listener configuration can use manual ack so the consumer confirms only after its local business fact is written.
- Spring Kafka has retry topics, DLTs, and error handlers, but this phase keeps the main path focused on Outbox publishing plus consumer idempotency facts.

Relevant Apache Kafka Docker guidance:

- The official Apache Kafka image supports single-node KRaft mode through Docker.
- Single-node setups must configure listener/advertised listener values and a one-node offsets topic replication factor.

## Scope Check

This plan implements one educational chapter: reliable event propagation after a local transfer transaction.

Included:

- A self-contained `11-outbox-publisher` copy of the chapter 10 service.
- Docker Compose MySQL + Kafka.
- Spring Kafka producer/consumer configuration.
- Topic `funds.transfer.events`.
- Outbox claim/publish/mark lifecycle.
- Consumer idempotency table and listener.
- Verification extensions for published/consumed event facts.
- Scripts and docs for running and demonstrating duplicate/retry behavior.

Excluded:

- Temporal, Saga orchestration, Camunda, Seata.
- CDC/Debezium.
- Kafka transactions.
- Schema Registry, Avro, Protobuf.
- Production monitoring, alerting, tracing, authentication.
- Real downstream payment, notification, ledger, or clearing services.

## File Structure

Create:

- `financial-consistency/11-outbox-publisher/` by copying `financial-consistency/10-service-prototype/`.
- `financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh`
- `financial-consistency/11-outbox-publisher/scripts/replay-transfer-event.sh`
- `financial-consistency/11-outbox-publisher/scripts/mark-outbox-pending.sh`
- `financial-consistency/11-outbox-publisher/service/src/main/resources/db/migration/V3__add_outbox_publisher_state.sql`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxMessageRecord.java`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublisher.java`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublishController.java`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/kafka/TransferEventEnvelope.java`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/consumer/ConsumerProcessedEventRepository.java`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/consumer/TransferEventConsumer.java`
- `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublisherIntegrationTest.java`
- `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/consumer/TransferEventConsumerIntegrationTest.java`
- `financial-consistency/11-outbox-publisher/docs/01-outbox-publisher.md`
- `financial-consistency/11-outbox-publisher/docs/02-kafka-boundaries.md`
- `financial-consistency/11-outbox-publisher/docs/03-consumer-idempotency.md`
- `financial-consistency/11-outbox-publisher/docs/04-verification.md`
- `financial-consistency/11-outbox-publisher/docs/05-failure-cases.md`

Modify in chapter 11 copy:

- `financial-consistency/11-outbox-publisher/README.md`
- `financial-consistency/11-outbox-publisher/docker-compose.yml`
- `financial-consistency/11-outbox-publisher/scripts/run-service.sh`
- `financial-consistency/11-outbox-publisher/service/pom.xml`
- `financial-consistency/11-outbox-publisher/service/src/main/resources/application.yml`
- `financial-consistency/11-outbox-publisher/service/src/main/resources/application-test.yml`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxRepository.java`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/MysqlFactExtractor.java`
- `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/TransferMysqlVerifier.java`
- `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/SchemaMigrationTest.java`
- `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/verification/TransferMysqlVerifierIntegrationTest.java`
- `financial-consistency/README.md`

## Shared Conventions

Use the existing package:

```text
com.interview.financialconsistency.serviceprototype
```

Use Kafka topic:

```text
funds.transfer.events
```

Use consumer group:

```text
funds-transfer-event-consumer
```

Use event envelope JSON:

```json
{
  "messageId": "M-...",
  "aggregateType": "TRANSFER",
  "aggregateId": "T-...",
  "eventType": "TransferSucceeded",
  "payload": "{\"transferId\":\"T-...\",\"fromAccountId\":\"A-001\",\"toAccountId\":\"B-001\",\"currency\":\"USD\",\"amount\":\"25.0000\"}"
}
```

Outbox statuses:

```text
PENDING, PUBLISHING, PUBLISHED, FAILED_RETRYABLE
```

Consumer processed statuses:

```text
PROCESSED, FAILED_RETRYABLE, FAILED_TERMINAL
```

Every integration test that mutates business tables must reset data in `@BeforeEach`:

```java
jdbcTemplate.update("delete from consumer_processed_event");
jdbcTemplate.update("delete from outbox_message");
jdbcTemplate.update("delete from ledger_entry");
jdbcTemplate.update("delete from transfer_order");
jdbcTemplate.update("delete from idempotency_record");
jdbcTemplate.update("update account set available_balance = 1000.0000, frozen_balance = 0.0000, version = 0 where account_id = 'A-001'");
jdbcTemplate.update("update account set available_balance = 100.0000, frozen_balance = 0.0000, version = 0 where account_id = 'B-001'");
```

## Task 1: Scaffold Chapter 11 From Chapter 10

**Files:**
- Create: `financial-consistency/11-outbox-publisher/`
- Modify: `financial-consistency/11-outbox-publisher/README.md`
- Modify: `financial-consistency/11-outbox-publisher/docker-compose.yml`
- Create: `financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh`
- Modify: `financial-consistency/11-outbox-publisher/scripts/run-service.sh`
- Modify: `financial-consistency/11-outbox-publisher/service/pom.xml`
- Modify: `financial-consistency/11-outbox-publisher/service/src/main/resources/application.yml`
- Modify: `financial-consistency/11-outbox-publisher/service/src/main/resources/application-test.yml`

- [ ] **Step 1: Verify chapter 10 exists**

Run:

```bash
test -d financial-consistency/10-service-prototype
test -f financial-consistency/10-service-prototype/service/pom.xml
```

Expected: both commands exit 0.

- [ ] **Step 2: Copy chapter 10**

Run:

```bash
cp -R financial-consistency/10-service-prototype financial-consistency/11-outbox-publisher
rm -rf financial-consistency/11-outbox-publisher/service/target
```

Expected: `financial-consistency/11-outbox-publisher/service/pom.xml` exists.

- [ ] **Step 3: Rename README**

Replace `financial-consistency/11-outbox-publisher/README.md` with:

````markdown
# 11 Outbox Publisher

这是第 10 章真实工程原型的下一步：保留 `TransferService` 的 MySQL 本地事务边界，把已提交的 `outbox_message(PENDING)` 发布到真实 Kafka，并用消费者幂等表证明重复消息不会造成重复业务效果。

## 目标

- 使用真实 Kafka topic `funds.transfer.events`。
- 用 `OutboxPublisher` 发布已提交的 Outbox 行。
- 发布成功后把 Outbox 标记为 `PUBLISHED`。
- 用 `TransferEventConsumer` 消费事件并写入 `consumer_processed_event`。
- 用 verifier 从 MySQL 事实检查发布和消费是否闭环。

## 运行方式

从仓库根目录运行：

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

手工启动服务：

```bash
bash financial-consistency/11-outbox-publisher/scripts/run-service.sh
```

## 关键边界

- `TransferService` 不直接调用 Kafka。
- Publisher 只能重发 Outbox 事件，不能重做转账。
- Kafka offset 不等于业务完成证明。
- Consumer 必须先写入本地幂等处理事实，再 ack Kafka 消息。
```

- [ ] **Step 4: Update Docker Compose**

Replace `financial-consistency/11-outbox-publisher/docker-compose.yml` with:

```yaml
services:
  mysql:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: funds_core
      MYSQL_USER: funds
      MYSQL_PASSWORD: funds
    ports:
      - "${MYSQL_HOST_PORT:-3308}:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-uroot", "-prootpass"]
      interval: 5s
      timeout: 3s
      retries: 20
    volumes:
      - funds-core-mysql-data:/var/lib/mysql

  kafka:
    image: apache/kafka:latest
    hostname: kafka
    ports:
      - "${KAFKA_HOST_PORT:-9092}:9092"
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:${KAFKA_HOST_PORT:-9092}
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      CLUSTER_ID: MkU3OEVBNTcwNTJENDM2Qk
    healthcheck:
      test: [ "CMD", "/opt/kafka/bin/kafka-topics.sh", "--bootstrap-server", "localhost:9092", "--list" ]
      interval: 5s
      timeout: 5s
      retries: 30
    volumes:
      - funds-core-kafka-data:/tmp/kraft-combined-logs

volumes:
  funds-core-mysql-data:
  funds-core-kafka-data:
```

- [ ] **Step 5: Add `test-outbox-publisher.sh`**

Create `financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/service"

docker compose -f "$ROOT_DIR/docker-compose.yml" up -d mysql kafka

for attempt in {1..90}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -prootpass --silent >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 90 ]; then
    echo "MySQL did not become ready in time" >&2
    exit 1
  fi
done

for attempt in {1..90}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 90 ]; then
    echo "Kafka did not become ready in time" >&2
    exit 1
  fi
done

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --if-not-exists \
  --topic funds.transfer.events \
  --partitions 1 \
  --replication-factor 1

mvn -f "$SERVICE_DIR/pom.xml" test
```

Make it executable:

```bash
chmod +x financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

- [ ] **Step 6: Update `run-service.sh`**

Replace script references so `run-service.sh` starts both services and creates the topic:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/service"

docker compose -f "$ROOT_DIR/docker-compose.yml" up -d mysql kafka

for attempt in {1..90}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -prootpass --silent >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 90 ]; then
    echo "MySQL did not become ready in time" >&2
    exit 1
  fi
done

for attempt in {1..90}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka /opt/kafka/bin/kafka-topics.sh --bootstrap-server localhost:9092 --list >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 90 ]; then
    echo "Kafka did not become ready in time" >&2
    exit 1
  fi
done

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server localhost:9092 \
  --create \
  --if-not-exists \
  --topic funds.transfer.events \
  --partitions 1 \
  --replication-factor 1

mvn -f "$SERVICE_DIR/pom.xml" spring-boot:run
```

- [ ] **Step 7: Add Spring Kafka dependency**

In `financial-consistency/11-outbox-publisher/service/pom.xml`, change name/description and add:

```xml
<dependency>
  <groupId>org.springframework.kafka</groupId>
  <artifactId>spring-kafka</artifactId>
</dependency>
```

Use:

```xml
<name>financial-consistency-outbox-publisher</name>
<description>Outbox publisher and Kafka consumer prototype for financial consistency learning.</description>
```

- [ ] **Step 8: Configure Kafka**

Update `application.yml` and `application-test.yml` to use port `3308` and Kafka:

```yaml
spring:
  application:
    name: financial-consistency-outbox-publisher
  datasource:
    url: jdbc:mysql://localhost:${MYSQL_HOST_PORT:3308}/funds_core?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
    username: funds
    password: funds
  flyway:
    enabled: true
    locations: classpath:db/migration
  kafka:
    bootstrap-servers: localhost:${KAFKA_HOST_PORT:9092}
    producer:
      key-serializer: org.apache.kafka.common.serialization.StringSerializer
      value-serializer: org.apache.kafka.common.serialization.StringSerializer
      acks: all
      retries: 3
      properties:
        enable.idempotence: true
    consumer:
      group-id: funds-transfer-event-consumer
      auto-offset-reset: earliest
      key-deserializer: org.apache.kafka.common.serialization.StringDeserializer
      value-deserializer: org.apache.kafka.common.serialization.StringDeserializer
    listener:
      ack-mode: manual
      missing-topics-fatal: false

app:
  kafka:
    transfer-events-topic: funds.transfer.events
  outbox:
    publisher-id: local-publisher
server:
  port: 8081
```

- [ ] **Step 9: Run first chapter test**

Run:

```bash
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml down -v
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: existing copied chapter 10 tests pass against MySQL + Kafka.

- [ ] **Step 10: Commit**

Run:

```bash
git add financial-consistency/11-outbox-publisher
git commit -m "feat: scaffold outbox publisher chapter"
```

## Task 2: Add Publisher Schema State

**Files:**
- Create: `financial-consistency/11-outbox-publisher/service/src/main/resources/db/migration/V3__add_outbox_publisher_state.sql`
- Modify: `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/SchemaMigrationTest.java`

- [ ] **Step 1: Write failing schema assertions**

Add assertions to `SchemaMigrationTest`:

```java
@Test
void outboxPublisherColumnsAndConsumerTableExist() {
    assertThat(columnNames("outbox_message"))
            .contains("locked_at", "locked_by", "last_error");
    assertThat(columnNames("consumer_processed_event"))
            .contains("event_id", "transfer_id", "topic", "partition_id",
                    "offset_value", "consumer_group", "status", "processed_at", "failure_reason");
}
```

If helper `columnNames` does not exist, add:

```java
private List<String> columnNames(String tableName) {
    return jdbcTemplate.queryForList(
            """
            select column_name
            from information_schema.columns
            where table_schema = database()
              and table_name = ?
            order by ordinal_position
            """,
            String.class,
            tableName);
}
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: fails because `consumer_processed_event`, `locked_at`, `locked_by`, and `last_error` do not exist.

- [ ] **Step 3: Add migration**

Create `V3__add_outbox_publisher_state.sql`:

```sql
alter table outbox_message
  drop check chk_outbox_status;

alter table outbox_message
  add column locked_at timestamp(6) null,
  add column locked_by varchar(128) null,
  add column last_error varchar(1024) null,
  add constraint chk_outbox_status check (status in ('PENDING', 'PUBLISHING', 'PUBLISHED', 'FAILED_RETRYABLE'));

create table consumer_processed_event (
  event_id varchar(64) not null primary key,
  transfer_id varchar(64) not null,
  topic varchar(255) not null,
  partition_id int not null,
  offset_value bigint not null,
  consumer_group varchar(128) not null,
  status varchar(32) not null,
  processed_at timestamp(6) null,
  failure_reason varchar(1024) null,
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  constraint chk_consumer_processed_status check (status in ('PROCESSED', 'FAILED_RETRYABLE', 'FAILED_TERMINAL')),
  unique key uk_consumer_topic_partition_offset (topic, partition_id, offset_value),
  index idx_consumer_transfer_id (transfer_id),
  index idx_consumer_status_created (status, created_at)
);
```

- [ ] **Step 4: Reset database and run tests**

Run:

```bash
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml down -v
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-consistency/11-outbox-publisher/service/src/main/resources/db/migration/V3__add_outbox_publisher_state.sql financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/SchemaMigrationTest.java
git commit -m "feat: add outbox publisher schema"
```

## Task 3: Implement Outbox Publisher

**Files:**
- Create: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxMessageRecord.java`
- Create: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/kafka/TransferEventEnvelope.java`
- Create: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublisher.java`
- Modify: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxRepository.java`
- Create: `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublisherIntegrationTest.java`

- [ ] **Step 1: Write failing publisher test**

Create `OutboxPublisherIntegrationTest`:

```java
package com.interview.financialconsistency.serviceprototype.outbox;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.sql.Timestamp;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class OutboxPublisherIntegrationTest {
    @Autowired
    private TransferService transferService;

    @Autowired
    private OutboxPublisher outboxPublisher;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void cleanBusinessTables() {
        jdbcTemplate.update("delete from consumer_processed_event");
        jdbcTemplate.update("delete from outbox_message");
        jdbcTemplate.update("delete from ledger_entry");
        jdbcTemplate.update("delete from transfer_order");
        jdbcTemplate.update("delete from idempotency_record");
        jdbcTemplate.update(
                "update account set available_balance = 1000.0000, frozen_balance = 0.0000, version = 0 where account_id = 'A-001'");
        jdbcTemplate.update(
                "update account set available_balance = 100.0000, frozen_balance = 0.0000, version = 0 where account_id = 'B-001'");
    }

    @Test
    void publisherMarksPendingOutboxAsPublishedAfterKafkaAck() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "outbox-publisher-key-1", "A-001", "B-001", "USD", new BigDecimal("25.0000")));

        String messageId = messageIdForTransfer(response.transferId());
        assertThat(outboxStatus(messageId)).isEqualTo("PENDING");

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);

        assertThat(outboxStatus(messageId)).isEqualTo("PUBLISHED");
        assertThat(publishedAt(messageId)).isNotNull();
        assertThat(attemptCount(messageId)).isEqualTo(1);
    }

    @Test
    void publisherDoesNotRecreateTransferFacts() {
        TransferResponse response = transferService.transfer(new TransferRequest(
                "outbox-publisher-key-2", "A-001", "B-001", "USD", new BigDecimal("25.0000")));

        assertThat(countRows("transfer_order")).isEqualTo(1);
        assertThat(countRows("ledger_entry")).isEqualTo(2);

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);

        assertThat(messageIdForTransfer(response.transferId())).isNotBlank();
        assertThat(countRows("transfer_order")).isEqualTo(1);
        assertThat(countRows("ledger_entry")).isEqualTo(2);
    }

    private String messageIdForTransfer(String transferId) {
        return jdbcTemplate.queryForObject(
                "select message_id from outbox_message where aggregate_id = ?",
                String.class,
                transferId);
    }

    private String outboxStatus(String messageId) {
        return jdbcTemplate.queryForObject(
                "select status from outbox_message where message_id = ?",
                String.class,
                messageId);
    }

    private Timestamp publishedAt(String messageId) {
        return jdbcTemplate.queryForObject(
                "select published_at from outbox_message where message_id = ?",
                Timestamp.class,
                messageId);
    }

    private int attemptCount(String messageId) {
        Integer count = jdbcTemplate.queryForObject(
                "select attempt_count from outbox_message where message_id = ?",
                Integer.class,
                messageId);
        return count == null ? 0 : count;
    }

    private int countRows(String tableName) {
        Integer count = jdbcTemplate.queryForObject("select count(*) from " + tableName, Integer.class);
        return count == null ? 0 : count;
    }
}
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: fails because `OutboxPublisher` and new repository methods do not exist.

- [ ] **Step 3: Add `OutboxMessageRecord`**

Create:

```java
package com.interview.financialconsistency.serviceprototype.outbox;

public record OutboxMessageRecord(
        String messageId,
        String aggregateType,
        String aggregateId,
        String eventType,
        String payload,
        String status,
        int attemptCount) {
}
```

- [ ] **Step 4: Add `TransferEventEnvelope`**

Create:

```java
package com.interview.financialconsistency.serviceprototype.kafka;

public record TransferEventEnvelope(
        String messageId,
        String aggregateType,
        String aggregateId,
        String eventType,
        String payload) {
}
```

- [ ] **Step 5: Extend `OutboxRepository`**

Add methods:

```java
public int claimPublishable(int batchSize, String publisherId) {
    return jdbcTemplate.update(
            """
            update outbox_message
            set status = 'PUBLISHING',
                locked_by = ?,
                locked_at = current_timestamp(6),
                attempt_count = attempt_count + 1,
                last_error = null
            where status in ('PENDING', 'FAILED_RETRYABLE')
            order by created_at, message_id
            limit ?
            """,
            publisherId,
            batchSize);
}

public List<OutboxMessageRecord> findClaimedBy(String publisherId) {
    return jdbcTemplate.query(
            """
            select message_id, aggregate_type, aggregate_id, event_type, payload, status, attempt_count
            from outbox_message
            where status = 'PUBLISHING'
              and locked_by = ?
            order by created_at, message_id
            """,
            (rs, rowNum) -> new OutboxMessageRecord(
                    rs.getString("message_id"),
                    rs.getString("aggregate_type"),
                    rs.getString("aggregate_id"),
                    rs.getString("event_type"),
                    rs.getString("payload"),
                    rs.getString("status"),
                    rs.getInt("attempt_count")),
            publisherId);
}

public void markPublished(String messageId) {
    int updated = jdbcTemplate.update(
            """
            update outbox_message
            set status = 'PUBLISHED',
                published_at = current_timestamp(6),
                locked_at = null,
                locked_by = null,
                last_error = null
            where message_id = ?
            """,
            messageId);
    if (updated != 1) {
        throw new IllegalStateException("Expected to mark one outbox message published but updated " + updated);
    }
}

public void markFailedRetryable(String messageId, String error) {
    int updated = jdbcTemplate.update(
            """
            update outbox_message
            set status = 'FAILED_RETRYABLE',
                locked_at = null,
                locked_by = null,
                last_error = ?
            where message_id = ?
            """,
            error == null ? "" : error.substring(0, Math.min(error.length(), 1024)),
            messageId);
    if (updated != 1) {
        throw new IllegalStateException("Expected to mark one outbox message retryable but updated " + updated);
    }
}
```

- [ ] **Step 6: Implement `OutboxPublisher`**

Create:

```java
package com.interview.financialconsistency.serviceprototype.outbox;

import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.financialconsistency.serviceprototype.kafka.TransferEventEnvelope;
import java.util.concurrent.TimeUnit;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

@Component
public class OutboxPublisher {
    private final OutboxRepository outboxRepository;
    private final KafkaTemplate<String, String> kafkaTemplate;
    private final ObjectMapper objectMapper;
    private final String topic;
    private final String publisherId;

    public OutboxPublisher(
            OutboxRepository outboxRepository,
            KafkaTemplate<String, String> kafkaTemplate,
            ObjectMapper objectMapper,
            @Value("${app.kafka.transfer-events-topic}") String topic,
            @Value("${app.outbox.publisher-id}") String publisherId) {
        this.outboxRepository = outboxRepository;
        this.kafkaTemplate = kafkaTemplate;
        this.objectMapper = objectMapper;
        this.topic = topic;
        this.publisherId = publisherId;
    }

    public int publishBatch(int batchSize) {
        outboxRepository.claimPublishable(batchSize, publisherId);
        int published = 0;
        for (OutboxMessageRecord message : outboxRepository.findClaimedBy(publisherId)) {
            try {
                kafkaTemplate.send(topic, message.aggregateId(), envelopeJson(message)).get(10, TimeUnit.SECONDS);
                outboxRepository.markPublished(message.messageId());
                published++;
            } catch (Exception ex) {
                outboxRepository.markFailedRetryable(message.messageId(), ex.getMessage());
            }
        }
        return published;
    }

    private String envelopeJson(OutboxMessageRecord message) {
        try {
            return objectMapper.writeValueAsString(new TransferEventEnvelope(
                    message.messageId(),
                    message.aggregateType(),
                    message.aggregateId(),
                    message.eventType(),
                    message.payload()));
        } catch (JsonProcessingException ex) {
            throw new IllegalStateException("Failed to serialize outbox envelope " + message.messageId(), ex);
        }
    }
}
```

- [ ] **Step 7: Run tests**

Run:

```bash
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml down -v
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: tests pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/kafka financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/outbox
git commit -m "feat: publish outbox messages to kafka"
```

## Task 4: Add Consumer Idempotency

**Files:**
- Create: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/consumer/ConsumerProcessedEventRepository.java`
- Create: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/consumer/TransferEventConsumer.java`
- Create: `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/consumer/TransferEventConsumerIntegrationTest.java`

- [ ] **Step 1: Write failing consumer test**

Create `TransferEventConsumerIntegrationTest`:

```java
package com.interview.financialconsistency.serviceprototype.consumer;

import static org.assertj.core.api.Assertions.assertThat;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.financialconsistency.serviceprototype.kafka.TransferEventEnvelope;
import com.interview.financialconsistency.serviceprototype.outbox.OutboxPublisher;
import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.util.Map;
import java.util.concurrent.TimeUnit;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class TransferEventConsumerIntegrationTest {
    @Autowired
    private TransferService transferService;

    @Autowired
    private OutboxPublisher outboxPublisher;

    @Autowired
    private KafkaTemplate<String, String> kafkaTemplate;

    @Autowired
    private ObjectMapper objectMapper;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @Value("${app.kafka.transfer-events-topic}")
    private String topic;

    @BeforeEach
    void cleanBusinessTables() {
        jdbcTemplate.update("delete from consumer_processed_event");
        jdbcTemplate.update("delete from outbox_message");
        jdbcTemplate.update("delete from ledger_entry");
        jdbcTemplate.update("delete from transfer_order");
        jdbcTemplate.update("delete from idempotency_record");
        jdbcTemplate.update(
                "update account set available_balance = 1000.0000, frozen_balance = 0.0000, version = 0 where account_id = 'A-001'");
        jdbcTemplate.update(
                "update account set available_balance = 100.0000, frozen_balance = 0.0000, version = 0 where account_id = 'B-001'");
    }

    @Test
    void consumerWritesProcessedEventAfterPublishedTransferEvent() throws Exception {
        TransferResponse response = createTransfer("consumer-key-1");
        String messageId = messageIdForTransfer(response.transferId());

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);

        awaitProcessedEventCount(messageId, 1);
        assertThat(processedStatus(messageId)).isEqualTo("PROCESSED");
    }

    @Test
    void duplicatePublishedEventIsProcessedOnlyOnce() throws Exception {
        TransferResponse response = createTransfer("consumer-key-2");
        String messageId = messageIdForTransfer(response.transferId());
        String envelopeJson = envelopeJson(messageId);

        assertThat(outboxPublisher.publishBatch(10)).isEqualTo(1);
        awaitProcessedEventCount(messageId, 1);

        kafkaTemplate.send(topic, response.transferId(), envelopeJson).get(10, TimeUnit.SECONDS);
        kafkaTemplate.send(topic, response.transferId(), envelopeJson).get(10, TimeUnit.SECONDS);
        Thread.sleep(1500);

        assertThat(processedEventCount(messageId)).isEqualTo(1);
    }

    private TransferResponse createTransfer(String idempotencyKey) {
        return transferService.transfer(new TransferRequest(
                idempotencyKey, "A-001", "B-001", "USD", new BigDecimal("25.0000")));
    }

    private String messageIdForTransfer(String transferId) {
        return jdbcTemplate.queryForObject(
                "select message_id from outbox_message where aggregate_id = ?",
                String.class,
                transferId);
    }

    private String envelopeJson(String messageId) throws Exception {
        Map<String, Object> row = jdbcTemplate.queryForMap(
                """
                select message_id, aggregate_type, aggregate_id, event_type, cast(payload as char) as payload
                from outbox_message
                where message_id = ?
                """,
                messageId);
        return objectMapper.writeValueAsString(new TransferEventEnvelope(
                (String) row.get("message_id"),
                (String) row.get("aggregate_type"),
                (String) row.get("aggregate_id"),
                (String) row.get("event_type"),
                (String) row.get("payload")));
    }

    private void awaitProcessedEventCount(String eventId, int expected) throws InterruptedException {
        for (int attempt = 0; attempt < 60; attempt++) {
            if (processedEventCount(eventId) == expected) {
                return;
            }
            Thread.sleep(500);
        }
        assertThat(processedEventCount(eventId)).isEqualTo(expected);
    }

    private int processedEventCount(String eventId) {
        Integer count = jdbcTemplate.queryForObject(
                "select count(*) from consumer_processed_event where event_id = ?",
                Integer.class,
                eventId);
        return count == null ? 0 : count;
    }

    private String processedStatus(String eventId) {
        return jdbcTemplate.queryForObject(
                "select status from consumer_processed_event where event_id = ?",
                String.class,
                eventId);
    }
}
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: fails because consumer classes do not exist.

- [ ] **Step 3: Implement repository**

Create:

```java
package com.interview.financialconsistency.serviceprototype.consumer;

import org.springframework.dao.DuplicateKeyException;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Repository;

@Repository
public class ConsumerProcessedEventRepository {
    private final JdbcTemplate jdbcTemplate;

    public ConsumerProcessedEventRepository(JdbcTemplate jdbcTemplate) {
        this.jdbcTemplate = jdbcTemplate;
    }

    public boolean insertProcessed(
            String eventId,
            String transferId,
            String topic,
            int partitionId,
            long offsetValue,
            String consumerGroup) {
        try {
            jdbcTemplate.update(
                    """
                    insert into consumer_processed_event (
                        event_id, transfer_id, topic, partition_id, offset_value,
                        consumer_group, status, processed_at
                    )
                    values (?, ?, ?, ?, ?, ?, 'PROCESSED', current_timestamp(6))
                    """,
                    eventId,
                    transferId,
                    topic,
                    partitionId,
                    offsetValue,
                    consumerGroup);
            return true;
        } catch (DuplicateKeyException ex) {
            return false;
        }
    }

    public int countByEventId(String eventId) {
        Integer count = jdbcTemplate.queryForObject(
                "select count(*) from consumer_processed_event where event_id = ?",
                Integer.class,
                eventId);
        return count == null ? 0 : count;
    }
}
```

- [ ] **Step 4: Implement listener**

Create:

```java
package com.interview.financialconsistency.serviceprototype.consumer;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.interview.financialconsistency.serviceprototype.kafka.TransferEventEnvelope;
import org.apache.kafka.clients.consumer.ConsumerRecord;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.support.Acknowledgment;
import org.springframework.stereotype.Component;

@Component
public class TransferEventConsumer {
    private final ConsumerProcessedEventRepository repository;
    private final ObjectMapper objectMapper;
    private final String consumerGroup;

    public TransferEventConsumer(
            ConsumerProcessedEventRepository repository,
            ObjectMapper objectMapper,
            @Value("${spring.kafka.consumer.group-id}") String consumerGroup) {
        this.repository = repository;
        this.objectMapper = objectMapper;
        this.consumerGroup = consumerGroup;
    }

    @KafkaListener(topics = "${app.kafka.transfer-events-topic}")
    public void consume(ConsumerRecord<String, String> record, Acknowledgment acknowledgment) throws Exception {
        TransferEventEnvelope envelope = objectMapper.readValue(record.value(), TransferEventEnvelope.class);
        JsonNode payload = objectMapper.readTree(envelope.payload());
        String transferId = payload.get("transferId").asText();
        repository.insertProcessed(
                envelope.messageId(),
                transferId,
                record.topic(),
                record.partition(),
                record.offset(),
                consumerGroup);
        acknowledgment.acknowledge();
    }
}
```

This listener acks duplicates too, because a duplicate key means the event was already processed.

- [ ] **Step 5: Run tests**

Run:

```bash
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml down -v
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/consumer financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/consumer
git commit -m "feat: consume transfer events idempotently"
```

## Task 5: Add Publish API And Demo Scripts

**Files:**
- Create: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublishController.java`
- Create: `financial-consistency/11-outbox-publisher/scripts/replay-transfer-event.sh`
- Create: `financial-consistency/11-outbox-publisher/scripts/mark-outbox-pending.sh`
- Create: `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublishControllerIntegrationTest.java`

- [ ] **Step 1: Write failing controller test**

Create `OutboxPublishControllerIntegrationTest`:

```java
package com.interview.financialconsistency.serviceprototype.outbox;

import static org.assertj.core.api.Assertions.assertThat;

import com.interview.financialconsistency.serviceprototype.transfer.TransferRequest;
import com.interview.financialconsistency.serviceprototype.transfer.TransferResponse;
import com.interview.financialconsistency.serviceprototype.transfer.TransferService;
import java.math.BigDecimal;
import java.util.Map;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.boot.test.web.client.TestRestTemplate;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
@ActiveProfiles("test")
class OutboxPublishControllerIntegrationTest {
    @Autowired
    private TestRestTemplate restTemplate;

    @Autowired
    private TransferService transferService;

    @Autowired
    private JdbcTemplate jdbcTemplate;

    @BeforeEach
    void cleanBusinessTables() {
        jdbcTemplate.update("delete from consumer_processed_event");
        jdbcTemplate.update("delete from outbox_message");
        jdbcTemplate.update("delete from ledger_entry");
        jdbcTemplate.update("delete from transfer_order");
        jdbcTemplate.update("delete from idempotency_record");
        jdbcTemplate.update(
                "update account set available_balance = 1000.0000, frozen_balance = 0.0000, version = 0 where account_id = 'A-001'");
        jdbcTemplate.update(
                "update account set available_balance = 100.0000, frozen_balance = 0.0000, version = 0 where account_id = 'B-001'");
    }

    @Test
    void publishOncePublishesPendingOutbox() {
        TransferResponse transfer = transferService.transfer(new TransferRequest(
                "outbox-api-key-1", "A-001", "B-001", "USD", new BigDecimal("25.0000")));
        String messageId = messageIdForTransfer(transfer.transferId());

        Map<?, ?> response = restTemplate.postForObject("/outbox/publish-once", null, Map.class);

        assertThat(response).containsEntry("published", 1);
        assertThat(outboxStatus(messageId)).isEqualTo("PUBLISHED");
    }

    private String messageIdForTransfer(String transferId) {
        return jdbcTemplate.queryForObject(
                "select message_id from outbox_message where aggregate_id = ?",
                String.class,
                transferId);
    }

    private String outboxStatus(String messageId) {
        return jdbcTemplate.queryForObject(
                "select status from outbox_message where message_id = ?",
                String.class,
                messageId);
    }
}
```

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: fails because `/outbox/publish-once` does not exist.

- [ ] **Step 3: Implement controller**

Create:

```java
package com.interview.financialconsistency.serviceprototype.outbox;

import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

@RestController
@RequestMapping("/outbox")
public class OutboxPublishController {
    private final OutboxPublisher outboxPublisher;

    public OutboxPublishController(OutboxPublisher outboxPublisher) {
        this.outboxPublisher = outboxPublisher;
    }

    @PostMapping("/publish-once")
    public PublishOnceResponse publishOnce(@RequestParam(defaultValue = "10") int batchSize) {
        return new PublishOnceResponse(outboxPublisher.publishBatch(batchSize));
    }

    public record PublishOnceResponse(int published) {
    }
}
```

- [ ] **Step 4: Add replay script**

Create `scripts/replay-transfer-event.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: replay-transfer-event.sh <message-id>" >&2
  exit 1
fi

MESSAGE_ID="$1"
if [[ ! "$MESSAGE_ID" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
  echo "message id may only contain letters, numbers, underscore, dot, colon, or dash" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PAYLOAD="$(docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -N -B -ufunds -pfunds funds_core \
  -e "select json_object('messageId', message_id, 'aggregateType', aggregate_type, 'aggregateId', aggregate_id, 'eventType', event_type, 'payload', cast(payload as char)) from outbox_message where message_id = '${MESSAGE_ID}'")"

if [ -z "$PAYLOAD" ]; then
  echo "message not found: $MESSAGE_ID" >&2
  exit 1
fi

printf '%s\n' "$PAYLOAD" | docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T kafka \
  /opt/kafka/bin/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic funds.transfer.events
```

- [ ] **Step 5: Add mark pending script**

Create `scripts/mark-outbox-pending.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: mark-outbox-pending.sh <message-id>" >&2
  exit 1
fi

MESSAGE_ID="$1"
if [[ ! "$MESSAGE_ID" =~ ^[A-Za-z0-9_.:-]+$ ]]; then
  echo "message id may only contain letters, numbers, underscore, dot, colon, or dash" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -ufunds -pfunds funds_core \
  -e "update outbox_message set status = 'PENDING', locked_at = null, locked_by = null where message_id = '${MESSAGE_ID}'"
```

Make scripts executable.

- [ ] **Step 6: Run tests**

Run:

```bash
chmod +x financial-consistency/11-outbox-publisher/scripts/replay-transfer-event.sh financial-consistency/11-outbox-publisher/scripts/mark-outbox-pending.sh
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml down -v
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: tests pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublishController.java financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxPublishControllerIntegrationTest.java financial-consistency/11-outbox-publisher/scripts/replay-transfer-event.sh financial-consistency/11-outbox-publisher/scripts/mark-outbox-pending.sh
git commit -m "feat: expose outbox publishing controls"
```

## Task 6: Extend Verifier For Publish And Consume Facts

**Files:**
- Modify: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/MysqlFactExtractor.java`
- Modify: `financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/TransferMysqlVerifier.java`
- Modify: `financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/verification/TransferMysqlVerifierIntegrationTest.java`

- [ ] **Step 1: Write failing verifier tests**

Add these tests and helpers to `TransferMysqlVerifierIntegrationTest`:

```java
@Test
void verifierFindsPublishedTransferEventWithoutConsumerProcessing() {
    insertSuccessfulTransfer("T-PUBLISHED-NOT-CONSUMED", "REQ-PUBLISHED-NOT-CONSUMED", "50.0000");
    insertLedger("L-PUBLISHED-NOT-CONSUMED-1", "T-PUBLISHED-NOT-CONSUMED", "A-001", "DEBIT", "USD", "50.0000");
    insertLedger("L-PUBLISHED-NOT-CONSUMED-2", "T-PUBLISHED-NOT-CONSUMED", "B-001", "CREDIT", "USD", "50.0000");
    insertSucceededOutbox("M-PUBLISHED-NOT-CONSUMED", "T-PUBLISHED-NOT-CONSUMED");
    markOutboxStatus("M-PUBLISHED-NOT-CONSUMED", "PUBLISHED", 1);

    assertThat(verifyExtractedFacts())
            .extracting(DbInvariantViolation::invariant)
            .containsExactly("CONSUMER_PROCESSED_PUBLISHED_EVENT");
}

@Test
void verifierFindsPublishAttemptStillRetryable() {
    insertSuccessfulTransfer("T-PUBLISH-RETRY", "REQ-PUBLISH-RETRY", "50.0000");
    insertLedger("L-PUBLISH-RETRY-1", "T-PUBLISH-RETRY", "A-001", "DEBIT", "USD", "50.0000");
    insertLedger("L-PUBLISH-RETRY-2", "T-PUBLISH-RETRY", "B-001", "CREDIT", "USD", "50.0000");
    insertSucceededOutbox("M-PUBLISH-RETRY", "T-PUBLISH-RETRY");
    markOutboxStatus("M-PUBLISH-RETRY", "FAILED_RETRYABLE", 1);

    assertThat(verifyExtractedFacts())
            .extracting(DbInvariantViolation::invariant)
            .containsExactly("OUTBOX_PUBLISH_REQUIRED");
}

@Test
void verifierFindsDuplicateConsumerProcessingFacts() {
    DbHistory history = new DbHistory(List.of(
            new DbFact(
                    "consumer_processed_event",
                    "row-1",
                    "M-DUPLICATE-CONSUMED",
                    Map.of("event_id", "M-DUPLICATE-CONSUMED", "status", "PROCESSED")),
            new DbFact(
                    "consumer_processed_event",
                    "row-2",
                    "M-DUPLICATE-CONSUMED",
                    Map.of("event_id", "M-DUPLICATE-CONSUMED", "status", "PROCESSED"))));

    assertThat(verifier.verify(history))
            .extracting(DbInvariantViolation::invariant)
            .containsExactly("CONSUMER_IDEMPOTENT_PROCESSING");
}

@Test
void verifierFindsNoViolationsAfterPublishAndConsume() {
    insertSuccessfulTransfer("T-PUBLISHED-CONSUMED", "REQ-PUBLISHED-CONSUMED", "50.0000");
    insertLedger("L-PUBLISHED-CONSUMED-1", "T-PUBLISHED-CONSUMED", "A-001", "DEBIT", "USD", "50.0000");
    insertLedger("L-PUBLISHED-CONSUMED-2", "T-PUBLISHED-CONSUMED", "B-001", "CREDIT", "USD", "50.0000");
    insertSucceededOutbox("M-PUBLISHED-CONSUMED", "T-PUBLISHED-CONSUMED");
    markOutboxStatus("M-PUBLISHED-CONSUMED", "PUBLISHED", 1);
    insertProcessedEvent("M-PUBLISHED-CONSUMED", "T-PUBLISHED-CONSUMED");

    assertThat(verifyExtractedFacts()).isEmpty();
}

private void markOutboxStatus(String messageId, String status, int attemptCount) {
    jdbcTemplate.update(
            """
            update outbox_message
            set status = ?,
                attempt_count = ?,
                published_at = case when ? = 'PUBLISHED' then current_timestamp(6) else published_at end
            where message_id = ?
            """,
            status,
            attemptCount,
            status,
            messageId);
}

private void insertProcessedEvent(String eventId, String transferId) {
    jdbcTemplate.update(
            """
            insert into consumer_processed_event (
                event_id, transfer_id, topic, partition_id, offset_value,
                consumer_group, status, processed_at
            )
            values (?, ?, 'funds.transfer.events', 0, 100, 'funds-transfer-event-consumer',
                    'PROCESSED', current_timestamp(6))
            """,
            eventId,
            transferId);
}
```

Expected invariants:

```text
OUTBOX_PUBLISH_REQUIRED
CONSUMER_PROCESSED_PUBLISHED_EVENT
CONSUMER_IDEMPOTENT_PROCESSING
```

Rules:

- `PENDING` with `attempt_count=0` is recoverable and not a publish violation.
- `FAILED_RETRYABLE` or `PUBLISHING` with `attempt_count>0` should emit `OUTBOX_PUBLISH_REQUIRED`.
- `PUBLISHED` `TransferSucceeded` needs `consumer_processed_event(PROCESSED)`.
- Duplicate successful consumer facts in synthetic `DbHistory` should emit `CONSUMER_IDEMPOTENT_PROCESSING`.

- [ ] **Step 2: Run test to verify failure**

Run:

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: fails because extractor/verifier do not know `consumer_processed_event` or new invariants.

- [ ] **Step 3: Extract consumer facts**

Add to `MysqlFactExtractor.extractAll()`:

```java
facts.addAll(extractConsumerProcessedEvents());
```

Add method:

```java
private List<DbFact> extractConsumerProcessedEvents() {
    return jdbcTemplate
            .queryForList(
                    """
                    select event_id, transfer_id, topic, partition_id, offset_value,
                           consumer_group, status, processed_at, failure_reason, created_at, updated_at
                    from consumer_processed_event
                    order by event_id
                    """)
            .stream()
            .map(row -> fact("consumer_processed_event", row, "event_id", "event_id"))
            .toList();
}
```

- [ ] **Step 4: Add verifier invariants**

Add constants:

```java
public static final String OUTBOX_PUBLISH_REQUIRED = "OUTBOX_PUBLISH_REQUIRED";
public static final String CONSUMER_PROCESSED_PUBLISHED_EVENT = "CONSUMER_PROCESSED_PUBLISHED_EVENT";
public static final String CONSUMER_IDEMPOTENT_PROCESSING = "CONSUMER_IDEMPOTENT_PROCESSING";
```

Add logic:

- For each `outbox_message` with `event_type=TransferSucceeded`, `aggregate_type=TRANSFER`, `status in FAILED_RETRYABLE,PUBLISHING` and `attempt_count > 0`, report `OUTBOX_PUBLISH_REQUIRED`.
- For each `outbox_message` with `status=PUBLISHED`, require a `consumer_processed_event` where `event_id=message_id` and `status=PROCESSED`.
- For synthetic or extracted consumer facts, if the same `event_id` has more than one `PROCESSED`, report `CONSUMER_IDEMPOTENT_PROCESSING`.

- [ ] **Step 5: Run tests**

Run:

```bash
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml down -v
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-consistency/11-outbox-publisher/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification financial-consistency/11-outbox-publisher/service/src/test/java/com/interview/financialconsistency/serviceprototype/verification
git commit -m "feat: verify outbox publishing and consumption"
```

## Task 7: Add Chapter Documentation And Root Route

**Files:**
- Modify: `financial-consistency/11-outbox-publisher/README.md`
- Create: `financial-consistency/11-outbox-publisher/docs/01-outbox-publisher.md`
- Create: `financial-consistency/11-outbox-publisher/docs/02-kafka-boundaries.md`
- Create: `financial-consistency/11-outbox-publisher/docs/03-consumer-idempotency.md`
- Create: `financial-consistency/11-outbox-publisher/docs/04-verification.md`
- Create: `financial-consistency/11-outbox-publisher/docs/05-failure-cases.md`
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Expand README**

Replace `financial-consistency/11-outbox-publisher/README.md` with this chapter overview:

```markdown
# 11 Outbox Publisher

第 11 章把第 10 章提交后的 `outbox_message(PENDING)` 连接到真实 Kafka。核心目标不是追求更多框架，而是证明一件事：转账本地事务已经提交后，事件传播、重试、重复消费和验证应该分别由哪些事实负责。

## 目标

- `TransferService` 继续只写 MySQL，不调用 Kafka。
- `OutboxPublisher` 发布 `PENDING` 或 `FAILED_RETRYABLE` 事件到 `funds.transfer.events`。
- `TransferEventConsumer` 写入 `consumer_processed_event` 后再 ack Kafka。
- verifier 从 MySQL 事实检查成功转账、Outbox 发布和消费者处理是否闭环。

## 运行方式

```bash
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
bash financial-consistency/11-outbox-publisher/scripts/run-service.sh
```

## 发布链路

```text
transfer_order + ledger_entry + outbox_message(PENDING)
-> commit
-> OutboxPublisher
-> Kafka funds.transfer.events
-> outbox_message(PUBLISHED)
```

Publisher 重试只能重发 Outbox payload，不能重新执行转账。

## 消费者幂等

Kafka 可能重复投递消息。消费者以 `messageId` 写入 `consumer_processed_event`，重复消息命中主键后直接 ack，不重复产生业务处理事实。

## 验证方式

`GET /verification/violations` 会检查：

- 成功转账必须有正确 Outbox。
- 发布失败或停在发布中必须暴露为可恢复问题。
- `PUBLISHED` 事件必须有 `consumer_processed_event(PROCESSED)`。
- 同一事件不能有多个成功消费事实。

## 关键边界

Kafka offset 不是业务完成证明；offset 只说明消费者组对 broker 的读取进度。业务完成证明必须来自消费者自己的数据库事实。
````


- [ ] **Step 2: Write docs**

Create these docs with the specified headings and content points:

```text
docs/01-outbox-publisher.md
- # Outbox Publisher
- Explain that MySQL local transaction writes PENDING first.
- Explain claim: PENDING/FAILED_RETRYABLE -> PUBLISHING.
- Explain success: Kafka ack -> PUBLISHED.
- Explain failure: send error -> FAILED_RETRYABLE.
- State: publisher never calls TransferService.

docs/02-kafka-boundaries.md
- # Kafka Boundaries
- `acks=all` means broker replication accepted the record.
- `enable.idempotence=true` reduces duplicate broker writes from producer retries.
- Producer idempotence does not prove downstream business processing.
- Kafka transactions are intentionally not the mainline in this chapter.

docs/03-consumer-idempotency.md
- # Consumer Idempotency
- Consumer writes `consumer_processed_event` before ack.
- Duplicate `event_id` is treated as already processed and then acked.
- Offset progress is not a substitute for the local processed-event fact.

docs/04-verification.md
- # Verification
- List invariants `OUTBOX_PUBLISH_REQUIRED`, `CONSUMER_PROCESSED_PUBLISHED_EVENT`, and `CONSUMER_IDEMPOTENT_PROCESSING`.
- Explain verifier reads MySQL tables, not service memory or broker offsets.

docs/05-failure-cases.md
- # Failure Cases
- Publisher crashes before send: row remains PENDING/PUBLISHING and is retryable.
- Send succeeds but mark published fails: event may replay and consumer idempotency absorbs duplicate.
- Consumer processes but crashes before ack: Kafka redelivers and idempotency absorbs duplicate.
- Consumer acks without writing local fact: verifier detects missing business proof.
```

- [ ] **Step 3: Update root README**

Add phase after `10-service-prototype`:

```markdown
- [11-outbox-publisher](./11-outbox-publisher/README.md)
  Kafka Outbox 发布器和消费者幂等：把已提交的 Outbox 事件可靠发布到 Kafka，并用消费者处理事实验证传播闭环。
```

Ensure the design link remains present in the "正式设计文档" list:

```markdown
- [2026-05-03-financial-consistency-outbox-publisher-design.md](../docs/superpowers/specs/2026-05-03-financial-consistency-outbox-publisher-design.md)
```

- [ ] **Step 4: Run verification**

Run:

```bash
rg -n "11-outbox-publisher|Kafka offset|consumer_processed_event|Outbox Publisher|Kafka" financial-consistency/README.md financial-consistency/11-outbox-publisher
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: grep finds required terms and tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-consistency/README.md financial-consistency/11-outbox-publisher/README.md financial-consistency/11-outbox-publisher/docs
git commit -m "docs: document outbox publisher chapter"
```

## Task 8: Final Verification And Scope Guard

**Files:**
- Modify only if verification reveals a concrete mismatch in files created by this plan.

- [ ] **Step 1: Reset infrastructure and run full tests**

Run:

```bash
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml down -v
bash financial-consistency/11-outbox-publisher/scripts/test-outbox-publisher.sh
```

Expected: Maven test suite passes.

- [ ] **Step 2: Run service smoke check**

Start service:

```bash
bash financial-consistency/11-outbox-publisher/scripts/run-service.sh
```

In another shell:

```bash
curl -s -X POST http://localhost:8081/transfers \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: smoke-outbox-1' \
  -d '{"fromAccountId":"A-001","toAccountId":"B-001","currency":"USD","amount":"10.0000"}'
curl -s -X POST http://localhost:8081/outbox/publish-once
sleep 3
curl -s http://localhost:8081/verification/violations
```

Expected:

- Transfer response contains `"status":"SUCCEEDED"`.
- Publish response contains `"published":1`.
- Verification response is `[]`.

Stop service with `Ctrl-C`.

- [ ] **Step 3: Replay duplicate event**

Find a published message id:

```bash
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml exec -T mysql mysql -N -B -ufunds -pfunds funds_core \
  -e "select message_id from outbox_message where status = 'PUBLISHED' limit 1"
```

Run:

```bash
bash financial-consistency/11-outbox-publisher/scripts/replay-transfer-event.sh <message-id>
sleep 3
docker compose -f financial-consistency/11-outbox-publisher/docker-compose.yml exec -T mysql mysql -N -B -ufunds -pfunds funds_core \
  -e "select count(*) from consumer_processed_event where event_id = '<message-id>'"
```

Expected: count remains `1`.

- [ ] **Step 4: Scope guard**

Run:

```bash
rg -n "Temporal|Camunda|Seata|Saga|Debezium|Schema Registry|Avro" financial-consistency/11-outbox-publisher/service/src financial-consistency/11-outbox-publisher/scripts
```

Expected: no matches.

- [ ] **Step 5: Documentation boundary check**

Run:

```bash
rg -n "Kafka offset|consumer_processed_event|Outbox.*Kafka|不能.*重做转账|业务完成" financial-consistency/11-outbox-publisher/README.md financial-consistency/11-outbox-publisher/docs
```

Expected: matches explaining offset and business completion boundaries.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short --branch
```

Expected: only known unrelated pre-existing changes remain outside `financial-consistency/11-outbox-publisher` and `financial-consistency/README.md`.

- [ ] **Step 7: Commit final fixes if needed**

If files changed during final verification:

```bash
git add financial-consistency/11-outbox-publisher financial-consistency/README.md
git commit -m "chore: verify outbox publisher chapter"
```

If no files changed, do not create an empty commit.

## Self-Review Checklist

Before declaring this plan complete:

- Every design requirement in `2026-05-03-financial-consistency-outbox-publisher-design.md` maps to a task.
- `TransferService` remains free of Kafka calls.
- Kafka is only introduced through publisher/consumer boundaries.
- Consumer idempotency is a database fact, not broker offset.
- Verifier has positive and negative tests for publish and consume facts.
- Scripts run from repository root.
- No placeholders remain in this plan.
