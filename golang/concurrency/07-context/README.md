# 07 · context 与取消传播

> `04` 反复强调「每个 goroutine 要有退出路径」，`05` 给了 done channel 的雏形。本章讲把它**标准化**的工具：`context`——一个请求 fan-out 出几十个 goroutine 时，怎么**统一超时、统一取消、统一防泄漏**。
>
> 桥接锚点：context 取消 ≈ Java 的线程中断（`Thread.interrupt` + 协作检查），但**显式沿调用链传播**。

---

## 1. 核心问题

一个 HTTP 请求进来，你为它并发调了 DB、缓存、3 个下游 RPC，各开 goroutine。这时：

- 客户端断开了 / 请求超时了 → 怎么**一键通知这一整棵 goroutine 都别干了**、立刻收手？
- 上游设了 500ms 超时 → 怎么让这个**截止时间穿透**到每一个下游调用？
- 取消信号怎么不漏掉，避免某个 goroutine 永久等待（`04` 的泄漏）？

`context` 就是 Go 对这三件事的标准答案：**一个能沿调用链层层传递的「取消信号 + 截止时间 + 请求值」载体。**

---

## 2. 直觉理解

### context = 标准化的「done channel + 截止时间」

回忆 `05` 的 done channel：`close(done)` 广播「都退出吧」。`context` 就是把它**封装成统一接口**，再加上「截止时间」和「请求级值」：

```go
type Context interface {
    Done() <-chan struct{}        // 取消信号：被取消时这个 channel 关闭（= 广播）
    Err() error                   // 为什么结束：Canceled / DeadlineExceeded
    Deadline() (time.Time, bool)  // 有没有截止时间
    Value(key any) any            // 取请求级值（trace id 等）
}
```

你在 goroutine 里 `select { case <-ctx.Done(): return }`，就接上了这套取消广播。

### 取消树：父取消，子全取消

context 是**派生**的——从一个父 context 派生出子 context，形成一棵树：

```
ctx(请求根, 500ms 超时)
 ├── ctxDB     = WithTimeout(ctx, 200ms)
 ├── ctxRPC1   = WithCancel(ctx)
 └── ctxRPC2   = WithCancel(ctx)
```

**取消向下传播**：取消（或超时）父节点，整棵子树同时收到 `Done()`。这正是「一键通知一整棵 goroutine」的机制。

### 对照 Java 线程中断

| | Java | Go context |
|---|---|---|
| 取消信号 | `thread.interrupt()` | `cancel()` / 超时 |
| 检查点 | `Thread.interrupted()` / 抛 `InterruptedException` | `select <-ctx.Done()` / `ctx.Err()` |
| 传播 | 隐式挂在线程上 | **显式**把 ctx 传给每个下游 |
| 截止时间 | `Future.get(timeout)` | `WithTimeout` 穿透整条链 |

都是**协作式**取消——被取消方必须主动检查、主动收手；没人能强杀一个 goroutine。

---

## 3. 原理深入

### 3.1 构造器家族

```go
context.Background()                    // 根，常用于 main / 请求入口
context.TODO()                          // 占位：还不知道用哪个 ctx 时（别传 nil）

ctx, cancel := context.WithCancel(parent)        // 手动取消
ctx, cancel := context.WithTimeout(parent, d)    // d 之后自动取消
ctx, cancel := context.WithDeadline(parent, t)   // 到时间点 t 自动取消
ctx := context.WithValue(parent, key, val)       // 挂一个请求级值
```

- `WithTimeout` 本质 = `WithDeadline(parent, now+d)`。
- 凡是返回 `cancel` 的，**必须调用 cancel**（即使已超时也要调，用来释放资源）——见 5 节。
- Go 1.20+ 有 `WithCancelCause` / `context.Cause(ctx)`：能携带「为什么取消」的具体 error，比单纯 `Canceled` 信息多。

### 3.2 取消怎么沿树传播

`WithCancel` 返回的内部是个 `cancelCtx`，它持有：

- 一个 `done` channel；
- 一个 `children` 集合（它派生出的可取消子 context）。

调用 `cancel()` 时：

```
cancel():
  ① 关闭自己的 done channel  → 所有 select <-ctx.Done() 的 goroutine 被唤醒（广播，复用 05 的 close 机制）
  ② 设置 Err() = Canceled（或超时 = DeadlineExceeded）
  ③ 递归 cancel 所有 children
  ④ 把自己从 parent 的 children 里摘除（释放引用）
```

`WithTimeout`/`WithDeadline` 多一步：内部起一个 `time.AfterFunc` 定时器，到点自动调 `cancel()`。所以**超时 = 定时器触发的取消**，走的还是上面同一套传播。

> 这也解释了为什么取消是 O(树大小) 的廉价广播：就是关 channel + 递归关子节点，没有轮询。

### 3.3 Err() 区分结束原因

```go
<-ctx.Done()
switch ctx.Err() {
case context.Canceled:          // 被显式 cancel
case context.DeadlineExceeded:  // 超时
}
```

`ctx.Done()` 未关闭时 `Err()` 返回 nil。

---

## 4. 日常开发应用

### 传播惯例（社区铁律）

```go
// ctx 永远是第一个参数，名字就叫 ctx
func FetchUser(ctx context.Context, id int) (*User, error) {
    // 把 ctx 继续传给每一个下游调用——这就是"穿透"
    row := db.QueryRowContext(ctx, "SELECT ... WHERE id=$1", id)
    ...
}
```

- **首参 ctx，贯穿整条调用链**。标准库的 `http`、`database/sql`、grpc 都接受 `ctx` 并在内部 `select <-ctx.Done()`，所以你只要把 ctx 一路传下去，超时/取消就自动穿透到网络层。
- **不要把 ctx 存进 struct 字段**——它是「每次调用的」上下文，应当显式传参。

### 必须 defer cancel

```go
ctx, cancel := context.WithTimeout(parent, time.Second)
defer cancel()                  // 哪怕提前成功返回，也要 cancel 释放资源
resp, err := callDownstream(ctx)
```

### 给 goroutine 退出路径（回收 `04` 的泄漏）

```go
func worker(ctx context.Context, jobs <-chan Job) {
    for {
        select {
        case <-ctx.Done():      // 取消信号到 → 退出，不泄漏
            return
        case job := <-jobs:
            process(ctx, job)   // 继续往下传 ctx
        }
    }
}
```

### Value 要克制

```go
type ctxKey struct{}            // 用未导出类型做 key，避免跨包碰撞
ctx = context.WithValue(ctx, ctxKey{}, traceID)
id, _ := ctx.Value(ctxKey{}).(string)
```

- **只放请求级元数据**（trace id、用户身份、deadline），**不要拿来传函数参数**——那会让依赖变隐式、难测。
- key 用未导出的自定义类型，杜绝 `string` key 撞车。

---

## 5. 生产&调优实战

- **不调 cancel = 资源泄漏**：`WithTimeout`/`WithCancel` 内部挂了定时器和 parent 的 children 引用。不调 `cancel`，这些要等父 context 结束或超时才释放——在长生命周期父 ctx 下就是泄漏。`go vet` 的 **lostcancel** 会报「the cancel function is not used」。务必 `defer cancel()`。
- **超时分层**：整条请求一个总超时，单次下游调用可再套更短的子超时（`WithTimeout(ctx, ...)`），避免一个慢下游拖垮整体。子超时不会超过父截止时间（取更早的那个）。
- **区分超时来源**：日志/监控里用 `ctx.Err()` 和 `context.Cause(ctx)`（1.20+）区分「主动取消」「整体超时」「某层子超时」，定位「谁先到点」。
- **取消要快**：下游若在持锁/大循环里，要在循环内 `select <-ctx.Done()` 周期检查，否则取消信号到了它还在埋头干（协作式取消的代价）。
- **数据库/HTTP 用带 Context 的方法**：`QueryContext`/`ExecContext`/`http.NewRequestWithContext`，让取消能真正中断底层 I/O。

---

## 6. 面试高频考点

- **context 是干什么的？** 沿调用链传递取消信号 + 截止时间 + 请求级值；统一控制一棵 goroutine 的超时/取消，防泄漏。
- **取消是怎么传播的？** context 派生成树；cancel 关闭自己的 done channel（广播）+ 设 Err + 递归取消子节点 + 从父摘除。超时是定时器触发的 cancel。
- **WithCancel / WithTimeout / WithDeadline / WithValue 区别？** 手动取消 / 相对时长后自动取消 / 绝对时间点取消 / 挂请求值；前三个返回必须调用的 cancel。
- **为什么一定要 defer cancel()？** 释放内部定时器和父 context 的子引用，不调会泄漏；go vet lostcancel 检查。
- **context.Value 该用吗？** 仅请求级元数据（trace/auth），不传业务参数；key 用未导出类型防碰撞；滥用会让依赖隐式。
- **能存 ctx 到 struct 吗？** 不应该——ctx 是每次调用的上下文，应显式作首参传递。
- **和 channel / 线程中断的关系？** context 内部就是标准化的 done channel（close 广播）；语义上类似 Java 线程中断的协作式取消，但显式沿链传播 + 带截止时间。
- **超时了 goroutine 会被强杀吗？** 不会。协作式——goroutine 必须自己 select <-ctx.Done() 才会停。

---

## 7. 一句话总结

> **context = 标准化的「取消广播（done channel）+ 截止时间 + 请求值」，沿调用链显式传播、派生成取消树。** 父取消则整棵子树同时收到 `Done()`；超时 = 定时器触发的取消；它是给一整批 goroutine 统一退出路径、防泄漏的标准工具。铁律：ctx 作首参贯穿全链、`defer cancel()`、Value 只放请求级元数据。协作式取消——没人能强杀 goroutine，被取消方得自己检查。

← 上一章 [`06 sync 与内存模型`](../06-sync-memory-model/README.md) ｜ 下一章 → [`08 并发模式`](../08-patterns/README.md)：把前面所有原语组装成 worker pool / fan-in-out / pipeline / errgroup 等实战骨架。
