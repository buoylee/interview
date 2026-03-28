# 缓存策略

缓存是性能优化最直接、收益最高的手段之一。一次 Redis 读取约 0.5ms，一次 MySQL 查询可能 5-50ms，差距可达两个数量级。但缓存引入了数据一致性问题，如果策略选错或防护缺失，缓存反而会成为系统最脆弱的环节。本文覆盖缓存模式选型、三大缓存故障防御、多级缓存架构以及一致性保障方案。

---

## 一、缓存模式对比

### 1.1 五种核心模式

| 模式 | 读路径 | 写路径 | 一致性 | 适用场景 |
|------|--------|--------|--------|----------|
| Cache-Aside | 应用先查缓存，miss 则查 DB 并回填 | 应用写 DB，然后删缓存 | 最终一致 | 通用场景，最常用 |
| Read-Through | 缓存层代理读，miss 时自动加载 | — | 最终一致 | 封装读逻辑到缓存层 |
| Write-Through | — | 缓存层同步写 DB + 缓存 | 强一致 | 对一致性要求高 |
| Write-Behind | — | 缓存层异步批量写 DB | 弱一致 | 写密集、允许丢数据 |
| Write-Around | — | 直接写 DB，不更新缓存 | 最终一致 | 写多读少 |

### 1.2 Cache-Aside 伪代码（最常用）

```java
// 读操作
public User getUser(Long userId) {
    String key = "user:" + userId;
    // 1. 查缓存
    User user = redis.get(key, User.class);
    if (user != null) {
        return user;
    }
    // 2. 缓存未命中，查 DB
    user = userMapper.selectById(userId);
    if (user != null) {
        // 3. 回填缓存，设置 TTL
        redis.set(key, user, Duration.ofMinutes(30));
    }
    return user;
}

// 写操作
@Transactional
public void updateUser(User user) {
    // 1. 先更新 DB
    userMapper.updateById(user);
    // 2. 再删除缓存（不是更新缓存！）
    redis.delete("user:" + user.getId());
}
```

**为什么是删除而不是更新缓存？** 因为并发写场景下，更新缓存可能导致旧值覆盖新值（线程 A 先算出结果但后写入缓存）。删除缓存让下次读自然回填最新数据，避免了这种竞态条件。

### 1.3 Write-Behind 示例

```java
// 使用 Caffeine 的 Writer 实现 Write-Behind
LoadingCache<String, User> cache = Caffeine.newBuilder()
    .maximumSize(10_000)
    .writer(new CacheWriter<String, User>() {
        private final BlockingQueue<User> buffer = new LinkedBlockingQueue<>(1000);

        { // 启动异步刷盘线程
            ScheduledExecutorService executor = Executors.newSingleThreadScheduledExecutor();
            executor.scheduleWithFixedDelay(() -> {
                List<User> batch = new ArrayList<>();
                buffer.drainTo(batch, 200);
                if (!batch.isEmpty()) {
                    userMapper.batchUpdate(batch); // 批量写 DB
                }
            }, 1, 1, TimeUnit.SECONDS);
        }

        @Override
        public void write(String key, User value) {
            buffer.offer(value); // 放入缓冲队列
        }

        @Override
        public void delete(String key, User value, RemovalCause cause) {}
    })
    .build(key -> userMapper.selectById(extractId(key)));
```

---

## 二、缓存穿透防御

**定义**：查询一个数据库中不存在的 Key，每次都穿透到 DB。恶意攻击可利用此漏洞打垮数据库。

### 2.1 空值缓存

```java
public User getUser(Long userId) {
    String key = "user:" + userId;
    // 注意：需要能区分"缓存中存的是 null"和"缓存 miss"
    ValueWrapper wrapper = redis.get(key);
    if (wrapper != null) {
        return (User) wrapper.get(); // 可能返回 null
    }

    User user = userMapper.selectById(userId);
    if (user == null) {
        // 缓存空值，TTL 设短（防止被大量无效 Key 撑爆内存）
        redis.set(key, NullValue.INSTANCE, Duration.ofMinutes(5));
        return null;
    }
    redis.set(key, user, Duration.ofMinutes(30));
    return user;
}
```

### 2.2 布隆过滤器

```java
// 系统启动时加载所有有效 Key 到布隆过滤器
@PostConstruct
public void initBloomFilter() {
    // Guava BloomFilter，预计 100 万条数据，误判率 1%
    bloomFilter = BloomFilter.create(
        Funnels.longFunnel(), 1_000_000, 0.01);

    List<Long> allUserIds = userMapper.selectAllIds();
    allUserIds.forEach(bloomFilter::put);
}

public User getUser(Long userId) {
    // 1. 布隆过滤器前置拦截
    if (!bloomFilter.mightContain(userId)) {
        return null; // 一定不存在
    }
    // 2. 正常 Cache-Aside 逻辑
    return getFromCacheOrDB(userId);
}
```

**Redis 布隆过滤器**（分布式场景推荐）：

```bash
# 创建布隆过滤器，预计 100 万元素，误判率 1%
BF.RESERVE user_filter 0.01 1000000

# 添加元素
BF.ADD user_filter "user:1001"
BF.ADD user_filter "user:1002"

# 检查元素是否存在
BF.EXISTS user_filter "user:9999"  # 0 = 一定不存在
```

---

## 三、缓存雪崩防御

**定义**：大量 Key 在同一时间过期，或缓存服务宕机，导致请求全部打到 DB。

### 3.1 随机 TTL 打散

```java
// 基础 TTL + 随机偏移量
private Duration randomTtl(Duration baseTtl) {
    long baseSeconds = baseTtl.getSeconds();
    // 在基础 TTL 上加 0~20% 的随机偏移
    long jitter = ThreadLocalRandom.current().nextLong(baseSeconds / 5);
    return Duration.ofSeconds(baseSeconds + jitter);
}

// 使用
redis.set(key, value, randomTtl(Duration.ofMinutes(30)));
// 实际 TTL 在 30~36 分钟之间随机分布
```

### 3.2 缓存预热

```java
@Component
public class CacheWarmer implements ApplicationRunner {

    @Override
    public void run(ApplicationArguments args) {
        log.info("开始缓存预热...");
        // 预热热点数据
        List<Product> hotProducts = productMapper.selectTopN(1000);
        hotProducts.forEach(p -> {
            redis.set("product:" + p.getId(), p, randomTtl(Duration.ofHours(2)));
        });
        log.info("缓存预热完成，加载 {} 条数据", hotProducts.size());
    }
}
```

### 3.3 多级容灾

```
请求 → 本地缓存(Caffeine) → Redis 集群 → 数据库
         ↑ miss               ↑ miss / 宕机
         回填                  回填 + 降级
```

Redis 不可用时降级到本地缓存 + 限流保护 DB：

```java
public User getUser(Long userId) {
    String key = "user:" + userId;

    // 1. L1 本地缓存
    User user = localCache.getIfPresent(key);
    if (user != null) return user;

    try {
        // 2. L2 Redis
        user = redis.get(key, User.class);
        if (user != null) {
            localCache.put(key, user);
            return user;
        }
    } catch (Exception e) {
        log.warn("Redis 不可用，降级到 DB", e);
        // Redis 故障时不阻塞，直接查 DB
    }

    // 3. 查 DB（需限流保护）
    user = rateLimiter.acquire(() -> userMapper.selectById(userId));
    if (user != null) {
        localCache.put(key, user);
        trySetRedis(key, user); // 尝试回填 Redis
    }
    return user;
}
```

---

## 四、缓存击穿防御

**定义**：某个热 Key 过期瞬间，大量并发请求同时打到 DB。

### 4.1 互斥锁方案

```java
public User getUser(Long userId) {
    String key = "user:" + userId;
    User user = redis.get(key, User.class);
    if (user != null) return user;

    // 获取分布式锁
    String lockKey = "lock:" + key;
    boolean locked = redis.opsForValue()
        .setIfAbsent(lockKey, "1", Duration.ofSeconds(10));

    if (locked) {
        try {
            // Double-check：拿到锁后再查一次缓存
            user = redis.get(key, User.class);
            if (user != null) return user;

            user = userMapper.selectById(userId);
            redis.set(key, user, Duration.ofMinutes(30));
            return user;
        } finally {
            redis.delete(lockKey);
        }
    } else {
        // 没拿到锁，短暂等待后重试
        Thread.sleep(50);
        return getUser(userId); // 递归重试（生产环境加重试次数限制）
    }
}
```

### 4.2 逻辑过期方案（不阻塞任何请求）

```java
@Data
public class CacheData<T> {
    private T data;
    private long expireTime; // 逻辑过期时间戳
}

public User getUser(Long userId) {
    String key = "user:" + userId;
    CacheData<User> cacheData = redis.get(key, new TypeReference<>() {});

    if (cacheData == null) {
        // 初始数据不在缓存，同步加载
        return loadAndCache(userId);
    }

    if (System.currentTimeMillis() < cacheData.getExpireTime()) {
        // 逻辑未过期，直接返回
        return cacheData.getData();
    }

    // 逻辑已过期，返回旧数据 + 异步刷新
    REFRESH_EXECUTOR.execute(() -> {
        String lockKey = "refresh:" + key;
        if (redis.opsForValue().setIfAbsent(lockKey, "1", Duration.ofSeconds(30))) {
            try {
                loadAndCache(userId);
            } finally {
                redis.delete(lockKey);
            }
        }
    });

    return cacheData.getData(); // 返回旧数据，不阻塞
}
```

---

## 五、多级缓存架构

### 5.1 三级缓存设计

```
                           CDN（静态资源/API 缓存）
                                    ↓ miss
Client  ─→  Nginx（Proxy Cache / Lua 缓存）
                                    ↓ miss
              L1 本地缓存（Caffeine，毫秒级，JVM 内）
                                    ↓ miss
              L2 分布式缓存（Redis Cluster）
                                    ↓ miss
              L3 数据库（MySQL / PostgreSQL）
```

### 5.2 Caffeine + Redis 双层缓存实现

```java
@Component
public class MultiLevelCache {

    private final Cache<String, Object> localCache = Caffeine.newBuilder()
        .maximumSize(10_000)
        .expireAfterWrite(Duration.ofMinutes(5)) // 本地缓存 TTL 较短
        .recordStats()
        .build();

    @Autowired
    private StringRedisTemplate redis;

    public <T> T get(String key, Class<T> type, Supplier<T> dbLoader) {
        // L1: 本地缓存
        @SuppressWarnings("unchecked")
        T value = (T) localCache.getIfPresent(key);
        if (value != null) {
            return value;
        }

        // L2: Redis
        String json = redis.opsForValue().get(key);
        if (json != null) {
            value = JsonUtils.parse(json, type);
            localCache.put(key, value); // 回填 L1
            return value;
        }

        // L3: DB
        value = dbLoader.get();
        if (value != null) {
            redis.opsForValue().set(key, JsonUtils.toJson(value),
                randomTtl(Duration.ofMinutes(30))); // 回填 L2
            localCache.put(key, value); // 回填 L1
        }
        return value;
    }

    public void evict(String key) {
        redis.delete(key);
        localCache.invalidate(key);
        // 多实例场景：通过 Redis Pub/Sub 通知其他实例清除本地缓存
        redis.convertAndSend("cache:evict", key);
    }
}
```

### 5.3 本地缓存同步（Redis Pub/Sub）

```java
@Component
public class CacheEvictListener {

    @Autowired
    private Cache<String, Object> localCache;

    @Bean
    public RedisMessageListenerContainer listenerContainer(
            RedisConnectionFactory factory) {
        RedisMessageListenerContainer container = new RedisMessageListenerContainer();
        container.setConnectionFactory(factory);
        container.addMessageListener((message, pattern) -> {
            String key = new String(message.getBody());
            localCache.invalidate(key);
            log.debug("本地缓存已清除: {}", key);
        }, new ChannelTopic("cache:evict"));
        return container;
    }
}
```

---

## 六、淘汰策略选型

| 策略 | 原理 | 适用场景 | Redis 配置 |
|------|------|----------|-----------|
| LRU | 淘汰最近最少使用 | 通用，访问模式符合时间局部性 | `maxmemory-policy allkeys-lru` |
| LFU | 淘汰使用频率最低 | 有明确热点数据 | `maxmemory-policy allkeys-lfu` |
| TTL | 优先淘汰即将过期 | 所有 Key 都有 TTL | `maxmemory-policy volatile-ttl` |
| Random | 随机淘汰 | 访问模式无规律 | `maxmemory-policy allkeys-random` |

```bash
# Redis 内存配置
maxmemory 4gb
maxmemory-policy allkeys-lfu   # 推荐：有热点数据用 LFU
maxmemory-samples 10           # 采样数量，越大越精确但越慢
```

---

## 七、缓存一致性方案

### 7.1 延迟双删

```java
public void updateUser(User user) {
    String key = "user:" + user.getId();
    // 1. 先删缓存
    redis.delete(key);
    // 2. 更新 DB
    userMapper.updateById(user);
    // 3. 延迟再删一次（覆盖读请求回填的旧数据）
    executor.schedule(() -> redis.delete(key), 500, TimeUnit.MILLISECONDS);
}
```

**延迟时间怎么定？** 大于一次从库同步延迟 + 一次业务读取耗时即可，通常 200ms~1s。

### 7.2 Binlog 订阅（最终一致，推荐）

```
应用写 DB → MySQL binlog → Canal/Debezium → 消费者删除/更新缓存
```

```java
// Canal 消费者示例
@CanalEventListener
public class CacheInvalidator {

    @ListenPoint(schema = "user_db", table = "user")
    public void onUserChange(CanalEntry.EventType eventType,
                              CanalEntry.RowData rowData) {
        String userId = getColumnValue(rowData, "id");
        String key = "user:" + userId;
        redis.delete(key);
        // 发布本地缓存清除通知
        redis.convertAndSend("cache:evict", key);
        log.info("缓存已失效: {}", key);
    }
}
```

### 7.3 方案对比

| 方案 | 一致性 | 复杂度 | 延迟 | 推荐度 |
|------|--------|--------|------|--------|
| 先更新 DB 再删缓存 | 较好 | 低 | 低 | 中小项目推荐 |
| 延迟双删 | 较好 | 中 | 中 | 有从库读的场景 |
| Binlog 订阅 | 最终一致 | 高 | 秒级 | 大型项目推荐 |
| 分布式事务 | 强一致 | 很高 | 高 | 极少使用 |

---

## 八、缓存监控

### 8.1 核心指标

| 指标 | 健康值 | 告警阈值 | 含义 |
|------|--------|----------|------|
| 命中率 | > 95% | < 80% | 缓存有效性 |
| 淘汰率 | < 1/s | > 100/s | 内存是否够用 |
| 内存使用率 | < 75% | > 90% | 容量规划 |
| 平均延迟 | < 1ms | > 5ms | Redis 性能 |
| 连接数 | - | > 80% maxconn | 连接池是否合理 |

### 8.2 Redis 监控命令

```bash
# 实时统计
redis-cli info stats | grep -E "keyspace_hits|keyspace_misses|evicted_keys"

# 命中率计算
# hit_rate = keyspace_hits / (keyspace_hits + keyspace_misses)

# 内存分析
redis-cli info memory | grep -E "used_memory_human|maxmemory_human|mem_fragmentation_ratio"

# 慢查询
redis-cli slowlog get 10

# 大 Key 扫描（线上慎用，会阻塞）
redis-cli --bigkeys --i 0.1
```

### 8.3 Caffeine 监控埋点

```java
Cache<String, Object> cache = Caffeine.newBuilder()
    .maximumSize(10_000)
    .recordStats()  // 开启统计
    .build();

// 暴露 Prometheus 指标
@Scheduled(fixedRate = 60_000)
public void reportCacheMetrics() {
    CacheStats stats = cache.stats();
    Metrics.gauge("cache.hit.rate", stats.hitRate());
    Metrics.gauge("cache.eviction.count", stats.evictionCount());
    Metrics.gauge("cache.size", cache.estimatedSize());
}
```

---

## 九、排查清单

| 问题 | 现象 | 排查 | 解决 |
|------|------|------|------|
| 缓存穿透 | DB QPS 异常高，大量 miss | 检查 miss 的 Key 是否存在 | 布隆过滤器 + 空值缓存 |
| 缓存雪崩 | 某时刻 DB 负载突增 | 检查是否有大批 Key 同时过期 | 随机 TTL + 预热 |
| 缓存击穿 | 单个热 Key 过期后 DB 突增 | 检查热 Key 的 TTL | 互斥锁 / 逻辑过期 |
| 内存暴涨 | Redis used_memory 快速增长 | bigkeys 扫描 + TTL 检查 | 设置淘汰策略 + 合理 TTL |
| 数据不一致 | 用户看到旧数据 | 检查缓存更新流程 | 延迟双删 / binlog |
| 热 Key 倾斜 | 单个 Redis 节点负载高 | hotkeys 分析 | 本地缓存 + Key 分片 |
