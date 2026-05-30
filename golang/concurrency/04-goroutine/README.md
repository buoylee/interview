# 04 · goroutine 实战

> 调度器内核三章讲完，回到地面。本章把 `go f()` 这一行掰开：**创建到底多便宜、栈怎么从 2KB 长大、以及实践里最容易踩的坑——goroutine 泄漏。**
>
> 桥接锚点：goroutine ≈ Java 虚拟线程（Loom）。创建便宜是优点，也意味着**泄漏起来比 Java 线程更隐蔽、更量大**。

---

## 1. 核心问题

`00` 已经回答了「goroutine 凭什么轻」。本章落到工程现场，三个实际问题：

1. `go f()` 到底做了什么，成本在哪？
2. 初始才 2KB 的栈，跑深递归/大局部变量时怎么办——**栈怎么长大**？
3. 最致命的：goroutine **开了不退出会怎样**？怎么发现、怎么防？

第 3 个是 Go 工程里最高频的并发 bug，本章重点。

---

## 2. 直觉理解

### `go f()` 的几种写法

```go
go doWork()                    // 调具名函数
go func() { doWork() }()       // 匿名函数（注意末尾的 () 是立即调用）
go func(id int) { ... }(i)     // 用参数传值，避免闭包捕获坑（见 4 节）
```

`go` 关键字把「函数调用」变成「新建一个 goroutine 去跑这个调用」，**立刻返回**，不等它。和 Java 的 `Thread.ofVirtual().start(r)` 是一回事。

### goroutine 的生命周期：谁负责让它结束？

这是 Go 并发的**核心心智**，和 Java 线程不同的地方：

- Java 里你开线程相对克制（线程贵），每个都「看得见」。
- Go 里 `go` 几乎零成本，于是你会**大量**地开——但每开一个，你都欠下一个问题：**它什么时候、由谁、怎么结束？**

如果答不上这个问题，它就可能**永远卡在某处**——这就是泄漏。记住一句话：

> **每个 goroutine 都必须有一条明确的退出路径。** 谁开的，谁负责保证它能结束（正常跑完，或被 context 取消，或 channel 关闭唤醒）。

---

## 3. 原理深入

### 3.1 创建成本：便宜在哪

`go f()` 编译成 runtime 的 `newproc`：分配一个 `g` 结构体（可从 P 的本地空闲 G 缓存复用）+ 一个 **2KB 栈**，设置好要执行的函数和参数，然后把这个新 G 放进当前 P 的 **`runnext` 槽**（`01` 讲过的局部性优化），等待调度。

对比创建一根 OS 线程（`clone` syscall + MB 级栈），这是**纯用户态、KB 级、还能复用结构体**的操作——快几个数量级。

### 3.2 可增长栈：2KB 怎么扛住深递归

goroutine 栈不是固定的，是**按需增长的连续栈**：

```
函数序言检查：当前栈够不够这次调用用？
   │ 不够
   ▼
morestack：
   ① 分配一块两倍大的新栈
   ② 把旧栈的内容整体拷贝过去
   ③ 调整栈上所有指针（指向旧栈的改指向新栈）—— 需要精确知道每个指针（配合 GC）
   ④ 释放旧栈，从新栈继续
```

几个关键点：

- **连续栈（contiguous/copying stack），Go 1.4 起**。更早是「分段栈（segmented stack）」，有「热分裂（hot split）」问题——循环边界反复跨段、反复分配释放，性能抖动。连续栈用「拷贝」换掉了这个坑。
- **拷贝栈要移动指针**，所以 runtime 必须精确掌握栈上哪些是指针——这也解释了 `00`/`03` 提过的：为什么 Go 不能随便把栈地址传给 C、cgo 要特殊处理。
- **有上限**：64 位默认最大栈 **1GB**（`debug.SetMaxStack` 可调），超了直接 `fatal: stack overflow`（通常是无限递归）。
- **会收缩**：GC 时若一个 goroutine 用的栈不到已分配的 1/4，会被**缩小**，把内存还回去。

所以「2KB 起步」既省内存（开几十万个才可能），又不限制单个 goroutine 干重活——按需长到够用为止。

### 3.3 goroutine 泄漏的本质

「泄漏」= 一个 goroutine **被永久挂起、再也不会结束**。最常见是**永久 park 在 channel 操作上**：

```go
func leak() {
    ch := make(chan int)        // 无缓冲
    go func() {
        val := <-ch             // 永远在等，因为没人会往 ch 发
        fmt.Println(val)        // 这行永远到不了
    }()
    // 函数返回，ch 没人持有也没人发送 → 那个 goroutine 永远 _Gwaiting
}
```

本质要点：

- 被泄漏的 goroutine 处于 `_Gwaiting`，**不消耗 CPU**，但**一直占着内存**——它的栈 + 它引用的所有对象。
- **GC 救不了你**：只要这个 goroutine 还「活着」（被 runtime 调度器记录、可能还引用着对象），它和它引用的东西就**不会被回收**。`runtime.NumGoroutine()` 会把它算进去。
- 泄漏不会立刻崩，而是**缓慢爬升**：goroutine 数和内存随时间单调上涨，最终 OOM。这是它隐蔽且危险的地方。

**三大泄漏来源**（背下来）：
1. **发/收一个没有对端的 channel**（上例）——最常见。
2. **漏了取消信号**：起了 goroutine 等某个条件，但触发条件的路径提前 return / 出错，没通知它退出。
3. **无超时的无限等待**：网络/锁/channel 没设超时，对端永久不响应。

---

## 4. 日常开发应用

### 坑①：闭包捕获循环变量（面试高频）

```go
// Go 1.21 及之前：BUG —— 所有 goroutine 共享同一个 i，常打印一堆相同的值
for i := 0; i < 3; i++ {
    go func() { fmt.Println(i) }()   // 捕获的是变量 i 本身，不是当次的值
}

// 修法 A：传参（任意版本都对，最稳）
for i := 0; i < 3; i++ {
    go func(i int) { fmt.Println(i) }(i)
}
// 修法 B：循环内拷贝一份（任意版本）
for i := 0; i < 3; i++ {
    i := i
    go func() { fmt.Println(i) }()
}
```

> **Go 1.22 起改了循环变量语义**：每次迭代是**独立**的变量，上面的 BUG 版自动变正确。但面试常问「为什么老代码有这个 bug」，要能讲清「捕获的是变量、不是值」+「1.22 改成每轮独立作用域」。生产代码若跨版本，仍建议显式传参最稳。

### 坑②：每个 goroutine 给一条退出路径

```go
// 用 context 让 goroutine 可被取消（07 章细讲）
func worker(ctx context.Context, jobs <-chan Job) {
    for {
        select {
        case <-ctx.Done():        // 退出路径①：被取消
            return
        case job, ok := <-jobs:
            if !ok {              // 退出路径②：jobs 关闭
                return
            }
            process(job)
        }
    }
}
```

### 坑③：WaitGroup 配对

```go
var wg sync.WaitGroup
for _, item := range items {
    wg.Add(1)                     // Add 必须在 go 之前（不能在 goroutine 内部 Add）
    go func(it Item) {
        defer wg.Done()           // defer 保证即使 panic 也会 Done，否则 Wait 永久阻塞=泄漏
        process(it)
    }(item)
}
wg.Wait()
```

---

## 5. 生产&调优实战

- **泄漏排查三板斧**：
  ```go
  import _ "net/http/pprof"       // 暴露 /debug/pprof
  // ...
  runtime.NumGoroutine()          // 埋点观察趋势：单调上涨 = 泄漏
  ```
  ```bash
  # 看当前所有 goroutine 卡在哪（按栈聚合，泄漏点会有成百上千个相同栈）
  go tool pprof http://localhost:6060/debug/pprof/goroutine
  # 或直接看文本：?debug=2 打印每个 goroutine 的完整栈
  curl 'http://localhost:6060/debug/pprof/goroutine?debug=2'
  ```
  详细实操链到已有笔记 `performance-tuning-roadmap/05b-go-debugging/01-goroutine-leak.md`。
- **判定信号**：`NumGoroutine()` 随请求量上涨后**不回落** = 泄漏；pprof 里某个栈（如 `chan receive`）聚集了海量 goroutine = 泄漏点。
- **限并发度**而非无限开：对会占 M 的活（文件/cgo，见 `03`）或下游有压力的调用，用带缓冲 channel/信号量/worker pool 限制同时在飞的 goroutine 数（`08`）。
- **测试里防泄漏**：`go.uber.org/goleak` 在测试结束断言没有遗留 goroutine，CI 拦截泄漏。

---

## 6. 面试高频考点

- **goroutine 为什么比线程轻？**（recap `00`）2KB 可增长栈 vs MB 固定；用户态切换纳秒级 vs 内核态微秒级；newproc 复用 G 结构体 vs clone syscall；M:N 复用。
- **goroutine 栈怎么增长？** 初始 2KB，函数序言检查栈不足 → morestack 分配两倍大新栈、拷贝旧栈内容、调整指针、释放旧栈（连续栈，Go 1.4 起）；上限 64 位默认 1GB；GC 时可收缩。
- **goroutine 泄漏是什么？怎么排查？** goroutine 永久挂起（多为等没有对端的 channel / 漏取消 / 无超时），占内存且 GC 回收不了，表现为 NumGoroutine 单调上涨；用 pprof goroutine profile 按栈聚合定位。
- **循环变量捕获为什么有 bug？** 闭包捕获的是变量本身而非当次值，1.21 及之前所有 goroutine 共享同一个循环变量；1.22 起每轮独立作用域修复；显式传参最稳。
- **怎么防止 goroutine 泄漏？** 每个 goroutine 给明确退出路径：context 取消、关闭 channel、设超时；WaitGroup 用 defer Done；测试上 goleak。
- **goroutine 数量级？** 几十万量级（1GB / 2KB），远超线程的几千。

---

## 7. 一句话总结

> **`go f()` = 用户态 KB 级地起一个任务，栈从 2KB 按需拷贝增长（上限 1GB）——便宜到你会大量地开。** 代价是：每个 goroutine 都必须有明确的退出路径，否则就永久 park 成泄漏（占内存、GC 回收不了、NumGoroutine 单调涨）。三大泄漏源：等没对端的 channel、漏取消、无超时；排查靠 pprof goroutine profile 按栈聚合。

← 上一章 [`03 netpoller`](../03-netpoller-blocking/README.md) ｜ 下一章 → [`05 channel 与 select`](../05-channel-select/README.md)：goroutine 之间怎么通信，以及泄漏最常发生的地方。
