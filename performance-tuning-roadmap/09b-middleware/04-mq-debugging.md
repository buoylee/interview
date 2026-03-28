# MQ 排查案例集

## 为什么需要 MQ 排查能力

MQ 问题的排查难度在于**链路长、现象与根因不一致**。消费积压不一定是 Consumer 慢，可能是分区倾斜；消息丢失不一定是 Broker 问题，可能是 Producer 的 acks 配置不当；频繁 Rebalance 不一定是网络抖动，可能是 Consumer 处理超时。本文以 Kafka 为主，整理生产环境最常见的 MQ 故障排查案例和方法论。

---

## 一、Consumer Lag 排查

Consumer Lag（消费延迟）是 MQ 监控的核心指标，表示 Consumer 当前消费位置与 Producer 最新写入位置之间的差距。

### 1.1 查看 Consumer Lag

```bash
# 方法 1：kafka-consumer-groups.sh（最常用）
kafka-consumer-groups.sh \
    --bootstrap-server kafka1:9092 \
    --describe \
    --group order-service

# 输出示例：
# GROUP          TOPIC       PARTITION  CURRENT-OFFSET  LOG-END-OFFSET  LAG     CONSUMER-ID                                    HOST            CLIENT-ID
# order-service  orders      0          12345678        12345700        22      order-svc-1-abc123                              /10.0.1.51      order-svc-1
# order-service  orders      1          23456789        23456900        111     order-svc-2-def456                              /10.0.1.52      order-svc-2
# order-service  orders      2          34567890        34568500        610     order-svc-3-ghi789                              /10.0.1.53      order-svc-3
# order-service  orders      3          45678901        45680200        1299    -                                               -               -
#                                                                       ^^^^
# 分区 3 的 Lag 最大且没有 Consumer，说明该分区没有被消费

# 方法 2：查看所有 Consumer Group
kafka-consumer-groups.sh \
    --bootstrap-server kafka1:9092 \
    --list

# 方法 3：查看 Consumer Group 状态
kafka-consumer-groups.sh \
    --bootstrap-server kafka1:9092 \
    --describe \
    --group order-service \
    --state

# 输出：
# GROUP           COORDINATOR (ID)    ASSIGNMENT-STRATEGY    STATE           #MEMBERS
# order-service   kafka2:9092 (2)     range                  Stable          3
```

### 1.2 Lag 监控方案

```bash
# 方案 1：Burrow（LinkedIn 开源的 Kafka 消费延迟监控）
# 不仅看 Lag 绝对值，还判断 Lag 趋势（是否在增长）
# 状态分为：OK, WARNING, ERROR, STOP

# 部署 Burrow
docker run -d --name burrow \
    -v /etc/burrow:/etc/burrow \
    -p 8000:8000 \
    linkedin/burrow

# 查询 API
curl http://localhost:8000/v3/kafka/local/consumer/order-service/lag
# {
#   "status": "WARNING",
#   "partitions": [
#     {"topic": "orders", "partition": 0, "status": "OK", "lag": 22},
#     {"topic": "orders", "partition": 2, "status": "WARNING", "lag": 610},
#     {"topic": "orders", "partition": 3, "status": "ERROR", "lag": 1299}
#   ]
# }

# 方案 2：Kafka Exporter + Prometheus + Grafana（推荐）
# kafka_consumergroup_lag{consumergroup="order-service",topic="orders",partition="0"}
# 详见第七节监控指标体系
```

### 1.3 Lag 告警阈值设置

| Lag 级别 | 条件 | 响应 |
|---------|------|------|
| 正常 | Lag < 1000 且趋势稳定 | 不告警 |
| 警告 | Lag > 1000 且持续增长 5 分钟 | Slack 通知 |
| 严重 | Lag > 10000 或增速 > 1000/min | 电话告警 |
| 紧急 | Consumer 全部离线（Lag 只增不减） | 立即处理 |

---

## 二、消息积压处理策略

当 Consumer Lag 持续增长到无法自然消化时，需要紧急处理。

### 2.1 原因分析

```
消息积压常见原因：
├── Consumer 端
│   ├── Consumer 实例宕机/减少
│   ├── 单条消息处理时间增加（下游服务变慢/数据库慢查询）
│   ├── 消费线程被阻塞（死锁/GC STW）
│   └── Rebalance 导致消费暂停
├── Producer 端
│   ├── 流量突增（如秒杀、大促）
│   └── 上游系统批量灌数据
└── Broker 端
    ├── 分区数不足
    ├── Broker 磁盘 I/O 瓶颈
    └── 分区 Leader 切换
```

### 2.2 处理策略

```bash
# 策略 1：增加 Consumer 实例（最常用）
# 前提：Consumer 实例数 < 分区数
# 如果已经等于分区数，需要先扩分区

# 查看当前分区数
kafka-topics.sh --bootstrap-server kafka1:9092 --describe --topic orders
# Topic: orders   PartitionCount: 6   ReplicationFactor: 3

# 扩分区（不可逆操作，慎重！）
kafka-topics.sh --bootstrap-server kafka1:9092 \
    --alter --topic orders --partitions 12

# 然后增加 Consumer 实例至 12 个

# 策略 2：临时消费者快速消费
# 启动一组临时 Consumer，只做转发不做业务处理
# 将消息转发到一个分区数更多的临时 Topic
# 然后用更多的 Consumer 并行处理临时 Topic

# 策略 3：跳过策略（数据可丢弃时）
# 将 Consumer 的 offset 直接跳到最新位置
kafka-consumer-groups.sh \
    --bootstrap-server kafka1:9092 \
    --group order-service \
    --topic orders \
    --reset-offsets \
    --to-latest \
    --execute

# 注意：跳过的消息将永远不会被消费！
# 仅适用于日志、监控等可丢弃的数据

# 策略 4：按时间重置偏移量（跳过部分消息）
kafka-consumer-groups.sh \
    --bootstrap-server kafka1:9092 \
    --group order-service \
    --topic orders \
    --reset-offsets \
    --to-datetime "2024-03-15T10:00:00.000" \
    --execute
```

### 2.3 积压处理决策树

```
消息积压
│
├─ 是否可以丢弃？
│  ├─ 是 → 重置 offset 到最新位置
│  └─ 否 ↓
│
├─ Consumer 数 < 分区数？
│  ├─ 是 → 增加 Consumer 实例
│  └─ 否 ↓
│
├─ 是否可以扩分区？
│  ├─ 是 → 扩分区 + 增加 Consumer
│  └─ 否 ↓
│
├─ 单条处理能加速吗？
│  ├─ 是 → 优化处理逻辑/修复下游瓶颈
│  └─ 否 ↓
│
└─ 启动临时消费者组，并行转储后处理
```

---

## 三、分区倾斜（Skew）排查与解决

分区倾斜指消息在分区间分布不均匀，导致某些分区的 Consumer 负载远高于其他分区。

### 3.1 识别分区倾斜

```bash
# 查看各分区的消息数量
kafka-run-class.sh kafka.tools.GetOffsetShell \
    --broker-list kafka1:9092 \
    --topic orders \
    --time -1    # -1 表示最新 offset

# 输出示例：
# orders:0:12345700
# orders:1:23456900
# orders:2:34568500      ← 明显偏多
# orders:3:8901200
# orders:4:9012300
# orders:5:9123400

# 计算偏差
# 平均值：(12345700+23456900+34568500+8901200+9012300+9123400)/6 ≈ 16235000
# 分区 2 的消息量是平均值的 2.13 倍 → 存在倾斜
```

### 3.2 倾斜原因

| 原因 | 说明 | 表现 |
|------|------|------|
| Key 分布不均 | 某些 Key 的消息量远超其他 Key | 特定分区 Lag 大 |
| 自定义分区器缺陷 | 分区算法不均匀 | 固定几个分区偏多 |
| 分区扩容后的残留 | 扩容前的数据集中在旧分区 | 旧分区消息多 |
| 热点用户/商品 | 大商家、热门商品 | 包含热点 Key 的分区偏多 |

### 3.3 解决方案

```java
// 方案 1：在 Key 中增加随机后缀打散
String key = orderId;  // 原始 Key
// 改为：
String key = orderId + "_" + (System.nanoTime() % 8);
// 同一个 orderId 会被分散到 8 个不同的分区

// 注意：这样会破坏同一 orderId 的消息有序性
// 如果需要有序，用下面的方案

// 方案 2：按二级维度分区
// 原始：按 merchantId 分区 → 大商家的消息集中
// 改为：按 merchantId + orderId.hashCode() % N 分区
public int partition(String topic, Object key, ...) {
    MerchantOrder order = parseKey(key);
    int subPartition = Math.abs(order.getOrderId().hashCode()) % SUB_PARTITION_COUNT;
    int base = Math.abs(order.getMerchantId().hashCode()) % mainPartitions;
    return (base * SUB_PARTITION_COUNT + subPartition) % totalPartitions;
}

// 方案 3：特殊处理热点 Key
// 识别出热点 Key 后，单独路由到专用分区或 Topic
if (isHotKey(key)) {
    // 发送到专用 Topic，用独立的 Consumer Group 处理
    producer.send(new ProducerRecord<>("orders-hot", key, value));
} else {
    producer.send(new ProducerRecord<>("orders", key, value));
}
```

---

## 四、Rebalance 风暴

Rebalance 是 Kafka Consumer Group 重新分配分区的过程。频繁的 Rebalance 会导致 Consumer **在 Rebalance 期间停止消费**，严重影响吞吐量。

### 4.1 Rebalance 触发条件

```
触发 Rebalance 的情况：
1. Consumer 加入或离开 Group
2. Consumer 心跳超时（session.timeout.ms）
3. Consumer 处理超时（max.poll.interval.ms）
4. Topic 分区数变化
5. Consumer 订阅的 Topic 变化（正则匹配新 Topic）
```

### 4.2 Rebalance 风暴排查

```bash
# 现象：Consumer 日志中频繁出现
# "Attempt to heartbeat failed since group is rebalancing"
# "Revoke previously assigned partitions"
# "Successfully joined group with generation X"

# 排查步骤：

# 1. 查看 Consumer Group 状态
kafka-consumer-groups.sh --bootstrap-server kafka1:9092 \
    --describe --group order-service --state
# 如果 STATE 频繁在 PreparingRebalance/CompletingRebalance 之间切换
# 说明正在发生 Rebalance 风暴

# 2. 查看 Consumer 成员变化
kafka-consumer-groups.sh --bootstrap-server kafka1:9092 \
    --describe --group order-service --members
# 观察 CONSUMER-ID 和 HOST 是否频繁变化

# 3. 检查 Consumer 日志中的原因
# "Member xxx sending LeaveGroup request due to consumer poll timeout"
# → max.poll.interval.ms 太小或单批处理太慢

# "Member xxx has failed heartbeat"
# → session.timeout.ms 太小或 GC STW 导致心跳延迟
```

### 4.3 解决 Rebalance 风暴

```properties
# 方案 1：调大超时参数
session.timeout.ms=45000              # 默认 45s，之前版本默认 10s
heartbeat.interval.ms=3000            # 心跳间隔 < session.timeout / 3
max.poll.interval.ms=600000           # 10 分钟（如果处理逻辑复杂）
max.poll.records=100                  # 减少单次 poll 的消息数

# 方案 2：使用 CooperativeStickyAssignor（Kafka 2.4+，关键优化）
partition.assignment.strategy=org.apache.kafka.clients.consumer.CooperativeStickyAssignor
```

### 4.4 CooperativeStickyAssignor 详解

```
传统 Eager Rebalance（RangeAssignor/RoundRobinAssignor）：
  1. 所有 Consumer 撤销全部分区
  2. 重新分配全部分区
  3. 在此期间 Consumer 完全停止消费
  → "Stop-the-World" 效果

CooperativeStickyAssignor（增量式 Rebalance）：
  1. 只撤销需要移动的分区
  2. 其他分区继续消费
  3. 分两轮完成：
     第一轮：确定哪些分区需要移动，撤销这些分区
     第二轮：将撤销的分区分配给新 Consumer
  → 影响最小化

示例：6 个分区，3 个 Consumer，新加入第 4 个 Consumer

Eager Rebalance：
  撤销全部 6 个分区 → 重新分配 → 所有 Consumer 停止消费数秒

Cooperative Rebalance：
  只撤销 1-2 个分区 → 将这些分区分配给新 Consumer
  其他 4-5 个分区不受影响，持续消费
```

```java
// 配置 CooperativeStickyAssignor
Properties props = new Properties();
props.put(ConsumerConfig.PARTITION_ASSIGNMENT_STRATEGY_CONFIG,
    CooperativeStickyAssignor.class.getName());

// 注意：从 Eager 迁移到 Cooperative 需要"滚动升级"
// 不能直接切换，否则会导致异常
// 步骤：
// 1. 先配置两种策略（兼容模式）
//    partition.assignment.strategy=
//      org.apache.kafka.clients.consumer.CooperativeStickyAssignor,
//      org.apache.kafka.clients.consumer.RangeAssignor
// 2. 滚动重启所有 Consumer
// 3. 移除 RangeAssignor，只保留 CooperativeStickyAssignor
// 4. 再次滚动重启
```

---

## 五、消息丢失排查

消息丢失可能发生在 Producer、Broker、Consumer 三个环节中的任何一个。

### 5.1 各环节丢失原因

```
Producer 丢失：
├── acks=0：消息发出就不管了
├── acks=1 + Leader 宕机：Leader 确认后、Follower 同步前宕机
├── buffer.memory 满：send() 抛异常但没有处理
├── 网络异常：消息发送失败但没有重试
└── 回调中没有检查异常

Broker 丢失：
├── min.insync.replicas=1 + Broker 磁盘故障
├── unclean.leader.election.enable=true：落后的副本被选为 Leader
├── 日志截断（Log Truncation）：新 Leader 的数据比旧 Leader 少
└── 磁盘写入缓存未刷盘时断电

Consumer 丢失：
├── 自动提交 offset + 处理失败：offset 已提交但消息没有成功处理
├── 消费线程异常未捕获：消息被跳过
└── Rebalance 时的消息丢失：上一个 Consumer 未提交 offset
```

### 5.2 防丢失配置

```properties
# === Producer 端 ===
acks=all                            # 所有 ISR 副本确认
retries=2147483647                  # 无限重试（配合 delivery.timeout.ms 使用）
delivery.timeout.ms=120000          # 总发送超时 2 分钟
enable.idempotence=true             # 幂等性，避免重试导致重复

# === Broker 端 ===
min.insync.replicas=2               # 至少 2 个副本同步
unclean.leader.election.enable=false # 禁止非 ISR 副本成为 Leader
default.replication.factor=3         # 默认 3 副本

# === Consumer 端 ===
enable.auto.commit=false            # 关闭自动提交
# 在业务处理成功后手动提交
```

```java
// Producer 正确的错误处理
producer.send(new ProducerRecord<>(topic, key, value), (metadata, exception) -> {
    if (exception != null) {
        // 必须处理发送失败
        log.error("消息发送失败: topic={}, key={}", topic, key, exception);
        // 重试或写入本地死信表
        deadLetterDao.save(topic, key, value, exception.getMessage());
    } else {
        log.debug("消息发送成功: topic={}, partition={}, offset={}",
            metadata.topic(), metadata.partition(), metadata.offset());
    }
});

// Consumer 正确的提交方式
try {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, String> record : records) {
        processRecord(record);  // 业务处理
    }
    consumer.commitSync();  // 处理成功后才提交
} catch (Exception e) {
    log.error("消费失败，不提交 offset，下次会重新消费", e);
    // 不调用 commitSync()，下次 poll() 会重新获取这批消息
}
```

### 5.3 消息丢失排查流程

```
怀疑消息丢失？
│
├─ 1. 确认是否真的丢失
│   ├─ Producer 是否有发送成功的日志/回调？
│   ├─ Broker 上该 Topic 的消息总数是否正确？
│   └─ Consumer 的 offset 是否有跳跃？
│
├─ 2. 定位丢失环节
│   ├─ Producer → Broker：检查 acks 配置和回调异常
│   ├─ Broker 存储：检查 ISR 变化和 Leader 切换
│   └─ Broker → Consumer：检查 offset 提交方式
│
└─ 3. 验证与修复
    ├─ 从 Broker 上读取原始消息确认
    │   kafka-console-consumer.sh --from-beginning
    ├─ 检查 Consumer Group 的 offset 变化
    └─ 修复配置并部署
```

---

## 六、消息乱序与幂等消费

### 6.1 消息乱序的原因

```
Kafka 保证分区内有序，但以下场景会破坏有序性：

1. 重试导致乱序
   Producer 发送 msg1, msg2
   msg1 发送失败并重试
   msg2 先到达 Broker
   结果：msg2 在 msg1 之前
   → 解决：enable.idempotence=true 或 max.in.flight.requests.per.connection=1

2. 分区变更导致乱序
   扩分区后，相同 Key 可能路由到不同分区
   不同分区的消息无法保证全局顺序
   → 解决：需要全局有序时，使用单分区（牺牲吞吐量）

3. Consumer 多线程处理
   Consumer 将消息分发到线程池
   线程执行顺序无法保证
   → 解决：相同 Key 的消息路由到同一线程
```

### 6.2 保证分区内有序的配置

```properties
# Producer 端
enable.idempotence=true
max.in.flight.requests.per.connection=5   # 幂等开启时 <=5 即可保证顺序
acks=all

# Consumer 端
# 单线程顺序处理（最安全，吞吐最低）
# 或按 Key 分线程处理（折衷方案）
```

```java
// 按 Key 分线程的有序消费
int THREAD_COUNT = 8;
ExecutorService[] executors = new ExecutorService[THREAD_COUNT];
for (int i = 0; i < THREAD_COUNT; i++) {
    executors[i] = Executors.newSingleThreadExecutor();
}

for (ConsumerRecord<String, String> record : records) {
    // 相同 Key 路由到相同线程，保证 Key 级别有序
    int threadIndex = Math.abs(record.key().hashCode()) % THREAD_COUNT;
    executors[threadIndex].submit(() -> process(record));
}
```

### 6.3 幂等消费

```
即使配置了 exactly-once，Consumer 端仍需要幂等处理：
- Rebalance 后可能重新消费已处理的消息
- Consumer 提交 offset 前宕机，重启后重新消费

幂等消费的实现方式：
1. 数据库唯一约束（最简单）
2. Redis 去重（高性能）
3. 业务状态机（最可靠）
```

```java
// 方式 1：数据库唯一约束
// 消息 ID 作为唯一键，重复消费时 INSERT 会报唯一约束冲突
try {
    orderDao.insert(order);  // 唯一键：order_id
    consumer.commitSync();
} catch (DuplicateKeyException e) {
    log.warn("订单已处理，跳过: {}", order.getOrderId());
    consumer.commitSync();  // 重复消息也要提交 offset
}

// 方式 2：Redis 去重
String deduplicationKey = "consumed:" + record.topic() + ":" + record.partition()
    + ":" + record.offset();
Boolean isNew = redisTemplate.opsForValue()
    .setIfAbsent(deduplicationKey, "1", Duration.ofHours(24));
if (Boolean.TRUE.equals(isNew)) {
    processRecord(record);  // 首次消费，处理业务
} else {
    log.warn("消息已消费，跳过: {}", deduplicationKey);
}
consumer.commitSync();

// 方式 3：业务状态机
// 订单状态：CREATED → PAID → SHIPPED → DELIVERED
// 只在合法状态转换时处理，否则忽略
OrderStatus currentStatus = orderDao.getStatus(orderId);
if (currentStatus == OrderStatus.CREATED && event.getType() == EventType.PAYMENT) {
    orderDao.updateStatus(orderId, OrderStatus.PAID);
} else {
    log.warn("非法状态转换，忽略: current={}, event={}", currentStatus, event.getType());
}
```

---

## 七、监控指标体系

### 7.1 Kafka Exporter + Prometheus + Grafana

```yaml
# docker-compose.yml - Kafka Exporter 部署
version: '3'
services:
  kafka-exporter:
    image: danielqsj/kafka-exporter:latest
    command:
      - '--kafka.server=kafka1:9092'
      - '--kafka.server=kafka2:9092'
      - '--kafka.server=kafka3:9092'
    ports:
      - "9308:9308"

# Prometheus 配置
# prometheus.yml
scrape_configs:
  - job_name: 'kafka-exporter'
    static_configs:
      - targets: ['kafka-exporter:9308']
    scrape_interval: 15s
```

### 7.2 核心监控指标

| 指标名 | 含义 | 告警阈值 |
|-------|------|---------|
| `kafka_consumergroup_lag` | Consumer Lag | > 10000 |
| `kafka_consumergroup_lag_sum` | Group 总 Lag | > 50000 |
| `kafka_topic_partition_current_offset` | 分区当前 offset | 增速异常时告警 |
| `kafka_brokers` | Broker 数量 | != 期望值 |
| `kafka_topic_partitions` | Topic 分区数 | 变化时告警 |
| `kafka_topic_partition_replicas` | 副本数 | != 期望值 |
| `kafka_topic_partition_in_sync_replica` | ISR 副本数 | < min.insync.replicas |
| `kafka_topic_partition_under_replicated_partition` | 副本不足的分区 | > 0 |

### 7.3 JMX 指标（Broker 内部指标）

```bash
# Kafka Broker 暴露 JMX 指标，需要开启 JMX
# kafka-server-start.sh 中设置
export JMX_PORT=9999
export KAFKA_JMX_OPTS="-Djava.rmi.server.hostname=10.0.1.60 -Dcom.sun.management.jmxremote.port=9999 -Dcom.sun.management.jmxremote.authenticate=false -Dcom.sun.management.jmxremote.ssl=false"
```

| JMX 指标 | Bean 路径 | 说明 |
|---------|----------|------|
| MessagesInPerSec | `kafka.server:type=BrokerTopicMetrics,name=MessagesInPerSec` | 入站消息速率 |
| BytesInPerSec | `kafka.server:type=BrokerTopicMetrics,name=BytesInPerSec` | 入站字节速率 |
| BytesOutPerSec | `kafka.server:type=BrokerTopicMetrics,name=BytesOutPerSec` | 出站字节速率 |
| RequestsPerSec | `kafka.network:type=RequestMetrics,name=RequestsPerSec,request=Produce` | Produce 请求速率 |
| TotalTimeMs | `kafka.network:type=RequestMetrics,name=TotalTimeMs,request=Produce` | Produce 请求总耗时 |
| UnderReplicatedPartitions | `kafka.server:type=ReplicaManager,name=UnderReplicatedPartitions` | 副本不足的分区数 |
| ISRShrinkRate | `kafka.server:type=ReplicaManager,name=IsrShrinksPerSec` | ISR 收缩速率 |
| ActiveControllerCount | `kafka.controller:type=KafkaController,name=ActiveControllerCount` | 活跃 Controller 数量（应为 1） |

### 7.4 Grafana Dashboard 推荐

```
推荐 Dashboard ID（从 Grafana.com 导入）：
- Kafka Exporter Overview: #7589
- Kafka Cluster: #12460
- Kafka Consumer Lag: #12124

核心面板：
1. Consumer Lag 趋势图（按 consumergroup + topic + partition）
2. Broker 消息流入/流出速率
3. ISR 副本状态
4. 分区 Leader 分布
5. 各 Topic 的消息积压量
6. Broker 磁盘使用率
```

---

## 八、排查 Checklist

| 问题 | 排查命令/方法 | 关键指标 |
|------|-------------|---------|
| 消费积压 | `kafka-consumer-groups.sh --describe` | LAG 列 |
| 分区倾斜 | `GetOffsetShell` 比较各分区 offset | 最大/最小比值 > 2 |
| Rebalance | Consumer 日志搜索 "rebalance" | Rebalance 频率 |
| 消息丢失 | 对比 Producer 发送量 vs Consumer 消费量 | 差值 > 0 |
| Broker 异常 | `kafka_brokers` 指标 | 数量变化 |
| ISR 异常 | `UnderReplicatedPartitions` | > 0 |
| 磁盘瓶颈 | `iostat -x 1` 看 Kafka 数据盘 | await > 10ms |
| 网络瓶颈 | `sar -n DEV 1` 看网卡流量 | 接近网卡带宽上限 |

### 快速诊断命令集

```bash
# 一键采集 Kafka 集群状态
echo "=== Broker List ===" && \
kafka-broker-api-versions.sh --bootstrap-server kafka1:9092 2>&1 | grep -c "ApiVersion" && \
echo "=== Topic List ===" && \
kafka-topics.sh --bootstrap-server kafka1:9092 --list && \
echo "=== Consumer Groups ===" && \
kafka-consumer-groups.sh --bootstrap-server kafka1:9092 --list && \
echo "=== Group Details ===" && \
kafka-consumer-groups.sh --bootstrap-server kafka1:9092 \
    --describe --all-groups 2>/dev/null && \
echo "=== Under-Replicated Partitions ===" && \
kafka-topics.sh --bootstrap-server kafka1:9092 \
    --describe --under-replicated-partitions
```
