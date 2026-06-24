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

## 3. 原理深入：把 `context.go` 拆开

> 这一节照 Go 1.25 的 `src/context/context.go` 走读。整个包才 ~800 行，值得一啃——啃完你能在白板上把取消树默写个七八成。

### 3.1 不是一个类型，是一族类型

`Context` 是个 4 方法接口，标准库给了一族实现，各管一摊，**靠组合内嵌拼起来**。先把「哪个构造器产出哪个类型」对上号：

| 类型 | 由谁产出 | 负责什么 | 关键手法 |
|---|---|---|---|
| `emptyCtx` | `Background()` / `TODO()` | 永不取消的空根：`Done()` 返回 `nil`、`Err()` 返回 `nil`、无 deadline、无值 | `backgroundCtx`/`todoCtx` 内嵌它，只多个 `String()` |
| `cancelCtx` | `WithCancel` / `WithCancelCause` | 取消的核心引擎：done channel + children 集合 | 内嵌 `Context`（指向 parent） |
| `timerCtx` | `WithDeadline` / `WithTimeout` | 在 cancelCtx 上加「定时器 + 截止时间」 | **内嵌 `cancelCtx`**，Done/Err/cancel 全白嫖 |
| `valueCtx` | `WithValue` | 挂一对 k-v | 内嵌 `Context`，只重写 `Value` |
| `withoutCancelCtx` | `WithoutCancel`（1.21） | 切断取消传播、保留值 | `Done()` 返回 `nil` |

> `Background()` / `TODO()` 都返回内嵌 `emptyCtx` 的类型，区别只在 `String()`——语义都是「永不取消的空根」；不确定用哪个 ctx 时传 `TODO()`，**永远别传 `nil`**。（另有 `afterFuncCtx`/`stopCtx` 服务于 `AfterFunc`，3.9 再提。）

记住一句：**`cancelCtx` 是取消机制的唯一引擎**。`timerCtx` 只是给它装了个闹钟；其余类型要么根本不取消（empty/value/withoutCancel），要么内嵌它来蹭。

### 3.2 解剖 `cancelCtx`

```go
type cancelCtx struct {
    Context                       // 内嵌 parent —— Deadline/Value 默认转发给它

    mu       sync.Mutex            // 保护下面四个字段
    done     atomic.Value          // of chan struct{}，懒创建，首次 cancel 时关闭
    children map[canceler]struct{} // 它派生出的可取消子节点；首次 cancel 后置 nil
    err      atomic.Value          // of error，首次 cancel 时写入（Canceled / DeadlineExceeded）
    cause    error                 // 具体取消原因（WithCancelCause 用），首次 cancel 写入
}
```

两个设计点值得停一下：

- **`children` 存的是 `canceler` 接口，不是 `*cancelCtx`：**

  ```go
  type canceler interface {
      cancel(removeFromParent bool, err, cause error)
      Done() <-chan struct{}
  }
  ```

  实现它的有 `*cancelCtx`、`*timerCtx`、`*afterFuncCtx`。存接口而非具体指针，父节点才能一视同仁地 `child.cancel(...)`，不必关心子节点带不带闹钟——**取消传播对子类型多态**。

- **`err` 是 `atomic.Value` 而不是裸 `error`**，这样 `Err()` 走一次原子读、不抢锁：

  ```go
  func (c *cancelCtx) Err() error {
      if err := c.err.Load(); err != nil {   // 注释原话：atomic load ~5x faster than a mutex
          <-c.Done()                          // 返回非 nil err 前先确保 done 已关（见 3.8 内存序）
          return err.(error)
      }
      return nil
  }
  ```

  `Err()` 常在热路径（循环里反复 `ctx.Err()`）被高频调，所以专门优化成无锁读。`done` 未关闭时 `err` 为 nil → 返回 nil；关闭后是 `Canceled`（显式取消）或 `DeadlineExceeded`（超时）。

### 3.3 `Done()` 为什么是懒创建的

注意 `done` 是 `atomic.Value`，**不是构造时就 `make` 好的 channel**——第一次有人调 `Done()` 才建：

```go
func (c *cancelCtx) Done() <-chan struct{} {
    d := c.done.Load()
    if d != nil {                  // 快路径：已建，原子读直接返回
        return d.(chan struct{})
    }
    c.mu.Lock()                    // 慢路径：加锁
    defer c.mu.Unlock()
    d = c.done.Load()              // 双重检查（防两个 goroutine 同时进来重复 make）
    if d == nil {
        d = make(chan struct{})
        c.done.Store(d)
    }
    return d.(chan struct{})
}
```

为什么懒？——**很多 context 从生到死没人 `select <-ctx.Done()`**（比如只用来把 deadline 透给下游、自己不监听），给每个 ctx 都预建 channel 是浪费。这是「双重检查锁（DCL）」的经典落地：快路径无锁原子读，只有第一次创建走锁。

> 面试点：「`context.Background().Done()` 返回什么？」——返回 `nil`（emptyCtx）。对 `nil` channel 的 `<-` 永久阻塞，所以 `select` 里那个分支永不被选中，语义正好是「永不取消」。

### 3.4 `cancel()` 一行行看

`WithCancel` 返回的 cancel 函数，本体是 `c.cancel(true, Canceled, nil)`：

```go
func (c *cancelCtx) cancel(removeFromParent bool, err, cause error) {
    // ... err 不能为 nil；cause 为 nil 时取 err
    c.mu.Lock()
    if c.err.Load() != nil {       // ① 幂等：已取消过直接返回（CancelFunc 允许被多次调用）
        c.mu.Unlock()
        return
    }
    c.err.Store(err)               // ② 写 err / cause —— 这一步定了 Err() 的返回值
    c.cause = cause
    d, _ := c.done.Load().(chan struct{})
    if d == nil {
        c.done.Store(closedchan)   // ③ 没人建过 done → 直接塞一个「预关闭」的复用 channel
    } else {
        close(d)                   //    建过 → 关掉它（广播，复用 05 的 close 机制）
    }
    for child := range c.children {        // ④ 递归取消所有子节点（持着父锁拿子锁）
        child.cancel(false, err, cause)    //    removeFromParent=false：整棵都要倒，没必要逐个摘
    }
    c.children = nil               // ⑤ 清空 children，断引用
    c.mu.Unlock()

    if removeFromParent {          // ⑥ 把自己从 parent 的 children 里摘掉
        removeChild(c.Context, c)
    }
}
```

几个源码细节是高频考点：

- **③ `closedchan`**：包级一个 `var closedchan = make(chan struct{})`，`init()` 里就 `close` 了。若某 ctx 从没人调过 `Done()`（done 还没建），取消时不必现 make 再 close，直接把这个**全局预关闭 channel** 塞进去——省一次分配。之后谁调 `Done()` 拿到的就是已关闭 channel，立刻可读。
- **④ 递归 + `removeFromParent=false`**：取消父节点时，子节点逐个 `cancel(false,...)`——传 false 是因为整棵子树都要清掉，逐个去父 map 里 `delete` 是多余的（⑤ 已把整个 map 置 nil）。只有**最初被显式 cancel 的那个节点**（⑥）才需要从它**还活着的** parent 里摘自己。
- **⑥ `removeChild` 防泄漏**：这就是「不调 cancel 会泄漏」的源码依据——子节点会一直挂在 parent 的 `children` map 里，parent 不死它就不死。`removeChild` 调 `parentCancelCtx` 找到父的 `*cancelCtx`，`delete(p.children, child)`。

### 3.5 `propagateCancel`：子怎么挂到父上（最硬的一段）

派生一个 cancelCtx 时，要让它「父取消时自己也被取消」。这件事由 `propagateCancel` 完成，是整个包最精妙的函数：

```go
func (c *cancelCtx) propagateCancel(parent Context, child canceler) {
    c.Context = parent                    // 内嵌字段指向 parent

    done := parent.Done()
    if done == nil {
        return                            // (a) parent 永不取消（如 Background）→ 无需挂，直接返回
    }
    select {
    case <-done:
        child.cancel(false, parent.Err(), Cause(parent))  // (b) parent 已取消 → 立刻取消 child
        return
    default:
    }

    if p, ok := parentCancelCtx(parent); ok {
        // (c) 99% 的情况：parent 是 *cancelCtx 或派生自它 → 直接挂进它的 children map
        p.mu.Lock()
        if err := p.err.Load(); err != nil {
            child.cancel(false, err.(error), p.cause)      // 挂的瞬间发现父刚被取消
        } else {
            if p.children == nil {
                p.children = make(map[canceler]struct{})
            }
            p.children[child] = struct{}{}
        }
        p.mu.Unlock()
        return
    }

    if a, ok := parent.(afterFuncer); ok {
        // (d) parent 实现了 AfterFunc 方法 → 用它注册回调（1.21 引入的快路径，免起 goroutine）
        // ... 把 c.Context 换成 stopCtx 以便日后注销
        return
    }

    goroutines.Add(1)
    go func() {                            // (e) 兜底：parent 是个「陌生的」自定义 Context
        select {
        case <-parent.Done():
            child.cancel(false, parent.Err(), Cause(parent))
        case <-child.Done():
        }
    }()
}
```

分支 (c) 是绝大多数情况——你的 parent 基本都从标准库派生而来。但它怎么知道「parent 是不是 cancelCtx 或其派生」？靠 `parentCancelCtx`：

```go
var cancelCtxKey int   // 一个哨兵 key（只用它的地址）

func parentCancelCtx(parent Context) (*cancelCtx, bool) {
    done := parent.Done()
    if done == closedchan || done == nil {
        return nil, false
    }
    p, ok := parent.Value(&cancelCtxKey).(*cancelCtx)   // ★ 用哨兵 key 把里头的 cancelCtx「问」出来
    if !ok {
        return nil, false
    }
    pdone, _ := p.done.Load().(chan struct{})
    if pdone != done {            // ★ 校验：问出来的 cancelCtx 的 done，得跟 parent.Done() 是同一个
        return nil, false
    }
    return p, true
}
```

这里有两个非常 Go 的技巧：

- **哨兵 key `&cancelCtxKey`**：`cancelCtx.Value` 对这个 key 做了特判，**返回自己**：

  ```go
  func (c *cancelCtx) Value(key any) any {
      if key == &cancelCtxKey {
          return c            // 「谁问我这个内部 key，我就把自己交出去」
      }
      return value(c.Context, key)
  }
  ```

  于是哪怕 parent 外面套了好几层 `valueCtx`/`timerCtx`，`parent.Value(&cancelCtxKey)` 会沿内嵌链一路往里问，**穿透这些包装**，问到最里层那个 `cancelCtx`。这就是「找到最近的可取消祖先」的实现——不是遍历指针，是借 `Value` 的转发链。

- **为什么还要比 `pdone != done`？** 防止有人用自定义 Context **包住**一个 cancelCtx 却**换了 Done channel**。这种情况不能绕过自定义层直接挂到里层 cancelCtx（否则自定义层的取消语义被跳过），所以 done 对不上就当「不是标准 cancelCtx」，落到兜底分支。

**分支 (e) 那条 goroutine，是真正的面试陷阱**：当 parent 是个你自己写的、没实现 `AfterFunc` 的 Context 时，标准库没法把 child 挂进任何 map，只能**起一条 goroutine 干等** `parent.Done()`。这条 goroutine：

- 活到 parent 或 child 任一被取消为止——child 自己被 cancel 时 `<-child.Done()` 分支命中，goroutine 才退出；
- 所以**用自定义 Context 派生大量子 ctx 又从不 cancel，会堆一堆这种 goroutine**（包里用 `var goroutines atomic.Int32` 计数，正是为测这条路径）；
- 1.21 加的分支 (d) 是逃生口：自定义 Context 只要实现 `AfterFunc(func()) func() bool`，就走注册回调而非起 goroutine。但**普通自定义 Context 仍走 (e)**。结论：**派生 context 尽量从标准库 ctx 派生，别从自定义 Context 派生**，否则每派生一次多一条 goroutine。

### 3.6 `timerCtx`：cancelCtx + 一个闹钟

```go
type timerCtx struct {
    cancelCtx                  // ★ 内嵌：Done/Err/children/cancel 全复用
    timer    *time.Timer       // 受 cancelCtx.mu 保护
    deadline time.Time
}
```

`WithTimeout(parent, d)` 就是 `WithDeadline(parent, now+d)`。`WithDeadline` 的关键步骤：

```go
func WithDeadlineCause(parent Context, d time.Time, cause error) (Context, CancelFunc) {
    if cur, ok := parent.Deadline(); ok && cur.Before(d) {
        return WithCancel(parent)        // ① 父截止更早 → 你这 deadline 没意义，退化成普通 WithCancel
    }
    c := &timerCtx{deadline: d}
    c.cancelCtx.propagateCancel(parent, c)   // ② 照样挂到取消树
    dur := time.Until(d)
    if dur <= 0 {
        c.cancel(true, DeadlineExceeded, cause)   // ③ 已经过期 → 当场取消
        return c, func() { c.cancel(false, Canceled, nil) }
    }
    c.timer = time.AfterFunc(dur, func() {        // ④ 没过期 → 起定时器，到点自动 cancel
        c.cancel(true, DeadlineExceeded, cause)
    })
    return c, func() { c.cancel(true, Canceled, nil) }
}
```

要点：

- **① 子 deadline 不会晚于父**：父截止时间若已更早，根本不建 timer，直接 `WithCancel`——父超时会沿取消树先把你带走。所以「整条链的有效 deadline 是沿途最早的那个」天然成立，不用你手动取 min。
- **④ 超时 = 定时器触发的取消**：`time.AfterFunc` 到点调的就是同一个 `cancel`，只是 err 传 `DeadlineExceeded`。**超时和手动取消走完全同一套传播逻辑**，区别只在 `Err()`。
- `timerCtx.cancel` 比 cancelCtx 多一步——**停掉 timer**：

  ```go
  func (c *timerCtx) cancel(removeFromParent bool, err, cause error) {
      c.cancelCtx.cancel(false, err, cause)   // 先走父类逻辑（关 done、递归子节点）
      if removeFromParent {
          removeChild(c.cancelCtx.Context, c)
      }
      c.mu.Lock()
      if c.timer != nil {
          c.timer.Stop()                       // 提前 cancel 时把没到点的闹钟摘掉，别让它白响
          c.timer = nil
      }
      c.mu.Unlock()
  }
  ```

  这就是「`defer cancel()` 即使已超时也要调」的另一半原因：**超时是 timer 自己调的 cancel，timer 会被它自己停掉**；但你若提前成功返回、没 cancel，timer 要一直挂到 deadline 才触发——这段时间它和它在父 children 里的引用都活着。`defer cancel()` 让你提前把 timer 停掉、把自己从父摘掉。

### 3.7 `valueCtx` 是一条链表，不是 map

```go
type valueCtx struct {
    Context              // 内嵌 parent
    key, val any         // 只装一对 k-v
}

func (c *valueCtx) Value(key any) any {
    if c.key == key {
        return c.val
    }
    return value(c.Context, key)   // 没命中 → 往 parent 问
}
```

**每个 `WithValue` 只存一对 k-v、套一层**。查找时从当前节点沿内嵌 `Context` 链一路往上比对 key，直到命中或到根：

```go
func value(c Context, key any) any {
    for {
        switch ctx := c.(type) {
        case *valueCtx:
            if key == ctx.key { return ctx.val }
            c = ctx.Context          // 没中，上一层
        case *cancelCtx:
            if key == &cancelCtxKey { return c }   // 顺带支持 3.5 的哨兵
            c = ctx.Context
        case *timerCtx:
            if key == &cancelCtxKey { return &ctx.cancelCtx }
            c = ctx.Context
        case backgroundCtx, todoCtx:
            return nil               // 到根，没找到
        default:
            return c.Value(key)
        }
    }
}
```

所以：

- **`Value` 查找是 O(链深度) 的线性扫**，不是 O(1) 哈希。链有多深取决于你套了多少层 `WithValue`。
- 为什么不用一个 map 存所有 k-v？——context 是**不可变 + 共享**的：父 ctx 可能同时被多个 goroutine 持有并各自派生。追加一层 immutable 节点的方式天然并发安全、无需加锁；换成可变 map 就得加锁、还破坏「父 ctx 不被子修改」的语义。代价就是查找线性。
- 实践含义：**别拿 `WithValue` 当通用字典**，套十几层既慢又难追；只放少量请求级元数据。

### 3.8 取消的内存可见性：`close(done)` 的 happens-before

接 `06` 内存模型：goroutine A 调 `cancel()`、goroutine B 在 `<-ctx.Done()` 上醒来，B 凭什么能看到 A 在 cancel 前写的数据、以及 `ctx.Err()` 的正确值？

- channel 的 `close` 与「从该 channel 收到零值」之间有 **happens-before**：`close(done)` 之前 A 的所有写，对醒来后的 B 可见。
- 这也是 `Err()` 里那行 `<-c.Done()` 的用意：它在返回非 nil err 前**先确保 done 已关闭**，从而保证「能看到 err」蕴含「能看到 cancel 前的状态」，不会出现 Err() 已非 nil、done 却还没关、B 读到半拉子状态。

一句话：**context 的取消信号天生带内存屏障**——`select <-ctx.Done()` 醒来后读到的东西是安全的。这是它直接建在 channel close 之上换来的红利。

### 3.9 版本演进（知道有就行，面试加分）

| 版本 | 加了什么 | 解决什么 |
|---|---|---|
| 1.20 | `WithCancelCause(parent)` + `Cause(ctx)` | 取消时携带**具体 error**，而非只有笼统的 `Canceled`；`Err()` 仍返回 `Canceled`/`DeadlineExceeded`，`Cause()` 返回你传的真因 |
| 1.21 | `WithoutCancel(parent)` | 派生一个**切断取消传播**但保留 Value 的 ctx——比如请求结束后还想用 trace id 异步写日志，不愿被请求取消带走 |
| 1.21 | `AfterFunc(ctx, f)` | 注册「ctx 取消后跑 f」、返回 stop；也是 3.5 分支 (d) 让自定义 Context 避开兜底 goroutine 的底层支撑 |
| 1.21 | `WithDeadlineCause` / `WithTimeoutCause` | 超时也能带 cause |

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

**源码层（看完 §3 自检，答得出才算真懂底层）：**

- **`Done()` 返回的 channel 什么时候创建？** 懒创建——首次调 `Done()` 才 `make`，靠 `done atomic.Value` + 双重检查锁。取消时若从没人调过 `Done()`，直接塞全局预关闭的 `closedchan`，省一次分配。`Background().Done()` 永远是 `nil`。
- **`propagateCancel` 怎么找到「最近的可取消祖先」？** 不是遍历指针，是用哨兵 key `&cancelCtxKey` 调 `parent.Value(...)`——`cancelCtx.Value` 对这个 key 特判返回自己，于是能穿透外层 `valueCtx`/`timerCtx` 包装问到里层 cancelCtx；再比 `pdone == done` 确认没被自定义 Context 换掉 channel，是才挂进它的 `children`。
- **从自定义 Context 派生会怎样？** 若它没实现 `AfterFunc` 方法，标准库挂不进 map，只能起一条 goroutine 干等 `parent.Done()`——派生越多堆越多。1.21 的 `AfterFunc` 快路径是逃生口；结论是尽量从标准库 ctx 派生。
- **`children` 为什么存 `canceler` 接口而不是 `*cancelCtx`？** 让父节点对 `*cancelCtx`/`*timerCtx`/`*afterFuncCtx` 一视同仁地 `child.cancel(...)`——取消传播对子类型多态。
- **`ctx.Value` 查找复杂度？** O(链深度) 线性扫——每个 `WithValue` 套一层、单存一对 k-v，沿内嵌 `Context` 链往上比对。用不可变链表而非 map 是为了免锁的并发安全（父 ctx 被多 goroutine 共享派生）。
- **取消信号为什么是内存安全的？** `close(done)` 与「从 done 收到零值」之间有 happens-before；`Err()` 还特意在返回非 nil err 前 `<-c.Done()`，保证「看到 err」蕴含「看到 cancel 前的写」。

---

## 7. 一句话总结

> **context = 标准化的「取消广播（done channel）+ 截止时间 + 请求值」，沿调用链显式传播、派生成取消树。** 父取消则整棵子树同时收到 `Done()`；超时 = 定时器触发的取消；它是给一整批 goroutine 统一退出路径、防泄漏的标准工具。铁律：ctx 作首参贯穿全链、`defer cancel()`、Value 只放请求级元数据。协作式取消——没人能强杀 goroutine，被取消方得自己检查。

← 上一章 [`06 sync 与内存模型`](../06-sync-memory-model/README.md) ｜ 下一章 → [`08 并发模式`](../08-patterns/README.md)：把前面所有原语组装成 worker pool / fan-in-out / pipeline / errgroup 等实战骨架。
