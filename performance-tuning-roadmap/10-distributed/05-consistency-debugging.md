# 一致性排查

## 为什么一致性问题是分布式系统最难排查的问题

在单体应用中，一个数据库事务保证 ACID，数据一致性是理所当然的。但在微服务架构中，**数据散落在多个服务的多个数据库中，没有全局事务**。你会遇到：订单创建成功但库存没扣、支付成功但订单状态没更新、消息丢了导致数据永远不一致。这些问题往往不会立刻暴露，而是在几小时甚至几天后才被发现——排查时现场早已被覆盖。

---

## 一、数据一致性问题分类

### 三种一致性模型

| 模型 | 定义 | 实现方式 | 典型场景 |
|------|------|---------|---------|
| 强一致性 | 写入后立即可读到最新值 | 分布式事务（2PC/3PC） | 银行转账 |
| 最终一致性 | 一段时间后数据达到一致 | 消息队列 + 补偿 | 电商下单 |
| 因果一致性 | 有因果关系的操作保证顺序 | 版本向量/逻辑时钟 | 社交评论 |

### 常见的一致性问题

```
场景 1：订单-库存不一致
  订单服务：订单已创建 ✓
  库存服务：库存未扣减 ✗
  原因：库存扣减的消息丢了 / 消费失败

场景 2：支付-订单状态不一致
  支付服务：支付成功 ✓
  订单服务：状态仍为"待支付" ✗
  原因：支付回调超时 / 订单服务重启丢了回调

场景 3：缓存-数据库不一致
  数据库：价格已改为 99 元
  Redis 缓存：价格仍为 199 元
  原因：缓存更新失败 / 更新顺序错误

场景 4：主从数据库不一致
  主库：数据已写入
  从库：数据还没同步过来
  原因：主从延迟 + 读写分离
```

---

## 二、最终一致性调试技巧

### 如何验证"最终"是否达到

**问题本质**：最终一致性承诺"最终"会一致，但没说多久。你需要回答两个问题：
1. 现在是否已经一致？
2. 如果不一致，是"还没到"还是"永远不会到了"？

```python
# 一致性检查脚本
import pymysql
import redis
from datetime import datetime, timedelta

class ConsistencyChecker:
    def __init__(self, order_db, inventory_db, redis_client):
        self.order_db = order_db
        self.inventory_db = inventory_db
        self.redis = redis_client

    def check_order_inventory_consistency(self, time_range_minutes: int = 60):
        """检查最近 N 分钟内的订单与库存是否一致"""
        cutoff = datetime.now() - timedelta(minutes=time_range_minutes)

        # 查询已支付的订单
        orders = self.order_db.execute("""
            SELECT order_id, product_id, quantity, created_at
            FROM orders
            WHERE status = 'PAID' AND created_at > %s
        """, (cutoff,))

        inconsistencies = []
        for order in orders:
            # 检查库存扣减记录
            deduction = self.inventory_db.execute("""
                SELECT id FROM inventory_deductions
                WHERE order_id = %s
            """, (order["order_id"],))

            if not deduction:
                age = (datetime.now() - order["created_at"]).total_seconds()
                inconsistencies.append({
                    "order_id": order["order_id"],
                    "product_id": order["product_id"],
                    "quantity": order["quantity"],
                    "age_seconds": age,
                    "status": "POSSIBLY_LOST" if age > 300 else "PENDING",
                })

        return inconsistencies

    def report(self, inconsistencies: list):
        for item in inconsistencies:
            if item["status"] == "POSSIBLY_LOST":
                print(f"[ALERT] 订单 {item['order_id']} 库存未扣减，"
                      f"已过 {item['age_seconds']:.0f}s，可能消息丢失")
            else:
                print(f"[WARN]  订单 {item['order_id']} 库存未扣减，"
                      f"已过 {item['age_seconds']:.0f}s，可能在途中")
```

### 一致性对账系统

```
定期对账流程：

T+0:   业务操作（下单、支付等）
T+5m:  准实时对账（消息处理延迟 < 5 分钟的应该已完成）
T+1h:  小时级对账（发现延迟较大的不一致）
T+24h: 日终对账（最终确认所有不一致并修复）

┌──────────┐     ┌──────────┐     ┌──────────┐
│ 订单数据  │────▶│  对账引擎 │◀────│ 库存数据  │
└──────────┘     └────┬─────┘     └──────────┘
                      │
           ┌──────────┴──────────┐
           │                     │
     ┌─────▼─────┐       ┌──────▼──────┐
     │  差异报告   │       │  自动补偿    │
     └───────────┘       └─────────────┘
```

```sql
-- 对账 SQL 示例：找出订单已支付但库存未扣减的记录
SELECT o.order_id, o.product_id, o.quantity, o.created_at
FROM orders o
LEFT JOIN inventory_deductions d ON o.order_id = d.order_id
WHERE o.status = 'PAID'
  AND o.created_at > NOW() - INTERVAL 24 HOUR
  AND d.id IS NULL
ORDER BY o.created_at;

-- 反向对账：库存已扣减但订单不存在（更严重）
SELECT d.order_id, d.product_id, d.quantity, d.created_at
FROM inventory_deductions d
LEFT JOIN orders o ON d.order_id = o.order_id
WHERE d.created_at > NOW() - INTERVAL 24 HOUR
  AND o.order_id IS NULL;
```

---

## 三、消息丢失排查

### MQ 消息丢失的三个环节

```
生产者 ──────────▶ Broker ──────────▶ 消费者
    │                  │                  │
    ▼                  ▼                  ▼
  生产丢失          存储丢失          消费丢失
  (发送失败/       (Broker 宕机/     (消费失败/
   未持久化)        数据丢失)          未确认)
```

### 排查清单

#### 环节 1：生产者端

```java
// Kafka 生产者防丢消息配置
Properties props = new Properties();

// 必须等待所有副本确认
props.put("acks", "all");                      // 不要用 "0" 或 "1"

// 发送失败时重试
props.put("retries", 3);
props.put("retry.backoff.ms", 1000);

// 幂等生产者（防止重试导致重复）
props.put("enable.idempotence", true);

// 同步发送确认
producer.send(record, (metadata, exception) -> {
    if (exception != null) {
        // 发送失败！必须处理
        log.error("Message send failed", exception);
        // 方案 1：重试
        // 方案 2：写入本地失败队列
        failedMessageStore.save(record);
    } else {
        log.debug("Message sent to partition {} offset {}",
            metadata.partition(), metadata.offset());
    }
});
```

```java
// RabbitMQ 生产者防丢消息
// 开启 Publisher Confirm
channel.confirmSelect();
channel.addConfirmListener(new ConfirmListener() {
    @Override
    public void handleAck(long deliveryTag, boolean multiple) {
        // Broker 已确认收到
    }

    @Override
    public void handleNack(long deliveryTag, boolean multiple) {
        // Broker 拒绝了消息，需要重发
        log.error("Message nacked: {}", deliveryTag);
        retryMessage(deliveryTag);
    }
});
```

#### 环节 2：Broker 端

```bash
# Kafka Broker 防丢消息配置
# server.properties

# 最小同步副本数（配合 acks=all）
min.insync.replicas=2

# 不允许非同步副本成为 Leader
unclean.leader.election.enable=false

# 日志刷盘策略
log.flush.interval.messages=1      # 每条消息刷盘（性能差但安全）
# 或者
log.flush.interval.ms=1000         # 每秒刷盘（性能与安全的折中）

# 检查副本同步状态
kafka-topics.sh --describe --topic order-events --bootstrap-server localhost:9092
# 关注 ISR（In-Sync Replicas）是否等于 Replicas
# Topic: order-events  Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1,2,3  ← 正常
# Topic: order-events  Partition: 0  Leader: 1  Replicas: 1,2,3  Isr: 1      ← 危险！
```

#### 环节 3：消费者端

```java
// Kafka 消费者防丢消息
Properties props = new Properties();

// 关闭自动提交
props.put("enable.auto.commit", false);

// 手动提交 offset
while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));

    for (ConsumerRecord<String, String> record : records) {
        try {
            // 先处理业务
            processMessage(record);

            // 处理成功后再提交 offset
            consumer.commitSync(Collections.singletonMap(
                new TopicPartition(record.topic(), record.partition()),
                new OffsetAndMetadata(record.offset() + 1)
            ));
        } catch (Exception e) {
            log.error("Message processing failed", e);
            // 不提交 offset，重启后会重新消费
            // 但要注意幂等处理（见下文）
            handleFailedMessage(record);
        }
    }
}
```

### 消息追踪排查

```bash
# Kafka：查看消费进度
kafka-consumer-groups.sh --describe --group order-consumer \
  --bootstrap-server localhost:9092

# 输出：
# GROUP           TOPIC           PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG
# order-consumer  order-events    0          12345           12350           5
# order-consumer  order-events    1          23456           23456           0
#
# LAG > 0 说明有消息积压
# CURRENT-OFFSET 长时间不变说明消费者可能挂了

# 查看特定 offset 的消息内容
kafka-console-consumer.sh --topic order-events \
  --bootstrap-server localhost:9092 \
  --partition 0 --offset 12345 --max-messages 1
```

---

## 四、消息乱序排查

### 分区内有序 vs 全局无序

```
Kafka 的顺序保证：
- 单分区内：严格有序 ✓
- 跨分区间：无顺序保证 ✗

示例：用户连续操作 创建订单 → 支付 → 发货

正确（相同 Key 发到同一分区）：
  Partition 0: [创建订单] → [支付] → [发货]    ← 顺序正确

错误（不同 Key 或没设 Key，分散到不同分区）：
  Partition 0: [创建订单]        [发货]
  Partition 1:        [支付]
  消费者可能先处理 [发货] 再处理 [支付] → 状态错乱
```

### 保证顺序的方案

```java
// 方案 1：使用业务 Key 保证同一实体的消息在同一分区
ProducerRecord<String, String> record = new ProducerRecord<>(
    "order-events",
    order.getId(),        // Key = orderId → 同一订单的消息发到同一分区
    serialize(event)
);
producer.send(record);

// 方案 2：消费端通过版本号处理乱序
@KafkaListener(topics = "order-events")
public void consume(OrderEvent event) {
    // 乐观锁：只接受版本号更大的事件
    int updated = jdbcTemplate.update(
        "UPDATE orders SET status = ?, version = ? " +
        "WHERE order_id = ? AND version < ?",
        event.getStatus(), event.getVersion(),
        event.getOrderId(), event.getVersion()
    );

    if (updated == 0) {
        log.info("Skipping stale event: orderId={}, version={}",
            event.getOrderId(), event.getVersion());
    }
}

// 方案 3：状态机保证合法转换
public boolean isValidTransition(OrderStatus current, OrderStatus target) {
    Map<OrderStatus, Set<OrderStatus>> validTransitions = Map.of(
        OrderStatus.CREATED, Set.of(OrderStatus.PAID, OrderStatus.CANCELLED),
        OrderStatus.PAID, Set.of(OrderStatus.SHIPPED, OrderStatus.REFUNDING),
        OrderStatus.SHIPPED, Set.of(OrderStatus.DELIVERED, OrderStatus.REFUNDING),
        OrderStatus.DELIVERED, Set.of(OrderStatus.COMPLETED, OrderStatus.REFUNDING)
    );

    return validTransitions.getOrDefault(current, Set.of()).contains(target);
}
```

---

## 五、幂等消费实现

### 为什么消费必须幂等

```
消息可能被重复消费的场景：
1. 消费者处理成功但提交 offset 前崩溃 → 重启后重新消费
2. 消费者组 rebalance → 部分消息被重新分配
3. 生产者重试 → 同一条消息被发送两次（即使开了幂等生产者，跨会话仍可能重复）
```

### 方案 1：去重表

```java
@Transactional
public void processOrderEvent(OrderEvent event) {
    String messageId = event.getMessageId();

    // 插入去重表（唯一索引保证幂等）
    try {
        jdbcTemplate.update(
            "INSERT INTO consumed_messages (message_id, topic, created_at) VALUES (?, ?, NOW())",
            messageId, "order-events"
        );
    } catch (DuplicateKeyException e) {
        log.info("Duplicate message, skipping: {}", messageId);
        return;  // 已处理过，跳过
    }

    // 执行业务逻辑（与去重记录在同一个事务中）
    orderService.updateStatus(event.getOrderId(), event.getStatus());
}
```

```sql
-- 去重表结构
CREATE TABLE consumed_messages (
    message_id VARCHAR(64) PRIMARY KEY,
    topic      VARCHAR(128) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB;

-- 定期清理（保留 7 天）
DELETE FROM consumed_messages WHERE created_at < NOW() - INTERVAL 7 DAY;
```

### 方案 2：版本号 / 乐观锁

```go
// 使用版本号实现幂等更新
func (s *OrderService) UpdateStatus(ctx context.Context, event *OrderEvent) error {
    result, err := s.db.ExecContext(ctx,
        `UPDATE orders
         SET status = ?, version = ?, updated_at = NOW()
         WHERE order_id = ? AND version = ?`,
        event.NewStatus, event.Version, event.OrderID, event.Version-1,
    )
    if err != nil {
        return fmt.Errorf("update failed: %w", err)
    }

    rows, _ := result.RowsAffected()
    if rows == 0 {
        // 版本不匹配，说明已经处理过或有更新的事件
        log.Info("skipping stale or duplicate event",
            zap.String("order_id", event.OrderID),
            zap.Int("version", event.Version))
        return nil  // 不报错，幂等处理
    }

    return nil
}
```

### 方案 3：状态机

```java
// 状态机天然具有幂等性：相同的状态转换只会执行一次
public class OrderStateMachine {

    private static final Map<OrderStatus, Map<OrderEvent, OrderStatus>> TRANSITIONS = Map.of(
        OrderStatus.CREATED, Map.of(
            OrderEvent.PAY_SUCCESS, OrderStatus.PAID,
            OrderEvent.CANCEL, OrderStatus.CANCELLED
        ),
        OrderStatus.PAID, Map.of(
            OrderEvent.SHIP, OrderStatus.SHIPPED
        ),
        OrderStatus.SHIPPED, Map.of(
            OrderEvent.DELIVER, OrderStatus.DELIVERED
        )
    );

    @Transactional
    public boolean transition(String orderId, OrderEvent event) {
        Order order = orderRepository.findByIdForUpdate(orderId);  // SELECT ... FOR UPDATE

        Map<OrderEvent, OrderStatus> validEvents = TRANSITIONS.get(order.getStatus());
        if (validEvents == null || !validEvents.containsKey(event)) {
            log.info("Invalid or duplicate transition: order={}, current={}, event={}",
                orderId, order.getStatus(), event);
            return false;  // 无效转换 → 幂等
        }

        OrderStatus newStatus = validEvents.get(event);
        order.setStatus(newStatus);
        order.setVersion(order.getVersion() + 1);
        orderRepository.save(order);

        log.info("Order state transition: {} → {} (event={})",
            order.getStatus(), newStatus, event);
        return true;
    }
}
```

---

## 六、分布式事务排查

### TCC 补偿失败排查

```
TCC（Try-Confirm-Cancel）流程：

Try:     预留资源（冻结库存、冻结余额）
Confirm: 确认执行（扣减库存、扣减余额）
Cancel:  取消预留（解冻库存、解冻余额）

问题场景：Try 成功，Confirm 部分失败，需要 Cancel 回滚
但如果 Cancel 也失败了怎么办？
```

```java
// TCC 补偿排查与恢复
public class TccRecoveryJob {

    // 定时任务：扫描需要恢复的事务
    @Scheduled(fixedRate = 60000)  // 每分钟执行
    public void recover() {
        // 查找超时未完成的事务（Try 后超过 5 分钟没有 Confirm/Cancel）
        List<TccTransaction> pendingTxns = txnRepository.findPending(
            Duration.ofMinutes(5)
        );

        for (TccTransaction txn : pendingTxns) {
            log.warn("Recovering TCC transaction: {}, status: {}",
                txn.getId(), txn.getStatus());

            if (txn.getRetryCount() > MAX_RETRY) {
                // 超过最大重试次数，需要人工介入
                log.error("TCC recovery failed after {} retries: {}",
                    MAX_RETRY, txn.getId());
                alertService.sendAlert("TCC 事务恢复失败，需人工介入: " + txn.getId());
                txn.setStatus(TccStatus.MANUAL_REQUIRED);
                txnRepository.save(txn);
                continue;
            }

            try {
                if (txn.getStatus() == TccStatus.TRYING) {
                    // Try 阶段超时 → Cancel 回滚
                    cancelAll(txn);
                } else if (txn.getStatus() == TccStatus.CONFIRMING) {
                    // Confirm 阶段失败 → 重试 Confirm（因为 Try 已成功，不能 Cancel）
                    confirmAll(txn);
                } else if (txn.getStatus() == TccStatus.CANCELLING) {
                    // Cancel 阶段失败 → 重试 Cancel
                    cancelAll(txn);
                }
            } catch (Exception e) {
                txn.setRetryCount(txn.getRetryCount() + 1);
                txnRepository.save(txn);
                log.error("TCC recovery attempt failed", e);
            }
        }
    }
}
```

### Saga 回滚异常排查

```
Saga 编排模式下的回滚：

正向操作：创建订单 → 扣库存 → 扣余额 → 发货
补偿操作：取消发货 ← 退余额 ← 恢复库存 ← 取消订单

问题：扣余额失败，需要回滚，但恢复库存的补偿也失败了
```

```python
# Saga 编排器（带补偿重试和日志）
class SagaOrchestrator:
    def __init__(self):
        self.steps: list[SagaStep] = []
        self.completed_steps: list[SagaStep] = []

    def add_step(self, name: str, execute_fn, compensate_fn):
        self.steps.append(SagaStep(name, execute_fn, compensate_fn))

    def run(self, context: dict) -> dict:
        for step in self.steps:
            try:
                logging.info(f"Saga step '{step.name}' executing")
                result = step.execute(context)
                context.update(result or {})
                self.completed_steps.append(step)
                logging.info(f"Saga step '{step.name}' completed")
            except Exception as e:
                logging.error(f"Saga step '{step.name}' failed: {e}")
                self._compensate(context)
                raise SagaRollbackError(f"Saga failed at step '{step.name}'", e)

        return context

    def _compensate(self, context: dict):
        """按逆序执行补偿操作"""
        for step in reversed(self.completed_steps):
            for attempt in range(3):  # 最多重试 3 次
                try:
                    logging.info(f"Compensating step '{step.name}' (attempt {attempt + 1})")
                    step.compensate(context)
                    logging.info(f"Compensation for '{step.name}' succeeded")
                    break
                except Exception as e:
                    logging.error(f"Compensation for '{step.name}' failed (attempt {attempt + 1}): {e}")
                    if attempt == 2:
                        # 补偿也失败了，记录到死信表
                        logging.critical(
                            f"Compensation PERMANENTLY FAILED for '{step.name}', "
                            f"manual intervention required"
                        )
                        self._save_to_dead_letter(step, context, e)

    def _save_to_dead_letter(self, step, context, error):
        """写入死信表，等待人工处理"""
        # INSERT INTO saga_dead_letters (saga_id, step_name, context, error, ...)
        pass

# 使用
saga = SagaOrchestrator()
saga.add_step("create_order", create_order, cancel_order)
saga.add_step("deduct_inventory", deduct_inventory, restore_inventory)
saga.add_step("deduct_balance", deduct_balance, refund_balance)
saga.add_step("ship", ship_order, cancel_shipment)

try:
    result = saga.run({"user_id": "u123", "product_id": "p456", "quantity": 1})
except SagaRollbackError as e:
    logging.error(f"Order creation saga failed and rolled back: {e}")
```

---

## 七、缓存与数据库一致性排查

### 常见的不一致模式

```
模式 1：先更新数据库，再删缓存（Cache-Aside）

时序问题：
T1: 线程 A 更新 DB: price = 99
T2: 线程 A 删除缓存 ✓
T3: 线程 B 读缓存 Miss
T4: 线程 B 读 DB: price = 99
T5: 线程 C 更新 DB: price = 199
T6: 线程 C 删除缓存 ✓
T7: 线程 B 把旧值写入缓存: price = 99  ← 不一致！

这个时序虽然概率很低，但在高并发下会发生。
```

### 延迟双删方案

```java
// 延迟双删
public void updatePrice(String productId, BigDecimal newPrice) {
    // 1. 先删缓存
    redis.delete("price:" + productId);

    // 2. 更新数据库
    productRepository.updatePrice(productId, newPrice);

    // 3. 延迟再删一次缓存（覆盖并发读写导致的脏数据）
    scheduledExecutor.schedule(() -> {
        redis.delete("price:" + productId);
        log.info("Delayed cache delete for product: {}", productId);
    }, 1, TimeUnit.SECONDS);  // 延迟 1 秒（大于一次读 DB + 写缓存的时间）
}
```

### Binlog 订阅方案（更可靠）

```
数据库 → Binlog → Canal/Debezium → 消息队列 → 缓存更新服务

优点：
- 数据库是唯一的数据源
- 缓存更新与业务逻辑解耦
- 不会遗漏（只要 Binlog 不丢）

缺点：
- 有延迟（通常 < 1s）
- 额外的组件维护成本
```

```yaml
# Debezium MySQL Connector 配置
{
    "name": "mysql-connector",
    "config": {
        "connector.class": "io.debezium.connector.mysql.MySqlConnector",
        "database.hostname": "mysql-primary",
        "database.port": "3306",
        "database.user": "debezium",
        "database.password": "dbz_password",
        "database.server.id": "184054",
        "database.include.list": "shop",
        "table.include.list": "shop.products,shop.inventory",
        "topic.prefix": "dbchanges",
        "schema.history.internal.kafka.bootstrap.servers": "kafka:9092",
        "schema.history.internal.kafka.topic": "schema-changes"
    }
}
```

```java
// 消费 Binlog 变更事件更新缓存
@KafkaListener(topics = "dbchanges.shop.products")
public void onProductChange(ConsumerRecord<String, String> record) {
    DebeziumEvent event = parseEvent(record.value());

    String productId = event.getAfter().get("id").toString();

    switch (event.getOp()) {
        case "c":  // CREATE
        case "u":  // UPDATE
            // 更新缓存
            Product product = buildProduct(event.getAfter());
            redis.set("product:" + productId, serialize(product), Duration.ofHours(1));
            log.info("Cache updated for product: {}", productId);
            break;

        case "d":  // DELETE
            redis.delete("product:" + productId);
            log.info("Cache deleted for product: {}", productId);
            break;
    }
}
```

### 缓存一致性排查清单

| 检查项 | 方法 | 判断标准 |
|-------|------|---------|
| 缓存与 DB 值是否一致 | 对比查询 | 核心字段值相同 |
| 缓存更新策略是什么 | 代码审查 | Cache-Aside / Write-Through / Binlog |
| 是否有并发写入问题 | 检查时序日志 | 更新和删除的时序是否正确 |
| 缓存 TTL 是否合理 | 检查配置 | 根据数据变更频率设置 |
| Binlog 消费是否有延迟 | 监控 consumer lag | Lag 应 < 1s |
| 是否有缓存穿透 | 检查 DB 访问量 | 不存在的 Key 不应打到 DB |
| 是否有缓存雪崩 | 检查 TTL 分布 | TTL 应加随机偏移 |

---

## 八、总结：一致性排查决策树

```
发现数据不一致
  │
  ├─ 是缓存不一致吗？
  │   ├─ 是 → 检查缓存更新策略、TTL、Binlog 延迟
  │   └─ 否 ↓
  │
  ├─ 是主从不一致吗？
  │   ├─ 是 → 检查主从延迟、是否读了从库
  │   └─ 否 ↓
  │
  ├─ 是跨服务不一致吗？
  │   ├─ 是 → 消息丢了？消息乱序了？消费失败了？
  │   │   ├─ 检查生产者：acks 配置、发送回调
  │   │   ├─ 检查 Broker：ISR、副本数、消费 Lag
  │   │   ├─ 检查消费者：offset 提交、幂等处理
  │   │   └─ 运行对账脚本确认范围
  │   └─ 否 ↓
  │
  └─ 是分布式事务不一致吗？
      ├─ TCC → 检查恢复任务日志、死信表
      ├─ Saga → 检查补偿操作日志、死信表
      └─ 两阶段提交 → 检查 TM 日志、参与者状态
```

| 问题类型 | 排查工具 | 修复手段 |
|---------|---------|---------|
| 消息丢失 | consumer lag、offset 检查 | 重发消息 / 对账补偿 |
| 消息乱序 | 检查 partition key | 版本号 / 状态机 |
| 重复消费 | 去重表 / 业务日志 | 确认幂等逻辑 |
| TCC 悬挂 | 恢复任务日志 | 手动 Cancel / Confirm |
| Saga 补偿失败 | 死信表 | 人工介入修数据 |
| 缓存脏数据 | 对比缓存与 DB | 删缓存 / Binlog 重放 |
