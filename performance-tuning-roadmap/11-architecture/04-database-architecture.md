# 数据库架构优化

单机数据库的容量和性能终究有上限。当单表数据量超过 5000 万行、单库写入 QPS 超过 5000、磁盘容量逼近上限时，就需要从架构层面解决问题。本文覆盖分库分表、读写分离、CQRS、冷热分离等核心数据库架构方案，帮你做出正确的架构选型。

---

## 一、分库分表策略

### 1.1 何时需要分库分表

```
先问自己这些问题：
1. 单表行数 > 5000 万？ → 考虑分表
2. 单库 QPS > 5000？    → 考虑分库
3. 数据量 > 单机磁盘容量？ → 必须分库
4. 数据增长速度快？     → 提前规划

注意：分库分表是最后手段，先尝试：
- 索引优化
- 慢 SQL 优化
- 缓存层
- 读写分离
- 冷热数据分离
```

### 1.2 垂直拆分

**垂直分库**：按业务领域拆分到不同数据库。

```
拆分前：
  monolith_db
    ├── user 表
    ├── order 表
    ├── product 表
    └── payment 表

拆分后：
  user_db      → user、user_address、user_preference
  order_db     → order、order_item、order_status
  product_db   → product、product_sku、category
  payment_db   → payment、refund、settlement
```

**垂直分表**：将大表中不常用的字段拆到扩展表。

```sql
-- 拆分前：user 表有 30 个字段
SELECT * FROM user WHERE id = 1;  -- 读取了大量不需要的字段

-- 拆分后
-- user 表（核心字段，高频查询）
CREATE TABLE user (
    id BIGINT PRIMARY KEY,
    username VARCHAR(50),
    email VARCHAR(100),
    status TINYINT,
    created_at DATETIME
);

-- user_detail 表（扩展字段，低频查询）
CREATE TABLE user_detail (
    user_id BIGINT PRIMARY KEY,
    bio TEXT,
    avatar_url VARCHAR(500),
    preferences JSON,
    FOREIGN KEY (user_id) REFERENCES user(id)
);
```

### 1.3 水平分片

**分片键选择原则**：
1. 查询必带该字段（避免全表扫描）
2. 数据分布均匀（避免热点）
3. 尽量让关联查询在同一个分片内

```
常见分片策略：

1. 取模法：shard_id = user_id % shard_count
   优点：分布均匀
   缺点：扩容困难（需要数据迁移）

2. 范围法：shard_0 = id [1, 1000万], shard_1 = id [1000万, 2000万]
   优点：扩容简单（新增分片即可）
   缺点：容易产生热点（新数据集中在最新分片）

3. 一致性哈希：shard_id = hash(user_id) % virtual_nodes
   优点：扩容只需迁移少量数据
   缺点：实现复杂

4. 按时间分片：shard_2024_01, shard_2024_02, ...
   优点：天然支持归档
   缺点：查询跨分片时性能差
```

**取模分片示例**：

```sql
-- 假设分 16 张表
-- user_00, user_01, ..., user_15

-- 路由规则
-- table_index = user_id % 16

-- 查询路由
SELECT * FROM user_07 WHERE user_id = 123;  -- 123 % 16 = 11 → user_11
```

### 1.4 分库分表带来的问题

| 问题 | 描述 | 解决方案 |
|------|------|----------|
| 跨库 JOIN | 不同分片的数据无法 JOIN | 应用层聚合 / 宽表冗余 |
| 分布式事务 | 跨库事务一致性 | Saga / TCC / 最终一致 |
| 全局唯一 ID | 自增 ID 冲突 | 雪花算法 / UUID / 号段模式 |
| 跨分片查询 | 聚合/排序/分页 | 中间件路由 + 归并 |
| 扩容困难 | 增加分片需数据迁移 | 预估容量多分几个 / 一致性哈希 |

### 1.5 全局 ID 生成

```java
// 雪花算法（Snowflake）- 64bit
// | 1bit符号 | 41bit时间戳 | 10bit机器ID | 12bit序列号 |
// 每毫秒可生成 4096 个 ID，每台机器每秒约 400 万个

// 使用 Hutool 的雪花算法
Snowflake snowflake = IdUtil.getSnowflake(workerId, datacenterId);
long id = snowflake.nextId();

// 号段模式（Leaf/美团方案）
// 预分配一段 ID 到内存，用完再取下一段
// 表结构：
CREATE TABLE id_alloc (
    biz_tag VARCHAR(128) PRIMARY KEY,
    max_id BIGINT NOT NULL,
    step INT NOT NULL DEFAULT 1000,
    description VARCHAR(256),
    update_time DATETIME
);
```

---

## 二、分库分表中间件

### 2.1 ShardingSphere

```yaml
# ShardingSphere-JDBC 配置（application.yml）
spring:
  shardingsphere:
    datasource:
      names: ds0, ds1
      ds0:
        type: com.zaxxer.hikari.HikariDataSource
        driver-class-name: com.mysql.cj.jdbc.Driver
        jdbc-url: jdbc:mysql://db0:3306/order_db
        username: root
        password: pass
      ds1:
        type: com.zaxxer.hikari.HikariDataSource
        driver-class-name: com.mysql.cj.jdbc.Driver
        jdbc-url: jdbc:mysql://db1:3306/order_db
        username: root
        password: pass
    rules:
      sharding:
        tables:
          order:
            actual-data-nodes: ds$->{0..1}.order_$->{0..15}
            database-strategy:
              standard:
                sharding-column: user_id
                sharding-algorithm-name: db-mod
            table-strategy:
              standard:
                sharding-column: order_id
                sharding-algorithm-name: table-mod
            key-generate-strategy:
              column: order_id
              key-generator-name: snowflake
        sharding-algorithms:
          db-mod:
            type: MOD
            props:
              sharding-count: 2    # 2 个库
          table-mod:
            type: MOD
            props:
              sharding-count: 16   # 每库 16 张表
        key-generators:
          snowflake:
            type: SNOWFLAKE
```

### 2.2 方案对比

| 特性 | ShardingSphere-JDBC | ShardingSphere-Proxy | Vitess |
|------|--------------------|--------------------|--------|
| 部署模式 | 嵌入应用（JAR 包） | 独立代理 | 独立集群 |
| 性能损耗 | 低（<5%） | 中（网络转发） | 中 |
| 语言限制 | Java 专用 | 无（MySQL 协议） | 无（MySQL 协议） |
| 运维复杂度 | 低 | 中 | 高 |
| 适用场景 | Java 项目 | 多语言项目 | 超大规模 |

---

## 三、读写分离

### 3.1 架构设计

```
                     ┌─────────────┐
      写请求 ──────→ │  Master (主)  │
                     └──────┬──────┘
                       binlog 复制
                     ┌──────┴──────┐
      读请求 ──────→ │  Slave (从)   │ × N
                     └─────────────┘
```

### 3.2 主从延迟问题

**主从延迟**是读写分离最大的痛点：写入主库后立刻从从库读，可能读到旧数据。

```java
// 场景：用户修改昵称后立刻查看
userService.updateNickname(userId, newName);      // 写主库
User user = userService.getUser(userId);           // 读从库（可能还是旧名字！）

// 解决方案 1：强制走主库
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ReadFromMaster {}

@ReadFromMaster
public User getUser(Long userId) {
    return userMapper.selectById(userId);
}

// 解决方案 2：写后短期走主库（Session 级别）
public void updateNickname(Long userId, String name) {
    userMapper.updateNickname(userId, name);
    // 设置标记，接下来 3 秒内该用户的读请求走主库
    MasterSlaveHint.setForceMain(userId, Duration.ofSeconds(3));
}

// 解决方案 3：监控主从延迟，延迟过大时读请求也走主库
// MySQL: SHOW SLAVE STATUS → Seconds_Behind_Master
```

### 3.3 ShardingSphere 读写分离配置

```yaml
spring:
  shardingsphere:
    rules:
      readwrite-splitting:
        data-sources:
          readwrite_ds:
            write-data-source-name: master_ds
            read-data-source-names:
              - slave_ds_0
              - slave_ds_1
            load-balancer-name: round_robin
            transaction-read-query-strategy: PRIMARY  # 事务中读也走主库
        load-balancers:
          round_robin:
            type: ROUND_ROBIN
```

---

## 四、CQRS 模式

### 4.1 核心思想

```
传统模式：
  同一个模型 + 同一个数据库 → 读写都走这里

CQRS 模式：
  Command（写）→ 写模型 → 写库（关系型数据库，保证一致性）
  Query（读）  → 读模型 → 读库（搜索引擎/缓存/物化视图，优化查询）
                            ↑
                     事件/消息 同步数据
```

### 4.2 实现示例

```java
// 写端（Command）
@Service
public class OrderCommandService {

    @Autowired
    private OrderRepository orderRepository; // MySQL
    @Autowired
    private EventPublisher eventPublisher;

    @Transactional
    public Long createOrder(CreateOrderCommand cmd) {
        Order order = Order.create(cmd);
        orderRepository.save(order);

        // 发布领域事件
        eventPublisher.publish(new OrderCreatedEvent(order));
        return order.getId();
    }
}

// 读端（Query）
@Service
public class OrderQueryService {

    @Autowired
    private ElasticsearchOperations esOps; // Elasticsearch

    public Page<OrderView> searchOrders(OrderSearchQuery query) {
        // 从 ES 查询，支持复杂搜索/聚合
        NativeQuery searchQuery = NativeQuery.builder()
            .withQuery(q -> q.bool(b -> {
                if (query.getUserId() != null)
                    b.filter(f -> f.term(t -> t.field("userId").value(query.getUserId())));
                if (query.getStatus() != null)
                    b.filter(f -> f.term(t -> t.field("status").value(query.getStatus())));
                return b;
            }))
            .withSort(Sort.by(Sort.Direction.DESC, "createdAt"))
            .withPageable(query.getPageable())
            .build();

        return esOps.search(searchQuery, OrderView.class);
    }
}

// 事件消费者（同步数据到读库）
@Component
public class OrderEventConsumer {

    @KafkaListener(topics = "order-events")
    public void onOrderEvent(OrderEvent event) {
        OrderView view = convertToView(event);
        esOps.save(view); // 写入 ES
    }
}
```

### 4.3 CQRS 适用场景

| 适用 | 不适用 |
|------|--------|
| 读写比例差异大（读多写少） | 简单 CRUD |
| 读写性能要求差异大 | 数据量小 |
| 查询模型复杂（搜索/聚合） | 强一致性要求 |
| 读写模型差异大 | 团队经验不足 |

---

## 五、冷热数据分离

### 5.1 分离策略

```
热数据（最近 3 个月）    → SSD + MySQL（高性能）
温数据（3-12 个月）      → HDD + MySQL / TiDB（容量优先）
冷数据（> 12 个月）      → 对象存储 / Hive / ClickHouse（归档查询）
```

### 5.2 归档方案

```sql
-- 方案 1：按时间分区（推荐）
CREATE TABLE orders (
    id BIGINT,
    user_id BIGINT,
    created_at DATETIME,
    -- ...
) PARTITION BY RANGE (TO_DAYS(created_at)) (
    PARTITION p202401 VALUES LESS THAN (TO_DAYS('2024-02-01')),
    PARTITION p202402 VALUES LESS THAN (TO_DAYS('2024-03-01')),
    PARTITION p202403 VALUES LESS THAN (TO_DAYS('2024-04-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- 归档旧分区
ALTER TABLE orders DROP PARTITION p202401;
-- 或者交换到归档表
ALTER TABLE orders EXCHANGE PARTITION p202401 WITH TABLE orders_archive;
```

### 5.3 pt-archiver 归档

```bash
# 安装 Percona Toolkit
apt-get install percona-toolkit

# 归档 90 天前的数据到归档表
pt-archiver \
    --source h=master-host,D=order_db,t=orders \
    --dest   h=archive-host,D=archive_db,t=orders_archive \
    --where "created_at < DATE_SUB(NOW(), INTERVAL 90 DAY)" \
    --limit 1000 \           # 每批处理 1000 行
    --sleep 0.5 \            # 每批间隔 0.5 秒（控制对线上影响）
    --progress 10000 \       # 每 10000 行打印进度
    --statistics \           # 完成后打印统计
    --bulk-delete \          # 批量删除（性能更好）
    --txn-size 1000          # 事务大小

# 只删除不归档（清理过期数据）
pt-archiver \
    --source h=master-host,D=order_db,t=orders \
    --where "created_at < DATE_SUB(NOW(), INTERVAL 365 DAY)" \
    --purge \                # 只删除不归档
    --limit 500 \
    --sleep 1
```

### 5.4 双写+切流方案

```java
// 归档过渡期：双写模式
@Service
public class OrderService {

    @Autowired
    private OrderRepository hotRepo;     // 热库
    @Autowired
    private OrderArchiveRepository coldRepo; // 冷库

    public Order getOrder(Long orderId, LocalDate createdAt) {
        if (createdAt.isAfter(hotColdBoundary())) {
            // 热数据查热库
            return hotRepo.findById(orderId);
        } else {
            // 冷数据查冷库
            return coldRepo.findById(orderId);
        }
    }

    private LocalDate hotColdBoundary() {
        return LocalDate.now().minusMonths(3);
    }
}
```

---

## 六、NewSQL 概览

### 6.1 TiDB

```
特点：
- 兼容 MySQL 协议（大部分场景可直接替换）
- 水平扩展（自动分片）
- 强一致（Raft 协议）
- HTAP（同时支持 OLTP + OLAP）

架构：
  TiDB Server（SQL 层，无状态）
      ↓
  PD（调度，元数据管理）
      ↓
  TiKV（分布式 KV 存储，Raft 复制）
  TiFlash（列存副本，分析查询）
```

```sql
-- TiDB 特有优化
-- 1. 使用 AUTO_RANDOM 替代 AUTO_INCREMENT（避免写入热点）
CREATE TABLE orders (
    id BIGINT PRIMARY KEY AUTO_RANDOM,
    user_id BIGINT,
    -- ...
);

-- 2. 使用 TiFlash 加速分析查询
ALTER TABLE orders SET TIFLASH REPLICA 1;
-- 之后分析查询会自动路由到 TiFlash 列存引擎

-- 3. 查看执行计划，确认是否走了 TiFlash
EXPLAIN ANALYZE SELECT user_id, SUM(amount) FROM orders
GROUP BY user_id;
```

### 6.2 NewSQL vs 分库分表

| 维度 | 分库分表 | TiDB | CockroachDB |
|------|----------|------|-------------|
| 兼容性 | 需改造 | MySQL 兼容 | PostgreSQL 兼容 |
| 运维复杂度 | 高（多个 MySQL） | 中 | 中 |
| 扩容 | 需数据迁移 | 自动 | 自动 |
| 事务 | 跨库困难 | 分布式事务 | 分布式事务 |
| 性能 | 单分片性能高 | 单机略低于 MySQL | 单机略低于 PostgreSQL |
| 成本 | 低（MySQL 免费） | 高（至少 3 节点） | 高 |
| 适合 | 分片规则简单 | MySQL 生态迁移 | PostgreSQL 生态迁移 |

### 6.3 迁移决策

```
是否需要分布式数据库？
│
├── 数据量 < 1 亿，单机 MySQL 能撑住
│   └── 不需要。做好索引优化 + 读写分离即可
│
├── 数据量 1-10 亿，查询模式简单
│   └── 分库分表（成本低，成熟）
│
├── 数据量 > 10 亿，需要复杂查询
│   └── TiDB / CockroachDB（自动扩展 + 分布式事务）
│
└── 需要 OLTP + OLAP 混合负载
    └── TiDB + TiFlash（HTAP）
```

---

## 七、总结与选型指南

| 问题 | 方案 | 复杂度 | 适用规模 |
|------|------|--------|----------|
| 读性能不足 | 读写分离 | 低 | 中 |
| 写性能不足 | 分库 | 高 | 大 |
| 单表过大 | 分表 | 中 | 中 |
| 查询模型复杂 | CQRS | 高 | 中~大 |
| 数据增长快 | 冷热分离 + 归档 | 中 | 大 |
| 全面瓶颈 | NewSQL | 中 | 大 |

### 实施顺序建议

```
1. 索引优化 + 慢 SQL 治理（零成本）
2. 缓存层（Redis + 本地缓存）
3. 读写分离（中等成本）
4. 冷热数据分离 + 归档
5. 垂直分库（按业务拆分）
6. 水平分表（最后手段）
7. 或直接迁移到 NewSQL
```
