# 超时传播与断路器

## 为什么超时和断路器是分布式系统的生命线

在单体应用中，一个函数调用慢了最多拖慢当前请求。但在微服务架构中，**一个下游服务变慢会拖垮整条调用链**——上游线程被阻塞、连接池耗尽、请求堆积、最终雪崩。超时是第一道防线，断路器是第二道。没有这两个机制的分布式系统，就像没有保险丝的电路——一个短路烧掉整栋楼。

---

## 一、超时传播链分析

### 调用链中的超时关系

假设一个请求链路：`Client → Gateway → OrderService → PaymentService → BankAPI`

```
Client (总超时 5s)
  └─ Gateway (超时 4s)
       └─ OrderService (超时 3s)
            └─ PaymentService (超时 2s)
                 └─ BankAPI (超时 1.5s)
```

**核心原则：上游超时 > 下游超时**

如果违反这个原则会怎样？

```
错误配置：
Client (超时 2s)
  └─ Gateway (超时 5s)    ← Client 已经放弃了，Gateway 还在等
       └─ OrderService (超时 10s)  ← 无意义的等待
```

结果：Client 2s 后超时返回错误，但 Gateway 和 OrderService 的线程/协程还在傻等。这些"僵尸请求"白白占用资源。

### 超时预算（Timeout Budget）

更好的做法是传播超时预算（Deadline Propagation）：

```go
// Go 中使用 context 传播 deadline
func (s *OrderService) CreateOrder(ctx context.Context, req *OrderReq) (*OrderResp, error) {
    // 检查剩余时间
    deadline, ok := ctx.Deadline()
    if ok {
        remaining := time.Until(deadline)
        if remaining < 100*time.Millisecond {
            return nil, status.Error(codes.DeadlineExceeded, "insufficient time budget")
        }
    }

    // 调用下游时，ctx 自动携带 deadline
    payResp, err := s.paymentClient.Pay(ctx, payReq)
    if err != nil {
        return nil, fmt.Errorf("payment failed: %w", err)
    }
    return &OrderResp{OrderID: payResp.OrderID}, nil
}
```

```java
// Java / gRPC 中传播 deadline
public void createOrder(CreateOrderRequest req, StreamObserver<CreateOrderResponse> observer) {
    // gRPC 自动传播 deadline
    Deadline deadline = Context.current().getDeadline();
    if (deadline != null) {
        long remaining = deadline.timeRemaining(TimeUnit.MILLISECONDS);
        if (remaining < 100) {
            observer.onError(Status.DEADLINE_EXCEEDED
                .withDescription("insufficient time budget").asRuntimeException());
            return;
        }
    }

    // 调用下游，deadline 自动传播
    PaymentResponse payResp = paymentStub.pay(payReq);
    observer.onNext(buildResponse(payResp));
    observer.onCompleted();
}
```

---

## 二、超时设置策略

### 超时类型分类

| 超时类型 | 说明 | 典型值 |
|---------|------|-------|
| 连接超时（Connect Timeout） | TCP 握手的超时 | 1-3s |
| 读超时（Read Timeout） | 等待响应数据的超时 | 根据业务设定 |
| 写超时（Write Timeout） | 发送请求数据的超时 | 1-5s |
| 总超时（Total Timeout） | 整个请求的端到端超时 | 根据 SLA 设定 |
| 空闲超时（Idle Timeout） | 连接空闲多久后关闭 | 60-300s |

### 超时计算公式

考虑重试的超时设置：

```
单次请求超时 = T
重试次数 = N
总超时 ≥ T × N + 重试间隔总和 + 业务处理时间

示例：
- 单次超时 = 1s
- 最多重试 2 次
- 退避间隔 = 200ms, 400ms
- 业务处理 = 200ms
总超时 ≥ 1s × 3 + 600ms + 200ms = 3.8s → 设置 4s
```

### 不同场景的超时建议

```yaml
# 内部同机房 RPC
connect_timeout: 500ms
read_timeout: 1s

# 跨机房 RPC
connect_timeout: 1s
read_timeout: 3s

# 调用外部 API（银行、支付）
connect_timeout: 3s
read_timeout: 10s

# 数据库查询
connect_timeout: 1s
read_timeout: 3s         # 简单查询
read_timeout: 30s        # 报表查询（应走专用连接池）

# 消息队列生产
send_timeout: 5s

# 文件上传/下载
connect_timeout: 5s
read_timeout: 60s        # 大文件需要更长
```

---

## 三、超时导致雪崩的案例分析

### 案例：一次真实的超时雪崩

**背景**：电商系统，促销期间流量 5 倍增长。

```
调用链：
App → API Gateway → ProductService → InventoryService → MySQL

配置：
- API Gateway: 超时 10s，线程池 200
- ProductService: 超时 10s，线程池 100
- InventoryService: 超时 30s（！），连接池 50
```

**故障过程**：

```
T+0min: MySQL 因促销锁竞争严重，部分查询从 50ms 变为 5s
T+2min: InventoryService 线程被慢查询占满
T+3min: ProductService 等 InventoryService 响应，线程也被占满
T+5min: API Gateway 等 ProductService，线程耗尽
T+6min: 所有用户请求超时，包括不依赖库存的查询
T+8min: 健康检查超时，Kubernetes 开始杀 Pod
T+10min: Pod 重启后立刻被积压请求打死，反复重启
```

**根因**：InventoryService 超时 30s 远大于上游 10s，慢请求不会被快速释放。

**修复方案**：

```yaml
# 修复后的超时配置
api_gateway:
  timeout: 5s
  thread_pool: 200

product_service:
  timeout: 3s           # 比上游小
  thread_pool: 100
  # 关键：对 inventory 调用单独设超时
  inventory_call_timeout: 2s

inventory_service:
  timeout: 2s           # 比上游小
  db_query_timeout: 1s  # 数据库查询强制超时
  connection_pool: 50
```

---

## 四、断路器原理

### 状态机

```
         失败率 ≥ 阈值
  ┌─────────────────────┐
  │                     ▼
┌──────┐           ┌──────┐
│Closed│           │ Open │──── 所有请求直接失败（快速失败）
└──────┘           └──────┘
  ▲                     │
  │    等待时间到期      │
  │                     ▼
  │               ┌──────────┐
  └───────────────│Half-Open │──── 放行少量探测请求
     探测成功      └──────────┘
                        │
                        │ 探测失败
                        └──→ 回到 Open
```

**三个状态**：

| 状态 | 行为 | 触发条件 |
|------|------|---------|
| Closed（关闭） | 正常放行请求，统计失败率 | 初始状态 / 探测成功 |
| Open（打开） | 所有请求直接拒绝，不调用下游 | 失败率超过阈值 |
| Half-Open（半开） | 放行少量探测请求 | Open 状态等待一段时间后 |

### 为什么需要断路器

没有断路器时：

```
下游故障 → 每个请求都尝试调用 → 全部超时 → 线程/连接被占满 → 上游也挂
```

有断路器时：

```
下游故障 → 失败率超阈值 → 断路器打开 → 请求直接返回 fallback → 线程立即释放
                                      → 定期探测 → 下游恢复 → 断路器关闭
```

---

## 五、断路器实现

### Java — Resilience4j

```java
// 1. 配置断路器
CircuitBreakerConfig config = CircuitBreakerConfig.custom()
    .failureRateThreshold(50)              // 失败率 50% 触发
    .slowCallRateThreshold(80)             // 慢调用率 80% 也触发
    .slowCallDurationThreshold(Duration.ofSeconds(2))  // 2s 以上算慢调用
    .waitDurationInOpenState(Duration.ofSeconds(30))    // Open 状态等 30s
    .permittedNumberOfCallsInHalfOpenState(5)           // Half-Open 放行 5 个
    .slidingWindowType(SlidingWindowType.COUNT_BASED)   // 基于计数的滑动窗口
    .slidingWindowSize(20)                              // 窗口大小 20 个请求
    .minimumNumberOfCalls(10)              // 至少 10 个请求才开始计算
    .build();

CircuitBreaker circuitBreaker = CircuitBreaker.of("paymentService", config);

// 2. 包装调用
Supplier<PaymentResult> decoratedSupplier = CircuitBreaker
    .decorateSupplier(circuitBreaker, () -> paymentService.pay(order));

// 3. 添加 fallback
Try<PaymentResult> result = Try.ofSupplier(decoratedSupplier)
    .recover(CallNotPermittedException.class, e -> {
        // 断路器打开时的 fallback
        log.warn("Circuit breaker is open, returning cached result");
        return PaymentResult.pending("payment queued for retry");
    })
    .recover(Exception.class, e -> {
        log.error("Payment failed", e);
        return PaymentResult.failed(e.getMessage());
    });
```

```yaml
# Spring Boot 配置方式
resilience4j:
  circuitbreaker:
    instances:
      paymentService:
        failure-rate-threshold: 50
        slow-call-rate-threshold: 80
        slow-call-duration-threshold: 2s
        wait-duration-in-open-state: 30s
        permitted-number-of-calls-in-half-open-state: 5
        sliding-window-size: 20
        minimum-number-of-calls: 10
        register-health-indicator: true   # 暴露到 Actuator
```

### Go — gobreaker

```go
import "github.com/sony/gobreaker/v2"

// 配置断路器
cb := gobreaker.NewCircuitBreaker[*PaymentResult](gobreaker.Settings{
    Name:        "payment-service",
    MaxRequests: 5,                        // Half-Open 时最多放行 5 个
    Interval:    30 * time.Second,         // Closed 状态下统计窗口
    Timeout:     30 * time.Second,         // Open 到 Half-Open 的等待时间
    ReadyToTrip: func(counts gobreaker.Counts) bool {
        // 自定义触发条件：失败率 > 50% 且请求数 > 10
        if counts.Requests < 10 {
            return false
        }
        failureRatio := float64(counts.TotalFailures) / float64(counts.Requests)
        return failureRatio > 0.5
    },
    OnStateChange: func(name string, from, to gobreaker.State) {
        log.Printf("circuit breaker %s: %s → %s", name, from, to)
        // 状态变化时发告警
        metrics.CircuitBreakerState.WithLabelValues(name).Set(float64(to))
    },
})

// 使用断路器
result, err := cb.Execute(func() (*PaymentResult, error) {
    ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
    defer cancel()
    return paymentClient.Pay(ctx, req)
})

if err != nil {
    if errors.Is(err, gobreaker.ErrOpenState) {
        // 断路器打开，走 fallback
        return &PaymentResult{Status: "pending"}, nil
    }
    return nil, fmt.Errorf("payment call failed: %w", err)
}
```

### Python — pybreaker

```python
import pybreaker
import logging

# 定义监听器
class CircuitBreakerListener(pybreaker.CircuitBreakerListener):
    def state_change(self, cb, old_state, new_state):
        logging.warning(f"Circuit breaker '{cb.name}': {old_state.name} → {new_state.name}")

    def failure(self, cb, exc):
        logging.error(f"Circuit breaker '{cb.name}' recorded failure: {exc}")

# 配置断路器
payment_breaker = pybreaker.CircuitBreaker(
    fail_max=5,                    # 连续失败 5 次触发
    reset_timeout=30,              # Open 状态等 30s
    exclude=[ValueError],          # 业务异常不算失败
    listeners=[CircuitBreakerListener()],
    name="payment-service",
)

# 使用装饰器方式
@payment_breaker
def call_payment_service(order_id: str, amount: float) -> dict:
    response = httpx.post(
        f"{PAYMENT_URL}/pay",
        json={"order_id": order_id, "amount": amount},
        timeout=2.0,
    )
    response.raise_for_status()
    return response.json()

# 调用并处理断路器打开
try:
    result = call_payment_service("order-123", 99.99)
except pybreaker.CircuitBreakerError:
    # 断路器打开，返回降级结果
    result = {"status": "pending", "message": "payment queued"}
except Exception as e:
    result = {"status": "failed", "message": str(e)}
```

---

## 六、配置实践与调优

### 断路器参数调优指南

| 参数 | 过小的问题 | 过大的问题 | 建议值 |
|------|-----------|-----------|-------|
| 失败率阈值 | 太敏感，偶发错误就触发 | 太迟钝，已经雪崩才触发 | 50-60% |
| 滑动窗口大小 | 样本少，波动大 | 反应慢 | 20-100 |
| 最小请求数 | 一两个失败就触发 | 低流量时不起作用 | 10-20 |
| Open 等待时间 | 恢复太快，下游没准备好 | 恢复太慢，长时间降级 | 15-60s |
| Half-Open 探测数 | 一个请求判断不准 | 探测请求太多冲击下游 | 3-10 |
| 慢调用阈值 | 正常请求被判为慢 | 真正慢的请求不被计入 | P99 的 2 倍 |

### 断路器 + 超时 + 重试的配合

```java
// 正确的组合顺序：重试 → 断路器 → 超时
// 即：超时 在最内层，断路器 包在外面，重试 包在最外面

// 超时配置
TimeLimiterConfig timeLimiterConfig = TimeLimiterConfig.custom()
    .timeoutDuration(Duration.ofSeconds(2))
    .build();
TimeLimiter timeLimiter = TimeLimiter.of("payment", timeLimiterConfig);

// 断路器配置（见上）
CircuitBreaker circuitBreaker = CircuitBreaker.of("payment", cbConfig);

// 重试配置
RetryConfig retryConfig = RetryConfig.custom()
    .maxAttempts(3)
    .waitDuration(Duration.ofMillis(500))
    .retryOnException(e -> !(e instanceof CallNotPermittedException)) // 断路器打开不重试
    .build();
Retry retry = Retry.of("payment", retryConfig);

// 组合：调用顺序从外到内 Retry → CircuitBreaker → TimeLimiter → 实际调用
Supplier<CompletionStage<PaymentResult>> supplier = () ->
    timeLimiter.executeCompletionStage(
        executorService,
        () -> CompletableFuture.supplyAsync(() -> paymentService.pay(order))
    );

Supplier<CompletionStage<PaymentResult>> decorated = Decorators
    .ofCompletionStage(supplier)
    .withCircuitBreaker(circuitBreaker)
    .withRetry(retry)
    .decorate();
```

### 监控断路器状态

```java
// 暴露 Prometheus 指标
circuitBreaker.getEventPublisher()
    .onStateTransition(event -> {
        circuitBreakerStateGauge
            .labels(event.getCircuitBreakerName())
            .set(stateToValue(event.getStateTransition().getToState()));
    })
    .onCallNotPermitted(event -> {
        circuitBreakerRejections
            .labels(event.getCircuitBreakerName())
            .inc();
    });
```

```yaml
# Grafana 告警规则
- alert: CircuitBreakerOpen
  expr: circuit_breaker_state{state="OPEN"} == 1
  for: 1m
  labels:
    severity: critical
  annotations:
    summary: "断路器 {{ $labels.name }} 已打开"
    description: "持续 1 分钟，下游服务可能故障"
```

---

## 七、排查清单

### 超时问题排查

| 检查项 | 命令/方法 | 正常标准 |
|-------|----------|---------|
| 上下游超时配置比例 | 检查配置文件 | 上游 > 下游 |
| 是否传播了 deadline | 代码审查 context 用法 | gRPC/HTTP header 传播 |
| 重试时是否扣减了超时预算 | 检查重试配置 | 总超时 ≥ 单次 × 重试次数 |
| 连接超时与读超时是否分开 | 检查 HTTP client 配置 | 分开设置 |
| 超时后资源是否释放 | 检查连接池、线程池监控 | 超时后连接归还 |
| 慢查询是否有独立超时 | 检查数据库配置 | 报表查询走独立连接池 |

### 断路器排查

| 检查项 | 命令/方法 | 正常标准 |
|-------|----------|---------|
| 断路器当前状态 | 监控面板 / Actuator | 非 Open 状态 |
| 失败率 | `resilience4j.circuitbreaker.failure.rate` | 低于阈值 |
| 被拒请求数 | `call_not_permitted_total` | 趋势下降 |
| Half-Open 探测结果 | 日志 / 指标 | 探测成功恢复 |
| 是否区分了业务异常和系统异常 | 代码检查 | 业务异常不触发断路器 |
| 断路器名称是否有辨识度 | 配置检查 | 能区分不同下游 |
