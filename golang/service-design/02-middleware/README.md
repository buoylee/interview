# 02 · 中间件与横切关注点:限流、重试、熔断

> 日志、认证、限流、重试、熔断、超时——这些**横切关注点**不该散在每个 handler 里,而是用**中间件**(HTTP)/**拦截器**(gRPC)统一处理。本章聚焦最容易答错的三个:**限流、重试、熔断**及其坑。
>
> 桥接锚点:Java 的 Resilience4j(RateLimiter/Retry/CircuitBreaker)、Spring 拦截器/AOP ←→ Go 的中间件 + `x/time/rate` + `gobreaker`。Go 更显式、无 AOP 魔法。

---

## 1. 核心问题

- 日志/认证这种每个接口都要的逻辑,怎么不重复写?
- 怎么限流(保护自己不被打垮)?令牌桶怎么用?
- 重试有什么坑(为什么会放大故障)?熔断又解决什么?

---

## 2. 直觉理解

### 横切 = 中间件洋葱包装

```go
handler = logging(auth(rateLimit(recover(mux))))   // 洋葱:请求穿过每一层
```

中间件(`func(http.Handler) http.Handler`,见 [`stdlib/01`](../../stdlib/01-net-http/README.md))/gRPC 拦截器把通用逻辑抽到一处。常见层:recover(兜 panic,见 [`error-handling/03`](../../error-handling/03-panic-recover-defer/README.md))、日志、trace、认证、限流、超时。

### 限流:令牌桶护住自己

```go
import "golang.org/x/time/rate"
limiter := rate.NewLimiter(100, 200)   // 每秒 100 个令牌、桶容量 200(允许突发)
if !limiter.Allow() {
    http.Error(w, "rate limited", http.StatusTooManyRequests)   // 429
    return
}
```

限流是**保护服务自己**不被流量打垮(过载保护)。令牌桶:匀速发令牌、桶能存一定量(容忍突发)。超限返回 429。

### 重试 + 熔断:对付下游故障的一对

- **重试**:下游临时抖动时再试一次,提高成功率——但**用错会放大故障**(下游已经挂了你还猛重试 = 雪上加霜)。
- **熔断**:下游持续失败时**直接快速失败**(不再打它),给它喘息时间,过段时间再试探恢复。重试和熔断**配合**用:熔断防止重试把下游打死。

---

## 3. 原理深入

### 3.1 限流:几个维度

- **令牌桶**(`rate.Limiter`):匀速 + 容忍突发(最常用)。
- **全局 vs 每用户/每 IP**:`map[key]*rate.Limiter` 做按 key 限流。
- **本地 vs 分布式**:单机用 `rate.Limiter`;多实例要全局限流用 Redis(见 [`redis-handson/`])。
- 限流位置:入口中间件(保护整个服务)、或下游调用端(保护下游)。

### 3.2 重试的正确姿势(坑最多)

```go
for attempt := 0; attempt < maxRetries; attempt++ {
    err := call(ctx)
    if err == nil { return nil }
    if !isRetryable(err) { return err }          // ① 只重试可重试错误(超时/503,非 400)
    backoff := base * (1 << attempt)             // ② 指数退避
    jitter := time.Duration(rand.Int63n(int64(backoff)))  // ③ 加抖动防惊群
    select {
    case <-time.After(backoff + jitter):
    case <-ctx.Done(): return ctx.Err()          // ④ 等待期间响应取消
    }
}
```

四条铁律(承接 [`concurrency/08`](../../concurrency/08-patterns/README.md) 重试模式):

1. **只重试可重试错误**(超时、503、连接失败;**别重试** 400/422 这种重试也没用的);
2. **指数退避**(别固定间隔猛重试);
3. **加抖动(jitter)**(防大量客户端同时重试造成「惊群」打垮下游);
4. **操作必须幂等**(重试可能导致重复执行,非幂等操作会出双花/重复下单——见 [`financial-consistency/`]);
5. 等待期间响应 ctx 取消。

### 3.3 熔断:三态状态机

```go
import "github.com/sony/gobreaker"
cb := gobreaker.NewCircuitBreaker(gobreaker.Settings{...})
result, err := cb.Execute(func() (any, error) { return call() })
```

熔断器三态:

- **Closed(闭合)**:正常放行,统计失败率;失败率超阈值 → 跳到 Open。
- **Open(断开)**:直接快速失败(不打下游),持续一段时间 → 转 Half-Open。
- **Half-Open(半开)**:放少量试探请求,成功 → 回 Closed,失败 → 回 Open。

作用:下游挂了就别再打它(快速失败 + 给它恢复时间),避免请求堆积拖垮自己(级联故障)。**重试 + 熔断 + 超时三件套**是微服务韧性的标配(Resilience4j 同款思路)。

### 3.4 超时(贯穿全链)

每个外部调用都要超时(见 [`stdlib/01`](../../stdlib/01-net-http/README.md) client、[`concurrency/07`](../../concurrency/07-context/README.md) ctx);超时是熔断/重试的基础——没有超时,一个慢下游能直接耗尽你的连接/goroutine。

---

## 4. 日常开发应用

- **横切用中间件/拦截器**:recover→日志→trace→认证→限流,洋葱包装,别在 handler 重复。
- **入口限流** `rate.Limiter`(令牌桶),超限 429;按用户/IP 用 `map[key]*Limiter`;多实例用 Redis。
- **重试**:只重试可重试错误 + 指数退避 + 抖动 + 幂等 + 响应 ctx。
- **熔断**(gobreaker)护下游,和重试配合(熔断防重试打死下游)。
- **所有外部调用设超时**(ctx/client timeout)。

---

## 5. 生产&调优实战

- **重试放大故障是经典事故**:下游过载时无脑重试 = 把它彻底打死(retry storm);务必退避 + 抖动 + 熔断兜底 + 限制重试次数。
- **非幂等操作重试 = 数据错乱**:支付/下单重试可能重复执行;要幂等键(见 [`financial-consistency/`])或别重试。
- **限流阈值要压测定**:拍脑袋的阈值要么没用要么误杀;按容量压测 + 留余量,配合监控动态调。
- **熔断阈值与恢复**:太敏感会误熔断、太迟钝起不到保护;失败率窗口 + Half-Open 试探数要按下游特性调。
- **中间件顺序有讲究**:recover 要在最外层(兜住内层所有 panic)、限流在认证后(别为非法请求耗令牌)或前(防刷)按需;trace 要早(覆盖全链)。
- **本地限流 ≠ 全局限流**:多实例下每实例独立 `rate.Limiter` 总量会翻倍;需要全局精确限流用 Redis 令牌桶。

## 6. 面试高频考点

- **横切关注点怎么处理?** 中间件(HTTP)/拦截器(gRPC)洋葱包装:recover/日志/trace/认证/限流/超时,统一不重复。
- **限流怎么做?** 令牌桶(`x/time/rate`,匀速+突发),超限 429;按 key 限流用 map;多实例用 Redis 全局限流。
- **重试有什么坑?** ① 只重试可重试错误(别重 400);② 指数退避;③ 加抖动防惊群;④ 操作必须幂等(否则重复执行);⑤ 等待响应 ctx。无脑重试会放大故障(retry storm)。
- **熔断解决什么?三态?** 下游持续失败时快速失败、给它恢复时间、防级联故障;Closed(正常统计失败率)→ Open(快速失败)→ Half-Open(试探)。
- **重试和熔断关系?** 配合:熔断防止重试把已挂的下游彻底打死。
- **中间件顺序?** recover 最外、trace 早、限流按需在认证前后。
- **和 Resilience4j?** 同款思路(RateLimiter/Retry/CircuitBreaker),Go 用中间件 + x/time/rate + gobreaker,无 AOP 魔法。

## 7. 一句话总结

> **横切关注点用中间件(HTTP)/拦截器(gRPC)洋葱包装**(recover→日志→trace→认证→限流→超时),不散落在 handler。**限流**用令牌桶(`x/time/rate`,匀速+突发,超限 429;多实例用 Redis 全局限流)保护自己。**重试**五铁律:只重可重试错误、指数退避、加抖动防惊群、操作必须幂等、响应 ctx——否则 retry storm 放大故障。**熔断**(gobreaker 三态 Closed→Open→Half-Open)在下游持续失败时快速失败、防级联故障,和重试配合(熔断防重试把下游打死)。所有外部调用必须有超时。≈ Resilience4j,但 Go 显式无 AOP。

← 上一章 [`01 gRPC vs REST`](../01-grpc-rest/README.md) ｜ 下一章 → [`03 可观测性接入`](../03-observability/README.md):服务跑起来后怎么看清它——OTel 三支柱、ctx 传 trace、链到 observability track。｜ 回 [`service-design` 索引](../README.md)
