# 用 Trace 定位分布式瓶颈

## 为什么 Trace 是分布式性能排查的核心工具

单体应用的性能问题可以用 profiler 抓到具体函数。但在微服务架构中，一个请求跨越 5-10 个服务、经过多次 RPC 和中间件调用——**日志只能告诉你"某个服务慢了"，Trace 能告诉你"哪个服务的哪个调用、在哪个环节、慢了多少"**。没有 Trace 的分布式系统排查，就像蒙眼找针。

---

## 一、分布式 Trace 核心概念回顾

### Trace / Span / SpanContext

```
Trace（一次完整请求的链路）
├── Span A: API Gateway (0ms ~ 350ms)
│   ├── Span B: OrderService.createOrder (10ms ~ 300ms)
│   │   ├── Span C: MySQL INSERT (20ms ~ 50ms)
│   │   ├── Span D: PaymentService.pay (60ms ~ 250ms)
│   │   │   ├── Span E: Redis GET (65ms ~ 70ms)
│   │   │   └── Span F: BankAPI.charge (80ms ~ 240ms)
│   │   └── Span G: Kafka PRODUCE (260ms ~ 280ms)
│   └── Span H: Response serialization (305ms ~ 310ms)
```

**关键术语**：

| 概念 | 说明 |
|------|------|
| Trace | 一次端到端请求的完整链路，由唯一的 TraceID 标识 |
| Span | 链路中的一个操作单元（一次 RPC、一次数据库查询） |
| SpanContext | 在服务间传递的上下文（TraceID + SpanID + 采样标记） |
| Parent Span | 父 Span，建立调用关系树 |
| Baggage | 随 Span 传播的业务数据（如用户 ID），谨慎使用 |

### OpenTelemetry Span 属性

```go
// Go - OpenTelemetry Span 创建
import "go.opentelemetry.io/otel"

func (s *OrderService) CreateOrder(ctx context.Context, req *OrderReq) (*OrderResp, error) {
    ctx, span := otel.Tracer("order-service").Start(ctx, "CreateOrder",
        trace.WithAttributes(
            attribute.String("order.user_id", req.UserID),
            attribute.Float64("order.amount", req.Amount),
            attribute.String("order.channel", req.Channel),
        ),
        trace.WithSpanKind(trace.SpanKindServer),
    )
    defer span.End()

    // 记录事件（时间点标记）
    span.AddEvent("validation_complete")

    // 调用数据库（会自动创建子 Span）
    order, err := s.repo.Insert(ctx, req)
    if err != nil {
        span.RecordError(err)
        span.SetStatus(codes.Error, err.Error())
        return nil, err
    }

    span.AddEvent("order_created", trace.WithAttributes(
        attribute.String("order.id", order.ID),
    ))

    return order, nil
}
```

```java
// Java - OpenTelemetry Span 创建
@WithSpan("CreateOrder")
public Order createOrder(
        @SpanAttribute("order.user_id") String userId,
        @SpanAttribute("order.amount") double amount,
        CreateOrderRequest request) {

    Span span = Span.current();
    span.addEvent("validation_complete");

    Order order = orderRepository.save(buildOrder(request));

    span.addEvent("order_created",
        Attributes.of(AttributeKey.stringKey("order.id"), order.getId()));

    return order;
}
```

---

## 二、Jaeger UI 分析技巧

### 基本搜索与过滤

```
常用搜索条件：
- Service: order-service
- Operation: CreateOrder
- Tags: http.status_code=500, error=true
- Min Duration: 1s（只看慢请求）
- Max Duration: 不设（看最慢的有多慢）
- Limit: 50（看最近 50 条）
```

### 关键路径识别

在 Jaeger 的瀑布图中，关键路径是决定总耗时的那条链路：

```
总耗时 350ms 的请求：

├── Span A: Gateway (0-350ms)                   ← 总框架
│   ├── Span B: OrderService (10-300ms)         ← 主要耗时在这
│   │   ├── Span C: MySQL INSERT (20-50ms)      30ms ✓ 正常
│   │   ├── Span D: PaymentService (60-250ms)   190ms ← 关键路径！
│   │   │   ├── Span E: Redis GET (65-70ms)     5ms ✓ 正常
│   │   │   └── Span F: BankAPI (80-240ms)      160ms ← 瓶颈！
│   │   └── Span G: Kafka PRODUCE (260-280ms)   20ms ✓ 正常
│   └── Span H: Serialization (305-310ms)       5ms ✓ 正常
```

**分析方法**：
1. 找到总耗时最长的 Span（Span D: 190ms）
2. 进入 Span D，找最长的子 Span（Span F: 160ms）
3. 结论：BankAPI 调用是瓶颈，160ms / 350ms = 45% 的时间花在这里

### 并行 vs 串行 Span 判断

```
串行执行（Span 无重叠）：
|--- Span C: MySQL ---|
                      |--- Span D: Payment ---|
                                               |--- Span G: Kafka ---|
总耗时 = C + D + G

并行执行（Span 有时间重叠）：
|--- Span C: MySQL ---|
|--- Span D: Payment ---------|
                |--- Span G: Kafka ---|
总耗时 = max(C, D, G)（不是相加）
```

**优化方向**：如果 Span 是串行的，考虑能否并行化。

```go
// 串行调用改并行
func (s *OrderService) CreateOrder(ctx context.Context, req *OrderReq) error {
    // 错误示范：串行调用
    // inventory, _ := s.inventoryClient.Reserve(ctx, req)
    // coupon, _ := s.couponClient.Validate(ctx, req)
    // price, _ := s.priceClient.Calculate(ctx, req)
    // 总耗时 = inventory + coupon + price

    // 正确做法：并行调用
    g, ctx := errgroup.WithContext(ctx)

    var inventory *InventoryResp
    g.Go(func() error {
        var err error
        inventory, err = s.inventoryClient.Reserve(ctx, req)
        return err
    })

    var coupon *CouponResp
    g.Go(func() error {
        var err error
        coupon, err = s.couponClient.Validate(ctx, req)
        return err
    })

    var price *PriceResp
    g.Go(func() error {
        var err error
        price, err = s.priceClient.Calculate(ctx, req)
        return err
    })

    if err := g.Wait(); err != nil {
        return err
    }
    // 总耗时 = max(inventory, coupon, price)
    return nil
}
```

---

## 三、跨服务延迟分析

### 区分"等待时间"和"处理时间"

```
客户端视角（Span D 总耗时 190ms）：
|<------ Span D: PaymentService.pay (190ms) ------>|

服务端视角（Span D-server 处理时间 150ms）：
     |<---- Span D-server: handle pay (150ms) ---->|

差值 = 190ms - 150ms = 40ms → 网络传输 + 序列化 + 排队
```

**差值过大的可能原因**：

| 差值范围 | 可能原因 | 排查手段 |
|---------|---------|---------|
| < 5ms | 正常（同机房网络） | 无需排查 |
| 5-50ms | 网络延迟或跨机房 | ping / traceroute |
| 50-200ms | 序列化开销或请求排队 | 检查线程池 / 消息大小 |
| > 200ms | 连接建立（没有连接池）或 DNS 解析 | 检查连接池配置 |

### 常见的 Trace 异常模式

**模式 1：阶梯型延迟（串行瓶颈）**

```
|-- DB Query 1 ---|
                  |-- DB Query 2 ---|
                                    |-- DB Query 3 ---|
→ 看是否能合并查询或并行化
```

**模式 2：长尾 Span（偶发慢调用）**

```
正常请求：|-- Redis GET 2ms --|
偶发慢：  |---------- Redis GET 200ms ----------|
→ 可能是 Redis 主从切换、大 Key、网络抖动
```

**模式 3：Gap（空白间隔）**

```
|-- Span A ---|          |-- Span B ---|
              ^^^^gap^^^^
→ 可能是 GC 停顿、线程池排队、context switch
```

**模式 4：Fan-out 放大**

```
|-- Service A --|
  |-- call B1 --|
  |-- call B2 --|
  |-- call B3 --|
  ...
  |-- call B50 --|  ← 对一个下游发了 50 次调用
→ 检查是否应该批量调用
```

---

## 四、日志关联

### TraceID 串联日志

**核心思路**：在每条日志中输出 TraceID，通过 TraceID 一键搜索整条链路的所有日志。

```java
// Java - MDC 注入 TraceID（配合 OpenTelemetry agent 自动注入）
// logback.xml 配置
// <pattern>%d{yyyy-MM-dd HH:mm:ss} [%thread] %-5level [traceId=%X{trace_id} spanId=%X{span_id}] %logger - %msg%n</pattern>

// 手动注入（如果不用 agent）
import io.opentelemetry.api.trace.Span;
import org.slf4j.MDC;

public class TraceFilter implements Filter {
    @Override
    public void doFilter(ServletRequest req, ServletResponse resp, FilterChain chain) {
        Span span = Span.current();
        MDC.put("trace_id", span.getSpanContext().getTraceId());
        MDC.put("span_id", span.getSpanContext().getSpanId());
        try {
            chain.doFilter(req, resp);
        } finally {
            MDC.clear();
        }
    }
}
```

```go
// Go - 结构化日志携带 TraceID
import (
    "go.opentelemetry.io/otel/trace"
    "go.uber.org/zap"
)

func LoggerFromContext(ctx context.Context) *zap.Logger {
    spanCtx := trace.SpanContextFromContext(ctx)
    return zap.L().With(
        zap.String("trace_id", spanCtx.TraceID().String()),
        zap.String("span_id", spanCtx.SpanID().String()),
    )
}

// 使用
func (s *OrderService) CreateOrder(ctx context.Context, req *OrderReq) error {
    log := LoggerFromContext(ctx)
    log.Info("creating order", zap.String("user_id", req.UserID))

    // 数据库操作...
    log.Info("order saved", zap.String("order_id", order.ID))

    return nil
}
```

```python
# Python - structlog 集成 trace
import structlog
from opentelemetry import trace

def add_trace_context(logger, method_name, event_dict):
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx.is_valid:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict

structlog.configure(
    processors=[
        add_trace_context,
        structlog.processors.JSONRenderer(),
    ]
)

log = structlog.get_logger()

# 输出示例：
# {"event": "order created", "trace_id": "abc123...", "span_id": "def456...", "order_id": "12345"}
```

### 日志与 Trace 联动查询

```
排查流程：

1. 用户报告"订单创建超时"
   ↓
2. 在 Jaeger 中搜索慢的 CreateOrder Trace
   → 找到 TraceID: abc123def456
   ↓
3. 用 TraceID 在 ELK/Loki 中搜索日志
   Kibana: trace_id: "abc123def456"
   Loki:   {service="order-service"} |= "abc123def456"
   ↓
4. 日志显示: "slow query detected: SELECT * FROM orders WHERE ..."
   ↓
5. 定位到具体 SQL，结合 Trace 中 MySQL Span 的耗时确认
```

---

## 五、上下文传播断裂排查

### 常见的 Trace 断裂场景

**场景 1：异步调用丢失 Context**

```java
// 错误：异步执行时没有传播 context
CompletableFuture.runAsync(() -> {
    // 这里没有 trace context！新线程拿不到
    orderNotificationService.notify(order);
});

// 正确：使用 Context 包装
Context otelContext = Context.current();
CompletableFuture.runAsync(otelContext.wrap(() -> {
    // 现在有 trace context 了
    orderNotificationService.notify(order);
}));
```

```go
// Go 中异步协程的 context 传播
// 错误：直接 go func()
go func() {
    notifyUser(order)  // 这里的 ctx 从哪来？
}()

// 正确：传递 ctx（但要注意 ctx 的生命周期）
go func(ctx context.Context) {
    // 创建新的 Span 关联到原始 Trace
    ctx, span := otel.Tracer("order-service").Start(ctx, "async-notify")
    defer span.End()
    notifyUser(ctx, order)
}(ctx)  // 注意：传入 ctx，而非闭包捕获
```

**场景 2：线程池切换**

```java
// 线程池会切换线程，默认丢失 ThreadLocal 中的 context
ExecutorService executor = Executors.newFixedThreadPool(10);

// 错误
executor.submit(() -> doWork());  // 丢失 trace context

// 正确：使用 OpenTelemetry 的 Context 包装器
ExecutorService tracedExecutor = Context.taskWrapping(executor);
tracedExecutor.submit(() -> doWork());  // 保留 trace context

// 或者在 Spring 中配置
@Bean
public Executor taskExecutor() {
    ThreadPoolTaskExecutor executor = new ThreadPoolTaskExecutor();
    executor.setCorePoolSize(10);
    executor.setMaxPoolSize(20);
    executor.setTaskDecorator(new ContextPropagatingTaskDecorator());
    return executor;
}
```

**场景 3：消息队列断裂**

```java
// Kafka 发送时需要将 SpanContext 注入 headers
public void sendMessage(String topic, String key, Object payload) {
    ProducerRecord<String, String> record = new ProducerRecord<>(topic, key, serialize(payload));

    // 注入 trace context 到 Kafka headers
    GlobalOpenTelemetry.getPropagators().getTextMapPropagator()
        .inject(Context.current(), record.headers(), (headers, k, v) -> {
            headers.add(k, v.getBytes(StandardCharsets.UTF_8));
        });

    kafkaTemplate.send(record);
}

// 消费时提取 SpanContext
@KafkaListener(topics = "order-events")
public void consume(ConsumerRecord<String, String> record) {
    // 提取 trace context
    Context extractedContext = GlobalOpenTelemetry.getPropagators().getTextMapPropagator()
        .extract(Context.current(), record.headers(), (headers, key) -> {
            Header header = headers.lastHeader(key);
            return header != null ? new String(header.value(), StandardCharsets.UTF_8) : null;
        });

    // 在提取的 context 下创建新的 Span
    try (Scope scope = extractedContext.makeCurrent()) {
        Span span = otel.Tracer("consumer").spanBuilder("process-order-event")
            .setSpanKind(SpanKind.CONSUMER)
            .startSpan();
        try {
            processEvent(record);
        } finally {
            span.end();
        }
    }
}
```

---

## 六、Trace 采样策略对排查的影响

### 采样方式对比

| 采样方式 | 说明 | 对排查的影响 |
|---------|------|-------------|
| 固定比率采样 | 1% 或 0.1% 的请求被采集 | 低频错误可能完全采不到 |
| 头部采样 | 在入口就决定是否采集 | 决策时不知道请求会不会出错 |
| 尾部采样 | 请求完成后再决定是否保留 | 能保留所有错误和慢请求 |
| 自适应采样 | 根据流量动态调整采样率 | 低流量接口也能采到 |

### 尾部采样配置（OpenTelemetry Collector）

```yaml
# otel-collector-config.yaml
processors:
  tail_sampling:
    decision_wait: 10s              # 等待 10s 收集所有 Span
    num_traces: 100000              # 内存中保持 10万 Trace
    policies:
      # 策略 1：所有错误都保留
      - name: errors
        type: status_code
        status_code: {status_codes: [ERROR]}

      # 策略 2：慢请求都保留（> 2s）
      - name: slow-requests
        type: latency
        latency: {threshold_ms: 2000}

      # 策略 3：特定接口全采
      - name: payment-all
        type: string_attribute
        string_attribute:
          key: http.route
          values: ["/api/v1/payment"]

      # 策略 4：其他请求 1% 采样
      - name: default
        type: probabilistic
        probabilistic: {sampling_percentage: 1}
```

### 排查时的采样陷阱

```
问题：用户报告"偶尔超时"，但在 Jaeger 里搜不到慢请求

可能原因：
1. 采样率太低 → 慢请求没被采到
2. 头部采样 → 在入口决策时还不知道会慢
3. Span 太多被截断 → 超过 maxSpansPerTrace 限制

解决方案：
1. 开启尾部采样，保证错误和慢请求 100% 采集
2. 对关键接口提高采样率
3. 临时全量采样排查问题（注意存储压力）
```

---

## 七、实操：PerfShop 下单链路 Trace 分析

### 场景：下单接口 P99 延迟从 500ms 飙到 3s

```
排查步骤：

Step 1: 在 Jaeger 搜索慢请求
  Service: api-gateway
  Operation: POST /api/v1/orders
  Min Duration: 2s
  → 找到若干慢请求 Trace

Step 2: 打开一个典型慢 Trace，查看瀑布图
  api-gateway (0ms ~ 2800ms)
  ├── auth-service.verify (10ms ~ 30ms)          ✓ 20ms 正常
  ├── order-service.create (40ms ~ 2700ms)        ← 问题在这
  │   ├── mysql.INSERT orders (50ms ~ 80ms)       ✓ 30ms 正常
  │   ├── inventory-service.reserve (90ms ~ 2500ms) ← 瓶颈！
  │   │   ├── redis.GET stock (100ms ~ 105ms)     ✓ 正常
  │   │   └── mysql.UPDATE inventory (110ms ~ 2480ms) ← 根因！
  │   └── kafka.PRODUCE order-event (2510ms ~ 2530ms) ✓ 正常
  └── response (2710ms ~ 2720ms)

Step 3: 分析根因
  - mysql.UPDATE inventory 耗时 2370ms（正常应 < 50ms）
  - 查看 Span 的 db.statement 属性：
    UPDATE inventory SET stock = stock - 1 WHERE product_id = 'hot-item-001'
  - 热门商品行锁竞争！

Step 4: 交叉验证
  - 用 TraceID 搜日志：确认有 "Lock wait timeout" 警告
  - 检查 MySQL 慢查询日志：确认同一条 SQL
  - 检查 Grafana 上 inventory-service 的 DB 延迟指标：P99 飙升

Step 5: 解决方案
  - 短期：热点商品库存分桶（拆成多行减少锁竞争）
  - 长期：预扣库存改为 Redis 原子操作，异步落库
```

---

## 八、排查清单

### Trace 分析检查项

| 检查项 | 方法 | 关注点 |
|-------|------|-------|
| 关键路径是哪个 Span | Jaeger 瀑布图 | 占总时间比例最大的 Span |
| Span 是串行还是并行 | 看时间轴重叠 | 串行的是否能改并行 |
| 客户端与服务端 Span 差值 | 对比同一调用两端时间 | 差值大说明网络/排队问题 |
| 是否有 Gap（空白） | 看 Span 之间的间隔 | Gap 可能是 GC 或排队 |
| Trace 是否完整 | 检查 Span 数量 | 断裂说明 context 传播有问题 |
| 异步调用是否关联 | 检查消息消费端是否有 Span | 没有说明 MQ 传播断了 |
| 采样率是否足够 | 检查能否搜到慢/错误请求 | 搜不到考虑尾部采样 |
| 业务标签是否充分 | 检查 Span 的 attributes | 应有 user_id、order_id 等 |
