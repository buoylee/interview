# 05 · channel 与 select

> goroutine 之间怎么传数据、怎么同步？Go 的答案是 **channel**——「不要用共享内存来通信，要用通信来共享内存」。本章拆 channel 的语义与 `hchan` 底层，以及多路复用的 `select`。
>
> 桥接锚点：有缓冲 channel ≈ Java `BlockingQueue`；无缓冲 channel ≈ `SynchronousQueue`；`close` ≈ 毒丸（poison pill）广播。

---

## 1. 核心问题

`04` 教你开 goroutine，但它们各跑各的——**怎么把数据从一个 goroutine 传给另一个、怎么让一个等另一个？** 两条路：

1. **共享内存 + 锁**（Java 的主路，Go 也支持，见 `06`）。
2. **channel 通信**（Go 主推）：把数据「发」进管道，另一头「收」。

本章讲第 2 条：channel 的同步语义（无缓冲 vs 有缓冲）、底层怎么实现、`close` 的全部规则、`select` 怎么多路监听。这也是 goroutine 泄漏（`04`）最高发的地方。

---

## 2. 直觉理解

### channel 是带类型的管道

```go
ch := make(chan int)        // 无缓冲
ch := make(chan int, 3)     // 有缓冲，容量 3
ch <- 42                    // 发送
v := <-ch                   // 接收
v, ok := <-ch               // 接收 + 判断是否已关闭（ok=false 表示关闭且取空）
close(ch)                   // 关闭
```

### 无缓冲 vs 有缓冲：同步交接 vs 异步队列

这是 channel 最核心的直觉：

- **无缓冲（`make(chan T)`）= 同步握手**。发送方会**阻塞**，直到有接收方就位，两边**当面交接**那一刻才同时继续。它既传数据，又是一次**同步点**（你能确定对方收到了）。≈ Java `SynchronousQueue`。
- **有缓冲（`make(chan T, n)`）= 异步队列**。缓冲没满时发送**不阻塞**（丢进队列就走）；满了才阻塞。接收方在队列空时才阻塞。≈ Java `BlockingQueue`（容量 n）。

```go
unbuf := make(chan int)
unbuf <- 1          // 阻塞，直到别的 goroutine <-unbuf

buf := make(chan int, 2)
buf <- 1; buf <- 2  // 不阻塞（缓冲够）
buf <- 3            // 阻塞（缓冲满了）
```

### close 是「广播信号」，不是「释放资源」

`close(ch)` 不是像关文件那样释放资源，而是一次**广播**：告诉所有接收方「不会再有新数据了」。所有正在/之后从它接收的 goroutine 都会被唤醒、立刻拿到零值 + `ok=false`。这是 Go 里**一对多通知**的常用手段（done channel）。

---

## 3. 原理深入

### 3.1 hchan 底层结构

channel 底层是一个 `hchan` 结构（加锁的）：

```
hchan:
  qcount     当前缓冲里有几个元素
  dataqsiz   缓冲容量（无缓冲=0）
  buf        指向环形缓冲数组（有缓冲才有）
  sendx/recvx 环形缓冲的发送/接收下标
  sendq      等待发送的 goroutine 队列（每个是一个 sudog）
  recvq      等待接收的 goroutine 队列
  lock       一把互斥锁（channel 操作都先抢它）
```

注意：**channel 不是无锁的**，每次收发都加 `lock`。它的价值是把同步逻辑封装好，不是性能极致。

### 3.2 发送的三条路径

`ch <- v` 时，持锁后按优先级走：

1. **recvq 里有等待的接收者** → **直接把 v 拷给那个接收者**（绕过缓冲，从发送方直接交到接收方），`goready` 唤醒它。最快路径。
2. **没有等待者，但缓冲有空位** → 把 v 拷进 `buf` 环形缓冲，发送方继续。
3. **没等待者、缓冲也满（或无缓冲且无接收者）** → 发送方把自己包成 sudog 挂进 `sendq`，`gopark` 挂起，等接收方来唤醒。

接收 `<-ch` 完全对称：有等待发送者→直接拿（并在有缓冲时把队头补进缓冲）；否则缓冲有数据→从 buf 取；否则挂进 `recvq` 阻塞。

> 「无缓冲 = 同步握手」在底层就是：发送必然走路径 1 或 3——要么正好有接收者当面交接，要么阻塞等一个。

### 3.3 close 的全部规则（背下来，面试常考边界）

`close(ch)` 设置关闭标志，并唤醒 `recvq`/`sendq` 里所有等待者。之后：

| 操作 | 结果 |
|---|---|
| 从已关闭 channel **接收** | 先取完缓冲剩余数据，取空后立即返回**零值 + `ok=false`**，永不阻塞 |
| 向已关闭 channel **发送** | **panic**：`send on closed channel` |
| **close 已关闭**的 channel | **panic**：`close of closed channel` |
| **close nil** channel | **panic** |

由此引出**关闭原则**（4 节细说）：**只由发送方关、只关一次。**

### 3.4 nil channel：永久阻塞（有妙用）

对 **nil channel** 收发会**永久阻塞**：

```go
var ch chan int        // nil
<-ch                   // 永远阻塞
ch <- 1                // 永远阻塞
```

看似没用，但在 `select` 里是个利器：**把某个 case 的 channel 置 nil，就能动态「关掉」这个分支**（永久阻塞 = select 永远不选它）。

### 3.5 select：多路复用

```go
select {
case v := <-ch1:        // 哪个 case 就绪就执行哪个
    use(v)
case ch2 <- x:
    sent()
case <-time.After(time.Second):   // 超时
    timeout()
default:                // 可选：所有 case 都没就绪时立刻走这里（非阻塞）
    nothingReady()
}
```

机制：

- **多个 case 同时就绪 → 伪随机挑一个**（不是从上到下，避免饿死）。
- **有 `default` 且无就绪 case → 立刻执行 default**（非阻塞 select）。
- **无 `default` 且无就绪 → 阻塞**，把自己挂到所有相关 channel 上，任一就绪即被唤醒。

---

## 4. 日常开发应用

### `for range` 收到关闭为止

```go
for v := range ch {     // 自动在 ch 关闭且取空后退出循环
    process(v)
}
```

### done channel：用 close 广播取消

```go
done := make(chan struct{})        // struct{} 零内存，纯信号
go worker(done)
// ...
close(done)                         // 一关，所有监听 done 的 goroutine 同时收到

func worker(done <-chan struct{}) {
    for {
        select {
        case <-done:                // 收到广播 → 退出（避免泄漏！）
            return
        case job := <-jobs:
            process(job)
        }
    }
}
```

> 这是 `04` 说的「给 goroutine 退出路径」的标准实现之一。生产里更常用 `context`（`07` 章），它本质就是把这套 done channel 封装好。

### 关闭原则（避免 panic 和泄漏）

- **只由发送方关闭**，接收方永远不关（接收方关了，发送方再发就 panic）。
- **只关一次**（重复 close panic）。多发送方场景，别让发送方各自关——用 `sync.Once` 或专门的协调 goroutine，或改用 context 取消。
- 不需要「通知接收方结束」时，**根本不用关**——channel 不关也会被 GC 回收，close 只为了广播信号。

---

## 5. 生产&调优实战

- **死锁会被运行时直接抓**：当**所有** goroutine 都阻塞，运行时报 `fatal error: all goroutines are asleep - deadlock!`。常见于无缓冲 channel 自发自收、忘了起接收方、WaitGroup 等不到。注意：只有「全部」阻塞才报；**部分**泄漏不报（那要靠 `04` 的 pprof）。
- **channel 泄漏 = goroutine 泄漏**：发/收一个永远没有对端的 channel，goroutine 永久 park。排查同 `04`（pprof goroutine 按 `chan send`/`chan receive` 栈聚合）。
- **缓冲大小怎么选**：
  - 无缓冲：需要「确认对方收到」的同步点时。
  - 小缓冲：解耦生产/消费的瞬时速度差，削峰。
  - 别用「超大缓冲」当背压消失术——缓冲满之前问题被隐藏，满了照样阻塞，还吃内存。背压要显式设计（`08` 限流）。
- **`time.After` 在循环里的坑**：`select` 里每轮 `time.After` 都新建一个 timer，长循环会堆积（GC 前不释放）。高频场景用 `time.NewTimer` + `Reset` 复用，或 `context` 超时。

---

## 6. 面试高频考点

- **无缓冲和有缓冲 channel 的区别？** 无缓冲=同步握手（发送阻塞到接收就位，是同步点）；有缓冲=异步队列（满才阻塞）。对应 SynchronousQueue / BlockingQueue。
- **channel 底层结构？** hchan：环形缓冲 buf + sendq/recvq 等待队列 + 一把 lock。发送优先直接交给等待接收者，否则进缓冲，否则阻塞入 sendq。
- **从已关闭 channel 收发会怎样？**（边界高频）收：取完剩余后返回零值+ok=false，不阻塞；发：panic；close 已关闭/nil：panic。
- **nil channel 收发？** 永久阻塞；可在 select 里置 nil 动态禁用某分支。
- **select 怎么选 case？** 多个就绪伪随机选一个；有 default 且无就绪走 default（非阻塞）；都没就绪且无 default 则阻塞等任一就绪。
- **谁该关闭 channel？** 发送方，且只关一次；接收方不关；多发送方用 Once/协调者/context。
- **channel 死锁什么时候报？** 所有 goroutine 都阻塞时运行时 fatal；部分泄漏不报。
- **（理念）为什么 Go 推 channel？** 「用通信共享内存」：把同步收敛到数据流转上，比裸共享内存+锁更难写错（但不是万能，简单计数仍用 atomic/锁，见 `06`）。

---

## 7. 一句话总结

> **channel = 带类型的管道 + 同步原语。** 无缓冲是同步握手（也是同步点），有缓冲是异步队列；底层 hchan = 环形缓冲 + 收发等待队列 + 锁，发送优先「直接交给等待的接收者」。`close` 是一对多**广播**（收到零值+ok=false），规则记死：发送方关、只关一次、向关闭的发送/重复关/关 nil 都 panic。`select` 多路复用、就绪伪随机选、`default` 转非阻塞。channel 用错就是 `04` 的 goroutine 泄漏高发区。

← 上一章 [`04 goroutine 实战`](../04-goroutine/README.md) ｜ 下一章 → [`06 sync 与内存模型`](../06-sync-memory-model/README.md)：另一条路——共享内存怎么安全地用（锁/atomic/happens-before/数据竞争）。
