# 09 · 陷阱与调优

> 全课收口。并发 bug 的共性是**难复现、不报错却悄悄要命**。这章把散落在 `04–08` 的坑汇成一张**清单**，再配一套**排查工具箱**（pprof / trace / race / GODEBUG），并收尾 GOMAXPROCS 容器坑与调度↔GC 的交互。
>
> 工具实操细节复用已有笔记，不重抄；本章给「什么现象 → 用哪个工具 → 看什么」的导航。

---

## 1. 核心问题

并发故障不像普通 bug 那样「抛异常、看栈、修」。它们往往：

- **不报错**：goroutine 泄漏只是内存慢慢涨；data race 只是偶尔结果不对。
- **难复现**：依赖调度时序，本地跑一万次没事，线上偶发。
- **要命**：泄漏 → OOM；死锁 → 整个服务卡死；竞态 → 数据损坏。

所以并发的功夫一半在「写对」（`04–08`），一半在「**会查**」。这章回答：**四大类并发故障各有什么信号、该掏出哪个工具。**

---

## 2. 直觉理解：四大类故障及其信号

| 类别 | 典型现象 | 第一反应工具 | 来源章 |
|---|---|---|---|
| **goroutine 泄漏** | 内存 + `NumGoroutine` 单调上涨，不回落 | pprof `goroutine` | `04`/`07` |
| **死锁 / 卡死** | 请求 hang、`all goroutines asleep` fatal | pprof `goroutine?debug=2` / trace | `05` |
| **数据竞争** | 偶发结果错、map concurrent write 崩 | `go test -race` | `06` |
| **调度异常** | CPU 抖动、延迟毛刺、M/线程数异常 | `GODEBUG=schedtrace` / trace | `01`/`03` |

记这张表，遇到现象能立刻对到工具，是这章最大的价值。

---

## 3. 原理深入：排查工具箱

### 3.1 pprof：五种 profile，对症下药

先暴露入口：

```go
import _ "net/http/pprof"            // 注册 /debug/pprof 到默认 mux
// 单独起一个 pprof 端口
go func() { log.Println(http.ListenAndServe("localhost:6060", nil)) }()
```

| profile | 看什么 | 何时用 |
|---|---|---|
| `goroutine` | 所有 goroutine 卡在哪（按栈聚合） | **泄漏/死锁**——某个栈聚集成百上千个就是泄漏点 |
| `profile`（CPU） | CPU 时间花在哪个函数 | CPU 高、热点定位 |
| `heap` | 内存分配/占用 | 内存涨、分配热点 |
| `mutex` | 锁竞争 | 锁争用重（需 `SetMutexProfileFraction`） |
| `block` | goroutine 阻塞在哪 | 阻塞分析（需 `SetBlockProfileRate`） |

```bash
go tool pprof http://localhost:6060/debug/pprof/goroutine     # 泄漏
curl 'http://localhost:6060/debug/pprof/goroutine?debug=2'    # 文本：每个 goroutine 完整栈
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30   # CPU
go tool pprof http://localhost:6060/debug/pprof/mutex         # 锁竞争
```

详见 `performance-tuning-roadmap/05a-go-profiling/01-go-pprof.md`。

### 3.2 go tool trace：调度级时间线

pprof 看「花在哪」，trace 看「**何时、被什么挡住**」——每个 G 的执行/阻塞/被抢占/等网络/等 syscall 的时间线，以及 GC、P 利用率。

```go
import "runtime/trace"
f, _ := os.Create("trace.out")
trace.Start(f); defer trace.Stop()
// ... 跑一段负载
```
```bash
go tool trace trace.out     # 浏览器打开，看 goroutine analysis / scheduler latency / GC
```

排查「为什么这个请求延迟高」最直观：是在等锁、等网络（netpoller，`03`）、被调度延迟、还是被 GC STW 打断。详见 `…/02-go-trace.md`。

### 3.3 -race：竞态检测器

```bash
go test -race ./...          # CI 必备
go run -race main.go         # 本地复现
```

运行时插桩，报出**实际跑到的**竞态（两条冲突访问的栈）。~2–20x 慢，只用于测试/压测。详见 `…/04-go-race-concurrency.md`。

### 3.4 GODEBUG：运行时内窥镜

```bash
GODEBUG=schedtrace=1000 ./app              # 每秒打印调度器状态（P/M/队列）
GODEBUG=schedtrace=1000,scheddetail=1 ./app # 每个 P/M/G 细节
GODEBUG=gctrace=1 ./app                    # 每次 GC 的耗时/堆大小
```

- `schedtrace` 的 `threads=` 飙高 → 大量阻塞 syscall（文件/cgo，`03`）。
- `runqueue=` 持续长 → 活堆在全局队列，G 数远超 P。

---

## 4. 日常开发应用：反模式清单（自查）

逐条对照你的代码：

- [ ] **无界开 goroutine**：`for ... { go f() }` 不限量 → 限并发度（worker pool / 信号量，`08`）。
- [ ] **goroutine 没有退出路径**：没 `select <-ctx.Done()` 或没监听 channel 关闭 → 泄漏（`04`/`07`）。
- [ ] **漏调 `cancel()`**：`WithTimeout`/`WithCancel` 不 `defer cancel()` → 资源泄漏（go vet lostcancel，`07`）。
- [ ] **`select` 里裸用 `time.After`** 在高频循环 → timer 堆积，改 `NewTimer`+`Reset` 或 ctx 超时（`05`）。
- [ ] **拷贝了含锁的结构体**：`Mutex`/`WaitGroup` 被值拷贝 → go vet copylocks（`06`）。
- [ ] **接收方关 channel / 关两次**：→ panic，应发送方关、只关一次（`05`）。
- [ ] **共享循环变量**（Go ≤1.21）：闭包捕获同一个 `i` → 传参或拷贝（`04`）。
- [ ] **裸并发读写 map**：→ fatal，用 Mutex+map 或 sync.Map（`06`）。
- [ ] **持锁做 I/O**：临界区里调网络/外部 → 缩小临界区（`06`）。

`go vet` + `golangci-lint`（含 copylocks、lostcancel 等）能自动抓住相当一部分，进 CI。

---

## 5. 生产&调优实战

### 5.1 GOMAXPROCS 容器坑（全课最实用的一条）

`00`/`01` 反复提到：Go ≤1.24 默认按**宿主机**核数设 `GOMAXPROCS`，无视 cgroup CPU 限额。4 核 limit 的 Pod 跑在 64 核机器 → `GOMAXPROCS=64` → 大量无谓 M 切换、调度抖动、P99 毛刺。

```go
import _ "go.uber.org/automaxprocs"     // import 即生效：按 cgroup 限额设 GOMAXPROCS
```

或 Go 1.25+ 关注 runtime 对 cgroup 的原生感知。容器里这一条几乎人人踩，面试也常问。

### 5.2 调度 ↔ GC 的交互

- Go 是**并发**三色标记 GC，STW 只在「标记开始/结束」很短一刻（亚毫秒级）——但它需要**可靠抢占所有 G**（`02`）才能对齐，这正是 1.14 异步抢占的动机之一。
- **GC assist**：分配太快时，分配方 goroutine 会被「拉去」帮忙做标记（mark assist），表现为该 goroutine 延迟上升。trace 里能看到。
- 调 GC 频率/内存用 `GOGC` / `GOMEMLIMIT`——细节链 `performance-tuning-roadmap/05a-go-profiling/03-go-gc-runtime.md`，本课不重讲。

### 5.3 监控埋点

```go
runtime.NumGoroutine()       // goroutine 数趋势（泄漏哨兵）
var ms runtime.MemStats; runtime.ReadMemStats(&ms)   // 堆/GC 指标
```

接 Prometheus（`runtime/metrics` 包，比 ReadMemStats 更细），把 goroutine 数、堆大小、GC 暂停、P99 延迟做成看板——并发问题大多先在这些曲线上露头。

### 5.4 压测才暴露并发问题

并发 bug 低负载藏得住，**压测 + `-race` + pprof 三件套**一起上才逼得出来：高并发跑出泄漏曲线、`-race` 抓竞态、pprof/trace 定位瓶颈。

---

## 6. 面试高频考点

- **怎么排查 goroutine 泄漏？** pprof `goroutine` profile 按栈聚合，找聚集成百上千的栈；监控 `NumGoroutine` 趋势单调涨；测试用 goleak。根因多为等没对端的 channel / 漏 ctx 取消 / 无超时。
- **怎么排查死锁？** 全阻塞会有 `all goroutines are asleep` fatal；部分卡死用 `goroutine?debug=2` 看每个 G 栈，或 trace 看谁在等谁。
- **怎么排查数据竞争？** `go test -race`，运行时报两条冲突访问栈；进 CI。
- **pprof 有哪些 profile？** CPU / heap / goroutine / mutex / block（后两个要开采样）；分别对 CPU 热点 / 内存 / 泄漏 / 锁争用 / 阻塞。
- **GOMAXPROCS 在容器里有什么坑？** 默认按宿主机核数而非 cgroup 限额，导致过度调度；用 automaxprocs 或 Go 1.25+ 原生感知修。
- **go tool trace 能看什么 pprof 看不到的？** 调度级时间线——G 的执行/阻塞/被抢占/等网络/等 syscall、GC 事件、P 利用率、调度延迟。
- **GC 和调度怎么交互？** 并发标记 + 极短 STW，依赖可靠抢占对齐所有 G；分配过快触发 mark assist 拖慢该 goroutine。

---

## 7. 一句话总结

> **并发的功夫一半在写对、一半在会查。** 四类故障对四类工具：泄漏→pprof goroutine、死锁→goroutine?debug=2/trace、竞态→`-race`、调度异常→schedtrace/trace。生产最实用一条：容器里用 `automaxprocs` 修 GOMAXPROCS。配合反模式自查清单 + `go vet`/lint + 压测三件套（压测+race+pprof），把「难复现、不报错」的并发 bug 在上线前逼出来。

← 上一章 [`08 并发模式`](../08-patterns/README.md) ｜ 下一章 → [`99 面试卡`](../99-interview-cards/README.md)：把全课高频考点压成速答表 + 深题卡。
