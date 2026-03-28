# Goroutine 泄漏排查

## 概述

Goroutine 非常轻量（初始栈仅 2-8KB），这让开发者习惯性地 `go func()` 启动大量 goroutine。但每个 goroutine 都需要显式的退出路径。如果一个 goroutine 启动后永远不退出，就是 goroutine 泄漏。泄漏的 goroutine 持续消耗内存（栈 + 引用的堆对象），最终导致 OOM。

## 常见泄漏模式

### 模式一：向无人接收的 channel 发送

```go
func leak() {
    ch := make(chan int)
    go func() {
        result := doWork()
        ch <- result // 永远阻塞：没有人从 ch 接收
    }()
    // 函数返回，ch 变量被 GC，但 goroutine 仍然活着
}
```

### 模式二：从无人发送的 channel 接收

```go
func leak() {
    ch := make(chan int)
    go func() {
        val := <-ch // 永远阻塞：没有人向 ch 发送
        process(val)
    }()
}
```

### 模式三：忘记 cancel context

```go
func leak() {
    ctx, cancel := context.WithCancel(context.Background())
    // 忘记调用 cancel()！

    go func() {
        select {
        case <-ctx.Done():
            return
        case <-workChan:
            // 处理工作
        }
    }()
    // 如果 workChan 也没有数据，goroutine 永远等待
}
```

### 模式四：忘记关闭 Ticker/Timer

```go
func leak() {
    ticker := time.NewTicker(time.Second)
    // 忘记 ticker.Stop()！

    go func() {
        for range ticker.C {
            doWork()
        }
        // 这个 goroutine 永远不会结束，因为 ticker 永远不会被 Stop
    }()
}
```

### 模式五：HTTP Body 忘记 Close

这个不是直接的 goroutine 泄漏，但会导致连接泄漏，间接引发 goroutine 泄漏（底层的 read goroutine 不会退出）：

```go
func fetchData(url string) ([]byte, error) {
    resp, err := http.Get(url)
    if err != nil {
        return nil, err
    }
    // 忘记 resp.Body.Close()！
    // 连接不会被归还到连接池，持续积累

    data, err := io.ReadAll(resp.Body)
    return data, err
}
```

正确写法：

```go
func fetchData(url string) ([]byte, error) {
    resp, err := http.Get(url)
    if err != nil {
        return nil, err
    }
    defer resp.Body.Close()

    // 即使不需要 body，也必须读完并 Close，否则连接无法复用
    data, err := io.ReadAll(resp.Body)
    return data, err
}
```

### 模式六：无限循环没有退出条件

```go
func leak() {
    go func() {
        for {
            // 轮询逻辑，但没有退出条件
            checkStatus()
            time.Sleep(time.Second)
        }
    }()
}
```

## 使用 pprof 排查 Goroutine 泄漏

### 观察 goroutine 数量趋势

首先确认是否存在泄漏——goroutine 数量是否持续增长：

```go
// 在 metrics 中暴露 goroutine 数量
var goroutineGauge = prometheus.NewGauge(prometheus.GaugeOpts{
    Name: "go_goroutines",
    Help: "Number of goroutines",
})

// 定期更新
go func() {
    for {
        goroutineGauge.Set(float64(runtime.NumGoroutine()))
        time.Sleep(10 * time.Second)
    }
}()
```

如果 Grafana 上看到 goroutine 数量线性增长，几乎可以确认存在泄漏。

### 获取 Goroutine Profile

```bash
# debug=1：按调用栈分组汇总
curl http://localhost:6060/debug/pprof/goroutine?debug=1
```

输出示例：

```
goroutine profile: total 12547
8234 @ 0x43e1c6 0x44f6b0 0x44f696 0x46e4d5 0x71c82d 0x46e001
#   0x71c82c    main.processOrder.func1+0x8c    /app/order.go:142
```

这告诉你：有 8234 个 goroutine 停在 `order.go:142` 这一行。

```bash
# debug=2：列出每个 goroutine 的完整栈（数据量大，慎用）
curl http://localhost:6060/debug/pprof/goroutine?debug=2
```

输出示例：

```
goroutine 18 [chan send, 247 minutes]:
main.processOrder.func1()
    /app/order.go:142 +0x8c
created by main.processOrder
    /app/order.go:138 +0x5a

goroutine 19 [chan send, 246 minutes]:
main.processOrder.func1()
    /app/order.go:142 +0x8c
```

关键信息：
- `[chan send, 247 minutes]`：这个 goroutine 在 channel 发送操作上阻塞了 247 分钟
- 创建位置：`order.go:138`
- 阻塞位置：`order.go:142`

### 用 go tool pprof 交互式分析

```bash
go tool pprof http://localhost:6060/debug/pprof/goroutine

(pprof) top 10
Showing nodes accounting for 12547, 100% of 12547 total
      flat  flat%   sum%        cum   cum%
     8234 65.63% 65.63%      8234 65.63%  runtime.gopark
     3102 24.72% 90.36%      3102 24.72%  runtime.gopark
```

```bash
(pprof) traces
# 查看具体的调用栈
```

## goleak 测试库

[uber-go/goleak](https://github.com/uber-go/goleak) 可以在测试中自动检测 goroutine 泄漏：

```bash
go get go.uber.org/goleak
```

### 在 TestMain 中全局检测

```go
package mypackage

import (
    "testing"
    "go.uber.org/goleak"
)

func TestMain(m *testing.M) {
    goleak.VerifyTestMain(m)
}
```

这样，如果任何测试结束后有多余的 goroutine 存活，goleak 会报错：

```
goleak: Errors on cleanup:
    found unexpected goroutines:
    [Goroutine 19 in state chan send, with main.processOrder.func1 on top of the stack:
    goroutine 19 [chan send]:
    main.processOrder.func1()
        /app/order.go:142 +0x8c
    ]
```

### 在单个测试中检测

```go
func TestProcessOrder(t *testing.T) {
    defer goleak.VerifyNone(t)

    // 你的测试代码
    processOrder(testOrder)
}
```

### 过滤已知的后台 goroutine

```go
func TestMain(m *testing.M) {
    goleak.VerifyTestMain(m,
        goleak.IgnoreTopFunction("go.opencensus.io/stats/view.(*worker).start"),
        goleak.IgnoreTopFunction("database/sql.(*DB).connectionOpener"),
    )
}
```

## 预防模式

### 模式一：context.WithCancel / WithTimeout + defer cancel()

```go
func processWithTimeout(parentCtx context.Context) error {
    ctx, cancel := context.WithTimeout(parentCtx, 5*time.Second)
    defer cancel() // 永远不要忘记 cancel

    resultCh := make(chan Result, 1) // 带缓冲！避免 goroutine 泄漏
    go func() {
        resultCh <- doExpensiveWork(ctx)
    }()

    select {
    case result := <-resultCh:
        return result.Err
    case <-ctx.Done():
        return ctx.Err()
    }
}
```

注意：`resultCh` 使用带缓冲的 channel（容量 1），这样即使 select 走了 `ctx.Done()` 分支，goroutine 中的 `resultCh <- ...` 也不会阻塞。

### 模式二：select + done channel

```go
func startWorker(done <-chan struct{}) {
    go func() {
        ticker := time.NewTicker(time.Second)
        defer ticker.Stop()

        for {
            select {
            case <-done:
                fmt.Println("worker stopped")
                return
            case <-ticker.C:
                doWork()
            }
        }
    }()
}

// 使用
done := make(chan struct{})
startWorker(done)

// 需要停止时
close(done)
```

### 模式三：errgroup 管理 goroutine 生命周期

```go
import "golang.org/x/sync/errgroup"

func processAll(ctx context.Context, items []Item) error {
    g, ctx := errgroup.WithContext(ctx)

    for _, item := range items {
        item := item // 捕获循环变量（Go 1.22 之前需要）
        g.Go(func() error {
            return processItem(ctx, item)
        })
    }

    return g.Wait() // 等待所有 goroutine 完成
}
```

## Goroutine 泄漏排查清单

1. **监控**：在 Grafana 上监控 `go_goroutines` 指标，设置告警（如 goroutine 数量超过 10000）
2. **定位**：通过 `/debug/pprof/goroutine?debug=1` 找到数量最多的 goroutine 类型
3. **分析**：查看阻塞位置和阻塞时长，判断是哪种泄漏模式
4. **修复**：根据泄漏模式选择修复方案（cancel context、关闭 channel、设置超时等）
5. **预防**：
   - 每个 `go func()` 都必须有明确的退出路径
   - 使用 `context.WithCancel/WithTimeout` 并 `defer cancel()`
   - Channel 发送方在不再发送时 close channel
   - 在 CI 中使用 goleak 自动检测
   - HTTP response body 始终 defer Close

## 小结

1. Goroutine 泄漏是 Go 生产环境最常见的问题之一
2. 六种常见泄漏模式：channel 阻塞、忘记 cancel、忘记 Stop、忘记 Close、无限循环
3. 用 pprof goroutine profile 排查：`/debug/pprof/goroutine?debug=1` 找最多的栈
4. 用 goleak 在测试中自动检测泄漏
5. 核心预防原则：每个 goroutine 都要有退出路径，用 context 控制生命周期
