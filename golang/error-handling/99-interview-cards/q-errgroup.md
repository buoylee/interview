# 并发错误:errgroup / errors.Join / goroutine panic

## 一句话回答

N 个 goroutine 的错误,按需求三选一:**首错即停**用 `errgroup.WithContext`(第一个非 nil 错误 cancel 派生 ctx 通知其余收手,`Wait` 返回那个首错,默认只留一个错误);**全收齐**用 `errors.Join`(1.20,实现 `Unwrap() []error`,`Is`/`As` 可遍历);**细粒度**用 error channel + WaitGroup。而 **panic 是另一回事**:`recover` 只救当前 goroutine,任何 `go` 出去的协程未自带 recover 而 panic 会 **crash 整个进程**,errgroup 也**不兜** panic。

## 三种聚合策略

| 需求 | 工具 | 行为 |
|---|---|---|
| 首错即停 | `errgroup.Group` + `WithContext` | 首个错 cancel ctx,`Wait` 返首错 |
| 全收齐 | `errors.Join(errs...)` | 聚合所有非 nil 错误,`Unwrap() []error` |
| 自己控 | error channel + `WaitGroup` | 手动收发(缓冲要够,否则泄漏) |

```go
g, ctx := errgroup.WithContext(ctx)
g.Go(func() error { return callA(ctx) })
g.Go(func() error { return callB(ctx) })
return g.Wait()          // 任一出错 → cancel ctx → 其余监听 ctx.Done() 收手;返回首错
```

## errgroup vs WaitGroup

- WaitGroup:只等,不管错误。
- errgroup:= WaitGroup + 收**第一个**错误 +(`WithContext` 时)**首错取消** + `SetLimit(n)` 限并发。
- ⚠️ errgroup 默认**只留第一个**错误,要全收用 `errors.Join`。

## goroutine panic = 整进程 crash

```go
go func() { panic("boom") }()    // 没人 recover → crash 整个程序(不是只死这一个协程)
```

`recover` 只对**当前 goroutine** 有效;主协程的 recover 接不住子协程的 panic。**铁律:每个 `go` 出去的协程自带 recover**(封装 safe-go),否则一个后台协程的边缘 panic 能掀翻整个服务。errgroup 的 `g.Go` 只收返回的 error,**不兜 panic**——任务内要自己 recover 转 error。

## 证据链接

- 正文:[`05 并发中的错误`](../05-concurrent-errors/README.md)
- 互链:[`concurrency/08-patterns`](../../concurrency/08-patterns/README.md)(errgroup 并发机制) / [`concurrency/07-context`](../../concurrency/07-context/README.md)(取消传播) / [`concurrency/04-goroutine`](../../concurrency/04-goroutine/README.md)(泄漏/panic)

## 易追问的延伸

- **首错取消能真中断下游吗?** 只有下游用带 ctx 的调用(`QueryContext`/`NewRequestWithContext`)并监听 `ctx.Done()` 才行(协作式)。
- **为什么只看到一个错误?** errgroup 默认只留首错;要全收用 `errors.Join`。
- **error channel 注意?** 缓冲要够 + 必须有人收,否则发送方永久阻塞 = goroutine 泄漏。
- **errgroup 忘了 Wait?** 协程可能泄漏、错误也丢——必须 `Wait`。
