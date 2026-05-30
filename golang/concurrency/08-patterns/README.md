# 08 · 并发模式（实战）

> 前面 `04–07` 是零件（goroutine / channel / sync / context），本章是**装配图**：工程里反复出现的几个并发骨架——worker pool、fan-in/out、pipeline、errgroup、限流、重试、优雅关闭。
>
> 桥接锚点：`errgroup` ≈ Java `StructuredTaskScope` / asyncio 的 `gather`·`TaskGroup`；worker pool ≈ `ThreadPoolExecutor`；限流 ≈ Guava `RateLimiter`。

---

## 1. 核心问题

「开 goroutine」很容易，但生产里真正的问题是：

- 要并发调 100 个下游，**不能真开 100 个**全压上去——怎么**限并发度**？
- 并发任务里**有一个失败**，怎么让其余的**立刻一起取消**、并拿到那个错误？
- 服务要下线了，怎么**不丢在途请求**地优雅关闭？

这章给出这些反复出现场景的标准答案。母题只有一个：**用有界的原语，把"无限开 goroutine"约束成"受控的并发度"。**

---

## 2. 直觉理解

| 模式 | 解决什么 | 关键原语 |
|---|---|---|
| **worker pool** | 限并发度地处理一批任务 | 固定数量 goroutine + jobs channel |
| **fan-out / fan-in** | 多 worker 并行处理 → 汇聚结果 | 多 goroutine 读同一 channel / 多 channel 并一个 |
| **pipeline** | 多阶段流水线，每段并发 | channel 串联各阶段 |
| **errgroup** | 一组并发任务 + 错误传播 + 联动取消 | `x/sync/errgroup` |
| **限流（semaphore / rate limit）** | 控制同时在飞 / 单位时间速率 | 带缓冲 channel / `x/time/rate` |
| **超时重试** | 容忍下游抖动 | `context` + 退避 + 抖动 |
| **singleflight** | 防缓存击穿（并发相同请求合并） | `x/sync/singleflight` |

---

## 3. 原理深入（模式详解）

### 3.1 worker pool —— 限并发度的基本盘

固定 N 个 worker 从 jobs channel 取活，天然把并发度钉在 N：

```go
func workerPool(ctx context.Context, jobs <-chan Job, n int) <-chan Result {
    results := make(chan Result)
    var wg sync.WaitGroup
    for i := 0; i < n; i++ {
        wg.Add(1)
        go func() {
            defer wg.Done()
            for job := range jobs {              // jobs 关闭后自动退出
                select {
                case results <- process(job):
                case <-ctx.Done():               // 取消则收手（07）
                    return
                }
            }
        }()
    }
    go func() { wg.Wait(); close(results) }()    // 所有 worker 完才关 results
    return results
}
```

要点：`for range jobs` 让 worker 在 jobs 关闭时退出；独立 goroutine `wg.Wait()` 后关 results，避免「向已关闭 channel 发送」panic（`05`）。

### 3.2 fan-out / fan-in

- **fan-out**：多个 worker 读**同一个** jobs channel（就是 3.1）。
- **fan-in**：把多个 channel 汇成一个：

```go
func fanIn(chans ...<-chan int) <-chan int {
    out := make(chan int)
    var wg sync.WaitGroup
    for _, c := range chans {
        wg.Add(1)
        go func(c <-chan int) {
            defer wg.Done()
            for v := range c { out <- v }
        }(c)
    }
    go func() { wg.Wait(); close(out) }()
    return out
}
```

### 3.3 pipeline

每个阶段是一个「读上游 channel、处理、写下游 channel」的 goroutine，用 channel 串起来；`ctx` 贯穿用于整条取消。阶段间天然解耦、各自并发。（结构同 3.1 的「读一个 chan 写一个 chan」，串多段即可。）

### 3.4 errgroup —— 现代首选（重点）

`golang.org/x/sync/errgroup` 把「并发一组任务 + 收集第一个错误 + 出错联动取消」打包好，是 `WaitGroup` 的升级版：

```go
import "golang.org/x/sync/errgroup"

func fetchAll(ctx context.Context, urls []string) error {
    g, ctx := errgroup.WithContext(ctx)   // 派生出会"出错即取消"的 ctx
    g.SetLimit(10)                         // 顺便限并发度为 10（Go 1.18+）
    results := make([]Data, len(urls))
    for i, url := range urls {
        i, url := i, url
        g.Go(func() error {                // 每个任务返回 error
            d, err := fetch(ctx, url)
            if err != nil {
                return err                 // 任一出错 → g 自动 cancel ctx，其余看 ctx.Done() 收手
            }
            results[i] = d
            return nil
        })
    }
    return g.Wait()                        // 返回第一个非 nil error（全成功则 nil）
}
```

对照你刚学的 asyncio，这就是 **`asyncio.TaskGroup` / `gather` 的 Go 版**：

| | asyncio | Go errgroup |
|---|---|---|
| 并发启动 | `gather` / `TaskGroup` | `g.Go(...)` |
| 出错行为 | `TaskGroup` 取消兄弟 / `gather` 快速失败 | 自动 cancel 派生 ctx |
| 等齐 | `await gather` | `g.Wait()` |
| 限并发 | 信号量包一层 | `g.SetLimit(n)` |

> **结论：新代码并发一组任务，优先 `errgroup`，别手撸 `WaitGroup`+错误收集+取消**——那些坑它都替你处理了。

### 3.5 限流：两种「限」

**① 限并发度（同时在飞几个）—— 信号量**。最简单用带缓冲 channel 当信号量：

```go
sem := make(chan struct{}, maxConcurrency)
for _, task := range tasks {
    sem <- struct{}{}                     // 拿令牌（满了就阻塞）
    go func(t Task) {
        defer func() { <-sem }()          // 还令牌
        do(t)
    }(task)
}
```
（或用 `golang.org/x/sync/semaphore` 的加权信号量；`errgroup.SetLimit` 也是这个作用。）

**② 限速率（每秒多少个）—— 令牌桶**：

```go
import "golang.org/x/time/rate"
limiter := rate.NewLimiter(rate.Limit(100), 10)   // 100 次/秒，突发 10
for ... {
    if err := limiter.Wait(ctx); err != nil { return err }  // 阻塞到拿到令牌
    call()
}
```

> 别混淆：**并发度**（同时几个）和**速率**（每秒几个）是两件事，常常要一起用。

### 3.6 超时重试（退避 + 抖动）

```go
func withRetry(ctx context.Context, fn func(context.Context) error) error {
    backoff := 100 * time.Millisecond
    for attempt := 0; attempt <= maxRetries; attempt++ {
        err := fn(ctx)
        if err == nil || !retryable(err) {        // 成功或不可重试 → 收
            return err
        }
        if attempt == maxRetries {
            return err
        }
        jitter := time.Duration(rand.Int63n(int64(backoff)))   // 抖动，防重试风暴
        select {
        case <-time.After(backoff + jitter):
        case <-ctx.Done():                        // 重试等待期间也要响应取消
            return ctx.Err()
        }
        backoff *= 2                              // 指数退避
    }
    return nil
}
```

### 3.7 singleflight —— 防缓存击穿

热点 key 缓存失效瞬间，成百上千并发请求同时打 DB（击穿）。`singleflight` 让同一 key 的并发请求**只执行一次**，其余等结果：

```go
import "golang.org/x/sync/singleflight"
var g singleflight.Group

func getUser(id string) (*User, error) {
    v, err, _ := g.Do(id, func() (any, error) {   // 同一 id 并发只跑一次回源
        return loadFromDB(id)
    })
    if err != nil { return nil, err }
    return v.(*User), nil
}
```

---

## 4. 日常开发应用：优雅关闭

服务下线要「停止接新活、放干在途活、限时兜底」。标准骨架：

```go
func main() {
    // 收到 SIGINT/SIGTERM 时自动 cancel 这个 ctx（07）
    ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
    defer stop()

    srv := &http.Server{Addr: ":8080", Handler: mux}
    go func() {
        if err := srv.ListenAndServe(); err != nil && err != http.ErrServerClosed {
            log.Fatal(err)
        }
    }()

    <-ctx.Done()                          // 阻塞直到收到关闭信号
    log.Println("shutting down...")

    shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()
    if err := srv.Shutdown(shutdownCtx); err != nil {   // 停止接新请求，等在途完成（限 10s）
        log.Printf("forced shutdown: %v", err)
    }
}
```

后台 worker 同理：用 `ctx` 让所有 worker 收手，`WaitGroup` 等它们排空再退出主程序。

---

## 5. 生产&调优实战

- **池大小怎么定**：CPU 密集 ≈ 核数（`GOMAXPROCS`）；I/O 密集可远大于核数（多数时间在等），按下游承载力和延迟压测定，不是越大越好——太大反而压垮下游/撑爆 M（`03` 文件/cgo 类活）。
- **背压（backpressure）要显式**：用有界 channel / 信号量让上游在下游忙时**自然阻塞**，而不是无限缓冲把问题往后拖到 OOM（呼应 `05` 缓冲选择）。
- **重试三铁律**：① 只重试**可重试错误**（超时/503，别重试 400/鉴权失败）；② **退避 + 抖动**防重试风暴；③ 被重试的操作要**幂等**，否则重试 = 重复副作用。
- **限流放哪层**：客户端限流（保护下游）、服务端限流（保护自己）常都要；令牌桶 `rate.Limiter` 是标准件。
- **errgroup 的错误只留第一个**：`g.Wait()` 只返回第一个非 nil error，其余被丢。要全收集就自己加 `sync.Mutex`+slice，或用支持多错误的封装。

---

## 6. 面试高频考点

- **怎么并发调用 N 个下游服务？**（高频）`errgroup.WithContext` + `g.SetLimit` 限并发 + `g.Go` 每个任务返回 error + `g.Wait` 收第一个错并联动取消。能说出「和 asyncio gather/TaskGroup 一回事」加分。
- **worker pool 怎么实现？** 固定 N 个 goroutine `for range jobs`；独立 goroutine `wg.Wait` 后 `close(results)`；ctx 控制取消。
- **errgroup 比 WaitGroup 强在哪？** WaitGroup 只等待、不处理错误和取消；errgroup 收集首个错误 + 出错自动 cancel 派生 ctx + SetLimit 限并发。
- **怎么限并发度？和限速率区别？** 并发度用信号量（带缓冲 channel / semaphore / SetLimit）；速率用令牌桶 `rate.Limiter`；前者管"同时几个"，后者管"每秒几个"。
- **重试要注意什么？** 只重试可重试错误、指数退避+抖动、操作幂等、重试期间响应 ctx 取消。
- **怎么优雅关闭？** `signal.NotifyContext` 收信号 → cancel ctx → `srv.Shutdown(timeoutCtx)` 停接新请求+放干在途 → WaitGroup 等后台 worker 排空。
- **缓存击穿怎么防？** singleflight 合并同 key 并发回源；配合空值缓存/随机过期。

---

## 7. 一句话总结

> **并发模式的母题 = 把"无限开 goroutine"约束成"受控并发度"。** 处理一批任务用 worker pool；并发一组任务+错误+取消用 **errgroup**（= Go 版 gather/TaskGroup，新代码首选）；限并发用信号量、限速率用令牌桶；重试要可重试+退避抖动+幂等；优雅关闭 = 信号→cancel→Shutdown→排空。这些骨架全是 `04–07` 原语的组装。

← 上一章 [`07 context`](../07-context/README.md) ｜ 下一章 → [`09 陷阱与调优`](../09-pitfalls-tuning/README.md)：把全课的坑和排查工具（泄漏/死锁/GOMAXPROCS/pprof/trace）收口。
