# 05 · 并发中的错误:errgroup、errors.Join、goroutine panic

> 单 goroutine 的错误前四章讲完了。并发把问题放大:一个请求 fan-out 出 N 个 goroutine,**N 个错误怎么收?第一个出错要不要取消其余?goroutine 里 panic 了会怎样?** 这章收尾,和 [`concurrency/08-patterns`](../../concurrency/08-patterns/README.md) 互链——那边讲 errgroup 的**并发机制**,这边只讲它的**错误**这一面。
>
> 桥接锚点:errgroup ≈ Java 的 `invokeAll` + 首个异常取消;`errors.Join` ≈ 把多个并行任务的异常 `addSuppressed` 聚合;goroutine panic ≈ 一个线程未捕获异常——但 Go 的后果更严重(整进程挂)。

---

## 1. 核心问题

```go
// 并发调 3 个下游,每个都可能出错
func fanout(ctx context.Context) error {
    go callA(ctx)   // err?
    go callB(ctx)   // err?
    go callC(ctx)   // err? 而且 callB 里要是 panic 了呢?
    // 怎么等它们、怎么收集错误、第一个失败要不要让其它别白干?
}
```

- N 个 goroutine 的错误,**怎么收集**?要**第一个错就停**,还是**全收齐**?
- goroutine 里 `panic` 了,主协程能接住吗?(03 章已剧透:不能)
- 裸 `go func()` 起协程,错误和 panic 都没人管——生产上怎么兜?

---

## 2. 直觉理解

三种聚合策略,按需求选:

| 需求 | 工具 | 行为 |
|---|---|---|
| **首错即停**(一个失败,其余没必要继续) | `errgroup.Group` + `WithContext` | 第一个非 nil 错误**取消 ctx**,`Wait` 返回那个首错 |
| **全收齐**(每个都要,汇总所有失败) | `errors.Join`(1.20) | 收集所有非 nil 错误聚合成一个 |
| **自己控制**(细粒度) | error channel + `sync.WaitGroup` | 手动收发 |

而 panic 是另一回事:**goroutine 的 panic 不是错误、不会变成返回值**,没被它**自己**recover 就**直接 crash 整个进程**。所以「每个 go 出去的协程自带 recover」是并发错误处理的铁律。

---

## 3. 原理深入

### 3.1 errgroup:首错取消的标准工具

```go
import "golang.org/x/sync/errgroup"

func fanout(ctx context.Context) error {
    g, ctx := errgroup.WithContext(ctx)        // 派生出会被首错取消的 ctx
    g.Go(func() error { return callA(ctx) })   // 每个任务一个 g.Go
    g.Go(func() error { return callB(ctx) })
    g.Go(func() error { return callC(ctx) })
    return g.Wait()                            // 等全部结束,返回"第一个"非 nil 错误
}
```

机制(错误这一面):

- `g.Go(f)` 起一个 goroutine 跑 `f`;`f` 返回非 nil 错误时,errgroup 用 `sync.Once` 记下**第一个**错误,并(若用了 `WithContext`)**cancel 那个派生 ctx**——其余还在跑、且监听 `ctx.Done()` 的任务因此被通知收手(协作式取消,见 [`concurrency/07-context`](../../concurrency/07-context/README.md))。
- `g.Wait()` 阻塞到所有任务结束,返回那个首错(没错则 nil)。
- `g.SetLimit(n)`(较新版本)可限制并发数,当 worker pool 用。

> 注意:errgroup 默认只留**第一个**错误,后续错误被丢弃。要「全收齐」用下面的 Join。

### 3.2 errors.Join:聚合所有错误

```go
func processAll(items []Item) error {
    var errs []error
    for _, it := range items {
        if err := process(it); err != nil {
            errs = append(errs, fmt.Errorf("item %s: %w", it.ID, err))
        }
    }
    return errors.Join(errs...)        // nil 会被忽略;全 nil 则返回 nil
}
```

- `errors.Join` 返回的错误实现 `Unwrap() []error`,所以 `errors.Is`/`As` 能**对每个子错误**匹配(02 章 3.4 的树遍历)。
- 并发场景配合:每个 goroutine 把错误塞进一个受 mutex 保护的 slice(或 channel),最后 `errors.Join`。

并发收集 + Join 的骨架:

```go
var (
    mu   sync.Mutex
    errs []error
    wg   sync.WaitGroup
)
for _, t := range tasks {
    wg.Add(1)
    go func(t Task) {
        defer wg.Done()
        if err := t.Run(); err != nil {
            mu.Lock(); errs = append(errs, err); mu.Unlock()
        }
    }(t)
}
wg.Wait()
return errors.Join(errs...)
```

### 3.3 goroutine 的 panic = 整进程 crash

```go
func main() {
    defer func() { recover() }()      // ❌ 救不了下面的 goroutine
    go func() { panic("boom") }()     // 这个 panic 没人 recover → 整个进程 crash
    time.Sleep(time.Second)
}
```

03 章讲过:`recover` 只对**当前 goroutine** 有效。一个 goroutine 的 panic 没被它**自己的** defer-recover 接住,会一路展开到该 goroutine 顶端,**终止整个程序**(不是只死那一个协程)。这是 Go 并发最危险的坑之一——一个后台协程的 panic 能掀翻整个服务。

**铁律:每个你 `go` 出去的 goroutine,都要自带 recover**。封装一个 safe-go:

```go
func Go(fn func()) {
    go func() {
        defer func() {
            if r := recover(); r != nil {
                log.Printf("goroutine panic: %v\n%s", r, debug.Stack())
                // 上报 metric / 告警
            }
        }()
        fn()
    }()
}
```

> errgroup 的 `g.Go` **本身不 recover** panic——它只捕获 `f` 返回的 error。如果 `f` 内部 panic,一样 crash 进程。需要的话在传给 `g.Go` 的函数里自己 recover 转成 error 返回。

### 3.4 用 channel 传错误(细粒度场景)

```go
errCh := make(chan error, len(tasks))   // 有缓冲,避免发送方阻塞泄漏
for _, t := range tasks {
    go func(t Task) { errCh <- t.Run() }(t)
}
for range tasks {
    if err := <-errCh; err != nil { /* 收集/处理 */ }
}
```

⚠️ channel 容量不足 + 没人收 = 发送方 goroutine 永久阻塞 = **泄漏**(见 [`concurrency/04-goroutine`](../../concurrency/04-goroutine/README.md))。

---

## 4. 日常开发应用

- **fan-out 调下游、首错即停** → `errgroup.WithContext`,最常用。记得每个任务**把 ctx 传下去**并监听取消,否则「取消」没人理。
- **批处理、要汇总所有失败**(校验一批、批量导入) → `errors.Join`。
- **起后台常驻协程**(消费者、定时任务) → 用 safe-go 包一层 recover,否则一次 panic 掀翻服务。
- **errgroup 一定要 `Wait`**:不 Wait 就 return,协程可能泄漏、错误也丢了。
- 错误里带上**是哪个任务**的上下文(`fmt.Errorf("item %s: %w", id, err)`),否则聚合后分不清谁错了。

---

## 5. 生产&调优实战

- **后台 goroutine 的 panic 是「静默杀手」**:它不像请求处理有框架兜底。所有长生命周期协程、消费者、worker,**必须**自带 recover + 告警,否则线上一个边缘 panic 直接重启进程。
- **首错取消 vs 全收齐的取舍**:对外聚合调用(凑齐 N 个下游结果)通常**首错即停**省资源;但「批量操作要告诉用户每条的成败」就得**全收**(Join)。别用 errgroup 然后奇怪「为什么只看到一个错误」。
- **errgroup 不兜 panic**:误以为 `g.Go` 会把 panic 变 error 是常见错觉。要么在任务内 recover 转 error,要么接受它会 crash。
- **取消要能穿透**:errgroup 取消的是 ctx,下游必须用带 ctx 的调用(`QueryContext`/`http.NewRequestWithContext`)才能真正中断,否则首错了别的还在白跑。
- **错误聚合别丢上下文**:并发收集时给每个错误打上任务标识 + `%w`,聚合后还能 `Is`/`As`、还能定位。

---

## 6. 面试高频考点

- **N 个 goroutine 的错误怎么收?** 首错即停用 `errgroup`(`WithContext` 让首错 cancel 其余,`Wait` 返首错);全收齐用 `errors.Join`(实现 `Unwrap() []error`,`Is`/`As` 可遍历);细粒度用 error channel + WaitGroup。
- **errgroup 和 WaitGroup 区别?** WaitGroup 只等、不管错误;errgroup = WaitGroup + 收集首个错误 + (WithContext 时)首错取消。errgroup 默认只留第一个错误。
- **goroutine 里 panic 会怎样?主协程能 recover 吗?** 不能——recover 只对当前 goroutine 有效;未被自己 recover 的 goroutine panic 会 **crash 整个进程**。每个 go 出去的协程要自带 recover。
- **errgroup 会捕获任务里的 panic 吗?** 不会,它只收 `f` 返回的 error;`f` 内 panic 照样 crash。需要就在任务里 recover 转 error。
- **errors.Join 是什么?怎么和 Is 配合?** 1.20+ 聚合多个错误,`Unwrap() []error`,`errors.Is`/`As` 对每个子错误递归匹配。
- **用 channel 传错误注意什么?** 缓冲要够 / 必须有人收,否则发送方阻塞泄漏。
- **首错取消能真正中断下游吗?** 只有下游用带 ctx 的调用并监听 `ctx.Done()` 才行(协作式取消)。

---

## 7. 一句话总结

> **并发错误三策略:首错即停用 `errgroup.WithContext`(第一个错 cancel 派生 ctx、`Wait` 返首错,默认只留一个错误);全收齐用 `errors.Join`(`Unwrap() []error`,`Is`/`As` 可遍历);细粒度用 error channel + WaitGroup(注意缓冲/收取,否则泄漏)。** 而 panic 是另一回事:**`recover` 只救当前 goroutine,任何 `go` 出去的协程未自带 recover 而 panic,会 crash 整个进程**——errgroup 也不兜 panic。铁律:每个 goroutine 自带 recover + 告警;首错取消要让下游传 ctx 才真能中断;聚合错误给每个打上任务标识 + `%w` 以便定位。

← 上一章 [`03 panic·recover·defer`](../03-panic-recover-defer/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md):速答表 + 深题卡(error vs 异常 / `%w`·Is·As / defer·recover 时机 / 何时 panic / errgroup)。｜ 回 [`error-handling` 索引](../README.md)
