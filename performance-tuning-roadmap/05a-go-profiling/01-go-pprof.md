# Go pprof 详解

## 概述

pprof 是 Go 内置的性能剖析工具，几乎是每个 Go 后端工程师排查性能问题的第一站。它不需要任何第三方依赖，与 Go 工具链深度集成，能够在生产环境以极低开销采集性能数据。

## pprof 六种 Profile 类型

### 1. CPU Profile

CPU Profile 通过定时中断采样（默认 100Hz，即每秒 100 次），记录每次中断时正在执行的函数调用栈。采样频率可调但通常不需要改。

**核心信息**：哪些函数消耗了最多的 CPU 时间。

```go
import "runtime/pprof"

f, _ := os.Create("cpu.prof")
pprof.StartCPUProfile(f)
defer pprof.StopCPUProfile()
// ... 你的业务逻辑
```

### 2. Heap Profile

内存分配剖析，有两个关键视角：

- **inuse_space**：当前正在使用的内存（存活对象），用于排查内存泄漏
- **alloc_space**：从程序启动以来累计分配的内存（含已 GC 回收的），用于排查分配热点
- **inuse_objects** / **alloc_objects**：对应的对象数量视角

```bash
# 查看当前存活内存
go tool pprof -inuse_space http://localhost:6060/debug/pprof/heap
# 查看累计分配
go tool pprof -alloc_space http://localhost:6060/debug/pprof/heap
```

### 3. Block Profile

记录 goroutine 在同步原语上阻塞等待的时间，包括：
- channel 发送/接收阻塞
- select 阻塞
- sync.Mutex / sync.RWMutex 阻塞（注意：mutex 有独立的 profile）

需要手动开启：
```go
runtime.SetBlockProfileRate(1) // 参数为纳秒，1 表示每次阻塞都记录
```

### 4. Mutex Profile

专门记录互斥锁的竞争情况——某个 goroutine 尝试获取锁时，锁被其他 goroutine 持有的等待时间。

```go
runtime.SetMutexProfileFraction(1) // 1 表示每次竞争都记录
```

### 5. Goroutine Profile

导出所有存活 goroutine 的调用栈快照。排查 goroutine 泄漏的利器。

```bash
# debug=1 按栈分组汇总
curl http://localhost:6060/debug/pprof/goroutine?debug=1
# debug=2 列出每个 goroutine 的完整栈
curl http://localhost:6060/debug/pprof/goroutine?debug=2
```

### 6. Threadcreate Profile

记录导致创建新 OS 线程的调用栈。实际使用较少，主要在排查 CGO 相关线程泄漏时有用。

## 两种接入方式

### 方式一：runtime/pprof（命令行程序）

适用于一次性运行的程序（CLI 工具、批处理任务）：

```go
package main

import (
    "os"
    "runtime/pprof"
)

func main() {
    // CPU Profile
    cpuFile, _ := os.Create("cpu.prof")
    pprof.StartCPUProfile(cpuFile)
    defer pprof.StopCPUProfile()

    // 业务逻辑
    doWork()

    // Heap Profile（在业务逻辑执行后采集）
    heapFile, _ := os.Create("heap.prof")
    pprof.WriteHeapProfile(heapFile)
    heapFile.Close()
}
```

### 方式二：net/http/pprof（HTTP 服务）

适用于长期运行的服务，生产环境推荐：

```go
import _ "net/http/pprof"

func main() {
    // 在独立端口暴露 pprof，不要和业务端口混用
    go func() {
        log.Println(http.ListenAndServe("localhost:6060", nil))
    }()

    // 启动业务 HTTP 服务
    // ...
}
```

注册后自动暴露以下端点：
- `/debug/pprof/profile` — CPU Profile（默认采集 30 秒）
- `/debug/pprof/heap` — Heap Profile
- `/debug/pprof/block` — Block Profile
- `/debug/pprof/mutex` — Mutex Profile
- `/debug/pprof/goroutine` — Goroutine Profile
- `/debug/pprof/trace` — Execution Trace

**安全注意**：生产环境务必在独立端口暴露，且限制访问来源。不要在公网端口上暴露 pprof。

## go tool pprof 命令行使用

```bash
# 从 HTTP 服务采集 30 秒 CPU profile
go tool pprof http://localhost:6060/debug/pprof/profile?seconds=30

# 从文件加载
go tool pprof cpu.prof
```

进入交互模式后的核心命令：

### top — 按消耗排序的热点函数

```
(pprof) top 10
Showing nodes accounting for 4.82s, 89.26% of 5.40s total
      flat  flat%   sum%        cum   cum%
     1.95s 36.11% 36.11%      1.95s 36.11%  runtime.memmove
     0.80s 14.81% 50.93%      0.80s 14.81%  runtime.memclrNoHeapPointers
     0.55s 10.19% 61.11%      0.55s 10.19%  encoding/json.stateInString
```

### flat vs cum 的含义

- **flat**：函数自身代码直接消耗的时间（不包含它调用的子函数）
- **cum (cumulative)**：函数自身 + 它调用的所有子函数的总耗时

实际经验：
- flat 高 → 这个函数本身有性能问题，检查其内部实现
- cum 高但 flat 低 → 问题在它调用的子函数中，需要继续下钻

### list — 查看函数源码级别的耗时

```
(pprof) list handleRequest
Total: 5.40s
ROUTINE ======================== main.handleRequest
     0.20s      2.80s (flat, cum) 51.85% of Total
         .          .     42: func handleRequest(w http.ResponseWriter, r *http.Request) {
     0.10s      0.10s     43:     data := readData(r)
         .      1.50s     44:     result := processData(data)
     0.10s      1.20s     45:     writeResponse(w, result)
         .          .     46: }
```

### peek — 查看调用关系

```
(pprof) peek processData
```

### web — 生成调用图并在浏览器中打开

```
(pprof) web
```
需要安装 Graphviz（`brew install graphviz`）。

## 火焰图生成

Go 1.21+ 内置了火焰图支持，无需额外安装 `go-torch`：

```bash
# 采集并直接在浏览器中打开交互式火焰图
go tool pprof -http=:8080 http://localhost:6060/debug/pprof/profile?seconds=30

# 从已有文件打开
go tool pprof -http=:8080 cpu.prof
```

浏览器中可以切换多种视图：
- **Top**：表格形式的热点函数
- **Graph**：调用关系图
- **Flame Graph**：火焰图（最直观）
- **Source**：源码级耗时

火焰图读法：
- X 轴：CPU 占比（越宽消耗越大）
- Y 轴：调用深度（上面是调用者，下面是被调用者）
- 颜色没有特殊含义，仅用于区分不同函数

## 实操示例：找到 CPU 热点函数

假设有一个 JSON 处理密集的 HTTP 服务：

```go
package main

import (
    "encoding/json"
    "net/http"
    _ "net/http/pprof"
)

type Payload struct {
    Items []Item `json:"items"`
}

type Item struct {
    ID   int    `json:"id"`
    Name string `json:"name"`
    Tags []string `json:"tags"`
}

func handleAPI(w http.ResponseWriter, r *http.Request) {
    var p Payload
    json.NewDecoder(r.Body).Decode(&p)

    // 业务处理
    for i := range p.Items {
        p.Items[i].Name = processName(p.Items[i].Name) // 假设有重计算
    }

    json.NewEncoder(w).Encode(p)
}

func main() {
    go func() {
        http.ListenAndServe("localhost:6060", nil)
    }()
    mux := http.NewServeMux()
    mux.HandleFunc("/api", handleAPI)
    http.ListenAndServe(":8080", mux)
}
```

排查步骤：

```bash
# 1. 用压测工具产生负载
hey -n 10000 -c 50 -m POST -D payload.json http://localhost:8080/api

# 2. 同时采集 CPU profile
go tool pprof -http=:9090 http://localhost:6060/debug/pprof/profile?seconds=30

# 3. 在浏览器中打开 http://localhost:9090，切换到 Flame Graph 视图
# 4. 找到最宽的火焰——通常是 json.Decode / json.Encode 或业务处理函数
# 5. 用 top 确认
(pprof) top 5
# 6. 用 list 查看源码级耗时
(pprof) list handleAPI
```

优化方向示例：
- 如果 `json.Decode` 耗时过大 → 考虑使用 `json-iterator` 或 `sonic` 等高性能 JSON 库
- 如果 `processName` 耗时大 → 检查其内部实现是否有不必要的字符串拷贝或正则编译
- 如果 `runtime.mallocgc` 很高 → 临时对象分配过多，考虑对象复用

## 常用 pprof 命令速查

| 命令 | 用途 |
|------|------|
| `top N` | 显示前 N 个热点函数 |
| `top -cum N` | 按 cumulative 排序 |
| `list funcName` | 查看函数源码级耗时 |
| `peek funcName` | 查看函数调用上下文 |
| `web` | 生成调用图 |
| `disasm funcName` | 查看汇编级耗时 |
| `focus funcName` | 只显示包含该函数的路径 |
| `ignore funcName` | 忽略包含该函数的路径 |

## 小结

pprof 是 Go 性能排查的基石工具。掌握要点：
1. 知道六种 profile 类型分别解决什么问题
2. HTTP 服务用 `net/http/pprof`，CLI 程序用 `runtime/pprof`
3. 看 CPU profile 先 top 找热点，再 list 看源码，最后用火焰图全局确认
4. 区分 flat 和 cum，决定是优化当前函数还是下钻子函数
5. Heap profile 区分 inuse_space（泄漏排查）和 alloc_space（分配优化）
