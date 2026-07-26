# MySQL ES CDC Hands-on M0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox - [ ] syntax for tracking.

**Goal:** Build a reproducible local foundation in which product-service commits MySQL-only business transactions, every search-relevant transaction increments product_search_revision, and Canal 1.1.8 publishes those committed revision rows to Kafka.

**Architecture:** A Maven multi-module project contains three independently deployable Spring Boot applications. M0 implements product-service and leaves health-only shells for search-sync-consumer and consistency-verifier. Docker Compose supplies MySQL, Kafka, Canal, Elasticsearch, and Toxiproxy; the M0 smoke test proves the path product-service → MySQL transaction → binlog → Canal → Kafka without writing Elasticsearch from the request path.

**Tech Stack:** Java 21, Spring Boot 4.1.0, Maven Wrapper, MySQL 8.4.8, Canal 1.1.8, Kafka 4.1.2 in single-node KRaft mode, Elasticsearch 8.17.0, Toxiproxy 2.12.0, Docker Compose v2, Bash, curl, jq.

## Global Constraints

- Work only in branch codex/mysql-es-cdc-handson and its isolated worktree.
- Java is exactly 21 for application compilation; Spring Boot is exactly 4.1.0.
- Use Maven Wrapper; a globally installed Maven may generate the wrapper but is not the documented build entrypoint.
- Container tags are MySQL 8.4.8, Canal 1.1.8, Kafka 4.1.2, Elasticsearch 8.17.0, and Toxiproxy 2.12.0; never use latest.
- MySQL is the only business fact source. product-service must not depend on Kafka or Elasticsearch clients.
- MySQL binlog_format is ROW and binlog_row_image is FULL.
- Every search-relevant write and its product_search_revision increment occur in one MySQL transaction.
- Every active index generation, including rebuilds, will eventually retain tombstones; M0 only establishes the source-side active flag and revision.
- Use deterministic IDs and seed data so scenario output is reproducible.
- Docker Compose is the only orchestration target in v1; do not add Kubernetes.
- Do not claim exactly-once or final consistency in M0. This milestone proves capture connectivity only.
- Command context: run build, Compose, script, and Git commands from `mysql-es-cdc-handson/`; file lists in this plan remain repository-worktree-relative.

## Locked File Map

M0 creates the following boundaries:

~~~text
mysql-es-cdc-handson/
├── .gitignore
├── .mvn/wrapper/
├── mvnw
├── mvnw.cmd
├── pom.xml
├── versions.env
├── Makefile
├── README.md
├── product-service/
│   ├── pom.xml
│   ├── Dockerfile
│   └── src/
├── search-sync-consumer/
│   ├── pom.xml
│   ├── Dockerfile
│   └── src/
├── consistency-verifier/
│   ├── pom.xml
│   ├── Dockerfile
│   └── src/
├── infra/
│   ├── compose.yaml
│   ├── mysql/
│   ├── kafka/
│   ├── canal/
│   ├── elasticsearch/
│   └── toxiproxy/
├── scenarios/scripts/
├── tests/contracts/
└── evidence/.gitkeep
~~~

No Java module may import another application module. Cross-process contracts are JSON, SQL schema, Kafka records, and HTTP; this keeps the later verifier implementation independent from the consumer projector.

---

### Task 1: Lock the build, versions, modules, and health-only application shells

**Files:**

- Create: mysql-es-cdc-handson/tests/contracts/m0-layout.sh
- Create: mysql-es-cdc-handson/versions.env
- Create: mysql-es-cdc-handson/pom.xml
- Create: mysql-es-cdc-handson/product-service/pom.xml
- Create: mysql-es-cdc-handson/search-sync-consumer/pom.xml
- Create: mysql-es-cdc-handson/consistency-verifier/pom.xml
- Create: mysql-es-cdc-handson/product-service/src/main/java/com/interview/mysqlescdc/product/ProductServiceApplication.java
- Create: mysql-es-cdc-handson/search-sync-consumer/src/main/java/com/interview/mysqlescdc/consumer/SearchSyncConsumerApplication.java
- Create: mysql-es-cdc-handson/consistency-verifier/src/main/java/com/interview/mysqlescdc/verifier/ConsistencyVerifierApplication.java
- Generate: mysql-es-cdc-handson/.mvn/wrapper/*
- Generate: mysql-es-cdc-handson/mvnw
- Generate: mysql-es-cdc-handson/mvnw.cmd
- Create: mysql-es-cdc-handson/.gitignore
- Create: mysql-es-cdc-handson/evidence/.gitkeep

**Interfaces:**

- Consumes: the approved component versions from the design document.
- Produces: three executable Spring Boot modules with actuator health endpoints and the root commands ./mvnw test and ./mvnw package.

- [ ] **Step 1: Write the failing layout contract**

Create tests/contracts/m0-layout.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

for path in \
  pom.xml \
  versions.env \
  mvnw \
  product-service/pom.xml \
  search-sync-consumer/pom.xml \
  consistency-verifier/pom.xml
do
  test -f "$path"
done

grep -Fq "SPRING_BOOT_VERSION=4.1.0" versions.env
grep -Fq "MYSQL_VERSION=8.4.8" versions.env
grep -Fq "CANAL_VERSION=1.1.8" versions.env
grep -Fq "KAFKA_VERSION=4.1.2" versions.env
grep -Fq "ELASTICSEARCH_VERSION=8.17.0" versions.env
grep -Fq "TOXIPROXY_VERSION=2.12.0" versions.env
grep -Fq "<java.version>21</java.version>" pom.xml

test "$(find . -name pom.xml -not -path '*/target/*' | wc -l | tr -d ' ')" = "4"
~~~

- [ ] **Step 2: Run the contract and verify the red state**

Run:

~~~bash
bash tests/contracts/m0-layout.sh
~~~

Expected: FAIL on the first missing path under mysql-es-cdc-handson.

- [ ] **Step 3: Create the exact version manifest**

Create versions.env:

~~~dotenv
JAVA_VERSION=21
SPRING_BOOT_VERSION=4.1.0
MAVEN_VERSION=3.9.11
MYSQL_VERSION=8.4.8
CANAL_VERSION=1.1.8
KAFKA_VERSION=4.1.2
ELASTICSEARCH_VERSION=8.17.0
TOXIPROXY_VERSION=2.12.0
~~~

- [ ] **Step 4: Create the root Maven parent**

Create pom.xml:

~~~xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>

  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
    <version>4.1.0</version>
    <relativePath/>
  </parent>

  <groupId>com.interview.mysqlescdc</groupId>
  <artifactId>mysql-es-cdc-handson</artifactId>
  <version>0.1.0-SNAPSHOT</version>
  <packaging>pom</packaging>

  <modules>
    <module>product-service</module>
    <module>search-sync-consumer</module>
    <module>consistency-verifier</module>
  </modules>

  <properties>
    <java.version>21</java.version>
    <maven.compiler.release>21</maven.compiler.release>
  </properties>

  <build>
    <pluginManagement>
      <plugins>
        <plugin>
          <groupId>org.apache.maven.plugins</groupId>
          <artifactId>maven-surefire-plugin</artifactId>
          <version>3.5.4</version>
        </plugin>
        <plugin>
          <groupId>org.apache.maven.plugins</groupId>
          <artifactId>maven-failsafe-plugin</artifactId>
          <version>3.5.4</version>
        </plugin>
      </plugins>
    </pluginManagement>
  </build>
</project>
~~~

- [ ] **Step 5: Create the three module POMs**

Create product-service/pom.xml:

~~~xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.interview.mysqlescdc</groupId>
    <artifactId>mysql-es-cdc-handson</artifactId>
    <version>0.1.0-SNAPSHOT</version>
  </parent>
  <artifactId>product-service</artifactId>
  <dependencies>
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
      <artifactId>spring-boot-starter-actuator</artifactId>
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
      <plugin>
        <groupId>org.apache.maven.plugins</groupId>
        <artifactId>maven-failsafe-plugin</artifactId>
        <executions>
          <execution>
            <goals>
              <goal>integration-test</goal>
              <goal>verify</goal>
            </goals>
          </execution>
        </executions>
      </plugin>
    </plugins>
  </build>
</project>
~~~

Create search-sync-consumer/pom.xml:

~~~xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.interview.mysqlescdc</groupId>
    <artifactId>mysql-es-cdc-handson</artifactId>
    <version>0.1.0-SNAPSHOT</version>
  </parent>
  <artifactId>search-sync-consumer</artifactId>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-actuator</artifactId>
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
~~~

Create consistency-verifier/pom.xml:

~~~xml
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0"
         xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
         xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd">
  <modelVersion>4.0.0</modelVersion>
  <parent>
    <groupId>com.interview.mysqlescdc</groupId>
    <artifactId>mysql-es-cdc-handson</artifactId>
    <version>0.1.0-SNAPSHOT</version>
  </parent>
  <artifactId>consistency-verifier</artifactId>
  <dependencies>
    <dependency>
      <groupId>org.springframework.boot</groupId>
      <artifactId>spring-boot-starter-actuator</artifactId>
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
~~~

- [ ] **Step 6: Add the three application entrypoints**

Create ProductServiceApplication.java:

~~~java
package com.interview.mysqlescdc.product;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class ProductServiceApplication {
    public static void main(String[] args) {
        SpringApplication.run(ProductServiceApplication.class, args);
    }
}
~~~

Create SearchSyncConsumerApplication.java:

~~~java
package com.interview.mysqlescdc.consumer;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class SearchSyncConsumerApplication {
    public static void main(String[] args) {
        SpringApplication.run(SearchSyncConsumerApplication.class, args);
    }
}
~~~

Create ConsistencyVerifierApplication.java:

~~~java
package com.interview.mysqlescdc.verifier;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

@SpringBootApplication
public class ConsistencyVerifierApplication {
    public static void main(String[] args) {
        SpringApplication.run(ConsistencyVerifierApplication.class, args);
    }
}
~~~

- [ ] **Step 7: Generate the Maven Wrapper and ignore generated state**

From mysql-es-cdc-handson run:

~~~bash
mvn -N wrapper:wrapper -Dmaven=3.9.11
chmod +x mvnw tests/contracts/m0-layout.sh
~~~

Create .gitignore:

~~~gitignore
target/
**/target/
.idea/
.vscode/
.DS_Store
evidence/*
!evidence/.gitkeep
infra/runtime/
~~~

Create the empty evidence/.gitkeep file with apply_patch.

- [ ] **Step 8: Verify build and layout**

Run:

~~~bash
bash tests/contracts/m0-layout.sh
./mvnw -q test
~~~

Expected: layout contract exits 0; Maven reports BUILD SUCCESS with all three modules.

- [ ] **Step 9: Commit the build foundation**

~~~bash
git add .
git commit -m "build(cdc-lab): add Maven module foundation"
~~~

---

### Task 2: Create the MySQL fact model and transactional product mutations

**Files:**

- Create: mysql-es-cdc-handson/infra/mysql/conf.d/cdc.cnf
- Create: mysql-es-cdc-handson/infra/mysql/init/00-users.sql
- Create: mysql-es-cdc-handson/infra/mysql/init/01-schema.sql
- Create: mysql-es-cdc-handson/infra/mysql/init/02-seed.sql
- Create: mysql-es-cdc-handson/product-service/src/main/resources/application.yaml
- Create: mysql-es-cdc-handson/product-service/src/main/java/com/interview/mysqlescdc/product/application/ProductMutationService.java
- Create: mysql-es-cdc-handson/product-service/src/main/java/com/interview/mysqlescdc/product/api/ProductController.java
- Create: mysql-es-cdc-handson/product-service/src/main/java/com/interview/mysqlescdc/product/api/ProductRequests.java
- Create: mysql-es-cdc-handson/product-service/src/test/java/com/interview/mysqlescdc/product/application/ProductMutationServiceIT.java

**Interfaces:**

- Consumes: MySQL database product_catalog and deterministic category IDs 10 and 20.
- Produces: createProduct(CreateProductRequest), changePrice(productId, priceCents), replaceInventory(productId, available, reserved), renameCategory(categoryId, name), and deleteProduct(productId). Each method returns the resulting revision.

- [ ] **Step 1: Write the failing transaction integration test**

Create ProductMutationServiceIT.java. The test connects to the Compose MySQL through the test profile and asserts facts directly:

~~~java
package com.interview.mysqlescdc.product.application;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.test.context.ActiveProfiles;

import com.interview.mysqlescdc.product.api.ProductRequests.CreateProductRequest;

@SpringBootTest
@ActiveProfiles("integration")
class ProductMutationServiceIT {
    @Autowired ProductMutationService service;
    @Autowired JdbcClient jdbc;

    @BeforeEach
    void cleanProducts() {
        jdbc.sql("DELETE FROM product_search_revision").update();
        jdbc.sql("DELETE FROM inventory").update();
        jdbc.sql("DELETE FROM products").update();
    }

    @Test
    void all_search_relevant_changes_advance_one_revision() {
        assertThat(service.createProduct(new CreateProductRequest(
                1001L, "SKU-1001", "Keyboard", "Mechanical", 10L, 12999L))).isEqualTo(1L);
        assertThat(service.replaceInventory(1001L, 8, 2)).isEqualTo(2L);
        assertThat(service.changePrice(1001L, 11999L)).isEqualTo(3L);
        assertThat(service.renameCategory(10L, "Computer Accessories")).isEqualTo(1);
        assertThat(revision(1001L)).isEqualTo(4L);
        assertThat(service.deleteProduct(1001L)).isEqualTo(5L);
        assertThat(active(1001L)).isFalse();
    }

    @Test
    void a_failed_business_write_rolls_back_its_revision() {
        service.createProduct(new CreateProductRequest(
                1001L, "DUPLICATE", "Keyboard", "Mechanical", 10L, 12999L));

        assertThatThrownBy(() -> service.createProduct(new CreateProductRequest(
                1002L, "DUPLICATE", "Mouse", "Wireless", 10L, 4999L)))
                .isInstanceOf(RuntimeException.class);

        assertThat(jdbc.sql("SELECT COUNT(*) FROM products WHERE id = 1002")
                .query(Long.class).single()).isZero();
        assertThat(jdbc.sql("SELECT COUNT(*) FROM product_search_revision WHERE product_id = 1002")
                .query(Long.class).single()).isZero();
    }

    private long revision(long productId) {
        return jdbc.sql("SELECT revision FROM product_search_revision WHERE product_id = :id")
                .param("id", productId).query(Long.class).single();
    }

    private boolean active(long productId) {
        return jdbc.sql("SELECT active FROM product_search_revision WHERE product_id = :id")
                .param("id", productId).query(Boolean.class).single();
    }
}
~~~

- [ ] **Step 2: Run the test and verify the red state**

Run:

~~~bash
./mvnw -pl product-service -Dtest=ProductMutationServiceIT test
~~~

Expected: FAIL during test compilation because ProductMutationService and ProductRequests do not exist.

- [ ] **Step 3: Add MySQL binlog configuration**

Create infra/mysql/conf.d/cdc.cnf:

~~~ini
[mysqld]
server-id=1
log-bin=mysql-bin
binlog-format=ROW
binlog-row-image=FULL
binlog-expire-logs-seconds=86400
gtid-mode=ON
enforce-gtid-consistency=ON
default-time-zone=+00:00
~~~

- [ ] **Step 4: Create users and schema**

Create infra/mysql/init/00-users.sql:

~~~sql
CREATE USER IF NOT EXISTS 'canal'@'%' IDENTIFIED BY 'canalpass';
GRANT SELECT, SHOW VIEW, REPLICATION SLAVE, REPLICATION CLIENT
ON *.* TO 'canal'@'%';

CREATE USER IF NOT EXISTS 'verifier'@'%' IDENTIFIED BY 'verifierpass';
GRANT SELECT ON product_catalog.* TO 'verifier'@'%';
FLUSH PRIVILEGES;
~~~

Create infra/mysql/init/01-schema.sql:

~~~sql
CREATE DATABASE IF NOT EXISTS product_catalog
  CHARACTER SET utf8mb4 COLLATE utf8mb4_0900_ai_ci;
USE product_catalog;

CREATE TABLE categories (
  id BIGINT NOT NULL,
  name VARCHAR(200) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id)
) ENGINE=InnoDB;

CREATE TABLE products (
  id BIGINT NOT NULL,
  sku VARCHAR(100) NOT NULL,
  name VARCHAR(200) NOT NULL,
  description TEXT NOT NULL,
  category_id BIGINT NOT NULL,
  price_cents BIGINT NOT NULL,
  status VARCHAR(32) NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (id),
  UNIQUE KEY uk_products_sku (sku),
  KEY ix_products_category (category_id),
  CONSTRAINT fk_products_category FOREIGN KEY (category_id) REFERENCES categories(id),
  CONSTRAINT ck_products_price CHECK (price_cents >= 0),
  CONSTRAINT ck_products_status CHECK (status IN ('ACTIVE', 'DELETED'))
) ENGINE=InnoDB;

CREATE TABLE inventory (
  product_id BIGINT NOT NULL,
  available_quantity INT NOT NULL,
  reserved_quantity INT NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (product_id),
  CONSTRAINT fk_inventory_product FOREIGN KEY (product_id) REFERENCES products(id),
  CONSTRAINT ck_inventory_available CHECK (available_quantity >= 0),
  CONSTRAINT ck_inventory_reserved CHECK (reserved_quantity >= 0)
) ENGINE=InnoDB;

CREATE TABLE product_search_revision (
  product_id BIGINT NOT NULL,
  revision BIGINT NOT NULL,
  active BOOLEAN NOT NULL,
  updated_at TIMESTAMP(6) NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
    ON UPDATE CURRENT_TIMESTAMP(6),
  PRIMARY KEY (product_id),
  CONSTRAINT fk_revision_product FOREIGN KEY (product_id) REFERENCES products(id),
  CONSTRAINT ck_revision_positive CHECK (revision > 0)
) ENGINE=InnoDB;
~~~

Create infra/mysql/init/02-seed.sql:

~~~sql
USE product_catalog;
INSERT INTO categories (id, name) VALUES
  (10, 'Accessories'),
  (20, 'Storage');
~~~

- [ ] **Step 5: Add application configuration and request records**

Create product-service/src/main/resources/application.yaml:

~~~yaml
spring:
  application:
    name: product-service
  datasource:
    url: jdbc:mysql://localhost:3308/product_catalog?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
    username: product
    password: productpass
  threads:
    virtual:
      enabled: true

server:
  port: 8081

management:
  endpoints:
    web:
      exposure:
        include: health,info,metrics,prometheus
  endpoint:
    health:
      probes:
        enabled: true
~~~

Create ProductRequests.java:

~~~java
package com.interview.mysqlescdc.product.api;

import jakarta.validation.constraints.Min;
import jakarta.validation.constraints.NotBlank;

public final class ProductRequests {
    private ProductRequests() {}

    public record CreateProductRequest(
            @Min(1) long id,
            @NotBlank String sku,
            @NotBlank String name,
            String description,
            @Min(1) long categoryId,
            @Min(0) long priceCents) {}

    public record ChangePriceRequest(@Min(0) long priceCents) {}

    public record ReplaceInventoryRequest(
            @Min(0) int availableQuantity,
            @Min(0) int reservedQuantity) {}

    public record RenameCategoryRequest(@NotBlank String name) {}

    public record RevisionResponse(long productId, long revision) {}
}
~~~

Add spring-boot-starter-validation to product-service/pom.xml before the test dependency.

- [ ] **Step 6: Implement the transactional mutation service**

Create ProductMutationService.java:

~~~java
package com.interview.mysqlescdc.product.application;

import org.springframework.jdbc.core.simple.JdbcClient;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import com.interview.mysqlescdc.product.api.ProductRequests.CreateProductRequest;

@Service
public class ProductMutationService {
    private final JdbcClient jdbc;

    public ProductMutationService(JdbcClient jdbc) {
        this.jdbc = jdbc;
    }

    @Transactional
    public long createProduct(CreateProductRequest request) {
        jdbc.sql("""
                INSERT INTO products
                    (id, sku, name, description, category_id, price_cents, status)
                VALUES
                    (:id, :sku, :name, :description, :categoryId, :priceCents, 'ACTIVE')
                """)
                .param("id", request.id())
                .param("sku", request.sku())
                .param("name", request.name())
                .param("description", request.description() == null ? "" : request.description())
                .param("categoryId", request.categoryId())
                .param("priceCents", request.priceCents())
                .update();
        jdbc.sql("""
                INSERT INTO inventory
                    (product_id, available_quantity, reserved_quantity)
                VALUES (:id, 0, 0)
                """).param("id", request.id()).update();
        jdbc.sql("""
                INSERT INTO product_search_revision (product_id, revision, active)
                VALUES (:id, 1, TRUE)
                """).param("id", request.id()).update();
        return 1L;
    }

    @Transactional
    public long changePrice(long productId, long priceCents) {
        requireOne(jdbc.sql("""
                UPDATE products SET price_cents = :price
                WHERE id = :id AND status = 'ACTIVE'
                """).param("price", priceCents).param("id", productId).update(), productId);
        return bump(productId);
    }

    @Transactional
    public long replaceInventory(long productId, int available, int reserved) {
        requireOne(jdbc.sql("""
                UPDATE inventory
                SET available_quantity = :available, reserved_quantity = :reserved
                WHERE product_id = :id
                """).param("available", available).param("reserved", reserved)
                .param("id", productId).update(), productId);
        return bump(productId);
    }

    @Transactional
    public int renameCategory(long categoryId, String name) {
        requireOne(jdbc.sql("UPDATE categories SET name = :name WHERE id = :id")
                .param("name", name).param("id", categoryId).update(), categoryId);
        return jdbc.sql("""
                UPDATE product_search_revision r
                JOIN products p ON p.id = r.product_id
                SET r.revision = r.revision + 1,
                    r.updated_at = CURRENT_TIMESTAMP(6)
                WHERE p.category_id = :categoryId AND r.active = TRUE
                """).param("categoryId", categoryId).update();
    }

    @Transactional
    public long deleteProduct(long productId) {
        requireOne(jdbc.sql("""
                UPDATE products SET status = 'DELETED'
                WHERE id = :id AND status = 'ACTIVE'
                """).param("id", productId).update(), productId);
        jdbc.sql("""
                UPDATE product_search_revision
                SET revision = revision + 1, active = FALSE
                WHERE product_id = :id
                """).param("id", productId).update();
        return currentRevision(productId);
    }

    private long bump(long productId) {
        jdbc.sql("""
                UPDATE product_search_revision
                SET revision = revision + 1
                WHERE product_id = :id AND active = TRUE
                """).param("id", productId).update();
        return currentRevision(productId);
    }

    private long currentRevision(long productId) {
        return jdbc.sql("""
                SELECT revision FROM product_search_revision WHERE product_id = :id
                """).param("id", productId).query(Long.class).single();
    }

    private static void requireOne(int count, long id) {
        if (count != 1) {
            throw new IllegalArgumentException("resource not found or inactive: " + id);
        }
    }
}
~~~

- [ ] **Step 7: Expose the mutation API without downstream writes**

Create ProductController.java:

~~~java
package com.interview.mysqlescdc.product.api;

import jakarta.validation.Valid;

import org.springframework.http.HttpStatus;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseStatus;
import org.springframework.web.bind.annotation.RestController;

import com.interview.mysqlescdc.product.api.ProductRequests.ChangePriceRequest;
import com.interview.mysqlescdc.product.api.ProductRequests.CreateProductRequest;
import com.interview.mysqlescdc.product.api.ProductRequests.RenameCategoryRequest;
import com.interview.mysqlescdc.product.api.ProductRequests.ReplaceInventoryRequest;
import com.interview.mysqlescdc.product.api.ProductRequests.RevisionResponse;
import com.interview.mysqlescdc.product.application.ProductMutationService;

@RestController
@RequestMapping("/api")
public class ProductController {
    private final ProductMutationService service;

    public ProductController(ProductMutationService service) {
        this.service = service;
    }

    @PostMapping("/products")
    @ResponseStatus(HttpStatus.CREATED)
    RevisionResponse create(@Valid @RequestBody CreateProductRequest request) {
        return new RevisionResponse(request.id(), service.createProduct(request));
    }

    @PutMapping("/products/{id}/price")
    RevisionResponse changePrice(@PathVariable long id,
                                 @Valid @RequestBody ChangePriceRequest request) {
        return new RevisionResponse(id, service.changePrice(id, request.priceCents()));
    }

    @PutMapping("/products/{id}/inventory")
    RevisionResponse replaceInventory(@PathVariable long id,
                                      @Valid @RequestBody ReplaceInventoryRequest request) {
        return new RevisionResponse(id, service.replaceInventory(
                id, request.availableQuantity(), request.reservedQuantity()));
    }

    @PutMapping("/categories/{id}")
    int renameCategory(@PathVariable long id,
                       @Valid @RequestBody RenameCategoryRequest request) {
        return service.renameCategory(id, request.name());
    }

    @DeleteMapping("/products/{id}")
    RevisionResponse delete(@PathVariable long id) {
        return new RevisionResponse(id, service.deleteProduct(id));
    }
}
~~~

- [ ] **Step 8: Start only MySQL and run the integration test**

Start a task-local MySQL container so Task 2 does not depend on the later Compose task:

~~~bash
docker run -d --name mysql-es-cdc-m0-task2 \
  -e MYSQL_ROOT_PASSWORD=rootpass \
  -e MYSQL_DATABASE=product_catalog \
  -e MYSQL_USER=product \
  -e MYSQL_PASSWORD=productpass \
  -p 3308:3306 \
  -v "$PWD/infra/mysql/conf.d/cdc.cnf:/etc/mysql/conf.d/cdc.cnf:ro" \
  -v "$PWD/infra/mysql/init:/docker-entrypoint-initdb.d:ro" \
  mysql:8.4.8
cleanup_task2_mysql() {
  docker rm -f mysql-es-cdc-m0-task2 >/dev/null 2>&1 || true
}
trap cleanup_task2_mysql EXIT
until docker exec mysql-es-cdc-m0-task2 \
  mysqladmin ping -h 127.0.0.1 -uroot -prootpass --silent; do
  sleep 1
done
./mvnw -pl product-service -Dtest=ProductMutationServiceIT test
cleanup_task2_mysql
trap - EXIT
~~~

Expected: both tests PASS. Querying product_search_revision after each mutation shows revisions 1 through 5 and active=false after delete.

- [ ] **Step 9: Prove product-service has no forbidden dependency**

Run:

~~~bash
./mvnw -pl product-service dependency:tree
~~~

Expected: output contains neither org.springframework.kafka nor an Elasticsearch client artifact.

- [ ] **Step 10: Commit the source transaction boundary**

~~~bash
git add infra/mysql product-service
git commit -m "feat(cdc-lab): add transactional product revisions"
~~~

---

### Task 3: Add the pinned Docker Compose dependency stack and Canal-to-Kafka capture path

**Files:**

- Create: mysql-es-cdc-handson/infra/compose.yaml
- Create: mysql-es-cdc-handson/infra/kafka/create-topics.sh
- Create: mysql-es-cdc-handson/infra/canal/canal.properties
- Create: mysql-es-cdc-handson/infra/canal/instance.properties
- Create: mysql-es-cdc-handson/infra/elasticsearch/index-template.json
- Create: mysql-es-cdc-handson/infra/toxiproxy/proxies.json
- Create: mysql-es-cdc-handson/tests/contracts/m0-compose.sh

**Interfaces:**

- Consumes: product_catalog.product_search_revision row changes.
- Produces: Kafka topic product-search-revisions with three partitions and product_id-derived partitioning; Elasticsearch and Toxiproxy are ready but not yet in the business write path.

- [ ] **Step 1: Write the failing Compose contract**

Create tests/contracts/m0-compose.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
docker compose -f infra/compose.yaml config --quiet

for image in \
  mysql:8.4.8 \
  canal/canal-server:v1.1.8 \
  apache/kafka:4.1.2 \
  docker.elastic.co/elasticsearch/elasticsearch:8.17.0 \
  ghcr.io/shopify/toxiproxy:2.12.0
do
  grep -Fq "image: $image" infra/compose.yaml
done

grep -Fq "canal.serverMode = kafka" infra/canal/canal.properties
grep -Fq "canal.file.data.dir = /home/admin/canal-data" infra/canal/canal.properties
grep -Fq 'canal.auto.reset.latest.pos.mode = ${CANAL_AUTO_RESET_LATEST_POS_MODE:false}' infra/canal/canal.properties
grep -Fq "canal.instance.global.mode = spring" infra/canal/canal.properties
grep -Fq "canal.instance.global.lazy = false" infra/canal/canal.properties
grep -Fq "canal.instance.global.spring.xml = classpath:spring/file-instance.xml" \
  infra/canal/canal.properties
grep -Fq "chown admin:admin /home/admin/canal-data && exec /home/admin/app.sh" \
  infra/compose.yaml
grep -Fq "canal-data:/home/admin/canal-data" infra/compose.yaml
grep -Fq "canal.mq.topic=product-search-revisions" infra/canal/instance.properties
grep -Fq "canal.mq.partitionsNum=3" infra/canal/instance.properties
grep -Fq "product_catalog.product_search_revision:product_id" \
  infra/canal/instance.properties
~~~

- [ ] **Step 2: Run the contract and verify the red state**

Run:

~~~bash
bash tests/contracts/m0-compose.sh
~~~

Expected: FAIL because infra/compose.yaml does not exist.

- [ ] **Step 3: Create Kafka topic initialization**

Create infra/kafka/create-topics.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

/opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --create --if-not-exists \
  --topic product-search-revisions \
  --partitions 3 \
  --replication-factor 1

/opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --describe \
  --topic product-search-revisions
~~~

- [ ] **Step 4: Create Canal Kafka configuration**

Create infra/canal/canal.properties with the release defaults retained except for these complete lab overrides:

~~~properties
canal.id = 1
canal.ip =
canal.port = 11111
canal.metrics.pull.port = 11112
canal.destinations = products
canal.auto.scan = false
canal.serverMode = kafka
canal.file.data.dir = /home/admin/canal-data
canal.file.flush.period = 1000
canal.auto.reset.latest.pos.mode = ${CANAL_AUTO_RESET_LATEST_POS_MODE:false}
canal.instance.memory.buffer.size = 16384
canal.instance.memory.buffer.memunit = 1024
canal.instance.memory.batch.mode = MEMSIZE
canal.instance.memory.rawEntry = true
canal.instance.detecting.enable = false
canal.instance.transaction.size = 1024
canal.instance.binlog.format = ROW
canal.instance.binlog.image = FULL
canal.instance.tsdb.enable = true
canal.instance.global.mode = spring
canal.instance.global.lazy = false
canal.instance.global.spring.xml = classpath:spring/file-instance.xml
canal.mq.servers = toxiproxy:8667
canal.mq.retries = 3
canal.mq.acks = all
canal.mq.flatMessage = true
canal.mq.compressionType = none
~~~

Create infra/canal/instance.properties:

~~~properties
canal.instance.mysql.slaveId=1234
canal.instance.gtidon=true
canal.instance.master.address=toxiproxy:8668
canal.instance.master.journal.name=
canal.instance.master.position=
canal.instance.master.timestamp=
canal.instance.master.gtid=
canal.instance.dbUsername=canal
canal.instance.dbPassword=canalpass
canal.instance.connectionCharset=UTF-8
canal.instance.enableDruid=false
canal.instance.filter.regex=product_catalog\\.product_search_revision
canal.instance.filter.black.regex=
canal.instance.tsdb.enable=true
canal.mq.topic=product-search-revisions
canal.mq.partition=0
canal.mq.partitionsNum=3
canal.mq.partitionHash=product_catalog.product_search_revision:product_id
~~~

The implementation must mount these files at the paths expected by canal/canal-server:v1.1.8 and confirm the effective values from startup logs. If the image copies environment into another runtime path, change only the mount target, not the checked-in configuration content.

- [ ] **Step 5: Create the Compose stack**

Create infra/compose.yaml with these exact services and fixed lab ports:

~~~yaml
name: mysql-es-cdc-handson

services:
  mysql:
    image: mysql:8.4.8
    command: ["mysqld", "--defaults-extra-file=/etc/mysql/conf.d/cdc.cnf"]
    environment:
      MYSQL_ROOT_PASSWORD: rootpass
      MYSQL_DATABASE: product_catalog
      MYSQL_USER: product
      MYSQL_PASSWORD: productpass
    ports: ["3308:3306"]
    volumes:
      - mysql-data:/var/lib/mysql
      - ./mysql/conf.d/cdc.cnf:/etc/mysql/conf.d/cdc.cnf:ro
      - ./mysql/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD", "mysqladmin", "ping", "-h", "127.0.0.1", "-uroot", "-prootpass"]
      interval: 5s
      timeout: 3s
      retries: 30

  kafka:
    image: apache/kafka:4.1.2
    hostname: kafka
    environment:
      KAFKA_NODE_ID: 1
      KAFKA_PROCESS_ROLES: broker,controller
      KAFKA_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_LISTENERS: BROKER://:9092,CLIENT://:9094,EXTERNAL://:29092,CONTROLLER://:9093
      KAFKA_ADVERTISED_LISTENERS: BROKER://kafka:9092,CLIENT://toxiproxy:8667,EXTERNAL://localhost:29092
      KAFKA_INTER_BROKER_LISTENER_NAME: BROKER
      KAFKA_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,BROKER:PLAINTEXT,CLIENT:PLAINTEXT,EXTERNAL:PLAINTEXT
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: 1
      KAFKA_TRANSACTION_STATE_LOG_MIN_ISR: 1
      KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS: 0
      CLUSTER_ID: MkU3OEVBNTcwNTJENDM2Qk
    ports: ["29092:29092"]
    volumes:
      - kafka-data:/tmp/kraft-combined-logs
    healthcheck:
      test: ["CMD", "/opt/kafka/bin/kafka-topics.sh", "--bootstrap-server", "kafka:9092", "--list"]
      interval: 5s
      timeout: 5s
      retries: 30

  kafka-init:
    image: apache/kafka:4.1.2
    depends_on:
      kafka:
        condition: service_healthy
    volumes:
      - ./kafka/create-topics.sh:/create-topics.sh:ro
    entrypoint: ["/bin/bash", "/create-topics.sh"]

  canal:
    image: canal/canal-server:v1.1.8
    command:
      - /bin/bash
      - -c
      - chown admin:admin /home/admin/canal-data && exec /home/admin/app.sh
    environment:
      CANAL_AUTO_RESET_LATEST_POS_MODE: ${CANAL_AUTO_RESET_LATEST_POS_MODE:-false}
    depends_on:
      mysql:
        condition: service_healthy
      kafka-init:
        condition: service_completed_successfully
      toxiproxy:
        condition: service_started
    ports: ["11111:11111", "11112:11112"]
    volumes:
      - ./canal/canal.properties:/home/admin/canal-server/conf/canal.properties:ro
      - ./canal/instance.properties:/home/admin/canal-server/conf/products/instance.properties:ro
      - canal-data:/home/admin/canal-data

  elasticsearch:
    image: docker.elastic.co/elasticsearch/elasticsearch:8.17.0
    environment:
      discovery.type: single-node
      xpack.security.enabled: "false"
      ES_JAVA_OPTS: -Xms512m -Xmx512m
    ports: ["9200:9200"]
    volumes:
      - elasticsearch-data:/usr/share/elasticsearch/data
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:9200/_cluster/health"]
      interval: 5s
      timeout: 5s
      retries: 40

  toxiproxy:
    image: ghcr.io/shopify/toxiproxy:2.12.0
    command: ["-host=0.0.0.0", "-config=/config/proxies.json"]
    ports: ["8474:8474", "8666:8666", "8667:8667", "8668:8668"]
    depends_on:
      mysql:
        condition: service_healthy
      kafka:
        condition: service_healthy
      elasticsearch:
        condition: service_healthy
    volumes:
      - ./toxiproxy/proxies.json:/config/proxies.json:ro

volumes:
  mysql-data:
  kafka-data:
  canal-data:
  elasticsearch-data:
~~~

Create infra/toxiproxy/proxies.json:

~~~json
[
  {
    "name": "elasticsearch",
    "listen": "0.0.0.0:8666",
    "upstream": "elasticsearch:9200",
    "enabled": true
  },
  {
    "name": "kafka",
    "listen": "0.0.0.0:8667",
    "upstream": "kafka:9094",
    "enabled": true
  },
  {
    "name": "canal-mysql",
    "listen": "0.0.0.0:8668",
    "upstream": "mysql:3306",
    "enabled": true
  }
]
~~~

Create infra/elasticsearch/index-template.json with explicit field types for the future products indexes:

~~~json
{
  "index_patterns": ["products_v*", "products_adapter_v*"],
  "template": {
    "settings": {
      "number_of_shards": 1,
      "number_of_replicas": 0
    },
    "mappings": {
      "dynamic": "strict",
      "properties": {
        "product_id": {"type": "long"},
        "sku": {"type": "keyword"},
        "name": {"type": "text", "fields": {"keyword": {"type": "keyword"}}},
        "description": {"type": "text"},
        "category_id": {"type": "long"},
        "category_name": {"type": "keyword"},
        "price_cents": {"type": "long"},
        "available_quantity": {"type": "integer"},
        "searchable": {"type": "boolean"},
        "source_revision": {"type": "long"},
        "source_updated_at": {"type": "date"}
      }
    }
  }
}
~~~

- [ ] **Step 6: Validate configuration before starting containers**

Run:

~~~bash
chmod +x infra/kafka/create-topics.sh tests/contracts/m0-compose.sh
bash tests/contracts/m0-compose.sh
docker compose -f infra/compose.yaml config --quiet
~~~

Expected: both commands exit 0 and no image uses latest.

- [ ] **Step 7: Start dependencies and prove their readiness**

Run:

~~~bash
docker compose -f infra/compose.yaml up -d
docker compose -f infra/compose.yaml ps
curl -fsS http://localhost:9200/_cluster/health
curl -fsS http://localhost:8474/proxies
docker compose -f infra/compose.yaml exec -T mysql \
  mysql -uroot -prootpass -Nse \
  "SELECT @@binlog_format, @@binlog_row_image, @@gtid_mode"
docker compose -f infra/compose.yaml exec -T kafka \
  /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 \
  --describe --topic product-search-revisions
~~~

Expected:

- MySQL reports ROW, FULL, and ON.
- Kafka reports PartitionCount: 3.
- Elasticsearch cluster status is yellow or green.
- Toxiproxy lists three enabled proxies.
- Canal logs show destination products, MySQL endpoint toxiproxy:8668, and Kafka endpoint toxiproxy:8667 without authentication or binlog-format errors.
- Canal 1.1.8 release-native `file-instance.xml` writes the acknowledged products MQ client cursor to `/home/admin/canal-data/products/meta.dat`; `MetaLogPositionManager` uses that same cursor for parser resume. Restarting only Canal must preserve its SHA-256 and decoded file/position, leave Kafka end offsets unchanged, log exact resume from that cursor, and publish the first post-restart mutation exactly once at the next offset.
- The pinned server may log the known static-destination `CanalMQRunnable.future == null` stop NPE. This is an observed upstream limitation, not proof of harmless shutdown; acceptance depends on the cursor, offset, exact-resume, and exactly-next-event evidence above.

- [ ] **Step 8: Commit the dependency stack**

~~~bash
git add infra tests/contracts/m0-compose.sh
git commit -m "feat(cdc-lab): add pinned CDC dependency stack"
~~~

---

### Task 4: Package the applications and prove the M0 end-to-end capture contract

**Files:**

- Create: mysql-es-cdc-handson/product-service/Dockerfile
- Create: mysql-es-cdc-handson/search-sync-consumer/Dockerfile
- Create: mysql-es-cdc-handson/consistency-verifier/Dockerfile
- Modify: mysql-es-cdc-handson/infra/compose.yaml
- Create: mysql-es-cdc-handson/scenarios/scripts/wait-for-http.sh
- Create: mysql-es-cdc-handson/scenarios/scripts/smoke-m0.sh
- Create: mysql-es-cdc-handson/scenarios/scripts/record-image-digests.sh
- Create: mysql-es-cdc-handson/Makefile
- Create: mysql-es-cdc-handson/README.md
- Create: mysql-es-cdc-handson/docs/00-goals-and-invariants.md
- Create: mysql-es-cdc-handson/evidence/m0/.gitkeep

**Interfaces:**

- Consumes: POST /api/products and Kafka topic product-search-revisions.
- Produces: make up, make down, make reset, make verify, make smoke-m0, and an evidence/m0/version-manifest.json containing resolved container image IDs.

- [ ] **Step 1: Write the failing M0 smoke script**

Create scenarios/scripts/wait-for-http.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

url="$1"
deadline="$2"
start="$(date +%s)"
while ! curl -fsS "$url" >/dev/null; do
  now="$(date +%s)"
  if test "$((now - start))" -ge "$deadline"; then
    echo "timeout waiting for $url" >&2
    exit 1
  fi
  sleep 1
done
~~~

Create scenarios/scripts/smoke-m0.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."

./scenarios/scripts/wait-for-http.sh \
  http://localhost:8081/actuator/health/readiness 90

curl -fsS -X POST http://localhost:8081/api/products \
  -H 'Content-Type: application/json' \
  -d '{"id":1001,"sku":"SKU-1001","name":"Keyboard","description":"Mechanical","categoryId":10,"priceCents":12999}' \
  | jq -e '.productId == 1001 and .revision == 1'

rm -f evidence/m0/revision-message.json
docker compose -f infra/compose.yaml exec -T kafka \
  /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 \
  --topic product-search-revisions \
  --from-beginning \
  --timeout-ms 60000 \
  --max-messages 1 \
  > evidence/m0/revision-message.json

jq -e '
  .database == "product_catalog"
  and .table == "product_search_revision"
  and (.data | any(.product_id == "1001" and .revision == "1"))
' evidence/m0/revision-message.json

docker compose -f infra/compose.yaml exec -T mysql \
  mysql -uproduct -pproductpass product_catalog -Nse \
  "SELECT CONCAT(product_id, ':', revision, ':', active)
   FROM product_search_revision WHERE product_id = 1001" \
  | grep -Fx "1001:1:1"
~~~

- [ ] **Step 2: Run it and verify the red state**

Run:

~~~bash
bash scenarios/scripts/smoke-m0.sh
~~~

Expected: FAIL because product-service is not yet packaged or present in Compose.

- [ ] **Step 3: Add reproducible application images**

Create `product-service/Dockerfile`:

~~~dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/product-service-0.1.0-SNAPSHOT.jar app.jar
USER 10001
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
~~~

Create `search-sync-consumer/Dockerfile`:

~~~dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/search-sync-consumer-0.1.0-SNAPSHOT.jar app.jar
USER 10001
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
~~~

Create `consistency-verifier/Dockerfile`:

~~~dockerfile
FROM eclipse-temurin:21-jre
WORKDIR /app
COPY target/consistency-verifier-0.1.0-SNAPSHOT.jar app.jar
USER 10001
ENTRYPOINT ["java", "-jar", "/app/app.jar"]
~~~

Add these services to infra/compose.yaml:

~~~yaml
  product-service:
    build:
      context: ../product-service
    depends_on:
      mysql:
        condition: service_healthy
    environment:
      SPRING_DATASOURCE_URL: jdbc:mysql://mysql:3306/product_catalog?useSSL=false&allowPublicKeyRetrieval=true&serverTimezone=UTC
      SPRING_DATASOURCE_USERNAME: product
      SPRING_DATASOURCE_PASSWORD: productpass
    ports: ["8081:8081"]
~~~

The host-side `wait-for-http.sh` is the M0 product readiness proof; the JRE image is not required to contain curl or wget. Do not start the health-only consumer and verifier by default until their application.yaml files define distinct ports. Add them under Compose profiles with ports 8082 and 8083.

- [ ] **Step 4: Add command contracts**

Create Makefile:

~~~make
SHELL := /bin/bash
COMPOSE := docker compose -f infra/compose.yaml

.PHONY: package up down reset verify smoke-m0 evidence

package:
	./mvnw -q -DskipTests package

up: package
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

reset:
	$(COMPOSE) down --volumes --remove-orphans

verify:
	bash tests/contracts/m0-layout.sh
	bash tests/contracts/m0-compose.sh
	./mvnw -q test

smoke-m0: up
	bash scenarios/scripts/smoke-m0.sh

evidence:
	bash scenarios/scripts/record-image-digests.sh
~~~

- [ ] **Step 5: Record resolved image identities**

Create scenarios/scripts/record-image-digests.sh:

~~~bash
#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/../.."
mkdir -p evidence/m0

docker compose -f infra/compose.yaml images --format json \
  | jq -s '{
      milestone: "M0",
      captured_at: (now | todateiso8601),
      images: map({
        service: .Service,
        repository: .Repository,
        tag: .Tag,
        id: .ID
      })
    }' > evidence/m0/version-manifest.json
~~~

- [ ] **Step 6: Write the reader contract**

Create `README.md` with this M0 content:

~~~markdown
# MySQL → Canal → Elasticsearch 最终一致性实战

## 先给结论

Canal 是 MySQL binlog CDC（变更数据捕获）/增量订阅组件，不是端到端最终一致性方案。M0 只证明：MySQL 业务事实和 revision 在一个本地事务提交后，Canal 能把对应行变化发布到 Kafka。Kafka 中出现消息不等于 Elasticsearch 已经收敛。

## M0 能证明什么

- product-service 只提交 MySQL，不同步写 Kafka 或 Elasticsearch；
- Canal 1.1.8 读取 MySQL 8.4 row/full binlog；
- product_id 参与 Canal partitionHash，同一商品稳定进入同一 partition；
- Canal 生成的 Kafka record key 为 null，product_id 从 flat-message data 解析；
- 所有容器使用固定 tag，运行镜像身份可写入 evidence/m0。

M0 尚未提供 Elasticsearch 消费、逐 Bulk item 判定、revision 防倒退、DLQ、独立对账或全量重建，因此不宣称最终一致性。

## 运行

前置：Docker Compose v2、Java 21、jq、curl。Maven Wrapper 已固定构建工具；只有重新生成 Wrapper 时才需要本机 Maven。

```bash
make reset
make smoke-m0
make evidence
```

本地端口：product-service 8081、MySQL 3308、Kafka 29092、Canal 11111/11112、Elasticsearch 9200、Toxiproxy API 8474。仓库中的账号密码只用于本地实验，不得用于共享或生产环境。

完整目标与不变量见 [docs/00-goals-and-invariants.md](docs/00-goals-and-invariants.md)。
~~~

Create `docs/00-goals-and-invariants.md`:

~~~markdown
# Goal and invariants

## Target contract

MySQL is the fact source and Elasticsearch is a rebuildable current-state projection. When the recovery preconditions hold, every product eventually has exactly one Elasticsearch document whose managed fields equal the current MySQL aggregate, whose source_revision is the latest committed product revision, and whose searchable flag is false for deleted products.

## Recovery preconditions

- MySQL facts remain available and correct;
- binlog and Kafka retain every required incremental position, or a successful full rebuild replaces the missing interval;
- dependencies eventually recover;
- deterministic data errors are durably isolated and later replayed or repaired;
- an independent verifier can detect missing, extra, stale, modified, and tombstone differences.

## M0 status

M0 satisfies only the source transaction and binlog-to-Kafka capture prerequisites. It does not yet settle Elasticsearch writes, reject stale revisions, retain a DLQ, reconcile projections, detect all log gaps, or rebuild an index. A Kafka record proves that one capture message reached Kafka; it does not prove Elasticsearch convergence or end-to-end final consistency.
~~~

- [ ] **Step 7: Run the complete M0 verification from a clean data volume**

Run:

~~~bash
make reset
make verify
make smoke-m0
make evidence
git diff --check
~~~

Expected:

- all layout, Compose, and Maven tests pass;
- product 1001 is committed with revision 1;
- evidence/m0/revision-message.json contains the matching Canal flat message;
- evidence/m0/canal-position.json records the persisted `meta.dat` SHA-256 and decoded binlog file/position before and after a normal Canal restart;
- product-service dependency tree has no Kafka or Elasticsearch client;
- evidence/m0/version-manifest.json contains every pinned dependency image and no latest tag.

- [ ] **Step 8: Commit M0**

~~~bash
git add .
git commit -m "feat(cdc-lab): prove MySQL to Canal to Kafka capture"
~~~

## M0 Completion Gate

Do not start M1 until all of these are true:

- make reset followed by make smoke-m0 succeeds twice consecutively;
- Canal startup logs confirm ROW/FULL compatibility and the products destination;
- before normal Canal restart, the acknowledged cursor is persisted in `/home/admin/canal-data/products/meta.dat` and its SHA-256 plus decoded file/position are recorded;
- a normal Canal restart preserves that exact hash and position, startup logs read the same cursor, Kafka end offsets do not change merely because of restart, and the first post-restart mutation appears exactly once at the expected next offset;
- the known Canal 1.1.8 static-destination stop NPE is recorded as an upstream limitation and never generalized into a shutdown-safety guarantee;
- Kafka topic has exactly three partitions;
- revision 1 is produced only after the MySQL transaction commits;
- rolling back a failed product transaction leaves no product_search_revision row;
- product-service has no Kafka or Elasticsearch dependency;
- image identities are captured in evidence/m0/version-manifest.json;
- git status is clean after committing generated evidence policy files; runtime evidence may remain ignored.
