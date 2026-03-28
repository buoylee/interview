# PerfShop 三语言 Demo 服务

> 一个刻意包含典型性能问题的电商 Demo，提供 Java / Go / Python 三个版本，用于性能调优实战练习。

---

## 1. PerfShop 是什么

PerfShop 是一个**简化版电商系统**，专为性能调优学习设计。它不追求功能完整，而是刻意在关键路径上埋入常见性能问题（N+1 查询、缓存穿透、慢 SQL、内存泄漏、协程泄漏等），供学习者用各种工具定位和修复。

三个语言版本**功能完全一致、API 完全一致**，方便对比不同语言 / 运行时在相同业务逻辑下的性能表现。

---

## 2. 架构设计

```
                         ┌────────────────────────────────┐
                         │          Load Balancer          │
                         │       (Nginx / 手动切换)        │
                         └──────┬───────┬───────┬─────────┘
                                │       │       │
                    ┌───────────┘       │       └───────────┐
                    ▼                   ▼                   ▼
             ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
             │ Java (8081) │   │  Go (8082)   │   │Python (8083)│
             │ Spring Boot │   │     Gin      │   │   FastAPI   │
             └──────┬──────┘   └──────┬──────┘   └──────┬──────┘
                    │                 │                  │
          ┌─────────┴─────────────────┴──────────────────┴──────────┐
          │                    共享中间件层                           │
          │  ┌──────────┐  ┌──────────┐  ┌──────────┐              │
          │  │  MySQL    │  │  Redis   │  │  Kafka   │              │
          │  │  :3306    │  │  :6379   │  │  :9092   │              │
          │  └──────────┘  └──────────┘  └──────────┘              │
          └────────────────────────────────────────────────────────┘
```

### 核心设计原则

1. **单体架构**：每个语言版本都是单体服务，降低学习门槛
2. **共享存储**：三个版本连接同一套 MySQL / Redis / Kafka，数据一致
3. **可观测性内置**：每个版本都暴露 Prometheus 指标、接入 Jaeger 链路追踪、结构化日志输出到 stdout
4. **刻意的性能缺陷**：每个版本包含 8-10 个刻意埋入的性能问题，覆盖 CPU、内存、I/O、并发等维度

---

## 3. 中间件依赖部署

在启动应用之前，先拉起中间件：

```yaml
# infra-compose.yml
version: "3.8"

services:
  mysql:
    image: mysql:8.0
    container_name: perfshop-mysql
    ports:
      - "3306:3306"
    environment:
      MYSQL_ROOT_PASSWORD: perfshop123
      MYSQL_DATABASE: perfshop
    volumes:
      - ./sql/init.sql:/docker-entrypoint-initdb.d/init.sql:ro
      - mysql_data:/var/lib/mysql
    command: >
      --character-set-server=utf8mb4
      --collation-server=utf8mb4_unicode_ci
      --max-connections=500
      --slow-query-log=ON
      --slow-query-log-file=/var/log/mysql/slow.log
      --long-query-time=0.5

  redis:
    image: redis:7-alpine
    container_name: perfshop-redis
    ports:
      - "6379:6379"
    command: >
      redis-server
      --maxmemory 256mb
      --maxmemory-policy allkeys-lru
      --save ""

  kafka:
    image: bitnami/kafka:3.7
    container_name: perfshop-kafka
    ports:
      - "9092:9092"
    environment:
      KAFKA_CFG_NODE_ID: 1
      KAFKA_CFG_PROCESS_ROLES: broker,controller
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: 1@kafka:9093
      KAFKA_CFG_LISTENERS: PLAINTEXT://:9092,CONTROLLER://:9093
      KAFKA_CFG_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: CONTROLLER
      KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP: CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT
      KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE: "true"

volumes:
  mysql_data: {}
```

```bash
docker compose -f infra-compose.yml up -d

# 验证
mysql -h127.0.0.1 -uroot -pperfshop123 -e "SHOW DATABASES;"
redis-cli ping        # 返回 PONG
kafka-console-topics.sh --bootstrap-server localhost:9092 --list
```

---

## 4. 数据库初始化

`sql/init.sql` 创建核心表和测试数据：

```sql
CREATE TABLE IF NOT EXISTS products (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(200) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    stock INT NOT NULL DEFAULT 0,
    category VARCHAR(50),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_category (category)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS orders (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    total_amount DECIMAL(10,2) NOT NULL,
    status VARCHAR(20) DEFAULT 'PENDING',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB;

CREATE TABLE IF NOT EXISTS order_items (
    id BIGINT PRIMARY KEY AUTO_INCREMENT,
    order_id BIGINT NOT NULL,
    product_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    INDEX idx_order_id (order_id)
) ENGINE=InnoDB;

-- 插入 10000 条商品测试数据
DELIMITER //
CREATE PROCEDURE seed_products()
BEGIN
    DECLARE i INT DEFAULT 1;
    WHILE i <= 10000 DO
        INSERT INTO products (name, price, stock, category, description)
        VALUES (
            CONCAT('Product-', i),
            ROUND(RAND() * 1000 + 1, 2),
            FLOOR(RAND() * 500),
            ELT(FLOOR(RAND() * 5) + 1, 'electronics', 'clothing', 'food', 'books', 'sports'),
            CONCAT('Description for product ', i)
        );
        SET i = i + 1;
    END WHILE;
END //
DELIMITER ;

CALL seed_products();
DROP PROCEDURE seed_products;
```

---

## 5. 三语言版本构建与运行

### 5.1 Java 版 (Spring Boot 3.x)

```bash
cd perfshop-java
./mvnw clean package -DskipTests
java -jar target/perfshop-java-1.0.jar \
  --server.port=8081 \
  --spring.datasource.url=jdbc:mysql://localhost:3306/perfshop \
  --spring.datasource.username=root \
  --spring.datasource.password=perfshop123
```

关键依赖：
- Spring Boot 3.x + Spring Web
- MyBatis-Plus（ORM）
- Micrometer + Prometheus（指标暴露于 `/actuator/prometheus`）
- OpenTelemetry Java Agent（链路追踪，通过 `-javaagent` 挂载）

```bash
# 带 OTel Agent 启动
java -javaagent:opentelemetry-javaagent.jar \
  -Dotel.service.name=perfshop-java \
  -Dotel.exporter.otlp.endpoint=http://localhost:4317 \
  -jar target/perfshop-java-1.0.jar
```

### 5.2 Go 版 (Gin)

```bash
cd perfshop-go
go build -o perfshop-go ./cmd/server
./perfshop-go \
  --port=8082 \
  --dsn="root:perfshop123@tcp(localhost:3306)/perfshop?parseTime=true" \
  --redis-addr="localhost:6379"
```

关键依赖：
- Gin（HTTP 框架）
- GORM（ORM）
- `prometheus/client_golang`（指标暴露于 `/metrics`）
- OpenTelemetry Go SDK（链路追踪）

### 5.3 Python 版 (FastAPI)

```bash
cd perfshop-python
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8083 --workers 4
```

关键依赖：
- FastAPI + Uvicorn
- SQLAlchemy 2.0（ORM）
- `prometheus-fastapi-instrumentator`（指标暴露于 `/metrics`）
- `opentelemetry-instrument`（自动埋点）

```bash
# 带 OTel 自动埋点启动
opentelemetry-instrument \
  --service_name perfshop-python \
  --exporter_otlp_endpoint http://localhost:4317 \
  uvicorn app.main:app --host 0.0.0.0 --port 8083 --workers 4
```

---

## 6. API 接口说明

三个版本的 API 完全一致：

### 6.1 商品模块

| 方法 | 路径 | 说明 | 刻意的性能问题 |
|------|------|------|----------------|
| GET | `/api/products` | 商品列表（分页） | N+1 查询 |
| GET | `/api/products/:id` | 商品详情 | 缓存穿透 |
| GET | `/api/products/search?q=xxx` | 商品搜索 | LIKE '%xxx%' 全表扫描 |
| POST | `/api/products` | 创建商品 | 无性能问题 |

```bash
# 获取商品列表（默认第1页，每页20条）
curl http://localhost:8081/api/products?page=1&size=20

# 商品详情
curl http://localhost:8081/api/products/42

# 商品搜索
curl "http://localhost:8081/api/products/search?q=phone"
```

### 6.2 订单模块

| 方法 | 路径 | 说明 | 刻意的性能问题 |
|------|------|------|----------------|
| POST | `/api/orders` | 创建订单 | 大事务、锁竞争 |
| GET | `/api/orders/:id` | 订单详情 | 多次 DB 查询未聚合 |
| GET | `/api/orders/user/:uid` | 用户订单列表 | 未加索引的排序 |
| POST | `/api/orders/:id/pay` | 模拟支付 | 同步调用外部 API（慢）|

```bash
# 创建订单
curl -X POST http://localhost:8081/api/orders \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": 1001,
    "items": [
      {"product_id": 1, "quantity": 2},
      {"product_id": 5, "quantity": 1}
    ]
  }'

# 查询订单
curl http://localhost:8081/api/orders/1

# 模拟支付
curl -X POST http://localhost:8081/api/orders/1/pay
```

### 6.3 系统模块

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/health` | 健康检查 |
| GET | `/metrics` 或 `/actuator/prometheus` | Prometheus 指标 |
| GET | `/api/debug/leak` | 触发内存泄漏（学习用） |
| GET | `/api/debug/cpu-burn?seconds=10` | 触发 CPU 密集计算 |
| GET | `/api/debug/deadlock` | 触发死锁（Go/Java） |
| GET | `/api/debug/goroutine-leak` | 触发协程泄漏（Go 版本） |

```bash
# 健康检查
curl http://localhost:8081/health
# {"status": "UP", "version": "1.0.0"}

# 触发内存泄漏（仅调试用）
curl http://localhost:8081/api/debug/leak?size=10485760  # 泄漏 10MB

# 触发 CPU 热点
curl http://localhost:8081/api/debug/cpu-burn?seconds=5
```

---

## 7. 验证完整链路

### 7.1 确认指标接入

打开 Prometheus (http://localhost:9090)，进入 Status -> Targets，确认三个应用的 target 状态为 UP。

在 Graph 页面查询：

```promql
# 请求速率
rate(http_requests_total{job="perfshop-java"}[1m])

# 请求延迟 P99
histogram_quantile(0.99, rate(http_request_duration_seconds_bucket{job="perfshop-go"}[5m]))
```

### 7.2 确认链路接入

1. 发几个请求后打开 Jaeger UI (http://localhost:16686)
2. 在 Service 下拉框选择 `perfshop-java`
3. 点击 Find Traces，应能看到完整的请求链路，包含 HTTP -> DB -> Redis 各段耗时

### 7.3 确认日志接入

打开 Grafana (http://localhost:3000)，进入 Explore，选择 Loki 数据源：

```logql
{container="perfshop-java"} |= "ERROR"
```

---

## 8. 埋入的性能问题清单

每个问题都有对应的 Git 分支（`fix/xxx`），供你对比修复前后的性能差异：

| 编号 | 问题类型 | 所在接口 | 预期现象 |
|------|----------|----------|----------|
| P01 | N+1 查询 | GET /api/products | 列表接口产生 20+ 条 SQL |
| P02 | 缓存穿透 | GET /api/products/:id | 不存在的 ID 每次打到 DB |
| P03 | 全表扫描 | GET /api/products/search | EXPLAIN 显示 type=ALL |
| P04 | 大事务 | POST /api/orders | 事务内调用外部 HTTP |
| P05 | 连接泄漏 | POST /api/orders/:id/pay | DB 连接池耗尽 |
| P06 | 内存泄漏 | GET /api/debug/leak | 堆内存持续增长 |
| P07 | CPU 热点 | GET /api/debug/cpu-burn | 正则/序列化热点 |
| P08 | 协程泄漏 | GET /api/debug/goroutine-leak | goroutine 数持续增长 |
| P09 | 慢日志 | 所有接口 | 同步写日志阻塞请求 |
| P10 | 未压缩响应 | GET /api/products | 大 JSON 响应无 gzip |

---

## 9. 下一步

1. 先完成 [监控栈部署](01-monitoring-stack.md)
2. 启动 PerfShop 并确认指标、链路、日志三大支柱全部接入
3. 用 wrk / k6 对各接口施加压力，开始你的性能调优之旅
