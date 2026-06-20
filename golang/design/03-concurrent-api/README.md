# 03 · 并发安全的 API 设计

> 设计一个会被并发使用的类型/库,有几条 Go 特有的铁律:**零值可用、谁负责同步要说清、库别偷偷开 goroutine、ctx 作首参、不可拷贝要标记、别在 API 暴露 channel/Mutex**。这是架构师级并发设计题,把 [`concurrency`](../../concurrency/) 的机制上升到「怎么设计 API」。
>
> 桥接锚点:Java 有 `ConcurrentHashMap`/`synchronized`/线程安全集合的明确契约;Go 默认类型**不保证并发安全**,且把「谁同步」的责任更多交给调用方——设计时必须显式说明。

---

## 1. 核心问题

- 我的类型该不该自己加锁(并发安全),还是让调用方加?怎么决定、怎么说清?
- 我能在库函数里 `go func(){...}` 开个后台 goroutine 吗?
- 一个会被并发调用的 API,参数/返回值该怎么设计才不坑人?

---

## 2. 直觉理解

### 默认不保证并发安全,且要显式声明契约

Go 的类型(map、slice、自定义 struct)**默认不是并发安全的**。设计 API 时,你必须**明确并文档化**两种契约之一:

- **「调用方负责同步」**(最常见):类型本身不加锁,文档写明「并发使用需外部加锁」。`map`、大多数 struct 走这条——把锁的粒度和成本留给调用方。
- **「本类型并发安全」**:内部自己加锁(如 `sync.Map`、连接池),文档保证可并发调用。

最坏的是**不说**——调用方猜不到,踩并发 fatal(见 [`data-structures/01`](../../data-structures/01-map/README.md))。**契约必须写进 doc 注释。**

### 库别偷偷开 goroutine

> 调用方应当掌控 goroutine 的生命周期。

如果你的库函数内部 `go func(){...}` 开了个后台 goroutine 却不给调用方停止它的手段,那就是**埋了泄漏隐患**(见 [`concurrency/04`](../../concurrency/04-goroutine/README.md)):调用方不知道它存在、停不掉、它 panic 还会 crash 整个进程(见 [`error-handling/05`](../../error-handling/05-concurrent-errors/README.md))。

设计原则:**要么别在库里开 goroutine,要么给调用方控制权**——接收 `context` 让它能取消、或返回一个 `Close()/Stop()` 方法、或让调用方自己决定是否并发。

### 零值可用,且让 ctx 作首参

- **零值可用**(见 [`type-system/00`](../../type-system/00-values-layout/README.md)):`sync.Mutex`、`bytes.Buffer` 零值即用,无需 `New`。设计类型尽量做到这点。
- **`ctx context.Context` 作第一个参数**(社区铁律,见 [`concurrency/07`](../../concurrency/07-context/README.md)):任何可能阻塞/做 IO/可取消的 API 都收 ctx,让调用方控制超时/取消。

---

## 3. 原理深入

### 3.1 「谁负责同步」的设计决策

| 策略 | 适用 | 代价 |
|---|---|---|
| 调用方加锁(类型不安全) | 通用类型、锁粒度由调用方定更优 | 调用方易忘 → 必须文档警示 |
| 内部加锁(类型安全) | 共享单例、调用方难正确加锁 | 锁粒度固定、可能过度同步 |
| 不可变(immutable) | 配置、值对象 | 改要造新对象 |
| 每 goroutine 一份(不共享) | 无状态 / 可复制 | —— |

最优常是**让类型不可变或不共享**,从源头免锁(「不要通过共享内存来通信」)。

### 3.2 不可拷贝类型要标记

含 `sync.Mutex` 的类型**不能被拷贝**(拷贝锁=拷贝状态,互斥失效,见 [`type-system/02`](../../type-system/02-method-sets/README.md))。设计这类类型:

- **所有方法用指针接收者**(别让值方法拷贝锁);
- 嵌一个 `noCopy` 或靠 `go vet copylocks` 检查;
- 构造函数返回 `*T`,引导调用方用指针。

### 3.3 别在 API 暴露 channel 和 Mutex

- **别导出 channel 作为 API**(一般):`func Events() <-chan Event` 看着方便,但谁关闭、缓冲多大、调用方走了怎么办都成契约负担,且容易泄漏。优先用**方法 + 回调**或迭代器;真要用 channel 也要文档化关闭责任(见 [`concurrency/05`](../../concurrency/05-channel-select/README.md))。
- **别导出 Mutex**:嵌入 `sync.Mutex` 会把 `Lock`/`Unlock` 提升为公共方法(见 [`type-system/04`](../../type-system/04-embedding/README.md)),外部能锁你的内部状态。用**未导出字段** `mu sync.Mutex` 封装。

### 3.4 ctx 的设计惯例

- `ctx` 永远**第一个参数**、名为 `ctx`;不要存进 struct 字段(它是每次调用的上下文)。
- 库内部把 ctx **一路往下传**给阻塞调用(DB/HTTP),让取消穿透(见 [`concurrency/07`](../../concurrency/07-context/README.md))。
- 别用 `context.Value` 传业务参数(只放请求级元数据)。

### 3.5 返回错误而非 panic(API 边界)

库的公共 API **返回 error,不 panic**(见 [`error-handling/00`](../../error-handling/00-philosophy/README.md));内部用 panic 也要在边界 recover 转 error。并发场景尤其:goroutine 里的 panic 会 crash 进程,库若开 goroutine 必须自己 recover。

---

## 4. 日常开发应用

- **文档写清并发契约**:doc 注释明确「并发安全」或「调用方需加锁」。
- **默认让类型不可变 / 不共享**,免锁最省心;非要共享状态再加锁。
- **锁用未导出字段** `mu sync.Mutex`,别嵌入暴露;含锁类型全用指针接收者 + `go vet`。
- **库别偷开 goroutine**:要开就收 ctx 能取消 / 给 Close,且 goroutine 自带 recover。
- **可阻塞/IO 的 API 收 `ctx` 作首参**;一路往下传。
- **构造做到零值可用**就别逼调用方 New。
- **别导出 channel/Mutex** 作 API。

---

## 5. 生产&调优实战

- **「谁同步」不清是并发事故根源**:调用方按「以为安全」并发用一个不安全类型 → map 并发 fatal、data race。契约文档 + `-race` 测试是底线(见 [`engineering/02`](../../engineering/02-toolchain/README.md))。
- **库偷开 goroutine = 隐形泄漏/crash**:第三方库后台 goroutine 不可控是真实生产坑;自己写库务必给生命周期控制(ctx/Close)。
- **锁粒度设计**:内部加锁要权衡粒度——粗锁简单但限并发,细锁/分片锁(见 [`data-structures/04`](../../data-structures/04-struct-alignment/README.md) false sharing)高并发但易死锁。读多写少用 `RWMutex`。
- **不可变 + 值传递在并发下最安全**:无共享即无竞争,虽有拷贝成本但省掉锁和 bug,常更划算。
- **ctx 取消要真能中断**:库内阻塞调用必须接 ctx,否则「取消」是空头支票(见 [`concurrency/07`](../../concurrency/07-context/README.md))。

---

## 6. 面试高频考点

- **设计的类型该不该自己加锁?** 决策:通用类型让**调用方负责同步**(文档写明、锁粒度灵活);共享单例/调用方难正确加锁的内部加锁(并发安全)。**关键是把契约写进 doc**,别不说。
- **能在库里开 goroutine 吗?** 不要偷开;要开必须给调用方控制权(收 ctx 可取消 / 提供 Close)、且 goroutine 自带 recover(否则泄漏 + panic crash 进程)。
- **并发 API 几条铁律?** 零值可用、谁同步要文档化、ctx 作首参且往下传、不可拷贝(含锁)用指针接收者 + 不导出锁、别在 API 暴露 channel/Mutex、返回 error 不 panic。
- **为什么别导出 Mutex/channel?** 嵌入 Mutex 会把 Lock/Unlock 变公共 API(外部能锁你内部);导出 channel 让关闭责任/缓冲/泄漏成契约负担。用未导出字段 / 方法封装。
- **含锁类型注意?** 不可拷贝(拷贝锁失效),全用指针接收者,`go vet copylocks` 检查。
- **和 Java 并发设计对比?** Java 有线程安全集合明确契约;Go 默认不安全、更多把同步责任交调用方,必须显式文档化。

---

## 7. 一句话总结

> **并发安全 API 设计铁律:① 默认类型不保证并发安全,必须文档化契约**(「调用方负责同步」还是「本类型安全」,别不说——否则踩并发 fatal);**② 优先让类型不可变/不共享**(无共享即无竞争,免锁最稳);要共享再加锁,**锁用未导出字段、含锁类型全用指针接收者**(不可拷贝,`go vet copylocks`);**③ 库别偷开 goroutine**——要开就收 `ctx` 可取消 / 提供 `Close`、且 goroutine 自带 recover(否则泄漏 + panic crash 进程);**④ `ctx` 作首参并一路下传**(让取消真能中断);**⑤ 别在 API 暴露 channel/Mutex**(关闭责任/锁外泄);**⑥ 公共 API 返回 error 不 panic;零值可用**。Go 比 Java 更把「谁同步」的责任交给调用方,所以显式契约是命门。

← 上一章 [`02 函数式选项`](../02-functional-options/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md):接口设计、组合·DI、函数式选项、并发 API 速查。｜ 回 [`design` 索引](../README.md)
