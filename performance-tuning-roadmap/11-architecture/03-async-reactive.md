# 异步与响应式编程

同步阻塞模型中，一个线程在等待 IO（网络/磁盘）时完全闲置，但仍占用内存（每线程约 1MB 栈空间）。当并发量达到数千时，线程数成为瓶颈——不是 CPU 不够用，而是线程切换和内存开销拖垮了系统。异步和响应式编程的核心目标是：用少量线程处理大量并发 IO，让 CPU 不浪费在"等待"上。

---

## 一、异步编程模型演进

### 1.1 演进路径

```
Callback（回调地狱）
    ↓ 解决嵌套问题
Future / Promise（可组合的异步结果）
    ↓ 解决背压和流式处理
Reactive Streams（响应式流）
    ↓ 语言原生支持
async/await（语法糖，本质还是 Future）
    ↓ 更轻量的运行时
Virtual Threads / Goroutine（轻量级线程）
```

### 1.2 模型对比

| 模型 | 代表 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|----------|
| 同步阻塞 | Servlet/JDBC | 简单直观 | 线程占用高 | 低并发/CPU 密集 |
| Callback | Node.js 早期 | 非阻塞 | 回调地狱 | 简单异步 |
| Future/Promise | CompletableFuture | 可组合 | 异常处理复杂 | 多步异步编排 |
| Reactive | Reactor/RxJava | 背压/流控 | 学习曲线陡峭 | 高并发 IO 密集 |
| async/await | Python asyncio/Kotlin | 写法接近同步 | 传染性（全链路异步） | 通用异步 |
| 轻量线程 | Virtual Thread/Goroutine | 写法同步，运行异步 | 生态兼容问题 | 新项目首选 |

---

## 二、Java CompletableFuture 实战

### 2.1 基础用法

```java
// 异步执行任务
CompletableFuture<User> userFuture = CompletableFuture.supplyAsync(
    () -> userService.getUser(userId),
    customExecutor  // 指定线程池！不要用默认的 ForkJoinPool
);

// 链式转换
CompletableFuture<String> nameFuture = userFuture
    .thenApply(user -> user.getName())
    .thenApply(name -> "Hello, " + name);

// 获取结果（带超时）
String greeting = nameFuture.get(3, TimeUnit.SECONDS);
```

### 2.2 并行调用 + 结果合并

```java
// 场景：商品详情页需要并行查询多个服务
public ProductDetail getProductDetail(Long productId) {
    // 并行发起 3 个请求
    CompletableFuture<Product> productFuture = CompletableFuture.supplyAsync(
        () -> productService.getProduct(productId), ioExecutor);

    CompletableFuture<List<Review>> reviewsFuture = CompletableFuture.supplyAsync(
        () -> reviewService.getReviews(productId), ioExecutor);

    CompletableFuture<Inventory> inventoryFuture = CompletableFuture.supplyAsync(
        () -> inventoryService.getInventory(productId), ioExecutor);

    // 等待全部完成
    CompletableFuture.allOf(productFuture, reviewsFuture, inventoryFuture)
        .orTimeout(3, TimeUnit.SECONDS)  // Java 9+: 整体超时
        .join();

    return ProductDetail.builder()
        .product(productFuture.join())
        .reviews(reviewsFuture.join())
        .inventory(inventoryFuture.join())
        .build();
}
```

### 2.3 异常处理

```java
CompletableFuture<User> future = CompletableFuture
    .supplyAsync(() -> userService.getUser(userId))
    .exceptionally(ex -> {
        log.error("查询用户失败", ex);
        return User.defaultUser(); // 降级返回默认用户
    });

// 更精细的异常处理
CompletableFuture<Result> future = CompletableFuture
    .supplyAsync(() -> riskyOperation())
    .handle((result, ex) -> {
        if (ex != null) {
            // 区分异常类型
            if (ex.getCause() instanceof TimeoutException) {
                return Result.timeout();
            }
            return Result.error(ex.getMessage());
        }
        return Result.success(result);
    });
```

### 2.4 常见陷阱

```java
// 陷阱 1：使用默认线程池
// CompletableFuture 默认用 ForkJoinPool.commonPool()
// 这是全局共享的，IO 任务会饿死 CPU 任务
CompletableFuture.supplyAsync(() -> blockingIO()); // 危险！

// 正确做法：IO 任务用独立线程池
ExecutorService ioExecutor = Executors.newFixedThreadPool(
    20, new ThreadFactoryBuilder().setNameFormat("io-pool-%d").build());
CompletableFuture.supplyAsync(() -> blockingIO(), ioExecutor);

// 陷阱 2：忽略异常
CompletableFuture.runAsync(() -> {
    throw new RuntimeException("silently swallowed!"); // 没人知道出错了
});

// 正确做法：始终处理异常
CompletableFuture.runAsync(() -> riskyOperation())
    .whenComplete((result, ex) -> {
        if (ex != null) log.error("异步任务失败", ex);
    });

// 陷阱 3：join() 在主线程中阻塞
@GetMapping("/api/data")
public Data getData() {
    return asyncService.fetchData().join(); // 阻塞了 Tomcat 线程！
    // 应该返回 CompletableFuture 或用 WebFlux
}
```

---

## 三、Spring WebFlux 与 Project Reactor

### 3.1 核心概念

```java
// Mono：0 或 1 个元素的异步序列
Mono<User> user = userRepository.findById(userId);

// Flux：0 到 N 个元素的异步序列
Flux<Order> orders = orderRepository.findByUserId(userId);
```

### 3.2 响应式 Controller

```java
@RestController
@RequestMapping("/api/users")
public class UserController {

    @GetMapping("/{id}")
    public Mono<User> getUser(@PathVariable Long id) {
        return userService.findById(id)  // 不阻塞线程
            .timeout(Duration.ofSeconds(3))
            .onErrorReturn(User.defaultUser());
    }

    @GetMapping("/{id}/detail")
    public Mono<UserDetail> getUserDetail(@PathVariable Long id) {
        // 并行查询 + 合并
        Mono<User> userMono = userService.findById(id);
        Mono<List<Order>> ordersMono = orderService.findByUserId(id)
            .collectList();
        Mono<UserPrefs> prefsMono = prefsService.findByUserId(id);

        return Mono.zip(userMono, ordersMono, prefsMono)
            .map(tuple -> UserDetail.builder()
                .user(tuple.getT1())
                .orders(tuple.getT2())
                .prefs(tuple.getT3())
                .build());
    }

    @GetMapping(value = "/stream", produces = MediaType.TEXT_EVENT_STREAM_VALUE)
    public Flux<User> streamUsers() {
        return userService.findAll()
            .delayElements(Duration.ofMillis(100)); // SSE 推送
    }
}
```

### 3.3 WebFlux vs Spring MVC 性能对比

| 指标 | Spring MVC (Tomcat) | WebFlux (Netty) |
|------|--------------------|--------------------|
| 线程数 | 200（默认） | 2 * CPU 核数 |
| 每线程内存 | ~1MB | ~几 KB（事件循环） |
| 10K 并发连接 | ~10GB 内存 | ~几十 MB |
| 适用场景 | CRUD/传统业务 | 网关/高并发 IO |
| 开发复杂度 | 低 | 高 |
| 调试难度 | 低 | 高（堆栈难读） |

**何时用 WebFlux**：高并发 IO 密集型（如 API 网关、消息推送）。CRUD 应用不要用——复杂度收益不成正比。

---

## 四、背压（Backpressure）机制

### 4.1 为什么需要背压

```
生产者（1000 msg/s）──→ 消费者（100 msg/s）
                           ↑
                      没有背压：OOM
                      有背压：通知生产者降速
```

### 4.2 Reactor 中的背压

```java
// 基于请求的背压
Flux.range(1, 1_000_000)
    .subscribe(new BaseSubscriber<Integer>() {
        @Override
        protected void hookOnSubscribe(Subscription s) {
            request(10); // 初始请求 10 个元素
        }

        @Override
        protected void hookOnNext(Integer value) {
            processSlowly(value);
            request(1); // 每处理完 1 个，再请求 1 个
        }
    });

// 溢出策略
Flux.create(sink -> {
    // 高速生产
    for (int i = 0; i < 1_000_000; i++) {
        sink.next(i);
    }
}, FluxSink.OverflowStrategy.DROP)  // 消费不过来就丢弃
    .onBackpressureBuffer(1000)      // 或者缓冲 1000 个
    .onBackpressureDrop(dropped ->    // 丢弃时的回调
        log.warn("Dropped: {}", dropped))
    .subscribe(this::process);
```

### 4.3 背压策略对比

| 策略 | 行为 | 适用场景 |
|------|------|----------|
| BUFFER | 缓冲到内存（可能 OOM） | 短暂突发 |
| DROP | 丢弃新数据 | 实时数据（旧数据无价值） |
| LATEST | 只保留最新 | 监控/状态更新 |
| ERROR | 抛异常 | 不允许丢数据 |
| REQUEST | 按需请求（Pull 模式） | 精确流控 |

---

## 五、Go 的 goroutine + channel 模型

Go 天生异步——goroutine 是用户态轻量线程（初始栈 2KB），channel 用于协程间通信。

### 5.1 并行请求模式

```go
func getProductDetail(ctx context.Context, productID int64) (*ProductDetail, error) {
    g, ctx := errgroup.WithContext(ctx)

    var product *Product
    var reviews []*Review
    var inventory *Inventory

    // 并行请求
    g.Go(func() error {
        var err error
        product, err = productService.Get(ctx, productID)
        return err
    })
    g.Go(func() error {
        var err error
        reviews, err = reviewService.List(ctx, productID)
        return err
    })
    g.Go(func() error {
        var err error
        inventory, err = inventoryService.Get(ctx, productID)
        return err
    })

    // 等待全部完成（任一失败则取消其他）
    if err := g.Wait(); err != nil {
        return nil, err
    }

    return &ProductDetail{
        Product:   product,
        Reviews:   reviews,
        Inventory: inventory,
    }, nil
}
```

### 5.2 Fan-out / Fan-in 模式

```go
// Fan-out: 多个 goroutine 从同一个 channel 读取
func fanOut(ctx context.Context, input <-chan Task, workers int) <-chan Result {
    results := make(chan Result, workers)
    var wg sync.WaitGroup

    for i := 0; i < workers; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for task := range input {
                select {
                case <-ctx.Done():
                    return
                case results <- process(task):
                }
            }
        }()
    }

    go func() {
        wg.Wait()
        close(results)
    }()

    return results
}
```

### 5.3 限制并发数

```go
// 使用带缓冲的 channel 作为信号量
func processWithLimit(tasks []Task, maxConcurrency int) []Result {
    sem := make(chan struct{}, maxConcurrency)
    results := make([]Result, len(tasks))
    var wg sync.WaitGroup

    for i, task := range tasks {
        wg.Add(1)
        sem <- struct{}{} // 获取信号量（达到上限时阻塞）
        go func(idx int, t Task) {
            defer wg.Done()
            defer func() { <-sem }() // 释放信号量
            results[idx] = process(t)
        }(i, task)
    }

    wg.Wait()
    return results
}
```

---

## 六、Python asyncio 模型

### 6.1 基础用法

```python
import asyncio
import aiohttp

async def fetch_user(session: aiohttp.ClientSession, user_id: int) -> dict:
    async with session.get(f"http://api/users/{user_id}") as resp:
        return await resp.json()

async def get_product_detail(product_id: int) -> dict:
    async with aiohttp.ClientSession() as session:
        # 并行请求
        product, reviews, inventory = await asyncio.gather(
            fetch_product(session, product_id),
            fetch_reviews(session, product_id),
            fetch_inventory(session, product_id),
        )
        return {
            "product": product,
            "reviews": reviews,
            "inventory": inventory,
        }

# 带超时
async def fetch_with_timeout(url: str, timeout: float = 3.0):
    try:
        async with asyncio.timeout(timeout):  # Python 3.11+
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return await resp.json()
    except asyncio.TimeoutError:
        return None  # 超时降级
```

### 6.2 限制并发

```python
import asyncio

async def process_all(urls: list[str], max_concurrency: int = 20):
    semaphore = asyncio.Semaphore(max_concurrency)

    async def fetch_with_limit(url: str):
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as resp:
                    return await resp.json()

    tasks = [fetch_with_limit(url) for url in urls]
    return await asyncio.gather(*tasks, return_exceptions=True)
```

### 6.3 asyncio 的坑

```python
# 坑 1：在 async 函数中调用同步阻塞代码
async def bad_example():
    result = requests.get("http://api/data")  # 阻塞整个事件循环！

# 正确做法：用 aiohttp 或 run_in_executor
async def good_example():
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, requests.get, "http://api/data")

# 坑 2：创建过多 Task 导致内存爆炸
async def bad_batch():
    tasks = [fetch(url) for url in million_urls]  # 100万个 Task 同时创建
    await asyncio.gather(*tasks)  # OOM

# 正确做法：用信号量控制并发
```

---

## 七、线程模型选择

### 7.1 对比

| 模型 | 实现 | 线程数 | 适用场景 | 代表 |
|------|------|--------|----------|------|
| Thread-per-Request | Tomcat | 200-500 | 传统 CRUD | Spring MVC |
| EventLoop | Netty | CPU 核数 | 高并发网关 | Spring WebFlux |
| Virtual Thread | JDK 21+ | 数百万 | 通用（IO 密集） | Spring MVC + VT |
| Goroutine | Go runtime | 数百万 | 通用 | Go 标准库 |

### 7.2 Java 虚拟线程（JDK 21+）

```java
// Spring Boot 3.2+ 开启虚拟线程
spring.threads.virtual.enabled=true

// 效果：Tomcat 每个请求分配一个虚拟线程
// 写法和同步代码完全一样，但底层不阻塞平台线程

// 手动使用虚拟线程
try (var executor = Executors.newVirtualThreadPerTaskExecutor()) {
    List<Future<User>> futures = userIds.stream()
        .map(id -> executor.submit(() -> userService.getUser(id)))
        .toList();

    List<User> users = futures.stream()
        .map(f -> f.get(3, TimeUnit.SECONDS))
        .toList();
}
```

**虚拟线程注意事项**：
- 不要池化虚拟线程（创建开销极低，池化无意义）
- 避免在虚拟线程中使用 `synchronized`（会 pin 住平台线程），改用 `ReentrantLock`
- JDBC 驱动需要支持（MySQL Connector/J 8.0.33+ 已支持）

---

## 八、异步 vs 同步决策树

```
你的场景是什么？
│
├── CPU 密集型（计算/加密/压缩）
│   └── 用同步 + 线程池，异步没有收益
│
├── IO 密集型（网络调用/数据库/文件）
│   ├── 并发量 < 500 QPS
│   │   └── 同步阻塞足够（Spring MVC + Tomcat）
│   │
│   ├── 并发量 500-5000 QPS
│   │   ├── JDK 21+ 可用？
│   │   │   ├── 是 → 虚拟线程（最简单）
│   │   │   └── 否 → CompletableFuture + 自定义线程池
│   │   └── Go 项目 → goroutine（天然异步）
│   │
│   └── 并发量 > 5000 QPS
│       ├── API 网关/代理 → WebFlux / Netty
│       ├── 流式处理 → Reactive Streams
│       └── Go 项目 → goroutine + channel
│
├── 多个独立的下游调用需要并行
│   └── CompletableFuture.allOf / asyncio.gather / errgroup
│
└── 需要流式推送（SSE/WebSocket）
    └── WebFlux / Reactor
```

### 关键原则

1. **不要为了异步而异步**——同步代码更容易写、调试和维护
2. **先度量再优化**——确认瓶颈确实在线程模型上
3. **异步有传染性**——一旦用了异步，调用链上都要异步
4. **JDK 21 虚拟线程是最佳平衡点**——同步写法 + 异步性能
5. **Go 不需要这个决策**——goroutine 天然解决了这个问题

---

## 九、总结速查

| 语言/框架 | 推荐方案 | 并行编排 | 超时控制 |
|-----------|----------|----------|----------|
| Java 21+ | 虚拟线程 | StructuredTaskScope | Future.get(timeout) |
| Java 17 | CompletableFuture | allOf/anyOf | orTimeout() |
| Java 高并发 | WebFlux/Reactor | Mono.zip/Flux.merge | timeout() |
| Go | goroutine + channel | errgroup | context.WithTimeout |
| Python | asyncio | asyncio.gather | asyncio.timeout |
| Node.js | Promise | Promise.all | AbortController |
