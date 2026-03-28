# Go GC 与运行时调优

## 概述

Go 使用自动垃圾回收（GC），开发者不需要手动管理内存。但"自动"不等于"不需要关心"——GC 配置不当会导致内存浪费、延迟毛刺甚至 OOM。理解 GC 原理和调优手段，是 Go 后端工程师的必备技能。

## Go GC 原理

### 三色标记法

Go GC 使用并发三色标记-清除算法。所有对象被分为三种颜色：

- **白色**：未被扫描的对象（GC 结束时仍为白色的对象将被回收）
- **灰色**：已被发现但其引用的对象尚未扫描
- **黑色**：已被扫描且其引用的对象也已扫描（存活对象）

标记过程：
1. 从根对象（全局变量、goroutine 栈上的变量）出发，标记为灰色
2. 取出灰色对象，扫描其引用的对象标记为灰色，自身变为黑色
3. 重复直到没有灰色对象
4. 所有白色对象即为垃圾，回收

### 写屏障（Write Barrier）

由于 GC 与业务代码并发执行，在标记过程中业务代码可能修改对象引用关系。写屏障确保不会漏标存活对象。

Go 1.8+ 使用**混合写屏障（Hybrid Write Barrier）**，结合了插入写屏障和删除写屏障的优点，减少了 STW 的需求。

### 并发标记

Go GC 的大部分标记工作与业务 goroutine 并发执行。只有两个极短的 STW 阶段：

1. **Mark Setup**（开启写屏障）：通常 < 100us
2. **Mark Termination**（关闭写屏障、清理）：通常 < 100us

这意味着 Go GC 的 STW 时间通常在微秒级，对延迟敏感的服务非常友好。

### Mark Assist

当业务 goroutine 分配内存的速度超过 GC 标记的速度时，该 goroutine 会被"征用"参与标记工作（Mark Assist）。这是导致请求延迟抖动的常见原因。

## GOGC 环境变量

`GOGC` 控制 GC 触发频率，默认值为 100。

**含义**：当新分配的内存达到上次 GC 后存活内存的 `GOGC%` 时，触发下一次 GC。

```
触发 GC 的条件：新分配内存 >= 存活内存 * GOGC / 100
```

举例（假设上次 GC 后存活 100MB 内存）：
- `GOGC=100`（默认）：新分配 100MB 时触发 GC → 总内存约 200MB
- `GOGC=200`：新分配 200MB 时触发 GC → 总内存约 300MB
- `GOGC=50`：新分配 50MB 时触发 GC → 总内存约 150MB
- `GOGC=off`：完全关闭 GC（危险！仅用于特殊场景如 benchmark）

**调优原则**：
- 设大（如 200-400）→ GC 频率降低，CPU 开销减少，但内存使用增加
- 设小（如 50）→ GC 频率增加，内存使用减少，但 CPU 开销增加

```bash
# 运行时设置
GOGC=200 ./myservice

# 代码中动态调整
import "runtime/debug"
debug.SetGCPercent(200)
```

## GOMEMLIMIT（Go 1.19+）

`GOMEMLIMIT` 设置 Go 运行时的**软内存上限**。这是容器环境的关键配置。

### 为什么需要 GOMEMLIMIT

在容器环境中，常见问题是：
- 容器内存限制 1GB
- Go 程序存活内存 200MB，GOGC=100
- GC 在 400MB 时触发，峰值可能达到 600MB+
- 加上 goroutine 栈、OS 缓存等，总内存可能超 1GB → 被 OOMKill

### 使用方式

```bash
# 容器内存限制 1GB 时，GOMEMLIMIT 设为 800MB（留 20% 余量给非 Go 内存）
GOMEMLIMIT=800MiB ./myservice

# 代码中设置
debug.SetMemoryLimit(800 << 20) // 800 MiB
```

### GOMEMLIMIT 与 GOGC 的配合

推荐组合：**GOGC=100（或更高）+ GOMEMLIMIT=容器限制的 80%**

更激进的做法：**GOGC=off + GOMEMLIMIT**。关闭基于比例的 GC 触发，完全由内存上限驱动 GC。适用于内存变化范围大的场景。

```bash
# 容器限制 2GB，关闭 GOGC，用 GOMEMLIMIT 控制
GOGC=off GOMEMLIMIT=1600MiB ./myservice
```

注意：GOMEMLIMIT 是**软限制**。如果存活对象本身就超过了 limit，Go 不会崩溃，但 GC 会持续高频运行，导致 CPU 飙高。

## GC Pacer

GC pacer 是 Go 运行时的 GC 调度器，自动决定何时开始 GC 以及分配多少 CPU 给 GC。它的目标是在 GOGC 和 GOMEMLIMIT 的约束下，尽量减少 GC 对业务的影响。

开发者通常不需要直接干预 pacer，但需要理解：当 pacer 无法在内存达到上限前完成 GC 时，会触发 Mark Assist，让业务 goroutine 帮忙标记，这是延迟抖动的来源。

## runtime/metrics 包

Go 1.16+ 引入的 `runtime/metrics` 包是获取运行时指标的推荐方式：

```go
import "runtime/metrics"

func collectMetrics() {
    // 定义要采集的指标
    descs := []metrics.Sample{
        {Name: "/gc/cycles/total:gc-cycles"},
        {Name: "/gc/heap/allocs:bytes"},
        {Name: "/gc/pauses:seconds"},
        {Name: "/memory/classes/heap/objects:bytes"},
        {Name: "/sched/goroutines:goroutines"},
    }

    metrics.Read(descs)

    for _, d := range descs {
        switch d.Value.Kind() {
        case metrics.KindUint64:
            fmt.Printf("%s: %d\n", d.Name, d.Value.Uint64())
        case metrics.KindFloat64:
            fmt.Printf("%s: %.2f\n", d.Name, d.Value.Float64())
        case metrics.KindFloat64Histogram:
            // 处理直方图
        }
    }
}
```

## runtime.ReadMemStats

更传统的内存统计方式（注意：调用时会短暂 STW）：

```go
var m runtime.MemStats
runtime.ReadMemStats(&m)

fmt.Printf("Alloc = %v MiB\n", m.Alloc/1024/1024)       // 当前堆内存使用
fmt.Printf("TotalAlloc = %v MiB\n", m.TotalAlloc/1024/1024) // 累计分配
fmt.Printf("Sys = %v MiB\n", m.Sys/1024/1024)           // 从 OS 获取的总内存
fmt.Printf("NumGC = %v\n", m.NumGC)                      // GC 次数
fmt.Printf("PauseTotalNs = %v ms\n", m.PauseTotalNs/1e6) // GC 暂停总时间
fmt.Printf("LastGC = %v\n", time.Unix(0, int64(m.LastGC))) // 上次 GC 时间
```

关键字段含义：
- **Alloc**：当前堆上存活对象的内存（inuse）
- **TotalAlloc**：从启动以来累计分配的内存（只增不减）
- **Sys**：从操作系统获取的总内存（包含 Go 运行时、栈、堆等）
- **HeapIdle**：堆中空闲 span 的内存（可归还给 OS 但尚未归还）
- **HeapReleased**：已归还给 OS 的内存
- **NumGC**：GC 完成次数

## GODEBUG=gctrace=1

最直接的 GC 日志输出方式：

```bash
GODEBUG=gctrace=1 ./myservice
```

输出格式：
```
gc 1 @0.012s 2%: 0.021+1.3+0.015 ms clock, 0.17+0.68/1.1/0+0.12 ms cpu, 4->4->1 MB, 4 MB goal, 0 MB stacks, 0 MB globals, 8 P
```

各字段含义：
| 字段 | 含义 |
|------|------|
| `gc 1` | 第 1 次 GC |
| `@0.012s` | 程序启动后 0.012 秒 |
| `2%` | GC 占总 CPU 时间的百分比 |
| `0.021+1.3+0.015 ms clock` | STW扫描 + 并发标记 + STW标记终止（wall clock） |
| `0.17+0.68/1.1/0+0.12 ms cpu` | CPU 时间（assist/后台GC/空闲GC） |
| `4->4->1 MB` | GC前堆大小 → GC时堆大小 → GC后存活大小 |
| `4 MB goal` | 下次 GC 的目标堆大小 |
| `8 P` | 使用的 P（处理器）数量 |

**关注重点**：
- STW 时间（第一个和第三个时间）：应该在 1ms 以内
- `4->4->1 MB`：如果 GC 后存活内存持续增长 → 可能有内存泄漏
- GC CPU 百分比：超过 5-10% 说明 GC 压力大，考虑调大 GOGC 或减少分配

## 实操：调整 GOGC 观察 GC 行为变化

```go
package main

import (
    "fmt"
    "runtime"
    "time"
)

func allocateMemory() {
    var data [][]byte
    for i := 0; i < 100; i++ {
        data = append(data, make([]byte, 1<<20)) // 每次分配 1MB
        time.Sleep(10 * time.Millisecond)
    }
    _ = data
}

func main() {
    var before, after runtime.MemStats

    runtime.ReadMemStats(&before)
    allocateMemory()
    runtime.ReadMemStats(&after)

    fmt.Printf("GC 次数: %d\n", after.NumGC-before.NumGC)
    fmt.Printf("GC 暂停总时间: %v\n", time.Duration(after.PauseTotalNs-before.PauseTotalNs))
    fmt.Printf("最终堆内存: %d MB\n", after.Alloc/1024/1024)
}
```

运行对比：
```bash
# 默认 GOGC=100
GODEBUG=gctrace=1 go run main.go 2>&1 | grep "^gc"
# 预期：GC 约 6-8 次

# GOGC=400（降低 GC 频率）
GODEBUG=gctrace=1 GOGC=400 go run main.go 2>&1 | grep "^gc"
# 预期：GC 约 2-3 次，但峰值内存更高

# GOGC=50（提高 GC 频率）
GODEBUG=gctrace=1 GOGC=50 go run main.go 2>&1 | grep "^gc"
# 预期：GC 约 12-15 次，峰值内存更低
```

## 容器环境最佳实践

```dockerfile
ENV GOGC=100
ENV GOMEMLIMIT=800MiB  # 容器限制 1GB，留 200MB 余量

# 或者在 Kubernetes 中
# resources:
#   limits:
#     memory: 1Gi
# env:
#   - name: GOMEMLIMIT
#     value: "800MiB"
```

**关键建议**：使用 `automaxprocs` 库配合 GOMEMLIMIT，在容器环境中正确感知资源限制：

```go
import _ "go.uber.org/automaxprocs"
```

## 小结

1. Go GC 使用并发三色标记法，STW 时间极短（微秒级）
2. GOGC 控制 GC 频率，默认 100 意味着"新分配等于存活内存时触发 GC"
3. GOMEMLIMIT 是容器环境必备配置，设为容器内存限制的 80%
4. 用 `GODEBUG=gctrace=1` 观察 GC 行为，关注 STW 时间和 GC 频率
5. 用 `runtime.ReadMemStats` 或 `runtime/metrics` 获取运行时内存指标
6. GC 调优的本质是在"CPU 开销"和"内存使用"之间找平衡
