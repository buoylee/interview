# 查询优化与大表策略

## 为什么需要系统化的查询优化

单条 SQL 的优化靠 EXPLAIN 和索引能解决，但生产环境中面对的是：**百万行的大表分页查询、每天千万级的批量写入、主从延迟导致的数据不一致、越来越大的历史数据拖慢全表操作**。这些问题需要从 SQL 改写、批量策略、分页方案、数据架构层面系统化解决。

---

## 一、查询重写技巧

### 子查询改 JOIN

```sql
-- ❌ 关联子查询：外层每一行都要执行一次子查询
SELECT p.id, p.name, p.price
FROM products p
WHERE p.category_id IN (
    SELECT c.id FROM categories c WHERE c.parent_id = 10
);

-- ✅ 改为 JOIN：一次完成关联
SELECT p.id, p.name, p.price
FROM products p
JOIN categories c ON p.category_id = c.id
WHERE c.parent_id = 10;

-- 注意：MySQL 8.0 优化器已经能自动把部分 IN 子查询优化为半连接（semi-join），
-- 但 5.7 以下版本或复杂子查询仍需手动改写。
```

### EXISTS vs IN

```sql
-- 规则：外表小用 IN，外表大用 EXISTS

-- 场景 1：orders 表 100 万行，users 表 1 万行
-- 用 IN（子查询结果集小）
SELECT * FROM orders
WHERE user_id IN (SELECT id FROM users WHERE vip_level >= 3);

-- 场景 2：users 表 1 万行，orders 表 100 万行
-- 用 EXISTS（外表小，每次检查是否存在）
SELECT * FROM users u
WHERE EXISTS (
    SELECT 1 FROM orders o WHERE o.user_id = u.id AND o.total_amount > 1000
);
```

### NOT IN 的陷阱

```sql
-- ❌ NOT IN 遇到 NULL 会返回空结果！
SELECT * FROM products
WHERE category_id NOT IN (SELECT parent_id FROM categories);
-- 如果 categories.parent_id 中有 NULL，整个查询返回空！

-- ✅ 用 NOT EXISTS 替代
SELECT * FROM products p
WHERE NOT EXISTS (
    SELECT 1 FROM categories c WHERE c.parent_id = p.category_id
);

-- ✅ 或者排除 NULL
SELECT * FROM products
WHERE category_id NOT IN (
    SELECT parent_id FROM categories WHERE parent_id IS NOT NULL
);
```

### COUNT 优化

```sql
-- ❌ COUNT(*) 大表全表扫描很慢
SELECT COUNT(*) FROM products WHERE status = 'active';
-- 如果 status 选择性低，即使有索引也要扫描大量数据

-- ✅ 方案 1：用覆盖索引
ALTER TABLE products ADD INDEX idx_status (status);
SELECT COUNT(*) FROM products WHERE status = 'active';
-- InnoDB 会选择最小的索引来统计

-- ✅ 方案 2：维护计数缓存（精确计数场景）
-- 用 Redis 或单独的计数表维护
-- 写入/删除时同步更新

-- ✅ 方案 3：近似计数（不需要精确的场景）
-- MySQL
SELECT TABLE_ROWS FROM information_schema.TABLES
WHERE TABLE_SCHEMA = 'perfshop' AND TABLE_NAME = 'products';
-- 注意：InnoDB 的 TABLE_ROWS 是估算值，误差可能 10-30%

-- PostgreSQL
SELECT reltuples::bigint AS estimated_count
FROM pg_class WHERE relname = 'products';
```

### UNION 优化

```sql
-- ❌ UNION 默认去重（需要排序 + 去重，性能差）
SELECT user_id FROM orders WHERE status = 'paid'
UNION
SELECT user_id FROM orders WHERE total_amount > 1000;

-- ✅ 如果确认没有重复或不需要去重，用 UNION ALL
SELECT user_id FROM orders WHERE status = 'paid'
UNION ALL
SELECT user_id FROM orders WHERE total_amount > 1000;

-- ✅ 能合并的就不用 UNION
SELECT user_id FROM orders
WHERE status = 'paid' OR total_amount > 1000;
```

---

## 二、批量操作

### 批量插入

```sql
-- ❌ 逐条插入（每条一次网络往返 + 一次事务提交）
INSERT INTO order_items (order_id, product_id, quantity) VALUES (1, 100, 2);
INSERT INTO order_items (order_id, product_id, quantity) VALUES (1, 200, 1);
INSERT INTO order_items (order_id, product_id, quantity) VALUES (1, 300, 3);
-- 1000 条 = 1000 次网络往返

-- ✅ 批量插入（一次网络往返）
INSERT INTO order_items (order_id, product_id, quantity) VALUES
    (1, 100, 2),
    (1, 200, 1),
    (1, 300, 3),
    ...;  -- 一次插入多行

-- ⚠️ 注意单次不要太大（MySQL max_allowed_packet 默认 64MB）
-- 建议每批 500-1000 行
```

```java
// Java JDBC 批量插入
String sql = "INSERT INTO order_items (order_id, product_id, quantity) VALUES (?, ?, ?)";
try (PreparedStatement ps = conn.prepareStatement(sql)) {
    for (int i = 0; i < items.size(); i++) {
        ps.setLong(1, items.get(i).getOrderId());
        ps.setLong(2, items.get(i).getProductId());
        ps.setInt(3, items.get(i).getQuantity());
        ps.addBatch();

        if (i % 500 == 0) {  // 每 500 条提交一次
            ps.executeBatch();
            ps.clearBatch();
        }
    }
    ps.executeBatch();  // 处理剩余的
}
```

```yaml
# MyBatis-Plus 批量插入配置
# JDBC URL 加上 rewriteBatchedStatements=true
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/perfshop?rewriteBatchedStatements=true
    # 这个参数让 JDBC 驱动把多条 INSERT 合并成一条 multi-row INSERT
    # 不加这个参数，addBatch() 仍然是逐条发送！
```

### 批量更新

```sql
-- ❌ 逐条更新
UPDATE products SET price = 100 WHERE id = 1;
UPDATE products SET price = 200 WHERE id = 2;
UPDATE products SET price = 300 WHERE id = 3;

-- ✅ 使用 CASE WHEN 批量更新
UPDATE products SET price = CASE id
    WHEN 1 THEN 100
    WHEN 2 THEN 200
    WHEN 3 THEN 300
END
WHERE id IN (1, 2, 3);

-- ✅ 使用临时表 JOIN 更新（大批量）
CREATE TEMPORARY TABLE tmp_price_update (
    product_id BIGINT PRIMARY KEY,
    new_price DECIMAL(10,2)
);

INSERT INTO tmp_price_update VALUES (1, 100), (2, 200), (3, 300), ...;

UPDATE products p
JOIN tmp_price_update t ON p.id = t.product_id
SET p.price = t.new_price;

DROP TEMPORARY TABLE tmp_price_update;
```

### 批量删除

```sql
-- ❌ 一次删除大量数据（锁表时间长、binlog 暴增、主从延迟）
DELETE FROM log_entries WHERE created_at < '2023-01-01';
-- 可能删除几千万行，执行几分钟甚至几小时

-- ✅ 分批删除
DELIMITER //
CREATE PROCEDURE batch_delete_logs()
BEGIN
    DECLARE done INT DEFAULT 0;
    REPEAT
        DELETE FROM log_entries
        WHERE created_at < '2023-01-01'
        ORDER BY id
        LIMIT 5000;                    -- 每次删 5000 行

        SET done = ROW_COUNT() = 0;
        SELECT SLEEP(0.5);             -- 每批间隔 0.5 秒，避免主从延迟
    UNTIL done END REPEAT;
END //
DELIMITER ;

CALL batch_delete_logs();
```

---

## 三、分页优化

### OFFSET 分页的问题

```sql
-- 页面越靠后越慢
SELECT * FROM products ORDER BY id LIMIT 20 OFFSET 0;        -- 快
SELECT * FROM products ORDER BY id LIMIT 20 OFFSET 1000;     -- 还行
SELECT * FROM products ORDER BY id LIMIT 20 OFFSET 100000;   -- 慢！
SELECT * FROM products ORDER BY id LIMIT 20 OFFSET 1000000;  -- 非常慢！

-- OFFSET N 的实际操作：读 N+LIMIT 行，丢弃前 N 行
-- OFFSET 1000000 = 读 1000020 行，只返回 20 行
```

### 方案 1：延迟关联（Deferred Join）

```sql
-- 先通过覆盖索引找到 ID，再回表取数据
SELECT p.*
FROM products p
JOIN (
    SELECT id FROM products
    ORDER BY id
    LIMIT 20 OFFSET 100000
) t ON p.id = t.id;

-- 子查询走覆盖索引（只读 id），扫描快很多
-- 外层只通过主键取 20 行数据
```

### 方案 2：Keyset Pagination（游标分页）

```sql
-- 第 1 页
SELECT id, name, price, created_at
FROM products
WHERE status = 'active'
ORDER BY id
LIMIT 20;
-- 返回 id: 1, 2, ..., 20，记住最后一个 id = 20

-- 第 2 页（基于上一页最后一个 id）
SELECT id, name, price, created_at
FROM products
WHERE status = 'active' AND id > 20
ORDER BY id
LIMIT 20;

-- 第 N 页（不管第几页，性能都一样）
SELECT id, name, price, created_at
FROM products
WHERE status = 'active' AND id > #{lastId}
ORDER BY id
LIMIT 20;
```

**Keyset Pagination 的限制**：
1. 不能直接跳到第 N 页（只能上一页/下一页）
2. 排序字段需要有唯一性（或加辅助字段）
3. 不能统计总页数（总页数要单独查）

```sql
-- 多字段排序的 keyset pagination
-- 按 created_at DESC, id DESC 排序
SELECT id, name, price, created_at
FROM products
WHERE status = 'active'
  AND (created_at, id) < (#{lastCreatedAt}, #{lastId})
ORDER BY created_at DESC, id DESC
LIMIT 20;

-- 或者用 ROW 构造函数（MySQL 8.0+）
SELECT id, name, price, created_at
FROM products
WHERE status = 'active'
  AND ROW(created_at, id) < ROW(#{lastCreatedAt}, #{lastId})
ORDER BY created_at DESC, id DESC
LIMIT 20;
```

### 分页方案对比

| 方案 | 前 N 页性能 | 后 N 页性能 | 支持跳页 | 实现复杂度 |
|------|-----------|-----------|---------|----------|
| OFFSET + LIMIT | 好 | 差 | ✅ | 低 |
| 延迟关联 | 好 | 中等 | ✅ | 中 |
| Keyset Pagination | 好 | 好 | ❌ | 中 |
| Elasticsearch | 好 | 好 | ✅ | 高 |

**生产建议**：B端管理后台可以用 OFFSET（数据量可控）；C端用户列表、商品列表一律用 Keyset Pagination。

---

## 四、大表策略

### 分区表

```sql
-- MySQL RANGE 分区（按时间分区，最常用）
CREATE TABLE orders (
    id BIGINT AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    total_amount DECIMAL(10,2),
    status VARCHAR(20),
    created_at DATETIME NOT NULL,
    PRIMARY KEY (id, created_at),          -- 分区键必须包含在主键中
    INDEX idx_user (user_id, created_at)
) PARTITION BY RANGE (TO_DAYS(created_at)) (
    PARTITION p202301 VALUES LESS THAN (TO_DAYS('2023-02-01')),
    PARTITION p202302 VALUES LESS THAN (TO_DAYS('2023-03-01')),
    PARTITION p202303 VALUES LESS THAN (TO_DAYS('2023-04-01')),
    -- ...
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- 查询时指定分区键，实现分区裁剪
EXPLAIN SELECT * FROM orders
WHERE created_at >= '2023-03-01' AND created_at < '2023-04-01';
-- partitions: p202303  ← 只扫描一个分区

-- 添加新分区
ALTER TABLE orders REORGANIZE PARTITION p_future INTO (
    PARTITION p202304 VALUES LESS THAN (TO_DAYS('2023-05-01')),
    PARTITION p_future VALUES LESS THAN MAXVALUE
);

-- 删除旧分区（比 DELETE 快得多，秒级完成）
ALTER TABLE orders DROP PARTITION p202301;
```

**分区表注意事项**：
- 分区键必须是主键/唯一索引的一部分
- 查询**必须带分区键**，否则全分区扫描
- 单表分区数建议不超过 50-100 个
- 跨分区查询性能可能比不分区更差

### 数据归档

```sql
-- 方案 1：归档到历史表
CREATE TABLE orders_archive LIKE orders;

-- 分批归档
INSERT INTO orders_archive
SELECT * FROM orders
WHERE created_at < '2023-01-01'
ORDER BY id
LIMIT 10000;

DELETE FROM orders
WHERE id IN (
    SELECT id FROM orders_archive
    WHERE created_at < '2023-01-01'
    ORDER BY id
    LIMIT 10000
);

-- 方案 2：使用 pt-archiver（Percona 工具，生产推荐）
pt-archiver \
  --source h=127.0.0.1,D=perfshop,t=orders \
  --dest h=127.0.0.1,D=perfshop_archive,t=orders \
  --where "created_at < '2023-01-01'" \
  --limit 1000 \
  --commit-each \
  --sleep 0.5 \
  --progress 10000 \
  --statistics
```

### 冷热分离

```
架构示意：

用户请求 → 应用层路由
  ├─ 近期数据（热数据，近 3 个月）→ MySQL SSD 存储
  ├─ 历史数据（温数据，3-12 个月）→ MySQL HDD 存储 / TiDB
  └─ 归档数据（冷数据，> 12 个月）→ ClickHouse / S3 + Athena

路由策略示例（Java）：
```

```java
@Service
public class OrderQueryService {

    @Autowired
    private OrderMapper hotOrderMapper;        // 热数据 MySQL

    @Autowired
    private OrderArchiveMapper archiveMapper;  // 温数据

    public Order findOrder(Long orderId, LocalDateTime createdAt) {
        if (createdAt.isAfter(LocalDateTime.now().minusMonths(3))) {
            return hotOrderMapper.findById(orderId);     // 热库
        } else if (createdAt.isAfter(LocalDateTime.now().minusYears(1))) {
            return archiveMapper.findById(orderId);      // 归档库
        } else {
            return coldStorageClient.findById(orderId);  // 冷存储
        }
    }
}
```

---

## 五、读写分离排查

### 主从延迟检测

```sql
-- MySQL：查看从库延迟
SHOW SLAVE STATUS\G
-- Seconds_Behind_Master: 5   ← 延迟 5 秒

-- 更精确的方式（使用 pt-heartbeat）
-- 主库写入心跳
pt-heartbeat --update --database perfshop --create-table --daemonize

-- 从库检查延迟
pt-heartbeat --monitor --database perfshop --master-server-id=1
-- 0.05s [  0.02s,  0.03s,  0.05s ]
-- 实际延迟 0.05 秒

-- PostgreSQL：查看复制延迟
SELECT
    client_addr,
    state,
    sent_lsn,
    write_lsn,
    flush_lsn,
    replay_lsn,
    pg_wal_lsn_diff(sent_lsn, replay_lsn) AS replay_lag_bytes,
    write_lag,
    flush_lag,
    replay_lag
FROM pg_stat_replication;
```

### 读写路由策略

```java
// Spring + AbstractRoutingDataSource 实现读写分离
public class DynamicDataSource extends AbstractRoutingDataSource {
    @Override
    protected Object determineCurrentLookupKey() {
        return DynamicDataSourceContext.getDataSourceKey();
    }
}

// 通过注解标记读写
@Target(ElementType.METHOD)
@Retention(RetentionPolicy.RUNTIME)
public @interface ReadOnly {
}

// AOP 切面路由
@Aspect
@Component
public class DataSourceAspect {
    @Before("@annotation(readOnly)")
    public void setReadDataSource(ReadOnly readOnly) {
        DynamicDataSourceContext.setDataSourceKey("slave");
    }

    @After("@annotation(readOnly)")
    public void restoreDataSource() {
        DynamicDataSourceContext.clear();
    }
}

// 使用
@Service
public class ProductService {

    @ReadOnly
    public List<Product> listProducts(int page) {
        // 自动路由到从库
        return productMapper.selectPage(page);
    }

    @Transactional
    public void createProduct(Product product) {
        // 自动路由到主库
        productMapper.insert(product);
    }
}
```

### 读写分离常见问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| 写后读不到 | 主从延迟 | 写后短时间内强制读主库 |
| 事务中读从库 | 路由逻辑在事务内切换 | 事务中统一走主库 |
| 从库数据不一致 | 半同步复制未开启 | 开启半同步复制 |
| 从库查询慢 | 从库资源不足或回放慢 | 增加从库配置、延迟监控 |

```java
// 写后读主库策略
@Service
public class OrderService {

    @Transactional
    public Order createAndQuery(OrderCreateDTO dto) {
        // 写操作 → 主库
        orderMapper.insert(dto);
        Long orderId = dto.getId();

        // 写后立即读 → 强制主库（不走从库）
        DynamicDataSourceContext.forceMaster();
        try {
            return orderMapper.findById(orderId);
        } finally {
            DynamicDataSourceContext.clear();
        }
    }
}
```

---

## 六、常见 SQL 反模式

### 反模式 1：SELECT *

```sql
-- ❌ SELECT * 返回所有列
SELECT * FROM products WHERE category_id = 5;
-- 问题：1. 多传输不需要的数据  2. 无法使用覆盖索引  3. 表结构变更时行为不确定

-- ✅ 只查需要的列
SELECT id, name, price, main_image FROM products WHERE category_id = 5;
```

### 反模式 2：在循环中查询（N+1 问题）

```java
// ❌ N+1 查询
List<Order> orders = orderMapper.selectByUserId(userId);  // 1 次
for (Order order : orders) {
    List<OrderItem> items = itemMapper.selectByOrderId(order.getId());  // N 次
    order.setItems(items);
}

// ✅ 批量查询
List<Order> orders = orderMapper.selectByUserId(userId);
List<Long> orderIds = orders.stream().map(Order::getId).collect(toList());
Map<Long, List<OrderItem>> itemMap = itemMapper.selectByOrderIds(orderIds)
    .stream().collect(groupingBy(OrderItem::getOrderId));
orders.forEach(o -> o.setItems(itemMap.getOrDefault(o.getId(), emptyList())));
```

### 反模式 3：隐式大事务

```java
// ❌ 整个方法在一个大事务中
@Transactional
public void processOrders() {
    List<Order> orders = orderMapper.selectUnprocessed();     // 可能很多
    for (Order order : orders) {
        calculateDiscount(order);         // 业务逻辑
        callPaymentService(order);        // RPC 调用！事务中做 RPC 是大忌
        orderMapper.updateStatus(order);
        notifyUser(order);                // 发通知也在事务中...
    }
}  // 事务可能持续几分钟

// ✅ 缩小事务范围
public void processOrders() {
    List<Order> orders = orderMapper.selectUnprocessed();
    for (Order order : orders) {
        calculateDiscount(order);
        callPaymentService(order);        // 事务外做 RPC
        updateOrderInTransaction(order);  // 只有数据库操作在事务中
        notifyUser(order);                // 事务外发通知
    }
}

@Transactional
public void updateOrderInTransaction(Order order) {
    orderMapper.updateStatus(order);
}
```

### 反模式 4：过度依赖 ORDER BY RAND()

```sql
-- ❌ 随机排序全表
SELECT * FROM products ORDER BY RAND() LIMIT 10;
-- 全表扫描 + 排序，100 万行可能需要几秒

-- ✅ 先获取随机 ID，再查询
SELECT * FROM products
WHERE id >= (SELECT FLOOR(RAND() * (SELECT MAX(id) FROM products)))
ORDER BY id
LIMIT 10;
-- 注意：如果 id 不连续，结果可能有偏差
```

### 反模式 5：在 WHERE 中使用 OR 连接不同表字段

```sql
-- ❌
SELECT * FROM products
WHERE name LIKE '%手机%' OR description LIKE '%手机%';
-- 两个 LIKE 都无法使用索引，全表扫描

-- ✅ 用全文索引
ALTER TABLE products ADD FULLTEXT INDEX ft_search (name, description) WITH PARSER ngram;
SELECT * FROM products
WHERE MATCH(name, description) AGAINST('手机' IN BOOLEAN MODE);

-- ✅ 或者用 Elasticsearch 做搜索
```

---

## 七、查询优化速查表

| 问题 | 诊断方法 | 优化手段 |
|------|---------|---------|
| 全表扫描 | EXPLAIN type=ALL | 添加合适的索引 |
| filesort | EXPLAIN Extra=Using filesort | ORDER BY 走索引 |
| 临时表 | EXPLAIN Extra=Using temporary | 优化 GROUP BY |
| 子查询慢 | EXPLAIN 看 DEPENDENT SUBQUERY | 改写为 JOIN |
| 分页慢 | OFFSET 值很大 | Keyset Pagination |
| 批量操作慢 | 逐条提交 | 批量 INSERT/UPDATE |
| COUNT 慢 | 大表全量 COUNT | 计数缓存/近似值 |
| N+1 查询 | 循环中执行 SQL | 批量查询 + 内存关联 |
| 大事务 | 事务持续时间长 | 缩小事务范围 |
| 主从延迟 | `Seconds_Behind_Master` > 0 | 优化大事务、升级从库 |
