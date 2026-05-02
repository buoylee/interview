# Financial Consistency Service Prototype Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `financial-consistency/10-service-prototype/`, a Spring Boot + MySQL internal transfer service that writes idempotency records, transfer orders, double-entry ledger rows, account balances, and Outbox facts in one local transaction, then verifies those MySQL facts independently.

**Architecture:** The service is a single Funds Core Service, not a multi-service distributed system. Spring Boot exposes `POST /transfers`, the application layer owns the local transaction, repository classes use JDBC against MySQL, Flyway owns schema migration, and a separate verification package reads database rows into evidence facts and reports invariant violations. Kafka, Temporal, payment channels, and order/travel flows remain outside this phase.

**Tech Stack:** Java 17, Spring Boot 3.5.9, Maven, Spring Web, Spring JDBC, Spring transaction management, Flyway, MySQL Connector/J, MySQL via Docker Compose, JUnit 5 through `spring-boot-starter-test`.

---

## Documentation Basis

Current Spring Boot documentation was checked with ctx7 before writing this plan.

Relevant Spring Boot 3.5.9 guidance:

- `spring.datasource.url`, `spring.datasource.username`, and `spring.datasource.password` trigger DataSource auto-configuration when a JDBC URL is provided.
- Spring Boot integrates Flyway and can run migrations on application startup when Flyway is on the classpath.
- JDBC slice tests are transactional by default, but this plan uses `@SpringBootTest` against a Docker Compose MySQL instance because the phase must verify real MySQL rows and migration behavior.

## Scope Check

This plan implements one subsystem: the internal-transfer Funds Core Service prototype.

Included:

- One Spring Boot service.
- One MySQL schema.
- Internal transfer API.
- Idempotency record with request hash.
- Double-entry ledger.
- Outbox `PENDING` rows.
- Independent database-fact verifier.
- Integration tests and scripts that run against real MySQL.

Excluded:

- Kafka or any real broker.
- Temporal, Camunda, Seata, or workflow engines.
- Payment channel simulation.
- Order, inventory, travel, refund, or manual repair flows.
- Production authentication or authorization.

## File Structure

Create these files:

- `financial-consistency/10-service-prototype/README.md` - chapter entry point and learning path.
- `financial-consistency/10-service-prototype/docs/01-domain-model.md` - account, transfer, ledger, idempotency, Outbox model.
- `financial-consistency/10-service-prototype/docs/02-transaction-boundary.md` - local transaction sequence and failure boundaries.
- `financial-consistency/10-service-prototype/docs/03-outbox-flow.md` - why this phase writes only `PENDING`.
- `financial-consistency/10-service-prototype/docs/04-verification-from-mysql.md` - MySQL rows to facts to violations.
- `financial-consistency/10-service-prototype/docs/05-failure-cases.md` - scenario matrix and expected verifier output.
- `financial-consistency/10-service-prototype/docker-compose.yml` - local MySQL for tests and manual runs.
- `financial-consistency/10-service-prototype/scripts/test-service.sh` - start MySQL, run tests, leave container available.
- `financial-consistency/10-service-prototype/scripts/run-service.sh` - start MySQL and run Spring Boot.
- `financial-consistency/10-service-prototype/service/pom.xml` - independent Maven project.
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/ServicePrototypeApplication.java`
- `financial-consistency/10-service-prototype/service/src/main/resources/application.yml`
- `financial-consistency/10-service-prototype/service/src/main/resources/application-test.yml`
- `financial-consistency/10-service-prototype/service/src/main/resources/db/migration/V1__create_funds_core_schema.sql`
- `financial-consistency/10-service-prototype/service/src/main/resources/db/migration/V2__seed_demo_accounts.sql`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/account/AccountRecord.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/account/AccountRepository.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferRequest.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferResponse.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferService.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferController.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferRepository.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/ledger/LedgerRepository.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/idempotency/IdempotencyRepository.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxRepository.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/DbFact.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/DbHistory.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/DbInvariantViolation.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/MysqlFactExtractor.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/TransferMysqlVerifier.java`
- `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/VerificationController.java`
- `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/ServicePrototypeApplicationTest.java`
- `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/transfer/TransferServiceIntegrationTest.java`
- `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/verification/TransferMysqlVerifierIntegrationTest.java`

Modify:

- `financial-consistency/README.md` - add spec link and phase route.

## Shared Conventions

Use package:

```text
com.interview.financialconsistency.serviceprototype
```

Use table names:

```text
account
transfer_order
ledger_entry
idempotency_record
outbox_message
```

Use demo account ids:

```text
A-001
B-001
```

Use currency:

```text
USD
```

Use exact statuses:

```text
transfer_order.status: INITIATED, SUCCEEDED, FAILED
idempotency_record.status: PROCESSING, SUCCEEDED, FAILED, REJECTED
outbox_message.status: PENDING, PUBLISHED, FAILED_RETRYABLE
ledger_entry.direction: DEBIT, CREDIT
```

Use money as `BigDecimal` in Java and `decimal(19, 4)` in MySQL.

All tests and scripts run from the repository root unless a task explicitly sets another working directory.

## Test Data Isolation

Every integration test class that mutates business tables must reset data in `@BeforeEach` before running its assertions. Use this reset order so foreign-key additions in later phases do not make cleanup brittle:

```java
@BeforeEach
void resetData() {
    jdbcTemplate.update("delete from outbox_message");
    jdbcTemplate.update("delete from ledger_entry");
    jdbcTemplate.update("delete from transfer_order");
    jdbcTemplate.update("delete from idempotency_record");
    jdbcTemplate.update("update account set available_balance = 1000.0000, frozen_balance = 0.0000, version = 0 where account_id = 'A-001'");
    jdbcTemplate.update("update account set available_balance = 100.0000, frozen_balance = 0.0000, version = 0 where account_id = 'B-001'");
}
```

`SchemaMigrationTest` does not need this cleanup because it only checks schema and seed presence. All repository, service, controller, and verifier integration tests must include equivalent cleanup.

## Task 1: Scaffold The Spring Boot Service

**Files:**
- Create: `financial-consistency/10-service-prototype/README.md`
- Create: `financial-consistency/10-service-prototype/docker-compose.yml`
- Create: `financial-consistency/10-service-prototype/scripts/test-service.sh`
- Create: `financial-consistency/10-service-prototype/scripts/run-service.sh`
- Create: `financial-consistency/10-service-prototype/service/pom.xml`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/ServicePrototypeApplication.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/resources/application.yml`
- Create: `financial-consistency/10-service-prototype/service/src/main/resources/application-test.yml`
- Create: `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/ServicePrototypeApplicationTest.java`

- [ ] **Step 1: Run the missing test command**

Run:

```bash
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: fail because `test-service.sh` does not exist.

- [ ] **Step 2: Create `docker-compose.yml`**

Create `financial-consistency/10-service-prototype/docker-compose.yml`:

```yaml
services:
  mysql:
    image: mysql:8.4
    container_name: financial-consistency-mysql
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: funds_core
      MYSQL_USER: funds
      MYSQL_PASSWORD: funds
    ports:
      - "3307:3306"
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-uroot", "-prootpass"]
      interval: 5s
      timeout: 3s
      retries: 20
    volumes:
      - funds-core-mysql-data:/var/lib/mysql

volumes:
  funds-core-mysql-data:
```

- [ ] **Step 3: Create `test-service.sh`**

Create `financial-consistency/10-service-prototype/scripts/test-service.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/service"

docker compose -f "$ROOT_DIR/docker-compose.yml" up -d mysql

for attempt in {1..60}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -prootpass --silent >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 60 ]; then
    echo "MySQL did not become ready in time" >&2
    exit 1
  fi
done

mvn -f "$SERVICE_DIR/pom.xml" test
```

- [ ] **Step 4: Create `run-service.sh`**

Create `financial-consistency/10-service-prototype/scripts/run-service.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_DIR="$ROOT_DIR/service"

docker compose -f "$ROOT_DIR/docker-compose.yml" up -d mysql

for attempt in {1..60}; do
  if docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysqladmin ping -h 127.0.0.1 -uroot -prootpass --silent >/dev/null 2>&1; then
    break
  fi
  sleep 1
  if [ "$attempt" -eq 60 ]; then
    echo "MySQL did not become ready in time" >&2
    exit 1
  fi
done

mvn -f "$SERVICE_DIR/pom.xml" spring-boot:run
```

- [ ] **Step 5: Create `pom.xml`**

Create `financial-consistency/10-service-prototype/service/pom.xml`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>3.5.9</version>
    <relativePath/>
  </parent>

  <groupId>com.interview.financialconsistency</groupId>
  <artifactId>service-prototype</artifactId>
  <version>0.0.1-SNAPSHOT</version>
  <name>financial-consistency-service-prototype</name>
  <description>Internal transfer service prototype for financial consistency learning.</description>

  <properties>
    <java.version>17</java.version>
  </properties>

  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-web</artifactId>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-jdbc</artifactId>
    </dependency>
    <dependency>
      <groupId>org.flywaydb</groupId>
      <artifactId>flyway-core</artifactId>
    </dependency>
    <dependency>
      <groupId>org.flywaydb</groupId>
      <artifactId>flyway-mysql</artifactId>
    </dependency>
    <dependency>
      <groupId>com.mysql</groupId>
      <artifactId>mysql-connector-j</artifactId>
      <scope>runtime</scope>
    </dependency>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-test</artifactId>
      <scope>test</scope>
    </dependency>
  </dependencies>

  <build>
    <plugins>
      <plugin>
        <groupId>org.springframework.boot</groupId>
        <artifactId>spring-boot-maven-plugin</artifactId>
      </plugin>
    </plugins>
  </build>
</project>
```

- [ ] **Step 6: Create application class**

Create `ServicePrototypeApplication.java`:

```java
package com.interview.financialconsistency.serviceprototype;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class ServicePrototypeApplication {
    public static void main(String[] args) {
        SpringApplication.run(ServicePrototypeApplication.class, args);
    }
}
```

- [ ] **Step 7: Create application config**

Create `application.yml`:

```yaml
spring:
  application:
    name: financial-consistency-service-prototype
  datasource:
    url: jdbc:mysql://localhost:3307/funds_core?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
    username: funds
    password: funds
  flyway:
    enabled: true
    locations: classpath:db/migration
server:
  port: 8080
```

Create `application-test.yml`:

```yaml
spring:
  datasource:
    url: jdbc:mysql://localhost:3307/funds_core?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
    username: funds
    password: funds
  flyway:
    enabled: true
    locations: classpath:db/migration
```

- [ ] **Step 8: Add context-load test**

Create `ServicePrototypeApplicationTest.java`:

```java
package com.interview.financialconsistency.serviceprototype;

import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class ServicePrototypeApplicationTest {
    @Test
    void contextLoads() {
    }
}
```

- [ ] **Step 9: Add placeholder README**

Create `README.md`:

```markdown
# 10 真实工程原型

这是内部转账资金内核服务原型，用来把第 09 章的内存事实验证推进到 Spring Boot、MySQL、本地事务、双分录账本和 Outbox。
```

- [ ] **Step 10: Run tests**

Run:

```bash
chmod +x financial-consistency/10-service-prototype/scripts/test-service.sh financial-consistency/10-service-prototype/scripts/run-service.sh
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: Maven test passes. Flyway has no migrations yet, but the Spring context starts with a reachable MySQL DataSource.

- [ ] **Step 11: Commit**

Run:

```bash
git add financial-consistency/10-service-prototype
git commit -m "feat: scaffold financial consistency service prototype"
```

## Task 2: Add MySQL Schema And Seed Accounts

**Files:**
- Create: `financial-consistency/10-service-prototype/service/src/main/resources/db/migration/V1__create_funds_core_schema.sql`
- Create: `financial-consistency/10-service-prototype/service/src/main/resources/db/migration/V2__seed_demo_accounts.sql`
- Create: `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/SchemaMigrationTest.java`

- [ ] **Step 1: Write failing schema test**

Create `SchemaMigrationTest.java`:

```java
package com.interview.financialconsistency.serviceprototype;

import static org.assertj.core.api.Assertions.assertThat;

import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.test.context.ActiveProfiles;

@SpringBootTest
@ActiveProfiles("test")
class SchemaMigrationTest {
    @Autowired
    JdbcTemplate jdbcTemplate;

    @Test
    void flywayCreatesFundsCoreTablesAndSeedAccounts() {
        Integer tableCount = jdbcTemplate.queryForObject("""
                select count(*)
                from information_schema.tables
                where table_schema = database()
                  and table_name in ('account', 'transfer_order', 'ledger_entry', 'idempotency_record', 'outbox_message')
                """, Integer.class);

        Integer accountCount = jdbcTemplate.queryForObject(
                "select count(*) from account where account_id in ('A-001', 'B-001')",
                Integer.class);

        assertThat(tableCount).isEqualTo(5);
        assertThat(accountCount).isEqualTo(2);
    }
}
```

Run:

```bash
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: fail because tables do not exist.

- [ ] **Step 2: Add schema migration**

Create `V1__create_funds_core_schema.sql`:

```sql
create table account (
  account_id varchar(64) not null primary key,
  currency varchar(3) not null,
  available_balance decimal(19, 4) not null,
  frozen_balance decimal(19, 4) not null default 0.0000,
  version bigint not null default 0,
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  constraint chk_account_available_non_negative check (available_balance >= 0),
  constraint chk_account_frozen_non_negative check (frozen_balance >= 0)
);

create table transfer_order (
  transfer_id varchar(64) not null primary key,
  request_id varchar(128) not null,
  from_account_id varchar(64) not null,
  to_account_id varchar(64) not null,
  currency varchar(3) not null,
  amount decimal(19, 4) not null,
  status varchar(32) not null,
  failure_reason varchar(255),
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  constraint chk_transfer_amount_positive check (amount > 0),
  constraint chk_transfer_status check (status in ('INITIATED', 'SUCCEEDED', 'FAILED')),
  index idx_transfer_request_id (request_id),
  index idx_transfer_from_account (from_account_id),
  index idx_transfer_to_account (to_account_id)
);

create table idempotency_record (
  idempotency_key varchar(128) not null primary key,
  request_hash char(64) not null,
  business_type varchar(64) not null,
  business_id varchar(64),
  status varchar(32) not null,
  response_code int,
  response_body text,
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  constraint chk_idempotency_status check (status in ('PROCESSING', 'SUCCEEDED', 'FAILED', 'REJECTED'))
);

create table ledger_entry (
  entry_id varchar(64) not null primary key,
  transfer_id varchar(64) not null,
  account_id varchar(64) not null,
  direction varchar(16) not null,
  currency varchar(3) not null,
  amount decimal(19, 4) not null,
  entry_type varchar(32) not null,
  created_at timestamp(6) not null default current_timestamp(6),
  constraint chk_ledger_direction check (direction in ('DEBIT', 'CREDIT')),
  constraint chk_ledger_amount_positive check (amount > 0),
  unique key uk_ledger_transfer_account_direction_type (transfer_id, account_id, direction, entry_type),
  index idx_ledger_transfer_id (transfer_id),
  index idx_ledger_account_id (account_id)
);

create table outbox_message (
  message_id varchar(64) not null primary key,
  aggregate_type varchar(64) not null,
  aggregate_id varchar(64) not null,
  event_type varchar(64) not null,
  payload json not null,
  status varchar(32) not null,
  created_at timestamp(6) not null default current_timestamp(6),
  updated_at timestamp(6) not null default current_timestamp(6) on update current_timestamp(6),
  published_at timestamp(6) null,
  attempt_count int not null default 0,
  constraint chk_outbox_status check (status in ('PENDING', 'PUBLISHED', 'FAILED_RETRYABLE')),
  index idx_outbox_status_created (status, created_at),
  index idx_outbox_aggregate (aggregate_type, aggregate_id)
);
```

- [ ] **Step 3: Add seed migration**

Create `V2__seed_demo_accounts.sql`:

```sql
insert into account (account_id, currency, available_balance, frozen_balance, version)
values
  ('A-001', 'USD', 1000.0000, 0.0000, 0),
  ('B-001', 'USD', 100.0000, 0.0000, 0);
```

- [ ] **Step 4: Reset local test database and run tests**

Run:

```bash
docker compose -f financial-consistency/10-service-prototype/docker-compose.yml down -v
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: tests pass and schema has five tables plus two seed accounts.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-consistency/10-service-prototype/service/src/main/resources/db/migration financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/SchemaMigrationTest.java
git commit -m "feat: add funds core mysql schema"
```

## Task 3: Implement JDBC Repositories

**Files:**
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/account/AccountRecord.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/account/AccountRepository.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferRepository.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/ledger/LedgerRepository.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/idempotency/IdempotencyRepository.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/outbox/OutboxRepository.java`
- Create: `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/RepositoryIntegrationTest.java`

- [ ] **Step 1: Write failing repository integration test**

Create `RepositoryIntegrationTest.java` with these test methods:

```java
@Test
void accountRepositoryLocksAndUpdatesBalances()

@Test
void repositoriesWriteTransferLedgerIdempotencyAndOutboxFacts()
```

Required assertions:

- `AccountRepository.findForUpdate("A-001")` returns available balance `1000.0000`.
- Updating A by `-25.0000` and B by `25.0000` changes balances to `975.0000` and `125.0000`.
- Repository methods can insert:
  - `transfer_order` with status `SUCCEEDED`
  - two `ledger_entry` rows
  - `idempotency_record`
  - one `outbox_message` with status `PENDING`
- Counts from each table match expected inserted facts.

Run:

```bash
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: fail because repositories do not exist.

- [ ] **Step 2: Implement `AccountRecord`**

Create:

```java
package com.interview.financialconsistency.serviceprototype.account;

import java.math.BigDecimal;

public record AccountRecord(
        String accountId,
        String currency,
        BigDecimal availableBalance,
        BigDecimal frozenBalance,
        long version) {
}
```

- [ ] **Step 3: Implement repositories with `JdbcTemplate`**

Required repository methods:

```java
AccountRepository:
Optional<AccountRecord> findById(String accountId)
AccountRecord findForUpdate(String accountId)
void applyBalanceDelta(String accountId, BigDecimal delta)

TransferRepository:
void insert(String transferId, String requestId, String fromAccountId, String toAccountId, String currency, BigDecimal amount, String status, String failureReason)
Optional<String> findStatus(String transferId)

LedgerRepository:
void insert(String entryId, String transferId, String accountId, String direction, String currency, BigDecimal amount, String entryType)
int countByTransferId(String transferId)

IdempotencyRepository:
int insertProcessing(String idempotencyKey, String requestHash, String businessType)
Optional<Map<String, Object>> findForUpdate(String idempotencyKey)
void markCompleted(String idempotencyKey, String businessId, String status, int responseCode, String responseBody)

OutboxRepository:
void insertPending(String messageId, String aggregateType, String aggregateId, String eventType, String payload)
int countByAggregate(String aggregateType, String aggregateId)
```

Implementation requirements:

- Annotate repositories with `@Repository`.
- Use constructor injection for `JdbcTemplate`.
- `findForUpdate` queries must use `for update`.
- `applyBalanceDelta` must increment `version`.
- Do not use JPA entities.

- [ ] **Step 4: Run tests**

Run:

```bash
docker compose -f financial-consistency/10-service-prototype/docker-compose.yml down -v
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/{account,transfer,ledger,idempotency,outbox} financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/RepositoryIntegrationTest.java
git commit -m "feat: add funds core jdbc repositories"
```

## Task 4: Implement Transfer Service Transaction

**Files:**
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferRequest.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferResponse.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferService.java`
- Create: `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/transfer/TransferServiceIntegrationTest.java`

- [ ] **Step 1: Write failing transfer service tests**

Create tests:

```java
@Test
void successfulTransferWritesAllFactsInOneTransaction()

@Test
void duplicateRequestReturnsSameResultWithoutDuplicateLedger()

@Test
void sameIdempotencyKeyWithDifferentPayloadIsRejected()

@Test
void insufficientFundsDoesNotWriteLedgerOrOutbox()
```

Required assertions:

- Successful transfer from `A-001` to `B-001` for `25.0000`:
  - response status `SUCCEEDED`
  - A balance `975.0000`, B balance `125.0000`
  - one `transfer_order`
  - two `ledger_entry`
  - one `idempotency_record` status `SUCCEEDED`
  - one `outbox_message` status `PENDING`
- Duplicate same idempotency key and same payload:
  - same transfer id returned
  - ledger count remains 2
  - outbox count remains 1
- Same idempotency key with different amount:
  - response status `REJECTED`
  - no new ledger rows
- Insufficient funds:
  - response status `FAILED`
  - no ledger rows
  - no outbox row
  - account balances unchanged

Run:

```bash
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: fail because transfer service does not exist.

- [ ] **Step 2: Implement transfer request and response records**

Create:

```java
public record TransferRequest(
        String idempotencyKey,
        String fromAccountId,
        String toAccountId,
        String currency,
        BigDecimal amount) {
}
```

```java
public record TransferResponse(
        String transferId,
        String status,
        String message) {
}
```

- [ ] **Step 3: Implement request hashing**

Inside `TransferService`, implement a private canonical hash:

```java
private String requestHash(TransferRequest request) {
    String canonical = request.fromAccountId() + "|" +
            request.toAccountId() + "|" +
            request.currency() + "|" +
            request.amount().setScale(4, RoundingMode.UNNECESSARY).toPlainString();
    byte[] digest = MessageDigest.getInstance("SHA-256").digest(canonical.getBytes(StandardCharsets.UTF_8));
    return HexFormat.of().formatHex(digest);
}
```

If scale normalization fails, return a rejected response before writing money facts.

- [ ] **Step 4: Implement transactional transfer flow**

`TransferService.transfer(TransferRequest request)` must be annotated `@Transactional`.

Flow:

1. Validate nonblank idempotency key, different accounts, positive amount, 3-letter currency.
2. Compute request hash.
3. Insert idempotency record as `PROCESSING`.
4. If unique-key conflict occurs:
   - read idempotency record `for update`
   - if request hash differs, return `REJECTED`
   - if status is `SUCCEEDED` or `FAILED`, return stored response
5. Lock accounts in sorted account id order to reduce deadlock risk.
6. If from account has insufficient funds:
   - create `transfer_order` with `FAILED`
   - mark idempotency `FAILED`
   - return `FAILED`
   - do not write ledger or outbox.
7. For success:
   - generate transfer id.
   - insert `transfer_order` `SUCCEEDED`.
   - insert debit and credit ledger entries.
   - update account balances.
   - insert Outbox `PENDING` event `TransferSucceeded`.
   - mark idempotency `SUCCEEDED`.
   - return `SUCCEEDED`.

Implementation constraints:

- Do not call external systems inside the transaction.
- Do not write Outbox outside the transaction.
- Do not catch and suppress unexpected database exceptions.
- Use deterministic JSON payload string for Outbox, enough for tests:

```json
{"transferId":"...","fromAccountId":"A-001","toAccountId":"B-001","currency":"USD","amount":"25.0000"}
```

- [ ] **Step 5: Run tests**

Run:

```bash
docker compose -f financial-consistency/10-service-prototype/docker-compose.yml down -v
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/transfer
git commit -m "feat: add transactional transfer service"
```

## Task 5: Add REST API

**Files:**
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferController.java`
- Create: `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/transfer/TransferControllerIntegrationTest.java`

- [ ] **Step 1: Write failing controller test**

Create tests using `@SpringBootTest(webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)` and `TestRestTemplate`:

```java
@Test
void postTransfersCreatesSuccessfulTransfer()

@Test
void postTransfersRequiresIdempotencyKeyHeader()

@Test
void postTransfersReturnsConflictForSameKeyDifferentPayload()
```

Required behavior:

- `POST /transfers` with header `Idempotency-Key: api-key-1` returns HTTP 201 and body status `SUCCEEDED`.
- Missing `Idempotency-Key` returns HTTP 400.
- Same key with different amount returns HTTP 409 and body status `REJECTED`.

Run:

```bash
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: fail because controller does not exist.

- [ ] **Step 2: Implement controller**

Create controller:

```java
@RestController
@RequestMapping("/transfers")
public class TransferController {
    private final TransferService transferService;

    public TransferController(TransferService transferService) {
        this.transferService = transferService;
    }

    @PostMapping
    ResponseEntity<TransferResponse> create(
            @RequestHeader(value = "Idempotency-Key", required = false) String idempotencyKey,
            @RequestBody TransferHttpRequest body) {
        if (idempotencyKey == null || idempotencyKey.isBlank()) {
            return ResponseEntity.badRequest().body(new TransferResponse(null, "REJECTED", "Idempotency-Key header is required"));
        }
        TransferResponse response = transferService.transfer(new TransferRequest(
                idempotencyKey,
                body.fromAccountId(),
                body.toAccountId(),
                body.currency(),
                body.amount()));
        return switch (response.status()) {
            case "SUCCEEDED" -> ResponseEntity.status(201).body(response);
            case "FAILED" -> ResponseEntity.unprocessableEntity().body(response);
            case "REJECTED" -> ResponseEntity.status(409).body(response);
            default -> ResponseEntity.internalServerError().body(response);
        };
    }

    public record TransferHttpRequest(
            String fromAccountId,
            String toAccountId,
            String currency,
            BigDecimal amount) {
    }
}
```

- [ ] **Step 3: Run tests**

Run:

```bash
docker compose -f financial-consistency/10-service-prototype/docker-compose.yml down -v
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: tests pass.

- [ ] **Step 4: Commit**

Run:

```bash
git add financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/transfer/TransferController.java financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/transfer/TransferControllerIntegrationTest.java
git commit -m "feat: expose transfer api"
```

## Task 6: Add MySQL Fact Extraction And Independent Verifier

**Files:**
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/DbFact.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/DbHistory.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/DbInvariantViolation.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/MysqlFactExtractor.java`
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/TransferMysqlVerifier.java`
- Create: `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/verification/TransferMysqlVerifierIntegrationTest.java`

- [ ] **Step 1: Write failing verifier tests**

Create tests:

```java
@Test
void verifierFindsNoViolationsForSuccessfulTransfer()

@Test
void verifierFindsUnbalancedLedgerInsertedByFixture()

@Test
void verifierFindsMissingOutboxForSuccessfulTransfer()

@Test
void verifierFindsFailedTransferWithLedgerRows()
```

Use `JdbcTemplate` fixtures to insert bad rows directly where needed, not through `TransferService`.

Expected invariants:

- `LEDGER_DOUBLE_ENTRY_REQUIRED`
- `LEDGER_BALANCED`
- `TRANSFER_OUTBOX_REQUIRED`
- `FAILED_TRANSFER_HAS_NO_LEDGER`

Run:

```bash
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: fail because verification classes do not exist.

- [ ] **Step 2: Implement verification records**

Create:

```java
public record DbFact(String tableName, String factId, String businessId, Map<String, String> attributes) {
    public DbFact {
        tableName = Objects.requireNonNull(tableName);
        factId = Objects.requireNonNull(factId);
        businessId = Objects.requireNonNull(businessId);
        attributes = attributes == null ? Map.of() : Map.copyOf(attributes);
    }
}
```

```java
public record DbHistory(List<DbFact> facts) {
    public DbHistory {
        facts = List.copyOf(Objects.requireNonNull(facts));
    }
}
```

```java
public record DbInvariantViolation(String invariant, String reason, List<String> relatedFactIds) {
    public DbInvariantViolation {
        invariant = Objects.requireNonNull(invariant);
        reason = Objects.requireNonNull(reason);
        relatedFactIds = relatedFactIds == null ? List.of() : List.copyOf(relatedFactIds);
    }
}
```

- [ ] **Step 3: Implement `MysqlFactExtractor`**

Requirements:

- Annotate with `@Component`.
- Use `JdbcTemplate`.
- Method:

```java
public DbHistory extractAll()
```

- Extract rows from:
  - `transfer_order`
  - `ledger_entry`
  - `idempotency_record`
  - `outbox_message`
  - `account`
- Use table primary key or natural key as `factId`.
- Use `transfer_id` for transfer and ledger facts, `aggregate_id` for Outbox facts, `idempotency_key` for idempotency facts, and `account_id` for account facts.

- [ ] **Step 4: Implement `TransferMysqlVerifier`**

Requirements:

- Annotate with `@Component`.
- Method:

```java
public List<DbInvariantViolation> verify(DbHistory history)
```

Rules:

- For each `transfer_order` with `status=SUCCEEDED`, require exactly two `ledger_entry` facts for that transfer id, one `DEBIT` and one `CREDIT`.
- For each successful transfer, require debit amount equals credit amount and currencies match.
- For each successful transfer, require at least one `outbox_message` fact with `aggregate_id=transfer_id` and `event_type=TransferSucceeded`.
- For each `transfer_order` with `status=FAILED`, require zero `ledger_entry` facts for that transfer id.
- For each idempotency key, reject multiple distinct successful business ids.

- [ ] **Step 5: Run tests**

Run:

```bash
docker compose -f financial-consistency/10-service-prototype/docker-compose.yml down -v
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: tests pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/verification
git commit -m "feat: verify mysql transfer facts"
```

## Task 7: Add Verification API And Failure Fixture Script

**Files:**
- Create: `financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/VerificationController.java`
- Create: `financial-consistency/10-service-prototype/scripts/insert-bad-ledger.sh`
- Create: `financial-consistency/10-service-prototype/scripts/delete-outbox-for-transfer.sh`
- Create: `financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/verification/VerificationControllerIntegrationTest.java`

- [ ] **Step 1: Write failing verification API test**

Create tests:

```java
@Test
void verificationEndpointReturnsNoViolationsForCleanDatabase()

@Test
void verificationEndpointReturnsViolationsAfterBadFixture()
```

Endpoint:

```text
GET /verification/violations
```

Expected response: JSON array of violation objects.

Run:

```bash
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: fail because controller does not exist.

- [ ] **Step 2: Implement `VerificationController`**

Create:

```java
@RestController
@RequestMapping("/verification")
public class VerificationController {
    private final MysqlFactExtractor extractor;
    private final TransferMysqlVerifier verifier;

    public VerificationController(MysqlFactExtractor extractor, TransferMysqlVerifier verifier) {
        this.extractor = extractor;
        this.verifier = verifier;
    }

    @GetMapping("/violations")
    public List<DbInvariantViolation> violations() {
        return verifier.verify(extractor.extractAll());
    }
}
```

- [ ] **Step 3: Add bad data scripts**

Create `insert-bad-ledger.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -ufunds -pfunds funds_core <<'SQL'
insert into transfer_order (transfer_id, request_id, from_account_id, to_account_id, currency, amount, status)
values ('BAD-LEDGER-1', 'manual-bad-ledger', 'A-001', 'B-001', 'USD', 10.0000, 'SUCCEEDED')
on duplicate key update status = values(status);

insert ignore into ledger_entry (entry_id, transfer_id, account_id, direction, currency, amount, entry_type)
values ('BAD-LEDGER-1-DEBIT', 'BAD-LEDGER-1', 'A-001', 'DEBIT', 'USD', 10.0000, 'TRANSFER');
SQL
```

Create `delete-outbox-for-transfer.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: delete-outbox-for-transfer.sh <transfer-id>" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TRANSFER_ID="$1"

docker compose -f "$ROOT_DIR/docker-compose.yml" exec -T mysql mysql -ufunds -pfunds funds_core \
  -e "delete from outbox_message where aggregate_type = 'TRANSFER' and aggregate_id = '${TRANSFER_ID}'"
```

- [ ] **Step 4: Make scripts executable and run tests**

Run:

```bash
chmod +x financial-consistency/10-service-prototype/scripts/insert-bad-ledger.sh financial-consistency/10-service-prototype/scripts/delete-outbox-for-transfer.sh
docker compose -f financial-consistency/10-service-prototype/docker-compose.yml down -v
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: tests pass.

- [ ] **Step 5: Commit**

Run:

```bash
git add financial-consistency/10-service-prototype/service/src/main/java/com/interview/financialconsistency/serviceprototype/verification/VerificationController.java financial-consistency/10-service-prototype/service/src/test/java/com/interview/financialconsistency/serviceprototype/verification/VerificationControllerIntegrationTest.java financial-consistency/10-service-prototype/scripts/insert-bad-ledger.sh financial-consistency/10-service-prototype/scripts/delete-outbox-for-transfer.sh
git commit -m "feat: expose mysql verification api"
```

## Task 8: Add Chapter Documentation And Root Route

**Files:**
- Modify: `financial-consistency/10-service-prototype/README.md`
- Create: `financial-consistency/10-service-prototype/docs/01-domain-model.md`
- Create: `financial-consistency/10-service-prototype/docs/02-transaction-boundary.md`
- Create: `financial-consistency/10-service-prototype/docs/03-outbox-flow.md`
- Create: `financial-consistency/10-service-prototype/docs/04-verification-from-mysql.md`
- Create: `financial-consistency/10-service-prototype/docs/05-failure-cases.md`
- Modify: `financial-consistency/README.md`

- [ ] **Step 1: Verify files exist**

Run:

```bash
test -f financial-consistency/10-service-prototype/README.md
test -f financial-consistency/README.md
```

Expected: both exit 0.

- [ ] **Step 2: Expand README**

`README.md` must include:

- `# 10 真实工程原型`
- `## 目标`
- `## 运行方式`
- `## 核心事务`
- `## 验证方式`
- `## 关键边界`

It must say MySQL is fact storage and local transaction boundary, not the independent consistency verifier.

- [ ] **Step 3: Write domain docs**

`01-domain-model.md` must explain:

- `account`
- `transfer_order`
- `idempotency_record`
- `ledger_entry`
- `outbox_message`
- Why balance and ledger must both exist.

- [ ] **Step 4: Write transaction boundary docs**

`02-transaction-boundary.md` must include the transfer sequence:

```text
idempotency -> account locks -> transfer_order -> ledger_entry -> account update -> outbox_message -> idempotency completion -> commit
```

It must explain why no external calls happen inside this transaction.

- [ ] **Step 5: Write Outbox docs**

`03-outbox-flow.md` must explain:

- Why first phase only writes `PENDING`.
- Why `PENDING` rows are recoverable facts.
- Why broker publishing is deferred.

- [ ] **Step 6: Write verification docs**

`04-verification-from-mysql.md` must explain:

```text
MySQL rows -> DbFact -> DbHistory -> TransferMysqlVerifier -> DbInvariantViolation
```

It must explicitly say verifier does not reuse transfer service code.

- [ ] **Step 7: Write failure case docs**

`05-failure-cases.md` must document:

- normal transfer
- duplicate request
- same idempotency key different payload
- insufficient funds
- single-sided ledger fixture
- missing Outbox fixture

- [ ] **Step 8: Update root README**

Add spec link:

```markdown
- [2026-05-03-financial-consistency-service-prototype-design.md](../docs/superpowers/specs/2026-05-03-financial-consistency-service-prototype-design.md)
```

Add phase after `09-code-lab`:

```markdown
- [10-service-prototype](./10-service-prototype/README.md)
  Spring Boot + MySQL 内部转账服务原型：本地事务、幂等、双分录账本、Outbox 和数据库事实验证。
```

- [ ] **Step 9: Run verification**

Run:

```bash
rg -n "10-service-prototype|financial-consistency-service-prototype-design|一致性判定器|MySQL" financial-consistency/README.md financial-consistency/10-service-prototype
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: required terms found and tests pass.

- [ ] **Step 10: Commit**

Run:

```bash
git add financial-consistency/README.md financial-consistency/10-service-prototype/README.md financial-consistency/10-service-prototype/docs
git commit -m "docs: document service prototype"
```

## Task 9: Final Verification And Scope Guard

**Files:**
- Modify only if verification reveals a concrete mismatch in files created by this plan.

- [ ] **Step 1: Reset database and run full tests**

Run:

```bash
docker compose -f financial-consistency/10-service-prototype/docker-compose.yml down -v
bash financial-consistency/10-service-prototype/scripts/test-service.sh
```

Expected: Maven test suite passes.

- [ ] **Step 2: Run service smoke check**

Start service in one terminal:

```bash
bash financial-consistency/10-service-prototype/scripts/run-service.sh
```

In another shell, run:

```bash
curl -s -X POST http://localhost:8080/transfers \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: smoke-1' \
  -d '{"fromAccountId":"A-001","toAccountId":"B-001","currency":"USD","amount": "10.0000"}'
curl -s http://localhost:8080/verification/violations
```

Expected:

- Transfer response contains `"status":"SUCCEEDED"`.
- Verification response is `[]`.

Stop the service with `Ctrl-C`.

- [ ] **Step 3: Run bad ledger fixture**

Run:

```bash
bash financial-consistency/10-service-prototype/scripts/insert-bad-ledger.sh
curl -s http://localhost:8080/verification/violations
```

Expected: response contains `LEDGER_DOUBLE_ENTRY_REQUIRED` or `LEDGER_BALANCED`.

- [ ] **Step 4: Confirm no forbidden infrastructure slipped in**

Run:

```bash
rg -n "Kafka|RabbitMQ|Temporal|Camunda|Seata|workflow" financial-consistency/10-service-prototype/service/src financial-consistency/10-service-prototype/scripts
```

Expected: no matches.

- [ ] **Step 5: Confirm MySQL/verifier boundary is documented**

Run:

```bash
rg -n "MySQL.*事实|一致性判定器|verifier" financial-consistency/10-service-prototype/README.md financial-consistency/10-service-prototype/docs
```

Expected: matches explaining MySQL as fact storage and verifier as independent checker.

- [ ] **Step 6: Check git status**

Run:

```bash
git status --short --branch
```

Expected: only known unrelated pre-existing changes remain outside `financial-consistency/10-service-prototype` and `financial-consistency/README.md`.

- [ ] **Step 7: Commit final fixes if needed**

If files changed during final verification:

```bash
git add financial-consistency/10-service-prototype financial-consistency/README.md
git commit -m "chore: verify service prototype"
```

If no files changed, do not create an empty commit.

## Self-Review Checklist

- Spec coverage: internal transfer API, MySQL schema, idempotency, double-entry ledger, Outbox, and independent verifier are all covered.
- Scope guard: no Kafka, Temporal, payment channel, order inventory, travel Saga, or multi-service deployment is introduced.
- Verification guard: tests check MySQL rows and verifier output, not only HTTP responses.
- Naming guard: MySQL is described as fact storage and transaction boundary, not as the consistency verifier.
- Reproducibility: scripts start Docker MySQL and run Maven tests from the repository root.
- Documentation basis: Spring Boot 3.5.9 docs were checked before choosing `spring.datasource.*`, Flyway startup migrations, and Spring JDBC test strategy.
