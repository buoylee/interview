# 并发性能排查

## 概述

并发性能问题是 Java 后端最难排查的一类问题 —— 它们往往不稳定复现、难以用传统手段定位、且修复不当可能引入新的正确性问题。本文覆盖锁竞争可视化、线程池调优、False Sharing、volatile 开销和 ThreadLocal 泄漏等核心主题。

---

## 1. 锁竞争可视化

### 方法一：JFR 的 Java Monitor Blocked 事件

```bash
# 启动 JFR 录制，使用 profile 配置（包含锁事件）
jcmd <pid> JFR.start settings=profile duration=60s filename=/tmp/lock-analysis.jfr

# 在 JMC 中分析：
# → Thread 视图 → Lock Instances
# 可以看到：
# - 哪些锁被等待最多
# - 每次等待的平均时间
# - 锁的持有者线程
# - 等待者线程和调用栈
```

### 方法二：async-profiler lock 模式

```bash
# 采集锁竞争火焰图
./asprof -e lock -d 30 -f /tmp/lock.html <pid>

# 设置阈值，只记录等待超过 1ms 的锁
./asprof -e lock -d 30 -i 1ms -f /tmp/lock.html <pid>

# 火焰图解读：
# - 栈顶宽帧 = 竞争最激烈的锁操作
# - 可以看到是 synchronized 锁还是 ReentrantLock
# - 可以追溯到业务代码的调用链
```

### 方法三：Thread Dump 看锁等待

```bash
# 采集多次 Thread Dump
for i in 1 2 3; do jstack <pid> > /tmp/tdump-$i.txt; sleep 5; done

# 统计 BLOCKED 线程数量
grep -c "BLOCKED" /tmp/tdump-*.txt

# 统计最热的锁地址
grep "waiting to lock" /tmp/tdump-1.txt | sort | uniq -c | sort -rn
# 输出：
#   45 - waiting to lock <0x00000007abc12345>
#    3 - waiting to lock <0x00000007def67890>
# → 0x00000007abc12345 这把锁最热，45 个线程在等
```

---

## 2. 线程池调优

### 核心参数

```java
ThreadPoolExecutor executor = new ThreadPoolExecutor(
    corePoolSize,       // 核心线程数：常驻线程
    maximumPoolSize,    // 最大线程数：高峰时扩展到的上限
    keepAliveTime,      // 非核心线程的空闲存活时间
    TimeUnit.SECONDS,
    workQueue,          // 任务队列
    threadFactory,      // 线程工厂（建议自定义线程名）
    rejectedHandler     // 拒绝策略
);
```

### 线程数计算

#### CPU 密集型任务

```
核心线程数 = CPU 核心数 + 1

理由：
- CPU 密集型任务几乎不会阻塞，线程数 ≈ CPU 核心数即可打满 CPU
- +1 是为了当某个线程偶尔因为页缺失等原因暂停时，有备用线程保持 CPU 利用率
```

```java
// CPU 密集型线程池
int cpuCores = Runtime.getRuntime().availableProcessors();
ThreadPoolExecutor cpuPool = new ThreadPoolExecutor(
    cpuCores + 1,
    cpuCores + 1,
    0, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(1000),
    new ThreadFactoryBuilder().setNameFormat("cpu-worker-%d").build(),
    new ThreadPoolExecutor.CallerRunsPolicy()
);
```

#### I/O 密集型任务

```
核心线程数 = CPU 核心数 * (1 + I/O 等待时间 / CPU 计算时间)

示例：
- 4 核 CPU
- 一个请求中：CPU 计算 10ms，等待数据库 90ms
- 核心线程数 = 4 * (1 + 90/10) = 40

这个公式是理论值，实际需要通过压测验证和调整
```

```java
// I/O 密集型线程池
ThreadPoolExecutor ioPool = new ThreadPoolExecutor(
    40,                 // 核心线程数
    60,                 // 最大线程数（突发流量缓冲）
    60, TimeUnit.SECONDS,
    new LinkedBlockingQueue<>(2000),
    new ThreadFactoryBuilder().setNameFormat("io-worker-%d").build(),
    new ThreadPoolExecutor.CallerRunsPolicy()
);
```

### 队列选择

| 队列类型 | 特点 | 适用场景 |
|---------|------|---------|
| `LinkedBlockingQueue(n)` | 有界队列，超过容量触发拒绝策略 | **推荐**，大多数场景 |
| `SynchronousQueue` | 无容量，直接交付 | 需要快速响应，配合大的 maximumPoolSize |
| `ArrayBlockingQueue(n)` | 有界，基于数组，性能稍好 | 高吞吐场景 |
| `LinkedBlockingQueue()` | **无界队列** | **不推荐**！maximumPoolSize 永远不会生效，可能 OOM |

### 拒绝策略

| 策略 | 行为 | 适用场景 |
|------|------|---------|
| `AbortPolicy` | 抛出 RejectedExecutionException | 默认策略，需要调用方处理异常 |
| `CallerRunsPolicy` | 由提交任务的线程直接执行 | **推荐**，天然限流，不丢弃任务 |
| `DiscardPolicy` | 静默丢弃 | 可容忍丢失的非关键任务 |
| `DiscardOldestPolicy` | 丢弃队列中最老的任务 | 只关心最新任务的场景 |

### 监控线程池

```java
// 关键监控指标
ScheduledExecutorService monitor = Executors.newSingleThreadScheduledExecutor();
monitor.scheduleAtFixedRate(() -> {
    log.info("Pool stats: active={}, poolSize={}, queue={}, completed={}",
        executor.getActiveCount(),          // 活跃线程数
        executor.getPoolSize(),             // 当前线程数
        executor.getQueue().size(),         // 队列积压
        executor.getCompletedTaskCount()    // 已完成任务数
    );
}, 0, 10, TimeUnit.SECONDS);

// 告警条件：
// 1. queue.size() 持续增长 → 处理速度跟不上提交速度
// 2. activeCount == maximumPoolSize → 线程全部在忙，新任务只能排队
// 3. rejectedCount > 0 → 已经开始拒绝任务
```

---

## 3. False Sharing

### 什么是 False Sharing

现代 CPU 的缓存以 **Cache Line**（通常 64 字节）为单位加载和失效。当两个线程频繁修改在同一 Cache Line 中的不同变量时，两个 CPU 核心的缓存会反复失效，导致性能急剧下降。

```
CPU Core 0 Cache              CPU Core 1 Cache
┌──────────────────────┐      ┌──────────────────────┐
│ Cache Line:          │      │ Cache Line:          │
│ [counter_A][counter_B]│     │ [counter_A][counter_B]│
└──────────────────────┘      └──────────────────────┘
        ↑                              ↑
   Thread-0 修改 counter_A        Thread-1 修改 counter_B
   → 整条 Cache Line 失效！       → 整条 Cache Line 失效！
   → Core 1 必须重新加载          → Core 0 必须重新加载
```

### 演示与测试

```java
// 有 False Sharing 问题的代码
public class FalseSharingDemo {
    static volatile long counter_A;  // 这两个字段可能在同一 Cache Line
    static volatile long counter_B;

    public static void main(String[] args) throws InterruptedException {
        Thread t1 = new Thread(() -> {
            for (long i = 0; i < 1_000_000_000L; i++) counter_A++;
        });
        Thread t2 = new Thread(() -> {
            for (long i = 0; i < 1_000_000_000L; i++) counter_B++;
        });

        long start = System.nanoTime();
        t1.start(); t2.start();
        t1.join(); t2.join();
        System.out.println("Time: " + (System.nanoTime() - start) / 1_000_000 + " ms");
    }
}
// 典型结果：约 8000-12000ms（因为 False Sharing 导致缓存行反复失效）
```

### 使用 @Contended 解决

```java
// JDK 8+：使用 @Contended 注解强制填充
// 需要 JVM 参数 -XX:-RestrictContended
import sun.misc.Contended;  // JDK 8
// import jdk.internal.vm.annotation.Contended;  // JDK 9+

public class NoFalseSharingDemo {
    @Contended
    static volatile long counter_A;  // 独占 Cache Line

    @Contended
    static volatile long counter_B;  // 独占 Cache Line

    // 同样的测试代码...
    // 典型结果：约 3000-4000ms（性能提升 2-3 倍）
}
```

```bash
# 启用 @Contended（JDK 9+ 需要 add-opens）
java -XX:-RestrictContended \
     --add-opens java.base/jdk.internal.vm.annotation=ALL-UNNAMED \
     FalseSharingDemo
```

### 手动填充

```java
// 不使用 @Contended 的手动填充方式
public class PaddedCounter {
    volatile long value;
    // 填充 7 个 long（7 * 8 = 56 字节），加上 value 的 8 字节 = 64 字节 = 一条 Cache Line
    long p1, p2, p3, p4, p5, p6, p7;
}
```

**实际影响**：JDK 内部的 `LongAdder`、`Striped64`、`ConcurrentHashMap` 的计数器等高性能并发类都使用了 `@Contended` 来避免 False Sharing。

---

## 4. volatile 开销

### volatile 的作用

`volatile` 通过插入内存屏障（Memory Barrier）保证：
1. **可见性**：一个线程的写入对其他线程立即可见
2. **有序性**：禁止指令重排序

### 开销分析

```java
// volatile 读：在读后插入 LoadLoad + LoadStore 屏障
// volatile 写：在写前插入 StoreStore 屏障，在写后插入 StoreLoad 屏障

// StoreLoad 屏障是最重的，在 x86 上会产生 lock 前缀的指令
// 强制将 CPU store buffer 刷新到缓存/内存
```

### 什么时候该用

```java
// 该用 volatile 的场景：
// 1. 状态标志
private volatile boolean running = true;
public void stop() { running = false; }
public void run() {
    while (running) { /* work */ }
}

// 2. 双重检查锁定的单例
private static volatile Singleton INSTANCE;

// 3. 一写多读的简单变量
private volatile long lastUpdateTime;
```

### 什么时候不该用

```java
// 不该用 volatile 的场景：

// 1. 复合操作（volatile 不保证原子性）
private volatile int count;
count++;  // 这不是原子的！读-改-写三步操作
// 应该用 AtomicInteger 或 LongAdder

// 2. 需要锁保护的不变量
// 如果多个字段需要保持一致性，volatile 做不到
// 应该用 synchronized 或 Lock

// 3. 高频读写的计数器（volatile 写开销大）
// 应该用 LongAdder（分段计数，最后汇总）
```

### 性能对比

```java
// 简单基准测试（JMH 结果）
// 普通变量读写：   ~1 ns
// volatile 读：    ~2-5 ns（多一次内存屏障检查）
// volatile 写：    ~20-40 ns（StoreLoad 屏障，需要刷新 store buffer）
// AtomicLong.CAS：~30-50 ns（竞争情况下更高）
// LongAdder.add： ~5-10 ns（低竞争），比 AtomicLong 好得多（高竞争）
```

---

## 5. ThreadLocal 泄漏

### 问题场景

在线程池环境下，线程是复用的。如果 `ThreadLocal` 使用后不 `remove()`，数据会一直留在线程的 `ThreadLocalMap` 中：

```java
// 危险代码
private static final ThreadLocal<UserContext> USER_CONTEXT = new ThreadLocal<>();

public void handleRequest(HttpServletRequest request) {
    UserContext ctx = new UserContext(request.getHeader("user-id"));
    USER_CONTEXT.set(ctx);

    // 处理业务逻辑...
    processRequest();

    // 忘记 remove！
    // 线程归还线程池后，UserContext 对象不会被回收
    // 下一个请求复用该线程时，可能读到上一个请求的用户数据（安全问题！）
    // 且随着时间推移，每个线程都积累越来越多的无用对象（内存泄漏）
}
```

### 正确用法

```java
// 正确用法：始终在 finally 中 remove
public void handleRequest(HttpServletRequest request) {
    try {
        UserContext ctx = new UserContext(request.getHeader("user-id"));
        USER_CONTEXT.set(ctx);
        processRequest();
    } finally {
        USER_CONTEXT.remove();  // 必须 remove！
    }
}

// 更好的方式：使用 Spring 的拦截器统一处理
@Component
public class UserContextInterceptor implements HandlerInterceptor {

    @Override
    public boolean preHandle(HttpServletRequest request, ...) {
        UserContext ctx = new UserContext(request.getHeader("user-id"));
        USER_CONTEXT.set(ctx);
        return true;
    }

    @Override
    public void afterCompletion(HttpServletRequest request, ...) {
        USER_CONTEXT.remove();  // 统一清理
    }
}
```

### 排查 ThreadLocal 泄漏

```bash
# 方法一：Heap Dump 分析
# 在 MAT 中搜索 ThreadLocal
# OQL: SELECT * FROM java.lang.ThreadLocal$ThreadLocalMap$Entry

# 方法二：Arthas 查看线程的 ThreadLocalMap
[arthas@12345]$ ognl '#thread=@java.lang.Thread@currentThread(), #thread.threadLocals'

# 方法三：查看 Thread 对象的 threadLocals 字段
# 在 MAT 中：
# 1. 打开 Histogram → 搜索 Thread
# 2. 右键某个 Thread 实例 → List Objects → with outgoing references
# 3. 展开 threadLocals → table → 查看每个 Entry 的 value
# 如果看到大量业务对象被 ThreadLocalMap 引用，就是泄漏
```

### ThreadLocal 内部机制

```
Thread 对象
  └─ threadLocals (ThreadLocalMap)
       └─ Entry[] table
            ├─ Entry(key=WeakReference<ThreadLocal>, value=UserContext)
            ├─ Entry(key=WeakReference<ThreadLocal>, value=TraceContext)
            └─ Entry(key=null, value=OldData)  ← key 被 GC 了，value 还在！
```

`ThreadLocalMap` 的 key 是对 `ThreadLocal` 对象的弱引用。当 `ThreadLocal` 对象被回收后，key 变为 null，但 value 仍然被强引用无法回收。虽然 `ThreadLocal` 在 `get()/set()` 时会清理这些 stale entry，但如果不再调用 `get()/set()`，这些 value 就永远无法回收。

**根本解决方案**：用完就 `remove()`。不要依赖弱引用的清理机制。

---

## 实践建议

1. **锁竞争是性能杀手**：如果发现大量 BLOCKED 线程，优先解决锁竞争而不是加机器
2. **线程池必须有界**：永远不要用无界队列的线程池（`Executors.newCachedThreadPool()` 在极端情况下也可能 OOM）
3. **False Sharing 在高频场景才值得关注**：普通业务代码不需要考虑 Cache Line 对齐
4. **ThreadLocal 的 remove() 是强制要求**：团队应该在 Code Review 中强制检查

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| 锁竞争可视化 | JFR Lock 事件 / async-profiler lock 模式 / Thread Dump |
| 线程池线程数 | CPU 密集 = cores+1，I/O 密集 = cores * (1 + wait/compute) |
| 队列选择 | 用有界队列，不要用无界的 LinkedBlockingQueue() |
| False Sharing | 同一 Cache Line 被多线程频繁修改，用 @Contended 解决 |
| volatile | 保证可见性和有序性，写开销大，不保证原子性 |
| ThreadLocal 泄漏 | 线程池复用线程，不 remove 导致数据残留和内存泄漏 |
