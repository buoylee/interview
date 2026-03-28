# Redis 性能排查

## 为什么需要 Redis 性能排查

Redis 号称单线程模型下能达到 10 万+ QPS，但生产环境中经常遇到"Redis 变慢了"的反馈。问题往往不在 Redis 本身，而在于**使用方式**——一个 `KEYS *` 就能打挂整个集群，一个 10MB 的大 Key 就能让 P99 飙到秒级。掌握 Redis 性能排查方法论，是中间件调优的基本功。

---

## 一、SLOWLOG 配置与使用

SLOWLOG 是 Redis 内置的慢查询日志，记录执行时间超过阈值的命令。**注意：这里的执行时间不包含网络 I/O 和排队时间，纯粹是命令执行耗时。**

### 1.1 配置参数

```bash
# 查看当前配置
redis-cli CONFIG GET slowlog-log-slower-than
# 1) "slowlog-log-slower-than"
# 2) "10000"           # 默认 10000 微秒 = 10ms

redis-cli CONFIG GET slowlog-max-len
# 1) "slowlog-max-len"
# 2) "128"             # 默认只保留 128 条

# 生产推荐配置
redis-cli CONFIG SET slowlog-log-slower-than 5000   # 5ms
redis-cli CONFIG SET slowlog-max-len 1000            # 保留 1000 条

# 写入配置文件持久化
redis-cli CONFIG REWRITE
```

### 1.2 查看和分析 SLOWLOG

```bash
# 查看最近 10 条慢查询
redis-cli SLOWLOG GET 10

# 输出示例：
# 1) 1) (integer) 14                    # 慢查询 ID
#    2) (integer) 1678901234             # 发生时间戳（Unix）
#    3) (integer) 38712                  # 执行耗时（微秒），38ms
#    4) 1) "SMEMBERS"                    # 命令及参数
#       2) "user:followers:100086"
#    5) "10.0.1.50:52314"               # 客户端地址
#    6) ""                               # 客户端名称

# 查看慢查询总数
redis-cli SLOWLOG LEN
# (integer) 47

# 清空慢查询日志
redis-cli SLOWLOG RESET
```

### 1.3 生产实践

```bash
# 将 SLOWLOG 定期采集到监控系统
# 以下脚本每分钟采集一次慢查询并写入日志文件
#!/bin/bash
while true; do
    redis-cli SLOWLOG GET 50 >> /var/log/redis-slowlog.log
    redis-cli SLOWLOG RESET
    sleep 60
done
```

> **关键点**：SLOWLOG 是环形缓冲区，满了会覆盖最早的记录。生产环境务必定期采集或接入监控。

---

## 二、慢命令排查——O(N) 命令识别

Redis 单线程模型意味着**一个慢命令会阻塞所有其他命令**。以下是常见的 O(N) 危险命令。

### 2.1 危险命令清单

| 命令 | 时间复杂度 | 危险场景 | 替代方案 |
|------|-----------|---------|---------|
| `KEYS pattern` | O(N)，N=总 key 数 | 生产环境全量扫描 | `SCAN cursor MATCH pattern COUNT 100` |
| `SMEMBERS key` | O(N)，N=集合元素数 | 大集合读取 | `SSCAN cursor COUNT 100` |
| `HGETALL key` | O(N)，N=哈希字段数 | 大哈希读取 | `HSCAN cursor COUNT 100` 或 `HMGET` 指定字段 |
| `LRANGE 0 -1` | O(N)，N=列表长度 | 大列表全量读取 | 分页 `LRANGE start stop` |
| `SORT key` | O(N+M*log(M)) | 大集合排序 | 应用层排序或使用 Sorted Set |
| `DEL bigkey` | O(N) (集合类) | 删除百万元素集合 | `UNLINK`（异步删除） |
| `FLUSHDB` | O(N) | 清空数据库 | `FLUSHDB ASYNC` |

### 2.2 禁用危险命令

```bash
# redis.conf 中禁用危险命令
rename-command KEYS ""
rename-command FLUSHALL ""
rename-command FLUSHDB ""

# 或重命名为复杂名称（运维紧急时可用）
rename-command KEYS "KEYS_DO_NOT_USE_IN_PROD_a8f3b2"
```

### 2.3 用 SCAN 替代 KEYS

```bash
# 错误做法：阻塞整个 Redis
redis-cli KEYS "user:session:*"

# 正确做法：渐进式扫描
redis-cli SCAN 0 MATCH "user:session:*" COUNT 100
# 1) "17920"              # 下一次游标
# 2) 1) "user:session:abc123"
#    2) "user:session:def456"

# 继续扫描，直到游标返回 "0"
redis-cli SCAN 17920 MATCH "user:session:*" COUNT 100
```

```python
# Python 实现完整扫描
import redis
r = redis.Redis(host='10.0.1.50', port=6379)

cursor = 0
keys = []
while True:
    cursor, partial_keys = r.scan(cursor=cursor, match='user:session:*', count=100)
    keys.extend(partial_keys)
    if cursor == 0:
        break

print(f"Total keys found: {len(keys)}")
```

---

## 三、大 Key 检测

大 Key 的危害：

- **读写耗时高**：序列化/反序列化一个 10MB 的 value 需要数十毫秒
- **网络带宽占用**：频繁读取大 Key 会打满网卡
- **删除阻塞**：DEL 一个包含百万元素的集合会阻塞数秒
- **主从同步延迟**：大 Key 会导致 RDB 传输和加载变慢
- **内存不均**：在集群模式下导致数据倾斜

### 3.1 redis-cli --bigkeys

```bash
# 内置大 Key 扫描工具（基于 SCAN，不阻塞）
redis-cli --bigkeys

# 输出示例：
# -------- summary -------
# Sampled 1523456 keys in the keyspace!
# Total key length in bytes is 28934012 (avg len 19.00)
#
# Biggest string found 'cache:product:detail:9527' has 5242880 bytes (5MB)
# Biggest   list found 'queue:pending_orders' has 892341 items
# Biggest    set found 'user:followers:100086' has 156782 members
# Biggest   hash found 'user:profile:200001' has 1024 fields
# Biggest   zset found 'rank:daily:20240315' has 500000 members

# 指定采样频率（每次 SCAN 的 COUNT）
redis-cli --bigkeys -i 0.1   # 每次扫描间隔 0.1 秒，降低对线上影响
```

### 3.2 MEMORY USAGE（Redis 4.0+）

```bash
# 精确查看单个 Key 的内存占用
redis-cli MEMORY USAGE "cache:product:detail:9527"
# (integer) 5243200    # 单位 bytes，约 5MB

# 带采样参数（对大集合用采样估算）
redis-cli MEMORY USAGE "user:followers:100086" SAMPLES 5
# (integer) 12582912   # 约 12MB
```

### 3.3 大 Key 定义参考标准

| 数据类型 | 大 Key 阈值 | 说明 |
|---------|------------|------|
| String | > 1MB | value 长度超过 1MB |
| Hash | > 5000 fields 或 value 总大小 > 5MB | 字段过多或总内存过大 |
| List | > 10000 elements | 元素过多 |
| Set | > 10000 members | 成员过多 |
| ZSet | > 10000 members | 成员过多 |

### 3.4 大 Key 处理策略

```bash
# 1. 大 String：拆分为多个小 Key
#    cache:product:detail:9527 → cache:product:basic:9527 + cache:product:spec:9527

# 2. 大集合：按业务拆分
#    user:followers:100086 → user:followers:100086:0, user:followers:100086:1 ...
#    按 hash(member) % N 分桶

# 3. 安全删除大 Key（避免阻塞）
redis-cli UNLINK "cache:product:detail:9527"   # 异步删除，后台线程处理

# 4. 渐进式删除大集合
# HSCAN + HDEL 分批删除
redis-cli HSCAN bigkey 0 COUNT 100
# 对返回的字段批量 HDEL
redis-cli HDEL bigkey field1 field2 field3 ...
```

---

## 四、Pipeline 优化

### 4.1 为什么需要 Pipeline

Redis 命令执行通常只需微秒级，但每条命令都要经过一次网络往返（RTT）。在跨机房场景（RTT ~1ms），逐条发送 1000 条命令需要 1 秒，而用 Pipeline 批量发送可能只需 2ms。

```
逐条发送：        Pipeline：
Client → SET k1    Client → SET k1
Client ← OK               SET k2
Client → SET k2            SET k3
Client ← OK               ...
Client → SET k3            SET k1000
Client ← OK        Client ← OK * 1000
...
总耗时 ≈ 1000 * RTT  总耗时 ≈ 1 * RTT + 执行时间
```

### 4.2 Jedis Pipeline 示例

```java
// 不用 Pipeline：1000 次 RTT
for (int i = 0; i < 1000; i++) {
    jedis.set("key:" + i, "value:" + i);  // 每次都等待响应
}

// 使用 Pipeline：1 次 RTT
Pipeline pipeline = jedis.pipelined();
for (int i = 0; i < 1000; i++) {
    pipeline.set("key:" + i, "value:" + i);  // 只发送，不等待
}
List<Object> results = pipeline.syncAndReturnAll();  // 一次性获取所有响应
```

### 4.3 Pipeline 注意事项

```
# Pipeline 不是万能的，需要注意：
# 1. 单次 Pipeline 不宜过大（建议 100-500 条），过大会：
#    - 占用过多内存缓冲区
#    - 单次阻塞时间过长
# 2. Pipeline 不保证原子性（不同于 MULTI/EXEC 事务）
# 3. Pipeline 内的命令不能依赖前一条命令的结果
#    如果需要依赖结果，用 Lua 脚本
```

### 4.4 Pipeline 性能对比

| 方式 | 1000 条命令耗时 (RTT=1ms) | 1000 条命令耗时 (RTT=0.1ms) |
|------|--------------------------|---------------------------|
| 逐条发送 | ~1000ms | ~100ms |
| Pipeline (batch=100) | ~12ms | ~3ms |
| Pipeline (batch=500) | ~4ms | ~1.5ms |

---

## 五、热 Key 识别与解决

热 Key（Hot Key）是指被高频访问的 Key。当某个 Key 的 QPS 达到数万甚至数十万时，单个 Redis 节点的 CPU、网卡带宽都可能成为瓶颈。

### 5.1 热 Key 识别方法

```bash
# 方法 1：redis-cli --hotkeys（需要开启 LFU 淘汰策略）
redis-cli CONFIG SET maxmemory-policy allkeys-lfu
redis-cli --hotkeys

# 输出示例：
# Summary of hot keys found so far:
# hot:product:flash_sale:001       counter: 89523
# hot:config:global_switch         counter: 45678
# hot:rank:realtime                counter: 31200

# 方法 2：MONITOR 命令（生产慎用，性能影响大）
redis-cli MONITOR | head -1000 > /tmp/redis_monitor.log
# 分析高频 Key
awk '{print $4}' /tmp/redis_monitor.log | sort | uniq -c | sort -rn | head 20

# 方法 3：代理层统计（推荐）
# Twemproxy/Codis/Redis Cluster Proxy 在代理层统计 Key 访问频次
```

### 5.2 热 Key 解决方案

```
方案 1：本地缓存（最常用）
┌──────────┐     ┌─────────────┐     ┌───────┐
│  Client   │ ──→ │ Local Cache │ ──→ │ Redis │
│ (Caffeine)│     │  (L1 Cache) │     │(L2)   │
└──────────┘     └─────────────┘     └───────┘
  命中率 > 90%      TTL 短（秒级）

方案 2：Key 分散（读写分离 + 副本）
  原始 Key: hot:product:001
  分散为:   hot:product:001:r1, hot:product:001:r2, hot:product:001:r3
  读时随机选一个副本，写时更新所有副本

方案 3：使用 Redis 集群的只读副本
  在 Redis Cluster 中，READONLY 命令允许从 slave 读取
```

```java
// 本地缓存 + Redis 两级缓存示例（Spring Boot + Caffeine）
@Bean
public CacheManager cacheManager() {
    CaffeineCacheManager manager = new CaffeineCacheManager();
    manager.setCaffeine(Caffeine.newBuilder()
        .maximumSize(10000)
        .expireAfterWrite(5, TimeUnit.SECONDS)  // 本地缓存 5 秒
    );
    return manager;
}

@Cacheable(value = "hotProducts", key = "#productId")
public Product getProduct(Long productId) {
    // 本地缓存未命中，查 Redis
    String json = redisTemplate.opsForValue().get("product:" + productId);
    if (json != null) {
        return JSON.parseObject(json, Product.class);
    }
    // Redis 未命中，查数据库
    Product product = productDao.findById(productId);
    redisTemplate.opsForValue().set("product:" + productId, JSON.toJSONString(product),
        Duration.ofMinutes(30));
    return product;
}
```

---

## 六、连接池调优

Redis 客户端的连接池配置不当是常见的性能问题来源：连接不够导致等待，连接泄漏导致耗尽。

### 6.1 Jedis 连接池配置

```java
JedisPoolConfig poolConfig = new JedisPoolConfig();

// 核心参数
poolConfig.setMaxTotal(50);          // 最大连接数（默认 8，太小）
poolConfig.setMaxIdle(50);           // 最大空闲连接（建议 = maxTotal）
poolConfig.setMinIdle(10);           // 最小空闲连接（保持预热）
poolConfig.setMaxWaitMillis(2000);   // 获取连接最大等待时间（ms）

// 连接健康检查
poolConfig.setTestOnBorrow(false);   // 借出时检查（有性能开销，不建议）
poolConfig.setTestWhileIdle(true);   // 空闲时检查（推荐）
poolConfig.setTimeBetweenEvictionRunsMillis(30000);  // 空闲检查间隔 30s
poolConfig.setMinEvictableIdleTimeMillis(60000);     // 空闲超过 60s 可被回收

JedisPool jedisPool = new JedisPool(poolConfig, "10.0.1.50", 6379, 2000, "password");
```

### 6.2 Lettuce 连接池配置（Spring Boot 默认）

```yaml
# application.yml
spring:
  redis:
    host: 10.0.1.50
    port: 6379
    password: your_password
    timeout: 2000ms
    lettuce:
      pool:
        max-active: 50       # 最大活跃连接
        max-idle: 50          # 最大空闲连接
        min-idle: 10          # 最小空闲连接
        max-wait: 2000ms      # 最大等待时间
```

### 6.3 连接池大小计算公式

```
最大连接数 = 业务线程数 * 单线程平均持有连接时间 / 命令平均执行时间

示例：
  业务线程数 = 200
  单次 Redis 操作 Pipeline 5 条命令，持有连接约 1ms
  命令平均执行时间 0.2ms
  最大连接数 ≈ 200 * 1 / 0.2 = 1000 ?  ← 不需要这么多

实际上：
  200 个线程不会同时访问 Redis
  并发因子通常 0.1~0.3
  最大连接数 ≈ 200 * 0.2 = 40，再留 20% 余量 ≈ 50
```

### 6.4 连接池问题排查

```bash
# 查看 Redis 当前连接数
redis-cli INFO clients
# connected_clients:156
# blocked_clients:0
# tracking_clients:0
# maxclients:10000

# 查看每个连接的详情
redis-cli CLIENT LIST
# id=1234 addr=10.0.1.50:52314 fd=5 name= db=0 cmd=get age=3600 idle=30 ...

# 查看连接来源分布
redis-cli CLIENT LIST | awk -F'[ =:]' '{print $4}' | sort | uniq -c | sort -rn
# 输出：
#   56 10.0.1.51    ← 应用服务器 1
#   48 10.0.1.52    ← 应用服务器 2
#   32 10.0.1.53    ← 应用服务器 3
#   20 10.0.2.10    ← 未知来源，需排查
```

---

## 七、Redis 延迟诊断

### 7.1 redis-cli --latency

```bash
# 持续测量客户端到 Redis 的往返延迟
redis-cli --latency -h 10.0.1.50 -p 6379
# min: 0, max: 3, avg: 0.18 (10234 samples)

# 分时段统计
redis-cli --latency-history -h 10.0.1.50 -p 6379
# min: 0, max: 1, avg: 0.15 (1471 samples) -- 15.01 seconds range
# min: 0, max: 2, avg: 0.19 (1489 samples) -- 15.01 seconds range
# min: 0, max: 12, avg: 0.31 (1445 samples) -- 15.01 seconds range  ← 这段有毛刺

# 延迟分布直方图
redis-cli --latency-dist -h 10.0.1.50 -p 6379
```

### 7.2 --intrinsic-latency（系统固有延迟）

```bash
# 测量当前系统的固有延迟（OS 调度、内存访问等，不涉及网络）
# 在 Redis 服务器本机执行
redis-cli --intrinsic-latency 100    # 测试 100 秒
# Max latency so far: 1 microseconds.
# Max latency so far: 4 microseconds.
# Max latency so far: 12 microseconds.
# Max latency so far: 68 microseconds.    ← 系统固有延迟上限

# 如果固有延迟就很高（>100us），说明是系统层面问题：
# - 虚拟机/容器 CPU 争抢
# - NUMA 跨节点内存访问
# - Swap 交换
# - Transparent Huge Pages (THP) 开启
```

### 7.3 常见延迟原因排查清单

| 延迟现象 | 可能原因 | 排查方法 |
|---------|---------|---------|
| 周期性延迟毛刺 | RDB/AOF 持久化 fork | `INFO persistence` 查看 `latest_fork_usec` |
| 某些命令特别慢 | O(N) 命令 | 查看 SLOWLOG |
| 所有命令都慢 | 网络问题或 Swap | `--latency` vs `--intrinsic-latency` 对比 |
| 突然延迟飙升 | 大 Key 操作或过期清理 | `INFO stats` 查看 `expired_keys` 速率 |
| 连接建立慢 | 连接数过多 | `INFO clients` 查看 `connected_clients` |
| 逐渐变慢 | 内存碎片化 | `INFO memory` 查看 `mem_fragmentation_ratio` |

### 7.4 THP 与 Swap 检查

```bash
# 检查 Transparent Huge Pages（必须关闭）
cat /sys/kernel/mm/transparent_hugepage/enabled
# [always] madvise never    ← always 说明开启了，需要关闭

# 关闭 THP
echo never > /sys/kernel/mm/transparent_hugepage/enabled
echo never > /sys/kernel/mm/transparent_hugepage/defrag

# 检查 Swap 使用
redis-cli INFO memory | grep process_id
# process_id:12345
cat /proc/12345/smaps | grep Swap | awk '{sum+=$2} END {print sum "KB"}'
# 0KB    ← 正常，没有使用 Swap

# 禁止 Redis 使用 Swap
# 方法 1：redis.conf
# 方法 2：系统级
echo 1 > /proc/12345/oom_score_adj   # 降低被 OOM Kill 优先级
sysctl vm.swappiness=1                # 尽量不使用 Swap
```

---

## 八、性能排查综合流程

```
Redis 变慢了？
│
├─ 1. redis-cli --latency 确认延迟是否真的高
│   └─ 对比 --intrinsic-latency，排除系统问题
│
├─ 2. SLOWLOG GET 查看是否有慢命令
│   └─ 有 → 优化命令（SCAN 替代 KEYS，UNLINK 替代 DEL）
│
├─ 3. redis-cli --bigkeys 检查大 Key
│   └─ 有 → 拆分或异步删除
│
├─ 4. INFO memory 检查内存状态
│   ├─ mem_fragmentation_ratio > 1.5 → 碎片整理
│   └─ used_memory 接近 maxmemory → 扩容或优化数据结构
│
├─ 5. INFO persistence 检查持久化
│   └─ latest_fork_usec 过高 → 减少 RDB 频率，考虑关闭 AOF
│
├─ 6. INFO clients 检查连接数
│   └─ connected_clients 过高 → 排查连接泄漏
│
└─ 7. 检查系统层面
    ├─ THP 是否关闭
    ├─ Swap 是否被使用
    └─ CPU 是否被争抢（容器场景检查 cgroup 限制）
```

### 快速诊断命令集

```bash
# 一键采集 Redis 状态信息
echo "=== Latency ===" && \
redis-cli --latency -h 10.0.1.50 -p 6379 --latency-samples 100 && \
echo "=== Slowlog ===" && \
redis-cli -h 10.0.1.50 SLOWLOG GET 10 && \
echo "=== Memory ===" && \
redis-cli -h 10.0.1.50 INFO memory && \
echo "=== Clients ===" && \
redis-cli -h 10.0.1.50 INFO clients && \
echo "=== Persistence ===" && \
redis-cli -h 10.0.1.50 INFO persistence && \
echo "=== Stats ===" && \
redis-cli -h 10.0.1.50 INFO stats | grep -E "keyspace_|expired_|evicted_"
```

---

## 九、排查 Checklist

| 检查项 | 命令 | 健康标准 |
|-------|------|---------|
| 慢查询数量 | `SLOWLOG LEN` | 24h 内 < 100 条 |
| 最大延迟 | `--latency` | avg < 1ms, max < 10ms |
| 系统固有延迟 | `--intrinsic-latency` | max < 100us |
| 大 Key | `--bigkeys` | 无 > 1MB 的 String，无 > 10000 元素的集合 |
| 内存碎片率 | `INFO memory` → `mem_fragmentation_ratio` | 1.0 ~ 1.5 |
| 连接数 | `INFO clients` → `connected_clients` | < maxclients * 80% |
| Fork 耗时 | `INFO persistence` → `latest_fork_usec` | < 100ms |
| THP | `/sys/kernel/mm/transparent_hugepage/enabled` | never |
| Swap 使用 | `/proc/<pid>/smaps` | 0KB |
| 危险命令 | 检查 `rename-command` 配置 | KEYS/FLUSHALL 已禁用 |
