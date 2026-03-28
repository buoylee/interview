# MQ 性能调优（Kafka 为主，RabbitMQ 对比）

## 为什么需要关注 MQ 性能

消息队列是分布式系统的"血管"——订单、支付、物流、通知都靠它流转。**MQ 的吞吐量决定了系统的上限，MQ 的延迟决定了用户的体验。**当 Kafka 的 Producer 因为 `buffer.memory` 不够而阻塞、Consumer 因为 `max.poll.records` 过小而处理不过来时，整个业务流水线都会堵塞。理解 MQ 的性能模型和调优参数，是高并发系统架构师的必备技能。

---

## 一、Kafka 性能模型

Kafka 之所以能达到百万级 TPS，核心依赖三个设计。

### 1.1 顺序写磁盘

```
传统数据库写入：随机写磁盘
┌────────────────────────────────┐
│  磁头在盘面上反复寻道           │
│  IOPS 受限（HDD ~200, SSD ~10K）│
│  延迟高：ms 级                  │
└────────────────────────────────┘

Kafka 写入：顺序追加写
┌────────────────────────────────┐
│  数据始终追加到文件末尾          │
│  吞吐取决于磁盘带宽（GB/s 级）  │
│  延迟低：us 级                  │
│  HDD 顺序写 ≈ 600MB/s          │
│  SSD 顺序写 ≈ 2-3GB/s          │
└────────────────────────────────┘

# Kafka 日志文件结构
/kafka-logs/orders-topic-0/
├── 00000000000000000000.log       # Segment 文件（默认 1GB）
├── 00000000000000000000.index     # 偏移量索引
├── 00000000000000000000.timeindex # 时间索引
├── 00000000001073741824.log       # 下一个 Segment
└── ...
```

### 1.2 零拷贝（Zero Copy）

```
传统数据传输（4 次拷贝 + 4 次上下文切换）：
  磁盘 → 内核缓冲区 → 用户空间 → Socket 缓冲区 → 网卡

Kafka 零拷贝（sendfile，2 次拷贝 + 2 次上下文切换）：
  磁盘 → 内核缓冲区 → 网卡（DMA 直接传输）
  跳过了用户空间，CPU 不参与数据搬运

# Linux sendfile 系统调用
# Kafka 通过 Java 的 FileChannel.transferTo() 实现
# Consumer 拉取消息时自动使用零拷贝
```

### 1.3 批量发送与压缩

```
单条发送：
  [msg1] → 网络 → Broker
  [msg2] → 网络 → Broker
  [msg3] → 网络 → Broker
  开销：3 次网络 I/O + 3 次磁盘写入

批量发送：
  [msg1, msg2, msg3] → 网络 → Broker
  开销：1 次网络 I/O + 1 次磁盘写入
  + 压缩后网络传输量大幅减少
```

---

## 二、Producer 调优

### 2.1 核心参数详解

```properties
# ========================
# Kafka Producer 核心配置
# ========================

# --- 批量发送 ---
batch.size=65536
# 默认 16384 (16KB)。单个分区的批次大小上限。
# 增大 → 吞吐量提升（更多消息合并发送）
# 推荐：32KB~256KB，视消息大小而定
# 如果消息本身很大（>10KB），可以设为 256KB~1MB

linger.ms=10
# 默认 0（立即发送）。等待凑批的最大时间。
# 设为 0 时 batch.size 几乎不生效（一有消息就发）
# 推荐：5~100ms，根据业务对延迟的容忍度
# 注意：linger.ms 和 batch.size 谁先到就触发发送

# --- 可靠性 ---
acks=1
# acks=0：不等待确认 → 最快，可能丢消息
# acks=1：Leader 确认 → 折衷（推荐大多数场景）
# acks=all/-1：所有 ISR 副本确认 → 最可靠，延迟最高
# 生产推荐：acks=all + min.insync.replicas=2

# --- 压缩 ---
compression.type=lz4
# none：不压缩
# gzip：压缩率最高，CPU 开销大
# snappy：折衷，压缩率和速度都不错
# lz4：速度最快，推荐
# zstd：压缩率接近 gzip，速度接近 lz4（Kafka 2.1+）

# --- 缓冲区 ---
buffer.memory=67108864
# 默认 33554432 (32MB)。Producer 总缓冲区大小。
# 当缓冲区满时，send() 会阻塞最多 max.block.ms（默认 60s）
# 推荐：64MB~256MB

max.block.ms=5000
# 缓冲区满时的最大阻塞时间，超时抛出 TimeoutException
# 推荐：5000ms（快速失败，让上层处理）

# --- 请求控制 ---
max.in.flight.requests.per.connection=5
# 单个连接上允许的未确认请求数
# =1 时保证消息顺序（但吞吐量降低）
# >1 时在 retries>0 且幂等未开启时可能乱序
# 推荐：5（默认值） + 开启幂等

enable.idempotence=true
# 开启幂等性，保证 exactly-once 语义（单分区内）
# 要求：acks=all, retries>0, max.in.flight.requests.per.connection<=5
```

### 2.2 不同场景的推荐配置

| 场景 | batch.size | linger.ms | acks | compression | 预期吞吐 |
|------|-----------|-----------|------|-------------|---------|
| 日志采集 | 256KB | 50ms | 1 | lz4 | 高吞吐，允许少量丢失 |
| 订单/支付 | 32KB | 5ms | all | lz4 | 中吞吐，不能丢 |
| 实时监控 | 16KB | 0ms | 1 | snappy | 低延迟 |
| 大数据管道 | 512KB | 100ms | 1 | zstd | 最大吞吐 |

### 2.3 Producer 常见瓶颈

```
# 瓶颈 1：缓冲区满（BufferExhaustedException）
# 现象：send() 阻塞，最终超时
# 原因：Producer 发送速度 > Broker 消费速度
# 解决：
#   - 增大 buffer.memory
#   - 开启压缩减少网络传输量
#   - 增加分区数提升并行度

# 瓶颈 2：批次太小，网络 I/O 成为瓶颈
# 现象：CPU 使用率低，但吞吐上不去
# 原因：linger.ms=0，消息逐条发送
# 解决：增大 linger.ms 和 batch.size

# 瓶颈 3：acks=all 延迟高
# 现象：P99 延迟 > 100ms
# 原因：需要等待所有 ISR 副本确认
# 解决：
#   - 确保 ISR 副本数合理（不要太多）
#   - Broker 端优化磁盘 I/O
#   - 如果业务允许，降级为 acks=1
```

---

## 三、Consumer 调优

### 3.1 核心参数详解

```properties
# ========================
# Kafka Consumer 核心配置
# ========================

# --- 拉取控制 ---
fetch.min.bytes=1
# 默认 1。Broker 返回数据的最小字节数。
# 增大 → 减少请求次数，但增加延迟
# 推荐：1024~65536（大数据处理场景可更大）

fetch.max.bytes=52428800
# 默认 50MB。单次 fetch 的最大字节数

fetch.max.wait.ms=500
# 默认 500ms。Broker 等待凑够 fetch.min.bytes 的最大时间

max.poll.records=500
# 默认 500。单次 poll() 返回的最大消息数
# 推荐：根据单条消息处理时间调整
# 如果处理一条消息需要 10ms，500 条需要 5 秒
# 必须保证在 max.poll.interval.ms 内处理完

max.poll.interval.ms=300000
# 默认 5 分钟。两次 poll() 之间的最大间隔
# 超过此时间，Consumer 被认为已死，触发 Rebalance
# 推荐：max.poll.records * 单条处理时间 * 安全系数(2~3)

# --- 会话管理 ---
session.timeout.ms=45000
# 默认 45s (Kafka 3.0+)。心跳超时时间。
# 超过此时间没有心跳，Consumer 被踢出组
# 推荐：10000~45000

heartbeat.interval.ms=3000
# 默认 3s。心跳发送间隔。
# 必须 < session.timeout.ms / 3

# --- 偏移量管理 ---
enable.auto.commit=false
# 默认 true。是否自动提交偏移量。
# 生产推荐：false（手动提交，避免消息丢失）

auto.commit.interval.ms=5000
# 自动提交间隔（仅 enable.auto.commit=true 时生效）

auto.offset.reset=latest
# 无初始偏移量时的行为
# earliest：从头开始消费
# latest：从最新位置开始消费
```

### 3.2 Consumer 处理模型优化

```java
// 模式 1：同步处理（简单但吞吐低）
while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    for (ConsumerRecord<String, String> record : records) {
        process(record);  // 同步处理，阻塞
    }
    consumer.commitSync();
}

// 模式 2：批量处理 + 异步提交（推荐）
while (true) {
    ConsumerRecords<String, String> records = consumer.poll(Duration.ofMillis(100));
    if (!records.isEmpty()) {
        List<Future<?>> futures = new ArrayList<>();
        for (ConsumerRecord<String, String> record : records) {
            futures.add(executor.submit(() -> process(record)));
        }
        // 等待所有任务完成
        for (Future<?> f : futures) { f.get(); }
        consumer.commitSync();
    }
}

// 模式 3：按分区独立线程（最佳吞吐）
// 每个分区一个处理线程，避免跨分区的处理竞争
Map<TopicPartition, List<ConsumerRecord<String, String>>> partitionRecords
    = records.partitions().stream()
    .collect(Collectors.toMap(
        tp -> tp,
        tp -> records.records(tp)
    ));

partitionRecords.forEach((partition, partRecords) -> {
    executor.submit(() -> {
        for (ConsumerRecord<String, String> record : partRecords) {
            process(record);
        }
        consumer.commitSync(Collections.singletonMap(
            partition,
            new OffsetAndMetadata(partRecords.get(partRecords.size() - 1).offset() + 1)
        ));
    });
});
```

### 3.3 Consumer 常见瓶颈

```
# 瓶颈 1：处理速度跟不上（Consumer Lag 持续增长）
# 解决：增加 Consumer 实例（不能超过分区数）

# 瓶颈 2：频繁 Rebalance
# 现象：Consumer 反复加入/离开组
# 原因：处理时间超过 max.poll.interval.ms
# 解决：减小 max.poll.records 或增大 max.poll.interval.ms

# 瓶颈 3：fetch 请求频繁但数据量小
# 解决：增大 fetch.min.bytes 和 fetch.max.wait.ms
```

---

## 四、分区策略

### 4.1 分区数选择

```bash
# 分区数的经验公式
# 目标吞吐量 / min(Producer 单分区吞吐, Consumer 单分区吞吐)

# 示例：
# 目标吞吐：100MB/s
# 单个 Producer 写单个分区：约 50MB/s
# 单个 Consumer 读单个分区：约 30MB/s
# 需要分区数 ≥ 100/30 ≈ 4 个（取 Consumer 侧的瓶颈）
# 考虑冗余：建议 6~12 个分区

# 分区数并非越多越好
# 分区过多的副作用：
# 1. 每个分区对应一个日志目录，文件描述符增加
# 2. Leader 选举时间增加（Broker 故障恢复慢）
# 3. Producer 的 buffer.memory 被分摊到更多分区
# 4. End-to-end 延迟增加（Broker 端有更多分区要管理）

# 一般建议：
# - 单 Topic 分区数 6~64
# - 集群总分区数 < 10万（Kafka 3.x KRaft 模式可支持更多）
```

### 4.2 分区器选择

```java
// 默认分区策略（Kafka 2.4+）：
// 1. 有 Key → hash(key) % numPartitions（保证相同 Key 到同一分区）
// 2. 无 Key → Sticky Partitioning（粘性分区，凑满一个 batch 再换分区）

// 自定义分区器（按业务路由）
public class OrderPartitioner implements Partitioner {
    @Override
    public int partition(String topic, Object key, byte[] keyBytes,
                         Object value, byte[] valueBytes, Cluster cluster) {
        int numPartitions = cluster.partitionCountForTopic(topic);
        if (key == null) {
            return ThreadLocalRandom.current().nextInt(numPartitions);
        }
        // 按用户 ID 分区，保证同一用户的消息有序
        String userId = extractUserId(key.toString());
        return Math.abs(userId.hashCode()) % numPartitions;
    }
}

// 配置
props.put(ProducerConfig.PARTITIONER_CLASS_CONFIG, OrderPartitioner.class.getName());
```

### 4.3 分区扩容注意事项

```bash
# 增加分区（只能增不能减）
kafka-topics.sh --bootstrap-server localhost:9092 \
    --alter --topic orders --partitions 12

# 注意：
# 1. 已有数据不会重新分配到新分区
# 2. 依赖 Key 分区的场景，扩容后相同 Key 可能路由到不同分区
#    → 导致消费者侧的"有序性"被破坏
# 3. Consumer Group 会触发 Rebalance
# 4. 建议在流量低谷期操作
```

---

## 五、RabbitMQ 性能对比

### 5.1 架构差异

| 维度 | Kafka | RabbitMQ |
|------|-------|----------|
| 消息模型 | Pull（Consumer 主动拉取） | Push（Broker 推送） |
| 存储方式 | 磁盘顺序写（日志） | 内存 + 磁盘（队列） |
| 吞吐量 | 百万级 TPS | 万级 TPS |
| 延迟 | ms 级（批量化导致） | us 级（单条推送） |
| 消息回溯 | 支持（按 offset/时间回溯） | 不支持（消费即删除） |
| 消费模式 | Consumer Group | 多种（direct/fanout/topic） |
| 消息路由 | 基于 Topic + Partition | 基于 Exchange + Binding |
| 协议 | 自定义二进制协议 | AMQP 标准协议 |

### 5.2 选型决策

```
选 Kafka 的场景：
  ✓ 高吞吐日志/事件流（>10 万 TPS）
  ✓ 需要消息回溯和重放
  ✓ 大数据管道（对接 Flink/Spark）
  ✓ Event Sourcing 架构
  ✓ 多消费者组独立消费同一份数据

选 RabbitMQ 的场景：
  ✓ 复杂路由需求（Exchange 多种类型）
  ✓ 需要消息确认和死信队列的可靠传递
  ✓ 低延迟（us 级）的消息推送
  ✓ 消息量不大（<1 万 TPS）的业务系统
  ✓ 需要优先级队列
  ✓ 需要延迟消息（RabbitMQ 原生支持插件）

两者都不是银弹：
  - Kafka 不适合做"任务队列"（没有消息级别的 ACK）
  - RabbitMQ 不适合做"事件溯源"（消费后消息被删除）
```

### 5.3 RabbitMQ 关键调优参数

```bash
# RabbitMQ 性能瓶颈通常在：
# 1. 队列深度（消息积压在内存中）
# 2. 消息持久化（磁盘 I/O）
# 3. 消费者 prefetch

# Prefetch（QoS）调优
# channel.basicQos(prefetchCount)
# 控制 Broker 一次推送给 Consumer 的最大未确认消息数

# prefetch=1：低吞吐，但保证公平分发
# prefetch=10~50：推荐，平衡吞吐与公平
# prefetch=0/无限：最高吞吐，但可能导致某些 Consumer 过载

# 持久化配置
# 队列持久化：durable=true
# 消息持久化：deliveryMode=2
# 注意：持久化会将吞吐量降低 2-10 倍

# Lazy Queue（惰性队列，RabbitMQ 3.6+）
# 消息直接写磁盘，不在内存中缓存
# 适合消息积压严重但消费不及时的场景
rabbitmqctl set_policy Lazy "^lazy\." '{"queue-mode":"lazy"}' --apply-to queues
```

---

## 六、性能基准测试

### 6.1 Kafka Producer 性能测试

```bash
# 使用 Kafka 自带的性能测试工具
# 测试 Producer 吞吐量
kafka-producer-perf-test.sh \
    --topic perf-test \
    --num-records 1000000 \
    --record-size 1024 \
    --throughput -1 \
    --producer-props \
        bootstrap.servers=kafka1:9092,kafka2:9092,kafka3:9092 \
        acks=1 \
        batch.size=65536 \
        linger.ms=10 \
        compression.type=lz4 \
        buffer.memory=67108864

# 输出示例：
# 1000000 records sent, 245678.5 records/sec (240.31 MB/sec),
# 12.3 ms avg latency, 156.0 ms max latency,
# 8 ms 50th, 23 ms 95th, 89 ms 99th, 145 ms 99.9th.
```

### 6.2 Kafka Consumer 性能测试

```bash
# 测试 Consumer 吞吐量
kafka-consumer-perf-test.sh \
    --bootstrap-server kafka1:9092,kafka2:9092,kafka3:9092 \
    --topic perf-test \
    --messages 1000000 \
    --threads 1 \
    --fetch-size 1048576

# 输出示例：
# start.time, end.time, data.consumed.in.MB, MB.sec, data.consumed.in.nMsgs, nMsgs.sec
# 2024-03-15 10:00:00, 2024-03-15 10:00:03, 976.5625, 325.52, 1000000, 333333.33
```

### 6.3 不同配置组合的性能对比

| 配置组合 | 吞吐量 (records/sec) | 平均延迟 (ms) | P99 延迟 (ms) | 适用场景 |
|---------|---------------------|-------------|-------------|---------|
| acks=0, 无压缩, batch=16K | 380,000 | 3.2 | 25 | 性能基准上限 |
| acks=1, lz4, batch=64K | 245,000 | 12.3 | 89 | 日志采集 |
| acks=all, lz4, batch=64K | 185,000 | 18.7 | 125 | 订单/支付 |
| acks=all, gzip, batch=256K | 120,000 | 35.2 | 210 | 大数据管道 |
| acks=1, 无压缩, batch=1 | 15,000 | 2.1 | 15 | 逐条发送（反模式） |

### 6.4 端到端延迟测试

```bash
# 使用 kafka-e2e-latency 工具（需要编译）
# 或者自行编写：
# 1. Producer 在消息中嵌入发送时间戳
# 2. Consumer 收到后计算 now() - timestamp

# 简易端到端延迟测试脚本
kafka-run-class.sh kafka.tools.EndToEndLatency \
    kafka1:9092 \
    perf-test \
    10000 \
    all \
    1024

# 输出示例：
# Avg latency: 4.5678 ms
# 50th: 3.2 ms
# 99th: 12.8 ms
# 99.9th: 45.3 ms
```

---

## 七、Broker 端调优

### 7.1 关键 Broker 配置

```properties
# ========================
# Kafka Broker 核心配置
# ========================

# --- 线程模型 ---
num.network.threads=8
# 网络 I/O 线程数，处理网络请求
# 推荐：CPU 核心数

num.io.threads=16
# 磁盘 I/O 线程数，处理磁盘读写
# 推荐：CPU 核心数 * 2

# --- 日志管理 ---
log.segment.bytes=1073741824
# 单个 Segment 文件大小：1GB

log.retention.hours=168
# 消息保留时间：7 天

log.retention.bytes=-1
# 按大小保留：-1 表示不限制

# --- 副本同步 ---
num.replica.fetchers=4
# 副本同步线程数（Follower 从 Leader 拉取数据）
# 推荐：2~4，过多会增加 Leader 负担

replica.lag.time.max.ms=30000
# Follower 最大落后时间，超过会被踢出 ISR

min.insync.replicas=2
# 最少同步副本数（配合 acks=all 使用）
# 推荐：副本数 - 1
```

### 7.2 OS 层调优

```bash
# 1. 文件描述符
ulimit -n 100000   # Kafka 需要大量文件描述符

# 2. 页缓存（Page Cache）
# Kafka 严重依赖 OS 页缓存，不建议给 Kafka JVM 太多堆内存
# 推荐：JVM 堆 6-8GB，剩余内存留给页缓存
# 例如：32GB 内存的机器，JVM 6GB，页缓存可用 ~24GB

# 3. 磁盘 I/O 调度器
cat /sys/block/sda/queue/scheduler
# 推荐 SSD 用 none/noop，HDD 用 deadline
echo deadline > /sys/block/sda/queue/scheduler

# 4. 网络参数
sysctl -w net.core.wmem_max=2097152
sysctl -w net.core.rmem_max=2097152
sysctl -w net.ipv4.tcp_wmem='4096 65536 2097152'
sysctl -w net.ipv4.tcp_rmem='4096 65536 2097152'

# 5. 禁用 Swap
sysctl -w vm.swappiness=1
```

---

## 八、调优 Checklist

| 调优维度 | 配置项 | 推荐值 | 说明 |
|---------|-------|-------|------|
| Producer 吞吐 | `batch.size` | 64KB~256KB | 增大批次 |
| Producer 吞吐 | `linger.ms` | 5~50ms | 等待凑批 |
| Producer 吞吐 | `compression.type` | lz4 | 减少网络和磁盘 I/O |
| Producer 吞吐 | `buffer.memory` | 64MB~256MB | 增大缓冲区 |
| Producer 可靠性 | `acks` | all | 所有 ISR 确认 |
| Producer 可靠性 | `enable.idempotence` | true | 幂等写入 |
| Consumer 吞吐 | `fetch.min.bytes` | 1KB~64KB | 减少请求次数 |
| Consumer 吞吐 | `max.poll.records` | 100~1000 | 根据处理能力 |
| Consumer 稳定性 | `max.poll.interval.ms` | 处理时间 * 3 | 防止误判超时 |
| Consumer 稳定性 | `session.timeout.ms` | 10s~45s | 心跳超时 |
| Broker | `num.io.threads` | CPU*2 | 磁盘 I/O 线程 |
| Broker | `min.insync.replicas` | 2 | 最小同步副本 |
| 分区 | 分区数 | 6~64 per topic | 根据吞吐需求 |
| OS | `vm.swappiness` | 1 | 禁用 Swap |
| OS | `ulimit -n` | 100000 | 文件描述符 |
