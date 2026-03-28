# 性能设计模式

好的性能不是调出来的，而是设计出来的。本文总结七种经过生产验证的性能设计模式，每种模式都解决一类特定的性能瓶颈。掌握这些模式的本质和适用场景，比记住具体 API 更重要。

---

## 一、对象池模式（Object Pool）

### 1.1 适用场景

对象创建开销大（数据库连接、线程、大型对象、正则 Pattern）且可以复用时，使用对象池避免反复创建销毁。

### 1.2 Apache Commons Pool

```java
// 1. 定义池化对象工厂
public class ExpensiveObjectFactory extends BasePooledObjectFactory<ExpensiveObject> {

    @Override
    public ExpensiveObject create() throws Exception {
        // 创建开销大的对象（如建立 TCP 连接）
        return new ExpensiveObject();
    }

    @Override
    public PooledObject<ExpensiveObject> wrap(ExpensiveObject obj) {
        return new DefaultPooledObject<>(obj);
    }

    @Override
    public void destroyObject(PooledObject<ExpensiveObject> p) throws Exception {
        p.getObject().close();
    }

    @Override
    public boolean validateObject(PooledObject<ExpensiveObject> p) {
        return p.getObject().isValid(); // 检测对象是否可用
    }
}

// 2. 配置池
GenericObjectPoolConfig<ExpensiveObject> config = new GenericObjectPoolConfig<>();
config.setMaxTotal(20);                    // 最大对象数
config.setMaxIdle(10);                     // 最大空闲
config.setMinIdle(5);                      // 最小空闲
config.setMaxWaitMillis(3000);             // 获取对象最大等待时间
config.setTestOnBorrow(true);              // 借出时检测有效性
config.setTimeBetweenEvictionRunsMillis(30000); // 驱逐检测间隔

GenericObjectPool<ExpensiveObject> pool =
    new GenericObjectPool<>(new ExpensiveObjectFactory(), config);

// 3. 使用
ExpensiveObject obj = pool.borrowObject();
try {
    obj.doWork();
} finally {
    pool.returnObject(obj); // 务必归还！
}
```

### 1.3 轻量级对象池（自定义）

```java
// 基于 ThreadLocal 的轻量级池（无锁，适合单线程内复用）
public class BufferPool {
    private static final ThreadLocal<byte[]> BUFFER =
        ThreadLocal.withInitial(() -> new byte[8192]);

    public static byte[] getBuffer() {
        return BUFFER.get();
    }
}

// 使用
byte[] buf = BufferPool.getBuffer();
// 使用 buf 读写数据...
// 不需要归还，ThreadLocal 自动管理生命周期
```

### 1.4 不适合池化的场景

- 对象创建开销小（POJO、DTO）
- 对象有状态且难以重置
- 并发度低，池的管理开销 > 创建开销

---

## 二、批处理模式（Batching）

### 2.1 核心思想

将多次小操作合并为一次大操作，减少网络往返、系统调用、锁竞争等开销。

### 2.2 数据库批量写入

```java
// 逐条插入（慢）
for (User user : users) {
    userMapper.insert(user);  // 每次一条 SQL，一次网络往返
}
// 10000 条 ≈ 10000 次网络往返 ≈ 30 秒

// 批量插入（快）
@Transactional
public void batchInsert(List<User> users) {
    int batchSize = 500;
    for (int i = 0; i < users.size(); i += batchSize) {
        List<User> batch = users.subList(i,
            Math.min(i + batchSize, users.size()));
        userMapper.batchInsert(batch); // 一次 SQL 插入 500 条
    }
}
// 10000 条 ≈ 20 次网络往返 ≈ 1 秒
```

```xml
<!-- MyBatis 批量插入 -->
<insert id="batchInsert">
    INSERT INTO user (name, email, status) VALUES
    <foreach collection="list" item="user" separator=",">
        (#{user.name}, #{user.email}, #{user.status})
    </foreach>
</insert>
```

### 2.3 请求合并（Request Collapsing）

```java
// 场景：100 个请求同时查询不同用户，合并为一次批量查询
public class UserBatchLoader {

    private final ScheduledExecutorService scheduler =
        Executors.newSingleThreadScheduledExecutor();
    private final Queue<BatchRequest<Long, User>> pendingRequests =
        new ConcurrentLinkedQueue<>();

    {
        // 每 5ms 执行一次合并
        scheduler.scheduleWithFixedDelay(this::flush, 5, 5, TimeUnit.MILLISECONDS);
    }

    public CompletableFuture<User> getUser(Long userId) {
        CompletableFuture<User> future = new CompletableFuture<>();
        pendingRequests.add(new BatchRequest<>(userId, future));
        return future;
    }

    private void flush() {
        List<BatchRequest<Long, User>> batch = new ArrayList<>();
        BatchRequest<Long, User> req;
        while ((req = pendingRequests.poll()) != null && batch.size() < 100) {
            batch.add(req);
        }
        if (batch.isEmpty()) return;

        // 一次批量查询
        List<Long> ids = batch.stream().map(BatchRequest::getKey).toList();
        Map<Long, User> users = userMapper.selectByIds(ids).stream()
            .collect(Collectors.toMap(User::getId, Function.identity()));

        // 分发结果
        batch.forEach(r -> r.getFuture().complete(users.get(r.getKey())));
    }
}
```

### 2.4 Kafka 批量发送

```java
// Kafka Producer 批量配置
Properties props = new Properties();
props.put("batch.size", 65536);          // 批量大小 64KB
props.put("linger.ms", 10);             // 等待 10ms 凑批
props.put("buffer.memory", 33554432);   // 发送缓冲区 32MB
props.put("compression.type", "lz4");   // 压缩
```

---

## 三、预计算模式（Pre-computation）

### 3.1 物化视图

```sql
-- 场景：商品列表页需要显示每个商品的评分、销量、评价数
-- 实时聚合太慢（JOIN + GROUP BY 多张表）

-- 创建物化表
CREATE TABLE product_summary (
    product_id BIGINT PRIMARY KEY,
    avg_rating DECIMAL(3,2),
    total_sales INT,
    review_count INT,
    updated_at DATETIME,
    INDEX idx_rating (avg_rating DESC),
    INDEX idx_sales (total_sales DESC)
);

-- 定时更新（每 5 分钟）
INSERT INTO product_summary (product_id, avg_rating, total_sales, review_count, updated_at)
SELECT
    p.id,
    COALESCE(AVG(r.rating), 0),
    COALESCE(SUM(oi.quantity), 0),
    COUNT(DISTINCT r.id),
    NOW()
FROM product p
LEFT JOIN review r ON r.product_id = p.id
LEFT JOIN order_item oi ON oi.product_id = p.id
GROUP BY p.id
ON DUPLICATE KEY UPDATE
    avg_rating = VALUES(avg_rating),
    total_sales = VALUES(total_sales),
    review_count = VALUES(review_count),
    updated_at = NOW();
```

### 3.2 计数器预计算

```java
// 场景：显示"点赞数"，不要每次 COUNT(*)
// 方案：维护独立计数器

// Redis 计数器（实时性好）
public long getLikeCount(Long articleId) {
    return redis.opsForValue().increment("article:likes:" + articleId, 0);
}

public void like(Long userId, Long articleId) {
    // 去重
    Boolean added = redis.opsForSet().add("article:likers:" + articleId, userId);
    if (Boolean.TRUE.equals(added)) {
        redis.opsForValue().increment("article:likes:" + articleId);
    }
}

// 定时同步到 DB（持久化）
@Scheduled(fixedRate = 60_000)
public void syncLikeCounts() {
    Set<String> keys = redis.keys("article:likes:*");
    for (String key : keys) {
        Long articleId = extractId(key);
        Long count = Long.parseLong(redis.opsForValue().get(key));
        articleMapper.updateLikeCount(articleId, count);
    }
}
```

---

## 四、懒加载模式（Lazy Loading）

### 4.1 延迟初始化

```java
// 场景：某些对象初始化开销大但不一定会被用到

// JDK 方式
public class HeavyService {
    private volatile ExpensiveResource resource;

    public ExpensiveResource getResource() {
        if (resource == null) { // first check (no lock)
            synchronized (this) {
                if (resource == null) { // second check (with lock)
                    resource = new ExpensiveResource(); // 只在首次访问时创建
                }
            }
        }
        return resource;
    }
}

// 更优雅的方式（利用类加载机制）
public class HeavyService {
    private static class Holder {
        static final ExpensiveResource INSTANCE = new ExpensiveResource();
    }

    public ExpensiveResource getResource() {
        return Holder.INSTANCE; // 首次调用时才加载内部类
    }
}
```

### 4.2 JPA 懒加载

```java
@Entity
public class Order {
    @Id
    private Long id;

    // 默认 EAGER → 每次查 Order 都会查 items
    // 改为 LAZY → 只在访问 items 时才查询
    @OneToMany(mappedBy = "order", fetch = FetchType.LAZY)
    private List<OrderItem> items;

    // Blob 字段也应该懒加载
    @Basic(fetch = FetchType.LAZY)
    @Lob
    private byte[] attachment;
}

// 注意 N+1 问题：
// 查 100 个 Order → 1 次查询
// 遍历访问每个 Order.items → 100 次查询（N+1）

// 解决：需要 items 时用 JOIN FETCH
@Query("SELECT o FROM Order o JOIN FETCH o.items WHERE o.userId = :userId")
List<Order> findWithItems(@Param("userId") Long userId);
```

---

## 五、无锁设计

### 5.1 CAS（Compare-And-Swap）

```java
// AtomicInteger 内部使用 CAS
AtomicInteger counter = new AtomicInteger(0);
counter.incrementAndGet(); // 无锁自增

// CAS 循环（自定义原子操作）
AtomicReference<BigDecimal> balance = new AtomicReference<>(BigDecimal.ZERO);

public void addBalance(BigDecimal amount) {
    BigDecimal oldVal, newVal;
    do {
        oldVal = balance.get();
        newVal = oldVal.add(amount);
    } while (!balance.compareAndSet(oldVal, newVal));
    // 如果 CAS 失败（值被其他线程改了），重试
}

// LongAdder：比 AtomicLong 更快的高并发计数器
LongAdder counter = new LongAdder();
counter.increment();     // 分段累加，减少 CAS 争用
long total = counter.sum(); // 汇总
```

### 5.2 Disruptor（高性能队列）

```java
// Disruptor 比 BlockingQueue 快一个数量级
// 原理：环形数组 + CAS + CPU 缓存行填充

// 1. 定义事件
public class OrderEvent {
    private long orderId;
    private BigDecimal amount;
    // getters/setters
}

// 2. 定义事件处理器
public class OrderEventHandler implements EventHandler<OrderEvent> {
    @Override
    public void onEvent(OrderEvent event, long sequence, boolean endOfBatch) {
        processOrder(event);
    }
}

// 3. 创建 Disruptor
Disruptor<OrderEvent> disruptor = new Disruptor<>(
    OrderEvent::new,           // 事件工厂
    1024 * 1024,               // Ring Buffer 大小（必须是 2 的幂）
    DaemonThreadFactory.INSTANCE,
    ProducerType.MULTI,        // 多生产者
    new YieldingWaitStrategy() // 等待策略
);

disruptor.handleEventsWith(new OrderEventHandler());
disruptor.start();

// 4. 发布事件
RingBuffer<OrderEvent> ringBuffer = disruptor.getRingBuffer();
long sequence = ringBuffer.next();
try {
    OrderEvent event = ringBuffer.get(sequence);
    event.setOrderId(12345);
    event.setAmount(new BigDecimal("99.99"));
} finally {
    ringBuffer.publish(sequence);
}
```

### 5.3 等待策略对比

| 策略 | CPU 占用 | 延迟 | 适用场景 |
|------|----------|------|----------|
| BusySpinWaitStrategy | 极高（100%） | 最低 | 超低延迟（独占 CPU 核） |
| YieldingWaitStrategy | 高 | 低 | 低延迟 |
| SleepingWaitStrategy | 低 | 中 | 通用 |
| BlockingWaitStrategy | 最低 | 高 | CPU 资源有限 |

---

## 六、零拷贝（Zero-Copy）

### 6.1 传统 IO vs 零拷贝

```
传统文件传输（4 次拷贝 + 4 次上下文切换）：
  磁盘 → 内核缓冲区 → 用户缓冲区 → Socket 缓冲区 → 网卡

零拷贝 sendfile（2 次拷贝 + 2 次上下文切换）：
  磁盘 → 内核缓冲区 → 网卡（DMA 直传）
  数据不经过用户空间！
```

### 6.2 Java 零拷贝

```java
// 1. transferTo / transferFrom（底层用 sendfile）
public void sendFile(File file, SocketChannel socketChannel) throws IOException {
    try (FileChannel fileChannel = FileChannel.open(file.toPath())) {
        long position = 0;
        long remaining = fileChannel.size();
        while (remaining > 0) {
            long transferred = fileChannel.transferTo(position, remaining, socketChannel);
            position += transferred;
            remaining -= transferred;
        }
    }
}

// 2. mmap（内存映射文件）
public void readWithMmap(File file) throws IOException {
    try (FileChannel channel = FileChannel.open(file.toPath())) {
        MappedByteBuffer buffer = channel.map(
            FileChannel.MapMode.READ_ONLY, 0, channel.size());
        // buffer 直接映射到文件，读 buffer 就是读文件
        // 不需要 read() 系统调用
        while (buffer.hasRemaining()) {
            byte b = buffer.get();
        }
    }
}

// 3. DirectByteBuffer（堆外内存）
ByteBuffer directBuffer = ByteBuffer.allocateDirect(1024 * 1024);
// 数据不在 JVM 堆中，避免 GC 拷贝
// 适合大量 IO 操作（Netty 默认使用）

// 注意：DirectByteBuffer 分配开销大，应该池化复用
```

### 6.3 Nginx 零拷贝

```nginx
# Nginx 默认启用 sendfile
http {
    sendfile on;            # 开启 sendfile 零拷贝
    tcp_nopush on;          # 配合 sendfile 使用，减少网络包
    tcp_nodelay on;         # 小数据包立即发送
}
```

---

## 七、压缩策略

### 7.1 传输压缩

```nginx
# Nginx gzip 配置
http {
    gzip on;
    gzip_min_length 1024;         # 小于 1KB 不压缩（压缩后可能更大）
    gzip_comp_level 4;            # 压缩级别 1-9（4 是性价比最佳）
    gzip_types
        text/plain
        text/css
        application/json
        application/javascript
        text/xml
        application/xml;
    gzip_vary on;                 # 添加 Vary: Accept-Encoding 头
}
```

```java
// Spring Boot 压缩
server:
  compression:
    enabled: true
    min-response-size: 1024
    mime-types: application/json,text/html,text/css,application/javascript
```

### 7.2 压缩算法对比

| 算法 | 压缩率 | 压缩速度 | 解压速度 | 适用场景 |
|------|--------|----------|----------|----------|
| gzip | 高 | 慢 | 中 | HTTP 传输（兼容性最好） |
| zstd | 很高 | 快 | 很快 | 通用（推荐新项目） |
| snappy | 低 | 很快 | 很快 | 实时计算（速度优先） |
| lz4 | 中 | 最快 | 最快 | 日志/消息队列 |
| brotli | 最高 | 最慢 | 快 | 静态资源预压缩 |

### 7.3 存储压缩

```sql
-- MySQL InnoDB 页压缩
CREATE TABLE logs (
    id BIGINT PRIMARY KEY,
    message TEXT,
    created_at DATETIME
) ROW_FORMAT=COMPRESSED KEY_BLOCK_SIZE=8;
-- 节省 50-70% 存储空间，但 CPU 开销增加 10-20%
```

```java
// Kafka 消息压缩
props.put("compression.type", "lz4");  // 推荐 lz4（速度 vs 压缩率平衡）
// 批量消息压缩效果更好，配合 batch.size 使用
```

### 7.4 选型建议

```
需要决定压缩算法？
│
├── HTTP API 响应
│   ├── 需要广泛兼容 → gzip（所有浏览器支持）
│   └── 新项目/内部服务 → zstd（更好的压缩率和速度）
│
├── 消息队列
│   └── lz4（Kafka 推荐）或 zstd
│
├── 日志存储
│   └── zstd（压缩率高 + 解压快）
│
├── 实时计算中间结果
│   └── snappy 或 lz4（速度优先）
│
└── 静态资源（预压缩）
    └── brotli（压缩率最高，可离线压缩）
```

---

## 八、模式选型速查表

| 模式 | 解决的问题 | 代价 | 收益 |
|------|------------|------|------|
| 对象池 | 对象创建开销大 | 池管理复杂度 | 减少创建/销毁开销 |
| 批处理 | 频繁小 IO 操作 | 增加延迟（攒批） | 减少网络往返/系统调用 |
| 预计算 | 实时计算太慢 | 数据一致性延迟 | 查询速度数量级提升 |
| 懒加载 | 不必要的初始化 | 首次访问延迟 | 减少启动时间/内存 |
| 无锁设计 | 锁竞争瓶颈 | 代码复杂度 | 消除锁开销 |
| 零拷贝 | 数据拷贝开销 | API 复杂度 | 减少 CPU 和内存开销 |
| 压缩 | 带宽/存储不足 | CPU 开销 | 减少 IO/存储 |

### 使用原则

1. **先度量后优化**——确认瓶颈在哪再选模式
2. **简单方案优先**——能用批处理解决的，不要上 Disruptor
3. **注意代价**——每种模式都有 trade-off，不是银弹
4. **组合使用**——批处理 + 压缩，懒加载 + 缓存
