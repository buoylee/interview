# 03 · 阻塞与 netpoller

> 调度器内核三章之三，收尾。`01` 排队、`02` 抢占，本章回答最后一块：**一个 goroutine 去做 `conn.Read()` 或 `time.Sleep()`，会不会把它脚下那根 OS 线程（M）一起卡住？** 答案是「绝大多数情况不会」——这正是 Go「写阻塞式代码，却拿到非阻塞性能」的秘密。
>
> 桥接锚点：这一章和你刚学完的 **asyncio 事件循环 + `to_thread`** 是同一套思想，只是 Go 把它藏进了 runtime。

---

## 1. 核心问题

`00` 说 M 是真 OS 线程，很贵，所以只有 GOMAXPROCS 量级的几个在跑 Go 代码。那问题来了：

```go
data := conn.Read(buf)   // 网络对端还没发数据，这一行要"等"
time.Sleep(3 * time.Second)
```

这些「等待」如果**直接让 M 陷进内核去等**，那几个宝贵的 M 一下就被占光，整个程序就瘫了——这正是 Python 里 `time.sleep` / 同步 socket **冻死事件循环**的处境。

**Go 凭什么不会？** 核心问题：goroutine 在等 I/O / 定时器时，**M 去哪了**？这一章给出两套机制的答案。

---

## 2. 直觉理解

### 把「阻塞」分成两类——这是理解本章的总纲

| 类别 | 例子 | runtime 能不能拦截 | 怎么处理 | M 会被卡住吗 |
|---|---|---|---|---|
| **① 网络 I/O / 定时器** | `conn.Read`、`time.Sleep`、channel | **能**（runtime 自己实现的） | **netpoller + 挂起 G** | **不会**，M 立刻去跑别的 G |
| **② 普通阻塞 syscall / cgo** | 磁盘文件读、`exec` 等外部命令、cgo 调 C 库 | **不能**（内核/C 的事） | **P 交接（handoff）** | **会**，但 P 被摘走给别的 M |

一句话总纲：

> **runtime 能管的阻塞（网络/定时器）→ 用 netpoller 把 G 挂起、M 立刻解放；runtime 管不了的阻塞（文件/cgo）→ M 只能真陷进去，但把 P 交给别的 M，保证全局不卡。**

### 直接对照你刚学的 asyncio

这两套机制，在 Python 里你都见过对应物：

- **netpoller** ≈ asyncio 事件循环底下的 **epoll**。区别：asyncio 让你写 `await reader.read()`（协作、要 await）；Go 让你写 `conn.Read()`（直线阻塞式），**让出动作藏在 runtime 里**，你看不见。
- **P 交接** ≈ asyncio 的 **`to_thread` / `run_in_executor`**。当一段调用没法变非阻塞时，把它甩到别的执行单元上，别卡住主调度。区别：asyncio 要你**手动** `await asyncio.to_thread(...)`；Go runtime **自动**帮你交接 P。

所以本章本质是：**Go 把「事件循环 + to_thread」这两件你在 asyncio 里要手动做的事，全焊进了 runtime。**

---

## 3. 原理深入

### 3.1 netpoller：网络 I/O 怎么做到不阻塞 M

Go runtime 内置一个**网络轮询器（netpoller）**，底层就是各平台的 I/O 多路复用：**epoll**（Linux）、**kqueue**（macOS/BSD）、**IOCP**（Windows）、event ports（Solaris）。注意它是**全局一套**，被整个 runtime 共享，不是每个 M 一个。

当一个 goroutine 做 `conn.Read()` 而数据还没到：

```
conn.Read()  fd 没就绪
   │  ① fd 早已被设成非阻塞模式 + 注册进 netpoller
   │  ② gopark：把当前 G 挂起（状态 _Gwaiting），记下"它在等这个 fd"
   ▼
   ③ M 被解放！立刻回到调度循环 findRunnable，去跑 P 上别的 G
   ⋮  （此刻这根 OS 线程没有被浪费，在为别人干活）
   ④ 数据到达，内核标记 fd 就绪
   ▼
   ⑤ netpoll() 探测到就绪 → 把等它的那个 G 重新变 runnable，丢回运行队列
   ⑥ 某个 M 捞起它，从 conn.Read() 的下一行继续
```

**netpoll 在什么时候被调用？** 就在 `01` 讲的 `findRunnable()` 里：

- M 找活时会**非阻塞地** `netpoll(0)` 瞄一眼有没有就绪的网络 G；
- 当 M 实在没活、准备休眠前，会**带超时地** `netpoll(delay)` ——`delay` 设成「距离下一个定时器到期还有多久」，于是这根 M 高效地睡到「有 I/O 或定时器到点」，不空转。
- `sysmon`（`02` 见过的巡逻线程）也会兜底跑 netpoll，防止所有 P 都忙时网络 G 迟迟没人唤醒。

**这就是和 asyncio 同构的地方**：park（让出）→ epoll 等就绪 → 唤醒。只不过 Go 把它全藏在 `conn.Read()` 底下。

### 3.2 `time.Sleep` 到底怎么让出（沉淀对话）

`time.Sleep` **根本不调用 OS 的 sleep 系统调用**（那样会把 M 塞进内核睡死）。它做四步：

1. **gopark**——挂起当前 G（这才是「让出 CPU」的真正动作），M 被解放去跑别的 G。
2. **注册一个定时器**——往当前 **P 的 timer 堆**（Go 1.14 起每个 P 自带一个最小堆）里塞一条：`when = 现在 + 3s`，到点回调 `goready(本G)`。
3. **M 跑别人**——这 3 秒，M 一直在为其他 G 干活。
4. **到点唤醒**——定时器触发 → G 重新 runnable → 被捞起，从 `Sleep` 下一行继续。

而「3 秒后准时回来」靠的是：调度循环里的 `checkTimers` 检查 timer 堆，以及上面 3.1 那个 `netpoll(delay)`——`delay` 就取自最近的定时器到期时间。所以：

> **让出 = gopark；定时 = per-P timer 堆；空闲时省电地等到点 = netpoll 带超时。** 三者配合。

对照记牢：**Go 的 `time.Sleep` 行为上等于 Python 的 `asyncio.sleep`（都是 park + timer + 让出），而不是 Python 的 `time.sleep`（调 OS syscall、冻死循环）。** 差别只在 Go 由 runtime 自动做、Python 要你手动换成 async 版。

### 3.3 普通阻塞 syscall：P 交接（handoff）

文件读、`os/exec` 跑外部命令、cgo 调阻塞的 C 函数——这些 runtime **拦不住**，M 会真的陷进内核/C 里。应对机制是 `entersyscall`/`exitsyscall` + `sysmon`：

```
G 即将进入可能阻塞的 syscall
   │  entersyscall：把 P 标记为 _Psyscall 状态（M 暂时"还攥着"P，乐观假设很快返回）
   ▼
情况 A（快）：syscall 立刻返回
   │  exitsyscall：M 直接拿回原来的 P，继续跑，零开销
   ▼
情况 B（慢/真阻塞）：M 迟迟陷在里面
   │  sysmon 巡逻发现这个 P 卡在 _Psyscall 太久
   │  → handoffp：把 P 从这根 M 摘走，交给（唤醒/新建的）另一根 M
   ▼
   别的 G 在新 M+这个 P 上继续跑，全局不卡
   │
   syscall 终于返回：原 M 尝试再抢一个 P；
   抢不到 → 把自己的 G 丢进全局队列，M 自己 park 休眠（留着复用）
```

**这就是「M 数量可以超过 GOMAXPROCS」的来源**（`01` 留的伏笔）：P 固定 = GOMAXPROCS，但阻塞在 syscall 里的 M 不占 P，runtime 会另起 M 接管 P 干活，于是同时存在的 M 可远多于 P。默认 M 上限 10000。

这正是 `to_thread` 的自动版：**runtime 帮你把「会阻塞的活」隔离到一根专门陷进去的 M 上，把 P（执行权）让给别人。**

### 3.4 为什么网络走 netpoller、文件走 syscall handoff

一句话：**能不能被 epoll/kqueue 监听**。

- **socket/pipe/终端** 这类 fd 可设非阻塞 + 可被 epoll 监听 → 走 netpoller（不阻塞 M）。Go 的 `net` 包默认就这么干。
- **普通磁盘文件** 在 Linux 上无法用 epoll 有效监听（对常规文件 epoll 总是「就绪」）→ 只能走阻塞 syscall + P 交接那条路。所以**大量文件 I/O 会撑大 M 数**，而大量网络 I/O 不会。（新内核的 io_uring 是另一条演进路线，Go runtime 的 poller 目前以 epoll 为主。）
- **cgo** 调进 C 后 runtime 完全失去控制 → 一律走 P 交接，且 cgo 切换本身有固定开销。

---

## 4. 日常开发应用

- **网络服务尽管写阻塞式代码**：`conn.Read` / `http` 客户端 / 数据库驱动（纯 Go 实现的，如 `pgx`、`go-sql-driver/mysql`）底层都走 netpoller，开几万个 goroutine 各自「阻塞」读写完全没问题——M 不会被占满。这就是 Go 写高并发网络服务的爽点。
- **警惕真阻塞的活会吃 M**：大量并发的**文件 I/O、`os/exec` 外部命令、阻塞型 cgo 库**，每个都会短暂占住一根 M。并发量大时 M 数会飙升（线程多 = 调度/内存开销大）。对策：用 **worker pool 限并发度**（`08`），别无限开 goroutine 去撞这些阻塞调用。
- **别在 goroutine 里调同步阻塞的 C 库还不限量**：这是 Go 版的「阻塞事件循环」——虽然不会像 asyncio 那样团灭（有 P 交接兜底），但会把 M 数顶到上限拖垮调度。
- **纯 Go 驱动 > cgo 驱动**：能选纯 Go 实现就选，避开 cgo 的 P 交接和切换开销（类比你 asyncio 里「选 `aiohttp` 而非 `requests`」的直觉）。

---

## 5. 生产&调优实战

- **M 数暴涨 = 阻塞 syscall 信号**：`GODEBUG=schedtrace=1000` 输出里的 `threads=` 持续走高，或 `runtime.NumGoroutine()` 正常但线程数异常多 → 多半是大量文件 I/O / exec / cgo 把 M 撑起来了。
  ```bash
  GODEBUG=schedtrace=1000 ./app   # 看 threads= 这个数
  cat /proc/<pid>/status | grep Threads   # 进程真实线程数
  ```
- **`go tool trace`** 里能看到 G 在「网络等待」(netpoller) vs 「syscall 阻塞」上的时间，区分是 I/O 等待还是真占线程（`09` 章）。
- **文件密集型服务**：考虑限制并发文件操作的 goroutine 数，或评估 M 上限（`debug.SetMaxThreads`）与系统 `ulimit -u`（线程数上限），防止「too many threads」崩溃。
- **超时一定要带**：netpoller 让「等」很便宜，但「无限等」会让 G 永久挂起 = goroutine 泄漏。网络调用务必上 `context` 超时（`07`）或 `SetDeadline`。

---

## 6. 面试高频考点

- **`time.Sleep` 是怎么实现的？为什么不阻塞线程？**（高频）不调 OS sleep；`gopark` 挂起 G + 往 per-P timer 堆注册定时器，M 去跑别的 G；到点 `goready` 唤醒。等价于 asyncio.sleep，而非 time.sleep。
- **网络 I/O 为什么不会阻塞 M？** fd 设非阻塞 + 注册 netpoller（epoll/kqueue），`gopark` 挂起 G、释放 M；fd 就绪后 netpoll 唤醒 G。M 全程不被占。
- **netpoller 是什么？** runtime 内置的全局网络轮询器，底层 epoll/kqueue/IOCP；把「会阻塞的网络等待」转成「挂起 G + 就绪唤醒」，是 asyncio 事件循环的内核态等价物。
- **遇到阻塞 syscall（文件/cgo）怎么办？** M 会真阻塞，但 `sysmon` 触发 `handoffp` 把 P 交给别的 M，其他 G 继续；这也是 M 数能超 GOMAXPROCS 的原因。
- **为什么 M 数量能超过 GOMAXPROCS？** P 固定=GOMAXPROCS，阻塞在 syscall 的 M 不占 P，runtime 另起 M 接管 P，故 M 可远多于 P。
- **为什么网络不撑 M、文件会撑 M？** 网络 fd 可被 epoll 监听 → netpoller；常规文件不可 epoll → 走阻塞 syscall + P 交接，每个并发文件操作短暂占一根 M。
- **（对标题）和 asyncio 的关系？** netpoller=事件循环的 epoll（但你写阻塞式、不用 await）；P 交接=自动版 `to_thread`/`run_in_executor`。Go 把这俩焊进 runtime。

---

## 7. 一句话总结

> **把阻塞分两类：runtime 管得了的网络/定时器，用 netpoller（park G + 释放 M + epoll 就绪唤醒）做到「写阻塞式、M 不卡」；runtime 管不了的文件/cgo，用 P 交接（把执行权让给别的 M）兜底。** 前者是 asyncio 事件循环的内核态翻版，后者是 `to_thread` 的自动版——Go 把你在 Python 里要手动拼的两件事，全焊进了 runtime。`time.Sleep` = gopark + per-P timer 堆 + netpoll 带超时空等。

← 上一章 [`02 抢占式调度`](../02-preemption/README.md) ｜ **调度器内核三章（GMP / 抢占 / netpoller）到此完结。** 下一章 → [`04 goroutine 实战`](../04-goroutine/README.md)：回到地面，看 goroutine 的创建、栈增长与泄漏。

> 延伸对照：Python 这边的同主题 [`asyncio 核心`](../../../python-concurrency/04-asyncio-core/README.md) 与 [`asyncio 陷阱（阻塞事件循环 / to_thread）`](../../../python-concurrency/05-asyncio-pitfalls/README.md)
