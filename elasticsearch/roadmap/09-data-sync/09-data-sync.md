# 阶段 9：数据同步与架构集成（1 周）

> **目标**：掌握 ES 在真实系统架构中的定位和数据同步方案。学完本阶段后，你应该能说清同步双写、MQ 异步、Canal CDC、Logstash JDBC 四种方案的优缺点，以及如何保证 MySQL 和 ES 之间的数据最终一致性。
>
> **前置依赖**：阶段 1-8 全部（需要完整的 ES 使用和原理能力）
>
> **为什么这个阶段排在最后？** 面试几乎必问"你们的数据怎么从 MySQL 同步到 ES 的？怎么保证一致性？"。这个问题综合考查 ES 知识（写入机制、幂等性）+ 分布式系统知识（最终一致性、消息队列）+ 系统设计能力。必须先掌握 ES 本身才能回答好这个问题。
>
> **核心认知**：**ES 不是主数据库**。它不支持事务、不保证强一致性。在真实系统中，MySQL 是真实数据源（Source of Truth），ES 只是搜索/分析的副本。

---

## 9.1 ES 在系统架构中的定位

### 典型的电商搜索架构

```
                        ┌───────────────┐
                        │   用户/前端    │
                        └───────┬───────┘
                                │
                        ┌───────▼───────┐
                        │   API 网关    │
                        └───────┬───────┘
                                │
                ┌───────────────┼───────────────┐
                │               │               │
        ┌───────▼───────┐ ┌────▼────┐ ┌────────▼────────┐
        │ 商品写入服务   │ │搜索服务  │ │ 推荐/分析服务   │
        └───────┬───────┘ └────┬────┘ └────────┬────────┘
                │              │               │
        ┌───────▼───────┐ ┌───▼────┐          │
        │    MySQL      │ │   ES   │◄─────────┘
        │ (主数据库)     │ │(搜索副本)│
        └───────┬───────┘ └────────┘
                │              ▲
                │              │
                └──── 同步机制 ─┘   ← 本阶段的核心内容
```

### 为什么不直接用 ES 当主数据库？

| 维度 | MySQL | ES |
|------|-------|-----|
| 事务（ACID） | ✅ 完整支持 | ❌ 不支持 |
| 强一致性 | ✅ | ❌ 近实时（1s 延迟） |
| 关联查询（JOIN） | ✅ 原生 SQL JOIN | ❌ 不支持（只有 nested/join 近似） |
| 全文搜索 | ❌ LIKE '%keyword%' 极慢 | ✅ 倒排索引天然适合 |
| 复杂聚合分析 | ❌ 大表聚合慢 | ✅ Doc Values 列式存储 |
| 高并发搜索 | ❌ 连接数限制 | ✅ 分片并行查询 |

**结论**：MySQL 做写入和事务，ES 做搜索和分析。两者互补，不是替代。

### 核心挑战——数据一致性

```
MySQL 写入成功 → ES 同步失败 → 用户在 MySQL 中有数据但搜不到
ES 写入成功 → MySQL 回滚 → 搜到了但实际不存在的数据

这就是分布式系统中经典的"双写一致性"问题
```

---

## 9.2 同步方案对比——五种方案全景

### 方案 1：同步双写

```
业务代码：
  begin transaction
    INSERT INTO products (name, price) VALUES ('iPhone', 9999);  ← MySQL
    
    PUT /products/_doc/1 { "name": "iPhone", "price": 9999 }    ← ES
  commit
```

```
问题 1：ES 写入不在 MySQL 事务中
  MySQL commit 成功 → ES 写入失败 → 数据不一致
  MySQL commit 失败 → ES 已经写入 → 数据不一致

问题 2：性能差
  同步调用 ES → 接口响应时间 = MySQL 写入 + ES 写入
  ES 慢或超时直接影响业务

问题 3：代码耦合
  每个写 MySQL 的地方都要加 ES 写入逻辑
```

| 优点 | 缺点 |
|------|------|
| 实现最简单 | 无法保证事务一致性 |
| 延迟最低（同步） | 性能差（同步调用） |
| | 代码耦合严重 |

**适用**：小型项目、一致性要求不高、快速原型。

### 方案 2：异步双写（MQ）

```
┌─────────────┐     ┌──────────┐     ┌──────────┐     ┌──────┐
│  业务服务    │ ──→ │  MySQL   │     │          │     │      │
│             │     │          │     │   MQ     │ ──→ │  ES  │
│  写 MySQL   │ ──→ │ 发 MQ 消息│ ──→ │(Kafka等) │     │      │
└─────────────┘     └──────────┘     └──────────┘     └──────┘
```

```java
// 伪代码
@Transactional
public void createProduct(Product product) {
    // 1. 写 MySQL
    productMapper.insert(product);
    
    // 2. 发 MQ 消息（在事务内发送，事务回滚则不发送）
    mqTemplate.send("product-sync", product);
}

// MQ 消费者
@MQListener("product-sync")
public void syncToES(Product product) {
    // 3. 写 ES（可重试）
    esClient.index("products", product.getId(), product);
}
```

**一致性保障：**

```
问题：MySQL 事务提交后、MQ 消息发成功前宕机 → 消息丢失 → ES 没有数据

解决方案 1：本地消息表
  MySQL 事务内同时写业务表 + 消息表
  → 定时任务扫描消息表，发送到 MQ
  → MQ 消费者写 ES 后删除消息
  → 如果 MQ 发送失败，下次定时任务会重试

解决方案 2：RocketMQ 事务消息
  半消息（prepare）→ 执行本地事务 → commit/rollback
  → 如果 commit → MQ 投递消息 → 消费者写 ES
  → 如果 rollback → MQ 丢弃消息

解决方案 3：消费者幂等性
  消费者用文档 _id 写 ES → 重复消费也只是覆盖，不产生副作用
  → 保证"至少一次"语义没问题
```

| 优点 | 缺点 |
|------|------|
| 解耦（业务代码不直接依赖 ES） | 有延迟（秒级） |
| 异步不影响业务性能 | MQ 可靠性要求高 |
| 可重试 | 需要处理消息积压 |

**适用**：中等规模、可接受秒级延迟、已有 MQ 基础设施的系统。

### 方案 3：CDC（Binlog 监听）——生产首选

```
┌──────────┐    Binlog     ┌──────────────┐     ┌──────┐
│  MySQL   │ ───────────→  │ Canal/Debezium│ ──→ │  ES  │
│          │               │ (伪装 Slave)  │     │      │
└──────────┘               └──────────────┘     └──────┘
```

**核心原理**：Canal/Debezium 伪装成 MySQL 的 Slave 节点，订阅 Binlog（二进制日志），实时捕获所有数据变更（INSERT/UPDATE/DELETE），然后转化为 ES 的写入操作。

**对业务代码完全透明**——业务代码只管写 MySQL，不需要关心 ES 同步。

| 优点 | 缺点 |
|------|------|
| **对业务代码零侵入** | 架构复杂（多一个组件） |
| 数据一致性好（基于 Binlog，不会漏数据） | Binlog 解析有延迟（通常 1-3 秒） |
| 能捕获所有变更（含直接 SQL 修改） | DDL 变更处理复杂 |

**适用**：**大型生产环境首选**。

### 方案 4：Logstash JDBC

```
Logstash 定时轮询（如每分钟）：
  SELECT * FROM products WHERE updated_at > :last_run_time
  → 增量数据 → 写入 ES
```

| 优点 | 缺点 |
|------|------|
| 配置简单（一个 .conf 文件） | 延迟高（分钟级） |
| 不需要额外组件 | 依赖 updated_at 字段（删除操作难处理） |

**适用**：数据实时性要求不高、简单场景。

### 方案 5：ETL 全量导入

定时（如每天凌晨）全量从 MySQL 导入到 ES。

| 优点 | 缺点 |
|------|------|
| 数据最终一致 | 延迟高（小时级） |
| 实现简单 | 对 MySQL 有查询压力 |

**适用**：冷数据、初始化导入、全量校对。

### 五种方案总结

```
               实时性 ◄────────────────────────────► 延迟
               │                                      │
  同步双写     │  MQ 异步    CDC       Logstash     全量ETL
  (毫秒级)    │  (秒级)    (1-3秒)   (分钟级)     (小时级)
               │                                      │
               实现简单 ◄────────────────────────► 架构复杂
```

> **面试怎么答**："你们的数据怎么从 MySQL 同步到 ES 的？"
>
> 生产中我们用 Canal CDC 方案。Canal 伪装为 MySQL Slave 订阅 Binlog，实时捕获数据变更（INSERT/UPDATE/DELETE），通过 Kafka 中间层投递到 ES 写入消费者。选 CDC 的原因是对业务代码零侵入、基于 Binlog 不会漏数据、延迟在 1-3 秒可接受。一致性通过消费者幂等（用业务主键作为 ES 文档 _id）+ 全量校对任务（每天凌晨对比 MySQL 和 ES 数据量和关键字段）来保障。

---

## 9.3 Canal/Debezium CDC 方案详解

### Canal 架构

```
┌──────────┐  Binlog 拉取  ┌──────────────┐   ┌──────────┐   ┌──────────┐
│  MySQL   │ ──────────→   │ Canal Server │ → │  Kafka   │ → │ Consumer │ → ES
│ (Master) │               │ (伪装 Slave)  │   │          │   │ (ES Writer)│
└──────────┘               └──────────────┘   └──────────┘   └──────────┘
                                    │
                               ┌────┴────┐
                               │ 位点管理 │  ← 记录消费到哪个 Binlog 位置
                               │(ZK/本地) │
                               └─────────┘
```

**Canal 的核心工作流程：**

1. **Canal Server 启动** → 伪装为 MySQL Slave，向 MySQL Master 发送 dump 协议请求
2. **MySQL 推送 Binlog** → Canal 接收并解析 Binlog 事件（INSERT/UPDATE/DELETE）
3. **Canal 产出结构化变更数据** → 包含表名、操作类型、变更前后的行数据
4. **投递到 Kafka**（或直接给 Client） → Consumer 根据变更类型执行 ES 操作

```json
// Canal 产出的变更消息示例
{
  "database": "shop",
  "table": "products",
  "type": "UPDATE",
  "data": [
    { "id": "1", "name": "iPhone 15", "price": "6999" }     // 变更后
  ],
  "old": [
    { "id": "1", "name": "iPhone 15", "price": "7999" }     // 变更前
  ]
}

// Consumer 的处理逻辑
switch (event.type) {
  case "INSERT":
  case "UPDATE":  → ES index（upsert）
  case "DELETE":  → ES delete
}
```

### Debezium 架构

```
┌──────────┐  Binlog   ┌────────────────┐   ┌────────┐   ┌──────────────┐
│  MySQL   │ ───────→  │   Debezium     │ → │ Kafka  │ → │ ES Sink      │ → ES
│          │           │  (Kafka Connect │   │        │   │ Connector    │
└──────────┘           │   Source)       │   └────────┘   └──────────────┘
                       └────────────────┘
```

Debezium 基于 Kafka Connect 框架，不需要自己写 Consumer——用 Elasticsearch Sink Connector 直接把 Kafka 消息写入 ES。

### Canal vs Debezium

| 维度 | Canal | Debezium |
|------|-------|----------|
| 来源 | 阿里开源 | Red Hat 开源 |
| 支持的数据库 | MySQL（主要） | MySQL/PostgreSQL/MongoDB/Oracle/SQL Server |
| 生态 | 国内广泛 | 国际生态更丰富 |
| 架构 | 独立 Server + Client | 基于 Kafka Connect |
| 运维 | 需自己管理位点 | Kafka Connect 管理 offset |

### CDC 常见问题

**问题 1：DDL 变更如何处理？**

MySQL 加字段 → Binlog 中有 DDL 事件 → Canal/Debezium 可以捕获。但 ES 的 Mapping 更新需要特殊处理：
- 新字段如果在 ES Mapping 中已有（dynamic: true） → 自动添加
- 新字段如果 ES 设了 dynamic: strict → 写入报错
- **最佳实践**：ES Mapping 提前预留好字段，或配合 Index Template 管理

**问题 2：Binlog 位点管理与故障恢复**

Canal 记录当前消费到的 Binlog 文件名和位置（position）。故障恢复时从上次的位点继续消费，不会丢数据。但如果 Binlog 已经被 MySQL 清理（expire_logs_days 到期），需要全量重新导入。

**问题 3：延迟监控**

监控 Canal/Debezium 的消费延迟——如果延迟超过阈值（如 10 秒），触发告警。常见延迟原因：ES 写入慢、Kafka 积压、MySQL 大事务导致 Binlog 过大。

---

## 9.4 异步双写（MQ 方案）详解

### 消费者幂等性

**这是面试必考的知识点。**

```
场景：MQ 消费者消费到一条消息后写入 ES，但在 ack 之前宕机了
  → MQ 重新投递同一条消息
  → 消费者再次写入 ES
  → 如果不做幂等处理，可能导致数据重复或不一致

解决：用业务主键作为 ES 文档 _id
  PUT /products/_doc/{product_id}   ← 用 product_id 作为 _id
  → 相同 _id 重复写入 = 覆盖（upsert） → 幂等！
```

### 消费失败处理

```
正常流程：
  MQ 消息 → 消费者 → 写 ES → ack → 完成

写 ES 失败：
  MQ 消息 → 消费者 → 写 ES 失败
  → 重试 3 次
  → 仍然失败 → 发送到死信队列（DLQ）
  → 人工或定时任务处理死信队列中的消息

监控告警：
  死信队列深度 > 0 → 触发告警
  消费延迟 > 阈值 → 触发告警
```

### 消息积压处理

```
场景：大促期间 MySQL 写入暴涨 → MQ 消息堆积 → ES 同步延迟飙升

解决：
  1. 增加消费者实例数（水平扩展）
  2. 批量消费：一次拉取多条消息 → 用 _bulk 批量写入 ES
  3. 临时关闭 ES 的 refresh（refresh_interval=-1）提升写入速度
  4. 大促结束后恢复正常配置
```

---

## 9.5 数据一致性保障

### 最终一致性

在分布式系统中，MySQL 和 ES 之间**不可能做到强一致性**（没有分布式事务支持）。目标是**最终一致性**——允许短暂不一致，但最终数据会一致。

### 全量校对机制

```
定时任务（如每天凌晨）：

步骤 1：对比数量
  MySQL: SELECT COUNT(*) FROM products WHERE status='active'  → 10000
  ES:    GET /products/_count { "query": { "match_all": {} } } → 9998
  → 差异 2 条 → 触发详细校对

步骤 2：详细校对
  MySQL: SELECT id, updated_at FROM products ORDER BY id
  ES:    scroll 遍历所有文档的 _id 和 updated_at
  → 对比找出差异的文档

步骤 3：增量修复
  只对差异文档做重新同步（从 MySQL 读取最新数据写入 ES）
```

### 补偿机制

```
实时补偿：
  业务接口查询 ES 没找到数据 → 回查 MySQL
  → 如果 MySQL 有 → 说明 ES 同步延迟 → 返回 MySQL 的数据 + 触发 ES 补偿同步

定时补偿：
  全量校对发现不一致 → 触发增量修复
```

### 监控告警

| 监控项 | 阈值 | 告警 |
|--------|------|------|
| 同步延迟 | > 10 秒 | ⚠️ |
| 消息积压数 | > 10000 | ⚠️ |
| ES 写入失败率 | > 0.1% | 🔴 |
| 死信队列深度 | > 0 | 🔴 |
| 全量校对差异数 | > 0 | ⚠️ |

---

## 9.6 ES 客户端使用

### Java 客户端

```java
// ES 8.x+ 推荐：Elasticsearch Java Client
ElasticsearchClient client = new ElasticsearchClient(transport);

// 索引文档
client.index(i -> i
    .index("products")
    .id("1")
    .document(new Product("iPhone 15", 6999))
);

// 搜索
SearchResponse<Product> response = client.search(s -> s
    .index("products")
    .query(q -> q.match(m -> m.field("name").query("手机")))
, Product.class);
```

### Python 客户端

```python
from elasticsearch import Elasticsearch

es = Elasticsearch("http://localhost:9200")

# 索引
es.index(index="products", id=1, document={"name": "iPhone 15", "price": 6999})

# 搜索
result = es.search(index="products", query={"match": {"name": "手机"}})
```

### 客户端最佳实践

| 实践 | 说明 |
|------|------|
| 连接池 | 复用 HTTP 连接，不要每次请求创建新连接 |
| 超时设置 | 连接超时 5s，读取超时 30s |
| 重试 | 写入失败重试 3 次，指数退避 |
| 批量操作 | 用 _bulk 而非单条写入 |
| 异步 | 高并发场景用异步客户端 |

---

## 面试高频题与参考答案

### Q1：你们的数据怎么从 MySQL 同步到 ES 的？

**答**：（见 9.2 节五种方案的面试回答）

### Q2：同步双写有什么问题？怎么解决？

**答**：同步双写最大的问题是无法保证事务一致性——MySQL 和 ES 不在同一个事务中，一个写入成功另一个失败就会导致数据不一致。而且同步调用 ES 会增加接口响应时间，ES 慢或超时直接影响业务。

解决方案是改为异步双写（通过 MQ 解耦）或使用 CDC 方案（Canal/Debezium 监听 Binlog）。MQ 方案通过本地消息表或事务消息保证消息不丢失，消费者用文档 _id 保证幂等性。CDC 方案对业务代码零侵入，且基于 Binlog 不会漏数据。

### Q3：Canal/Debezium 和 MQ 双写的区别？各自优缺点？

**答**：核心区别是数据变更的捕获方式。MQ 双写需要业务代码主动发消息，对代码有侵入；CDC 通过监听 MySQL Binlog 自动捕获所有变更，对业务代码零侵入。

MQ 双写的优点是架构相对简单（不需要 Canal 组件），延迟可控，但需要每个写 MySQL 的地方都发 MQ 消息，容易遗漏。CDC 的优点是捕获所有变更（包括直接 SQL 修改、存储过程等），不会遗漏，但架构多了 Canal/Debezium 组件，运维复杂度更高。

大型系统推荐 CDC，小型系统 MQ 双写足够。

### Q4：如何保证 MySQL 和 ES 的数据一致性？

**答**：首先明确目标是最终一致性，不追求强一致性。保障方案分三个层次：

第一，实时层：同步机制（CDC 或 MQ）保证数据变更秒级同步到 ES。消费者用 _id 幂等写入，失败重试+死信队列。

第二，校对层：每天一次全量校对——对比 MySQL 和 ES 的数据量和关键字段，发现差异后增量修复。

第三，补偿层：业务接口查 ES 没找到数据时回查 MySQL，如果 MySQL 有就返回 MySQL 数据并触发 ES 补偿同步。

监控层面关注同步延迟、消息积压、写入失败率和死信队列深度。

### Q5：ES 写入失败怎么办？如何保证消费幂等？

**答**：写入失败时先重试（3 次，指数退避），仍然失败就发送到死信队列（DLQ），触发告警后人工处理。常见失败原因：ES 集群 Red 状态、Mapping 类型冲突、文档大小超限。

消费幂等通过用业务主键作为 ES 文档 _id 来保证。比如 product_id=123 的商品，ES 文档 _id 也设为 123。重复消费同一条消息只是再次 PUT /products/_doc/123，相当于 upsert 覆盖，结果幂等。

### Q6：全量同步和增量同步怎么配合？

**答**：初始化阶段用全量同步（ETL 从 MySQL 批量导出写入 ES），建立完整的数据基线。之后切换为增量同步（CDC 或 MQ），只处理新产生的数据变更。

全量同步也作为日常校对手段——每天凌晨低峰期跑全量校对，发现增量同步遗漏的数据后做增量修复。如果 CDC 的 Binlog 位点丢失或过期，也需要一次全量重新导入。

---

## 动手实践

### 练习 1：Logstash JDBC 增量同步

```
# 这是最简单的同步方案，适合快速体验

# 1. 准备 MySQL 表
# CREATE TABLE products (
#   id INT PRIMARY KEY AUTO_INCREMENT,
#   name VARCHAR(255),
#   price DECIMAL(10,2),
#   updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
# );

# 2. Logstash 配置文件 (mysql-to-es.conf)
input {
  jdbc {
    jdbc_connection_string => "jdbc:mysql://localhost:3306/shop"
    jdbc_user => "root"
    jdbc_password => "password"
    jdbc_driver_library => "/path/to/mysql-connector-java.jar"
    jdbc_driver_class => "com.mysql.cj.jdbc.Driver"
    
    statement => "SELECT * FROM products WHERE updated_at > :sql_last_value"
    tracking_column => "updated_at"
    tracking_column_type => "timestamp"
    use_column_value => true
    
    schedule => "*/30 * * * * *"    # 每 30 秒执行一次
    last_run_metadata_path => "/tmp/logstash_jdbc_last_run"
  }
}

output {
  elasticsearch {
    hosts => ["http://localhost:9200"]
    index => "products"
    document_id => "%{id}"           # 用 MySQL 的 id 作为 ES 文档 _id（幂等）
  }
}

# 3. 运行 Logstash
# bin/logstash -f mysql-to-es.conf

# 4. 在 MySQL 中插入/更新数据，30 秒后在 ES 中验证
```

### 练习 2：模拟 MQ 双写的幂等性

```
# 模拟幂等写入：相同 _id 重复写入

# 1. 第一次写入
PUT /idempotent_test/_doc/product_001
{ "name": "iPhone 15", "price": 7999, "version": 1 }

# 2. "消费者重试"——相同 _id 再次写入（覆盖）
PUT /idempotent_test/_doc/product_001
{ "name": "iPhone 15", "price": 6999, "version": 2 }

# 3. 验证——只有最新版本
GET /idempotent_test/_doc/product_001
# 预期：price=6999, version=2（旧版本被覆盖，幂等！）

# 4. 清理
DELETE /idempotent_test
```

### 练习 3：全量校对模拟

```
# 模拟 MySQL 和 ES 数据不一致的检测

# 1. 创建索引并写入"MySQL 同步过来的"数据
PUT /consistency_test/_doc/1
{ "name": "商品 A", "price": 100 }
PUT /consistency_test/_doc/2
{ "name": "商品 B", "price": 200 }
PUT /consistency_test/_doc/3
{ "name": "商品 C", "price": 300 }

# 2. 假设 MySQL 中实际有 4 条数据（商品 D 同步丢失了）
# MySQL: id=1,2,3,4
# ES:    id=1,2,3

# 3. 校对——统计 ES 文档数
GET /consistency_test/_count
# 返回 3，MySQL 有 4 条 → 发现差异！

# 4. 补偿——从"MySQL"补写缺失的文档
PUT /consistency_test/_doc/4
{ "name": "商品 D", "price": 400 }

# 5. 再次校对
GET /consistency_test/_count
# 返回 4 → 一致！

# 6. 清理
DELETE /consistency_test
```

---

## 本阶段总结

```
ES 的定位：搜索/分析副本，不是主数据库
  MySQL = Source of Truth（事务+一致性）
  ES = Search Replica（全文搜索+聚合分析）

五种同步方案（按推荐度排序）：
  ★★★★★ CDC（Canal/Debezium）→ 大型生产首选，零侵入
  ★★★★  MQ 异步双写         → 中等规模，已有 MQ 设施
  ★★★   Logstash JDBC      → 低实时性要求，简单场景
  ★★    ETL 全量导入        → 初始化/冷数据/校对
  ★     同步双写            → 快速原型/小项目

一致性保障三板斧：
  实时层：CDC/MQ + 幂等消费 + 失败重试 + 死信队列
  校对层：定时全量对比 + 增量修复
  补偿层：查 ES 没有 → 回查 MySQL → 触发补偿同步

消费者幂等：用业务主键作为 ES 文档 _id
```

**下一阶段**：阶段 10 生产运维与高级特性——ILM 索引生命周期管理、快照恢复、安全配置、Suggester 自动补全、向量搜索、Ingest Pipeline、ELK 架构。这是 ES 知识的最后一块拼图。
