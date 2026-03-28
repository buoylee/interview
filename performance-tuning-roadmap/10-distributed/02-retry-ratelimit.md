# 重试风暴与限流

## 为什么重试和限流必须一起讨论

重试是容错的基本手段，限流是过载保护的基本手段。它们看似无关，实则互为因果：**不当的重试策略会引发重试风暴，需要限流来兜底；而限流触发后的 429 响应又会引发更多重试**。理解两者的相互作用，才能构建真正健壮的分布式系统。

---

## 一、重试风暴成因

### 指数级放大效应

假设调用链有 3 层，每层重试 3 次：

```
Client → A → B → C

C 故障时：
- B 调用 C 失败，重试 3 次 → C 承受 3 倍流量
- A 调用 B 失败（因为 B 也在等 C），重试 3 次
  每次 A 重试都让 B 重试 3 次 → C 承受 3 × 3 = 9 倍流量
- Client 调用 A 失败，重试 3 次
  → C 承受 3 × 3 × 3 = 27 倍流量
```

**N 层调用链，每层重试 R 次，最底层服务承受 R^N 倍流量。**

```
原始流量: 1000 QPS
3 层 × 3 次重试 = 27,000 QPS 打到最底层
```

这就是"重试风暴"——一个本来可以恢复的短暂故障，被重试放大成彻底的雪崩。

### 重试风暴的触发条件

```
                    ┌─────────────┐
                    │ 下游短暂抖动 │
                    └──────┬──────┘
                           ▼
                    ┌─────────────┐
                    │  请求超时失败 │
                    └──────┬──────┘
                           ▼
              ┌────────────────────────┐
              │ 所有上游同时发起重试     │
              └────────────┬───────────┘
                           ▼
              ┌────────────────────────┐
              │ 下游承受 N 倍流量       │
              │ 原本能恢复的也恢复不了了  │
              └────────────┬───────────┘
                           ▼
              ┌────────────────────────┐
              │ 更多超时 → 更多重试      │
              │ 正反馈循环（死亡螺旋）    │
              └────────────────────────┘
```

---

## 二、正确的重试策略

### 指数退避 + 抖动（Exponential Backoff with Jitter）

```
等待时间 = min(base × 2^attempt + random_jitter, max_wait)
```

**为什么需要抖动（Jitter）？** 如果所有客户端都用相同的退避时间，它们会同步重试，形成"惊群效应"。加入随机抖动可以打散重试时间。

```go
// Go 实现
func retryWithBackoff(ctx context.Context, maxRetries int, fn func() error) error {
    baseDelay := 100 * time.Millisecond
    maxDelay := 10 * time.Second

    for attempt := 0; attempt <= maxRetries; attempt++ {
        err := fn()
        if err == nil {
            return nil
        }

        // 不可重试的错误直接返回
        if !isRetryable(err) {
            return fmt.Errorf("non-retryable error: %w", err)
        }

        if attempt == maxRetries {
            return fmt.Errorf("max retries exceeded: %w", err)
        }

        // 指数退避
        delay := baseDelay * time.Duration(1<<uint(attempt))
        if delay > maxDelay {
            delay = maxDelay
        }

        // Full Jitter: 在 [0, delay] 范围内随机
        jitteredDelay := time.Duration(rand.Int63n(int64(delay)))

        log.Printf("retry attempt %d, waiting %v", attempt+1, jitteredDelay)

        select {
        case <-ctx.Done():
            return ctx.Err()
        case <-time.After(jitteredDelay):
        }
    }
    return nil
}

func isRetryable(err error) bool {
    // 只重试瞬时错误，不重试业务错误
    var netErr net.Error
    if errors.As(err, &netErr) && netErr.Timeout() {
        return true
    }
    // gRPC 状态码判断
    code := status.Code(err)
    return code == codes.Unavailable || code == codes.DeadlineExceeded
}
```

```java
// Java - Resilience4j 重试配置
RetryConfig config = RetryConfig.custom()
    .maxAttempts(3)
    .intervalFunction(IntervalFunction.ofExponentialRandomBackoff(
        100,    // 初始间隔 100ms
        2.0,    // 乘数
        0.5,    // 随机因子（±50%）
        10000   // 最大间隔 10s
    ))
    .retryOnException(e -> {
        if (e instanceof CallNotPermittedException) return false; // 断路器打开不重试
        if (e instanceof BusinessException) return false;         // 业务异常不重试
        return true;
    })
    .failAfterMaxAttempts(true)
    .build();

Retry retry = Retry.of("orderService", config);
```

```python
# Python - tenacity 库
from tenacity import (
    retry, stop_after_attempt, wait_exponential_jitter,
    retry_if_exception_type,
)
import httpx

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential_jitter(
        initial=0.1,       # 初始 100ms
        max=10,             # 最大 10s
        jitter=2,           # 抖动范围
    ),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
    before_sleep=lambda state: logging.warning(
        f"Retrying {state.fn.__name__}, attempt {state.attempt_number}"
    ),
)
def call_payment(order_id: str, amount: float) -> dict:
    resp = httpx.post(
        f"{PAYMENT_URL}/pay",
        json={"order_id": order_id, "amount": amount},
        timeout=2.0,
    )
    resp.raise_for_status()
    return resp.json()
```

### 重试策略最佳实践

| 实践 | 说明 |
|------|------|
| 只重试一层 | 整条链路只允许一层做重试，其他层不重试 |
| 只重试幂等操作 | GET、DELETE 可重试，非幂等 POST 需要幂等 Key |
| 限制总重试次数 | 一般 2-3 次够了，超过就走降级 |
| 设置重试预算 | 单位时间内重试请求不超过总请求的 10% |
| 区分可重试错误 | 5xx、超时可重试；4xx（除 429）不重试 |
| 尊重 Retry-After | 服务端返回 429 时携带的 Retry-After 头 |

---

## 三、幂等性保证

### 为什么重试需要幂等

```
Client → POST /orders (创建订单)
  ↓ 超时（请求实际到了服务端，已创建订单）
Client → POST /orders (重试，又创建了一个订单！)
```

### 幂等 Key 方案

```java
// 客户端生成幂等 Key
String idempotencyKey = UUID.randomUUID().toString();

HttpRequest request = HttpRequest.newBuilder()
    .uri(URI.create("https://api.example.com/orders"))
    .header("Idempotency-Key", idempotencyKey)
    .POST(HttpRequest.BodyPublishers.ofString(orderJson))
    .build();

// 服务端处理
@PostMapping("/orders")
public ResponseEntity<Order> createOrder(
        @RequestHeader("Idempotency-Key") String idempotencyKey,
        @RequestBody CreateOrderRequest request) {

    // 1. 检查幂等 Key 是否已处理过
    String cacheKey = "idempotent:" + idempotencyKey;
    String cachedResult = redis.get(cacheKey);
    if (cachedResult != null) {
        // 返回缓存的结果
        return ResponseEntity.ok(objectMapper.readValue(cachedResult, Order.class));
    }

    // 2. 使用分布式锁防并发
    boolean locked = redis.setIfAbsent(cacheKey + ":lock", "1", 30, TimeUnit.SECONDS);
    if (!locked) {
        return ResponseEntity.status(409).build(); // 正在处理中
    }

    try {
        // 3. 执行业务逻辑
        Order order = orderService.create(request);

        // 4. 缓存结果（设置 TTL，建议 24h）
        redis.setex(cacheKey, 86400, objectMapper.writeValueAsString(order));

        return ResponseEntity.ok(order);
    } finally {
        redis.del(cacheKey + ":lock");
    }
}
```

### 去重表方案

```sql
-- 去重表
CREATE TABLE idempotent_record (
    idempotent_key VARCHAR(64) PRIMARY KEY,
    biz_type       VARCHAR(32) NOT NULL,
    biz_result     TEXT,
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_created_at (created_at)  -- 用于定期清理
);

-- 业务操作与去重记录在同一个事务中
BEGIN;
INSERT INTO idempotent_record (idempotent_key, biz_type)
VALUES ('order-create-uuid-xxx', 'CREATE_ORDER')
ON DUPLICATE KEY UPDATE idempotent_key = idempotent_key; -- 忽略重复

-- 如果 affected_rows = 1（新插入），执行业务逻辑
INSERT INTO orders (...) VALUES (...);

-- 更新去重记录的结果
UPDATE idempotent_record SET biz_result = '{"order_id": 12345}'
WHERE idempotent_key = 'order-create-uuid-xxx';
COMMIT;
```

---

## 四、限流算法对比

### 四种主流算法

| 算法 | 原理 | 优点 | 缺点 | 适用场景 |
|------|------|------|------|---------|
| 固定窗口 | 按固定时间窗口计数 | 实现简单 | 窗口边界突发（2倍流量） | 粗粒度限流 |
| 滑动窗口 | 将窗口细分为多个小窗口 | 更平滑 | 内存稍多 | 通用限流 |
| 漏桶 | 固定速率处理，多余排队或丢弃 | 输出平滑 | 不能应对突发 | 流量整形 |
| 令牌桶 | 固定速率产生令牌，允许突发消费 | 允许一定突发 | 实现稍复杂 | API 限流 |

### 固定窗口的边界问题

```
窗口1 [00:00 - 01:00]  限制 100 请求
窗口2 [01:00 - 02:00]  限制 100 请求

在 00:59 来了 100 个请求（窗口1 允许）
在 01:01 来了 100 个请求（窗口2 允许）
→ 2 秒内实际通过了 200 个请求，是限制的 2 倍！
```

### 令牌桶实现

```go
// Go — 标准库的令牌桶
import "golang.org/x/time/rate"

// 每秒 100 个请求，突发允许 200
limiter := rate.NewLimiter(rate.Limit(100), 200)

func handleRequest(w http.ResponseWriter, r *http.Request) {
    if !limiter.Allow() {
        http.Error(w, "rate limit exceeded", http.StatusTooManyRequests)
        return
    }
    // 处理请求
}

// 带等待的限流（排队而非拒绝）
func handleRequestWithWait(w http.ResponseWriter, r *http.Request) {
    ctx, cancel := context.WithTimeout(r.Context(), 2*time.Second)
    defer cancel()

    if err := limiter.Wait(ctx); err != nil {
        http.Error(w, "rate limit exceeded", http.StatusTooManyRequests)
        return
    }
    // 处理请求
}

// 按用户限流
type UserRateLimiter struct {
    mu       sync.Mutex
    limiters map[string]*rate.Limiter
}

func (u *UserRateLimiter) GetLimiter(userID string) *rate.Limiter {
    u.mu.Lock()
    defer u.mu.Unlock()

    if lim, exists := u.limiters[userID]; exists {
        return lim
    }
    // 每个用户每秒 10 请求，突发 20
    lim := rate.NewLimiter(10, 20)
    u.limiters[userID] = lim
    return lim
}
```

---

## 五、客户端限流 vs 服务端限流 vs 中间件限流

### 三种限流位置对比

| 维度 | 客户端限流 | 服务端限流 | 中间件限流 |
|------|-----------|-----------|-----------|
| 位置 | 调用方 SDK | 被调方服务 | 网关/Sidecar |
| 生效时机 | 请求发出前 | 请求到达后 | 请求路由时 |
| 网络开销 | 无 | 有（请求已到） | 有但提前拦截 |
| 配置管理 | 分散在各客户端 | 集中在服务端 | 集中在中间件 |
| 全局视角 | 无（各自限各自） | 单实例视角 | 全局视角 |
| 典型实现 | SDK 内置 | 框架中间件 | Nginx/Envoy/网关 |

### 服务端限流 — Sentinel (Java)

```java
// 1. 定义资源和规则
FlowRule rule = new FlowRule();
rule.setResource("createOrder");
rule.setGrade(RuleConstant.FLOW_GRADE_QPS);  // 按 QPS 限流
rule.setCount(200);                           // 阈值 200 QPS
rule.setStrategy(RuleConstant.STRATEGY_DIRECT);
rule.setControlBehavior(RuleConstant.CONTROL_BEHAVIOR_WARM_UP);  // 冷启动
rule.setWarmUpPeriodSec(10);  // 10s 预热到满速

FlowRuleManager.loadRules(Collections.singletonList(rule));

// 2. 使用
@SentinelResource(value = "createOrder",
    blockHandler = "createOrderBlocked",
    fallback = "createOrderFallback")
public Order createOrder(CreateOrderRequest request) {
    return orderService.create(request);
}

// 被限流时的处理
public Order createOrderBlocked(CreateOrderRequest request, BlockException ex) {
    throw new ServiceException(429, "系统繁忙，请稍后重试");
}

// 业务异常时的降级
public Order createOrderFallback(CreateOrderRequest request, Throwable t) {
    log.error("createOrder fallback", t);
    throw new ServiceException(500, "下单暂时不可用");
}
```

### 中间件限流 — Nginx

```nginx
# Nginx 限流配置
http {
    # 定义限流区域：按客户端 IP，10MB 共享内存，每秒 10 请求
    limit_req_zone $binary_remote_addr zone=api_limit:10m rate=10r/s;

    # 按接口路径限流
    limit_req_zone $uri zone=uri_limit:10m rate=100r/s;

    server {
        location /api/ {
            # burst=20: 允许突发 20 个排队
            # nodelay: 突发请求不延迟，直接处理
            limit_req zone=api_limit burst=20 nodelay;

            # 限流时返回 429 而非默认的 503
            limit_req_status 429;

            proxy_pass http://backend;
        }
    }
}
```

---

## 六、过载保护与优雅降级

### 自适应过载保护

不预设固定阈值，根据系统实际负载自动调整：

```go
// 基于 CPU 使用率的自适应限流
type AdaptiveLimiter struct {
    maxCPU     float64       // 触发限流的 CPU 阈值
    cooldown   time.Duration // 限流后的冷却时间
    lastReject time.Time
    mu         sync.Mutex
}

func (l *AdaptiveLimiter) Allow() bool {
    cpuUsage := getCurrentCPUUsage()  // 获取当前 CPU 使用率

    if cpuUsage > l.maxCPU {
        l.mu.Lock()
        l.lastReject = time.Now()
        l.mu.Unlock()

        // 按概率丢弃请求（CPU 越高丢弃概率越大）
        dropRate := (cpuUsage - l.maxCPU) / (1.0 - l.maxCPU)
        if rand.Float64() < dropRate {
            return false
        }
    }
    return true
}

// 基于排队延迟的过载保护（Little's Law）
type QueueBasedLimiter struct {
    maxQueueTime time.Duration
    inflight     atomic.Int64
    avgLatency   *EWMA  // 指数加权移动平均
}

func (l *QueueBasedLimiter) Allow() bool {
    currentInflight := l.inflight.Load()
    avgLat := l.avgLatency.Value()

    // Little's Law: 队列延迟 ≈ inflight × avgLatency / concurrency
    estimatedQueue := time.Duration(float64(currentInflight) * avgLat)
    return estimatedQueue < float64(l.maxQueueTime)
}
```

### 优雅降级策略

```yaml
# 降级优先级定义
degradation_levels:
  level_0:  # 正常
    - all_features: enabled

  level_1:  # 轻度过载（CPU > 70%）
    - disable: recommendation_engine    # 关闭推荐
    - disable: user_behavior_tracking   # 关闭行为追踪
    - cache_mode: aggressive            # 更积极的缓存

  level_2:  # 中度过载（CPU > 85%）
    - disable: search_suggestion        # 关闭搜索建议
    - disable: real_time_inventory      # 库存改为异步更新
    - static_page: product_detail       # 商品详情走静态缓存

  level_3:  # 重度过载（CPU > 95%）
    - disable: non_core_apis            # 只保留核心交易链路
    - reject: new_user_registration     # 暂停注册
    - rate_limit: 50%                   # 全局限流 50%
```

---

## 七、排查清单与总结

### 重试风暴排查

| 检查项 | 方法 | 判断标准 |
|-------|------|---------|
| 下游是否承受了放大流量 | 监控下游 QPS | QPS 是正常的 N 倍 |
| 调用链有几层在重试 | 代码审查 | 应只有一层重试 |
| 重试是否有退避 | 检查重试配置 | 必须有指数退避 + 抖动 |
| 是否设置了重试预算 | 检查配置 | 重试流量 < 总流量 10% |
| 非幂等操作是否在重试 | 代码审查 | POST/PUT 需幂等保证 |
| 断路器是否生效 | 监控断路器状态 | 高失败率时应打开 |

### 限流问题排查

| 检查项 | 方法 | 判断标准 |
|-------|------|---------|
| 429 比例 | 监控 HTTP status | 不应持续高于 5% |
| 限流是否误杀 | 检查限流维度 | 应按用户/接口分别限流 |
| 是否有全局限流兜底 | 检查网关配置 | 网关必须有总流量限制 |
| 限流后是否返回 Retry-After | 检查响应头 | 应引导客户端等待 |
| 客户端是否尊重 429 | 检查客户端代码 | 不应立即重试 429 |
| 限流日志是否有可观测性 | 检查日志和指标 | 能区分被限流的请求来源 |
