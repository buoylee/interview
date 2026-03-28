# Go tool trace

## 概述

`go tool trace` 是 Go 运行时事件的可视化工具。如果说 pprof 是统计层面的性能剖析（"哪个函数消耗了多少 CPU"），那么 trace 就是时间轴层面的事件回放（"在第 3.5 秒时，goroutine #42 被调度到 P2 上执行了 200us，然后因为 channel 接收阻塞"）。

trace 能回答 pprof 回答不了的问题：
- 为什么某个请求延迟偶尔飙高？（调度延迟、GC STW）
- goroutine 是在执行、等待还是被阻塞？具体比例是多少？
- GC 的各个阶段对业务 goroutine 的影响有多大？

## 如何采集 Trace

### 方式一：代码中嵌入 runtime/trace

适用于 CLI 程序或需要精确控制采集范围的场景：

```go
package main

import (
    "os"
    "runtime/trace"
)

func main() {
    f, err := os.Create("trace.out")
    if err != nil {
        panic(err)
    }
    defer f.Close()

    trace.Start(f)
    defer trace.Stop()

    // 业务逻辑
    doWork()
}
```

### 方式二：net/http/pprof 的 trace 端点

适用于 HTTP 服务，生产环境推荐（采集时间建议 5-10 秒，不要太长）：

```bash
# 采集 5 秒的 trace 数据
curl -o trace.out http://localhost:6060/debug/pprof/trace?seconds=5

# 用 go tool trace 打开
go tool trace trace.out
```

### 方式三：go test 中采集

```bash
go test -trace=trace.out -run=TestMyFunc ./...
go tool trace trace.out
```

**注意**：trace 数据量远大于 pprof，采集时间不宜超过 10-20 秒，否则文件过大导致浏览器卡顿。

## Trace 界面解读

执行 `go tool trace trace.out` 后，浏览器会打开一个页面，包含以下几个关键分析视图：

### 1. Goroutine analysis

这是最常用的视图，展示所有 goroutine 按创建位置分组的统计信息：

```
Goroutine Name                Count  Exec Time  Net Wait  Block Wait  Sched Wait
main.handleRequest              847    3.2s       1.8s      0.3s        0.5s
runtime.gcBgMarkWorker           4     0.8s       0s        0s          0.1s
```

关键指标含义：
- **Exec Time**：goroutine 实际在 CPU 上执行的时间
- **Net Wait**：网络 I/O 等待时间（读/写 socket）
- **Block Wait**：同步阻塞时间（channel、mutex 等）
- **Sched Wait**：等待调度器分配到 P 上执行的时间（调度延迟）

**诊断思路**：
- Sched Wait 高 → goroutine 太多，调度器忙不过来，或者 GOMAXPROCS 设置过小
- Net Wait 高 → 下游服务慢或网络问题
- Block Wait 高 → 锁竞争严重或 channel 使用不当

### 2. Network wait profile

汇总所有网络 I/O 等待事件，帮助定位：
- 哪些 goroutine 在等待网络
- 等待发生在哪个调用栈
- 每次等待持续多久

### 3. Sync block profile

同步阻塞事件的汇总，包括：
- channel 操作阻塞
- mutex/rwmutex 阻塞
- select 阻塞
- sync.WaitGroup 等待

### 4. Scheduler latency profile

调度延迟分布。一个 goroutine 从"就绪可运行"到"实际被放到 CPU 上执行"之间的延迟。正常情况下这个值应该很小（微秒级），如果出现毫秒级的调度延迟，说明系统负载过高。

### 5. GC 事件可视化

在时间线视图中，GC 事件会被标记出来，包括：
- **GC Start/Stop**：整个 GC 周期
- **STW (Stop The World)**：所有 goroutine 暂停的阶段（Go 现代版本中通常 < 1ms）
- **Mark Assist**：业务 goroutine 被迫参与 GC 标记工作

通过时间线可以直观地看到 GC 是否和延迟毛刺关联。

## User-defined Tasks 和 Regions

Go 1.11+ 支持在代码中标注自定义的 task 和 region，让 trace 视图中能看到业务语义：

```go
import "runtime/trace"

func handleRequest(ctx context.Context, req *Request) {
    // 创建一个 task，表示一个逻辑上的工作单元
    ctx, task := trace.NewTask(ctx, "handleRequest")
    defer task.End()

    // Region 表示 task 内的一个阶段
    trace.WithRegion(ctx, "parseRequest", func() {
        parseRequest(req)
    })

    trace.WithRegion(ctx, "queryDB", func() {
        queryDatabase(ctx, req)
    })

    trace.WithRegion(ctx, "renderResponse", func() {
        renderResponse(ctx, req)
    })
}
```

在 trace 视图中可以按 task 和 region 查看每个业务阶段的耗时分布，非常适合分析请求处理链路中哪个环节最慢。

## 实操：分析 HTTP 服务的 Goroutine 调度问题

### 场景

一个 HTTP 服务在高并发下 P99 延迟从 5ms 飙到 50ms，但 CPU 使用率只有 40%。

### 排查步骤

```bash
# 1. 在高并发期间采集 5 秒 trace
curl -o trace.out http://localhost:6060/debug/pprof/trace?seconds=5

# 2. 打开 trace
go tool trace trace.out
```

### 分析过程

**第一步：查看 Goroutine analysis**

发现 `net/http.(*conn).serve` 类型的 goroutine 有 2000+ 个，且 Sched Wait 平均 15ms。

这说明：goroutine 数量远超 CPU 核数，调度器需要频繁切换，导致排队延迟。

**第二步：查看 Scheduler latency profile**

确认调度延迟呈长尾分布，P99 达到 40ms+。

**第三步：检查时间线视图**

发现大量 goroutine 处于 Runnable（就绪等待调度）状态，而不是 Running 状态。

### 根因与解决

问题：没有限制并发请求数，高峰期创建了大量 goroutine，导致调度延迟。

```go
// 修复：用 semaphore 限制并发
var sem = make(chan struct{}, 200) // 最多 200 个并发请求

func handleRequest(w http.ResponseWriter, r *http.Request) {
    sem <- struct{}{} // 获取令牌
    defer func() { <-sem }() // 归还令牌

    // 业务逻辑
}
```

或使用 `golang.org/x/sync/semaphore`：

```go
import "golang.org/x/sync/semaphore"

var sem = semaphore.NewWeighted(200)

func handleRequest(w http.ResponseWriter, r *http.Request) {
    if err := sem.Acquire(r.Context(), 1); err != nil {
        http.Error(w, "too many requests", http.StatusServiceUnavailable)
        return
    }
    defer sem.Release(1)

    // 业务逻辑
}
```

## pprof vs trace 适用场景对比

| 维度 | pprof | trace |
|------|-------|-------|
| **本质** | 统计采样 | 事件记录 |
| **数据量** | 小（KB~MB） | 大（MB~百MB） |
| **采集时长** | 可以长时间（30s~几分钟） | 宜短（5~10s） |
| **回答的问题** | "哪个函数最慢" | "为什么这一刻慢" |
| **CPU 热点** | 最擅长 | 不擅长 |
| **调度延迟** | 无法观测 | 直接可见 |
| **GC 影响** | 只能看到 GC 函数占比 | 能看到每次 GC 的时间线和 STW |
| **goroutine 行为** | 只有快照 | 有完整生命周期 |
| **锁竞争** | 有 block/mutex profile | 能看到具体时间点的竞争 |
| **网络 I/O** | 间接（通过 block profile） | 直接可见等待时间 |
| **生产环境开销** | 极低 | 较高（建议短时采集） |

### 典型工作流

1. **先用 pprof**：快速定位 CPU 热点和内存分配热点
2. **如果 pprof 解释不了问题**（比如 CPU 不高但延迟高）→ **用 trace**
3. **trace 中发现调度或 GC 问题** → 调整 GOMAXPROCS、GOGC 等运行时参数
4. **trace 中发现阻塞问题** → 回到 pprof 的 block/mutex profile 做更深入的统计分析

## 注意事项

1. trace 采集有运行时开销（约 5-10%），不建议在生产环境长时间开启
2. 高并发服务的 trace 文件会很大，5 秒可能就有几十 MB，浏览器渲染可能卡顿
3. Go 1.21+ 的 trace viewer 有显著改进，建议使用较新版本的 Go 工具链打开 trace 文件
4. 如果只需要看 goroutine 数量和状态，`/debug/pprof/goroutine?debug=1` 更轻量

## 小结

`go tool trace` 是 pprof 的互补工具，专注于时间维度的运行时事件分析。当你遇到"CPU 不高但延迟高"、"偶发性延迟毛刺"、"GC 是否影响了业务"这类问题时，trace 是最直接的排查工具。掌握 Goroutine analysis 和时间线视图的解读是核心技能。
