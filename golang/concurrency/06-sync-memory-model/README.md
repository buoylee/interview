# 06 · sync 与内存模型

> `05` 走的是「通信」这条路。本章走另一条：**共享内存怎么安全地用**——锁、atomic、以及它们背后的 **happens-before 内存模型**。`02` 埋的伏笔在这里收：因为抢占让「任意点可切」，裸共享内存必然出 data race。
>
> 桥接锚点：`sync.Mutex` ≈ `ReentrantLock`（但**不可重入**！）、`sync/atomic` ≈ `j.u.c.atomic`、内存模型 ≈ JMM 的 happens-before。

---

## 1. 核心问题

`02` 讲过：抢占让一个 goroutine 可能在**任意一条语句中间**被切走。所以这段在 asyncio 里没事、在 Go 里必崩：

```go
var counter int
for i := 0; i < 1000; i++ {
    go func() { counter++ }()   // 1000 个 goroutine 并发 counter++
}
// 结果几乎不可能是 1000 —— 这就是 data race
```

`counter++` 不是一条原子指令，是「读 → 加 1 → 写回」三步。两个 goroutine 可能同时读到同一个旧值，各加 1 写回，丢掉一次更新。本章回答：**共享内存这条路怎么走对**——用什么工具（atomic/mutex）、它们凭什么保证正确（内存模型）、怎么检测错误（`-race`）。

---

## 2. 直觉理解

### 三档工具，由轻到重

| 工具 | 适用 | 类比 |
|---|---|---|
| **`sync/atomic`** | 单个数值/指针的原子操作（计数器、标志位） | `AtomicLong`/`AtomicReference` |
| **`sync.Mutex` / `RWMutex`** | 保护一段临界区（多个字段的复合操作） | `ReentrantLock`/`ReentrantReadWriteLock` |
| **channel**（`05`） | 数据所有权转移、协调流程 | `BlockingQueue` + 协调 |

选择直觉：**能用 atomic 就别用锁，能用锁清晰就别硬套 channel。** 简单计数用 atomic，保护结构体多字段用 Mutex，编排数据流转用 channel。不要被「Go 推荐 channel」误导成「什么都用 channel」——官方也说：**计数器这种，锁/atomic 更合适。**

### sync 全家桶 ↔ JUC 映射

| Go | Java | 备注 |
|---|---|---|
| `sync.Mutex` | `ReentrantLock` | **Go 的不可重入**！递归加锁=死锁 |
| `sync.RWMutex` | `ReentrantReadWriteLock` | 读写锁 |
| `sync.WaitGroup` | `CountDownLatch`/`Phaser` | 等一组 goroutine 完成 |
| `sync.Once` | 双检锁/静态初始化 | 懒加载只跑一次 |
| `sync.Cond` | `Condition` | 条件变量（少用，多数场景 channel 更好） |
| `sync.Map` | `ConcurrentHashMap` | 特定场景（读多写少/键不相交）才比 `map+Mutex` 快 |
| `sync.Pool` | 对象池（无直接对应） | GC 感知的临时对象复用 |
| `sync/atomic` | `j.u.c.atomic.*` | CAS/Add/Load/Store |

### data race 的危害：不是「结果错」那么简单

data race 是**未定义行为（UB）**，不只是丢更新——可能读到撕裂的值（half-written）、可能因编译器/CPU 重排出现「不可能」的状态、甚至 map 并发写直接 `fatal error: concurrent map writes` 让进程崩。**别赌它「大概没事」。**

---

## 3. 原理深入

### 3.1 内存模型：happens-before（核心）

多个 goroutine 之间，**没有同步就没有顺序保证**——编译器和 CPU 都可能重排你的读写，一个 goroutine 看到另一个的写入顺序可能和源码不一样。Go 内存模型用 **happens-before** 定义「什么时候一个写对另一个 goroutine 可见」。

几条要背的规则：

- **channel**：一次发送 happens-before 对应的接收完成；channel 关闭 happens-before「因关闭而返回零值」的接收；**无缓冲** channel 的接收 happens-before 对应发送完成。
- **Mutex**：第 n 次 `Unlock` happens-before 第 m 次 `Lock` 返回（n < m）——所以锁既互斥，又建立可见性。
- **go 语句**：`go f()` happens-before f 开始执行（所以 f 能看到创建前的写）。
- **WaitGroup**：所有 `Done` happens-before `Wait` 返回。
- **Once**：`once.Do(f)` 里的 f happens-before 任何 `once.Do` 返回。

> **关键反例**：goroutine 的**结束**不 happens-before 任何东西。「我开了个 goroutine 改了全局变量，它跑完了我就能读到」——**错**，没有同步就没保证。必须用 channel/WaitGroup 建立 happens-before。

Go 1.19 把内存模型正式对齐到 C/C++ 的体系，并明确了 atomic 的语义。

### 3.2 Mutex：三个 Go 特有的点

```go
var mu sync.Mutex          // 零值即可用，不需要 new/构造
mu.Lock()
defer mu.Unlock()          // 惯用 defer，保证 panic 也释放
// 临界区
```

1. **不可重入**：同一个 goroutine 重复 `Lock` 同一把锁 → **死锁**（和 Java `ReentrantLock` 相反）。需要「递归调用都持锁」时，重构成「外层加锁、内层假设已持锁」。
2. **不可拷贝**：`Mutex`（及含它的结构体）一旦用过就不能按值拷贝——拷贝会复制锁状态，导致两把「半个锁」。`go vet` 的 copylocks 会报。所以含锁的结构体一般用指针传递。
3. **零值可用**：`var mu sync.Mutex` 直接能用，无需初始化。

**底层简述**（面试加分）：Mutex 有两种模式——
- **正常模式**：等待者排队，但唤醒的等待者要和「正在 CPU 上、新来的」goroutine 竞争（后者可「插队 barging」，配合自旋），吞吐高但可能让队尾饿。
- **饥饿模式**：当队头等待者等了 **>1ms**，切到饥饿模式，锁**直接移交队头**、禁止插队，保证公平、压住尾延迟。等待 <1ms 或队空时切回正常模式。

### 3.3 atomic 与 CAS

```go
var n atomic.Int64          // Go 1.19+ 类型化 atomic
n.Add(1)                    // 原子自增
v := n.Load()               // 原子读
n.Store(5)                  // 原子写
ok := n.CompareAndSwap(5, 6)// CAS：若当前是 5 则改成 6
```

- **CAS（CompareAndSwap）** 是无锁并发的基石：硬件保证「比较+交换」原子完成，失败就重试。乐观、无阻塞，但高竞争下重试多。
- atomic 适合**单个**值。多个字段要「一起」原子更新，atomic 做不到，得用 Mutex（或把多字段塞进一个指针用 `atomic.Pointer` 整体换）。

开头那个 counter 的正解：

```go
var counter atomic.Int64
for i := 0; i < 1000; i++ {
    go func() { counter.Add(1) }()
}
// 配合 WaitGroup 等完，counter.Load() == 1000
```

---

## 4. 日常开发应用

- **选型**：单计数/标志 → `atomic`；保护结构体一组字段 → `Mutex`；流程编排/所有权转移 → `channel`。
- **`sync.Once` 懒加载**：
  ```go
  var once sync.Once
  var conn *Conn
  func getConn() *Conn {
      once.Do(func() { conn = dial() })   // 并发调用，dial 只跑一次
      return conn
  }
  ```
- **`RWMutex` 读多写少**：多个读可并发持有读锁，写锁独占。但**读并发不高 / 写频繁时，RWMutex 比 Mutex 还慢**（读锁本身有开销），别无脑用。
- **含锁结构体用指针**：避免值拷贝复制了锁。
- **`map` 并发**：原生 map **不支持并发读写**（并发写直接崩）。要么 `Mutex`+map，要么 `sync.Map`（仅读多写少/键集稳定时更优）。

---

## 5. 生产&调优实战

- **`-race` 必须进 CI**：竞态检测器是 Go 最强的并发武器。它在运行时插桩内存访问，**实际跑到的**竞态会被报出来（含两条冲突访问的栈）。代价 ~2–20x 慢、~5–10x 内存，所以**用在测试/压测，不用于生产**。
  ```bash
  go test -race ./...
  go build -race && ./app   # 压测环境短跑，别上线
  ```
  工具细节链 `performance-tuning-roadmap/05a-go-profiling/04-go-race-concurrency.md`。
- **锁竞争剖析**：`runtime.SetMutexProfileFraction` + pprof 的 `mutex` profile 看哪把锁竞争重；`block` profile 看 goroutine 阻塞在哪。
  ```bash
  go tool pprof http://localhost:6060/debug/pprof/mutex
  ```
- **缩小临界区**：锁里只放真正需要保护的操作，别在持锁时做 I/O / 调用外部。能换 atomic 的热点计数就换。
- **false sharing（假共享）**：两个频繁被不同 goroutine 写的变量挤在同一 cache line（64B），会互相使对方缓存失效。高并发计数器场景按 cache line 填充（padding）能显著提速——属于极致调优，知道有这回事。

---

## 6. 面试高频考点

- **data race 和 race condition 区别？** data race=多 goroutine 无同步并发访问同一内存且至少一个写（具体、可被 `-race` 检测、是 UB）；race condition=更宽的时序逻辑 bug（可以没有 data race 也存在）。
- **happens-before 是什么？举几条规则。** 定义跨 goroutine 的写可见性顺序；channel 发送 hb 接收、Unlock hb 后续 Lock、go 语句 hb goroutine 启动、Done hb Wait 返回。强调：goroutine 结束不 hb 任何东西。
- **Go 的 Mutex 可重入吗？能拷贝吗？** 不可重入（递归 Lock 死锁）；不可拷贝（用过再拷会坏，go vet copylocks 报）；零值可用。
- **atomic 和 Mutex 怎么选？** 单个值的原子操作用 atomic（无锁、CAS、快）；多字段复合临界区用 Mutex。
- **Mutex 底层（正常 vs 饥饿模式）？** 正常模式允许新 goroutine 插队+自旋（吞吐高）；等待者等 >1ms 进饥饿模式，锁直接移交队头、禁插队（防尾延迟）。
- **RWMutex 什么时候反而更慢？** 读并发不高或写频繁时，读锁开销 + 写者饥饿让它劣于普通 Mutex。
- **sync.Once 怎么保证只执行一次？** 内部用 atomic 标志 + Mutex 双检：快路径 atomic 读标志，慢路径加锁再检查后执行并置标志；happens-before 保证 f 的副作用对后续所有调用可见。
- **map 能并发读写吗？** 不能，并发写直接 fatal；用 Mutex+map 或 sync.Map。
- **（理念）channel 还是锁？** 数据所有权转移/编排用 channel，简单共享状态保护用锁/atomic——别教条。

---

## 7. 一句话总结

> **共享内存这条路 = 用 atomic/Mutex 建立 happens-before，让一个 goroutine 的写对另一个可见且有序。** 因为抢占让任意点可切，无同步的共享访问就是 data race（UB，可能撕裂/崩溃，不只是丢更新）。选型：单值 atomic、临界区 Mutex（不可重入/不可拷贝/零值可用）、编排 channel。`go test -race` 是抓竞态的命根子，必须进 CI。

← 上一章 [`05 channel 与 select`](../05-channel-select/README.md) ｜ 下一章 → [`07 context 与取消传播`](../07-context/README.md)：把「让一组 goroutine 一起取消/超时」标准化。
