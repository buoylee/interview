# 限流·重试·熔断(韧性三件套)

## 一句话回答

横切关注点用**中间件/拦截器**洋葱包装。韧性三件套:**限流**用令牌桶(`golang.org/x/time/rate`,匀速 + 容忍突发,超限返 429;按 key 用 `map[key]*Limiter`,多实例要全局限流用 Redis)保护服务自己不被打垮;**重试**对付下游临时抖动但**五铁律**(只重试可重试错误、指数退避、加抖动防惊群、操作必须幂等、等待响应 ctx),否则无脑重试会 retry storm 放大故障;**熔断**(gobreaker 三态 Closed→Open→Half-Open)在下游持续失败时快速失败、给它恢复时间、防级联故障,**和重试配合**(熔断防重试把已挂的下游彻底打死)。所有外部调用必须有超时。

## 重试五铁律

```go
if !isRetryable(err) { return err }   // 只重可重试(超时/503,非 400)
backoff := base * (1<<attempt)        // 指数退避
+ jitter                              // 抖动防惊群
// 操作必须幂等(否则重复执行→重复下单)
select { case <-time.After(...): case <-ctx.Done(): return ctx.Err() }
```

## 熔断三态

Closed(正常,统计失败率)→ 超阈值 → Open(快速失败,不打下游)→ 一段时间 → Half-Open(放少量试探)→ 成功回 Closed / 失败回 Open。

## 证据链接

- 正文:[`02 中间件与横切`](../02-middleware/README.md);重试模式 [`concurrency/08`](../../../concurrency/08-patterns/README.md);幂等 [`financial-consistency/`];ctx 超时 [`concurrency/07`](../../../concurrency/07-context/README.md)

## 易追问的延伸

- **重试为什么放大故障?** 下游过载时还猛重试=彻底打死(retry storm);退避+抖动+熔断+限次兜底。
- **非幂等重试?** 支付/下单会重复执行;要幂等键或别重试。
- **本地 vs 全局限流?** 多实例每个独立 Limiter 总量翻倍;全局精确用 Redis 令牌桶。
- **中间件顺序?** recover 最外、trace 早、限流按需在认证前后。
- **和 Resilience4j?** 同款(RateLimiter/Retry/CircuitBreaker),Go 用中间件+x/time/rate+gobreaker,无 AOP。
