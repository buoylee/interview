# Go 基准测试与可观测性

## 概述

性能优化必须基于数据而非直觉。Go 内置了完善的基准测试框架，配合 benchstat 工具可以做出统计学意义上的性能对比。同时，在生产环境中持续观测服务性能需要 Prometheus 指标和 OpenTelemetry 链路追踪。

## testing.B 基准测试

### 基本结构

```go
func BenchmarkXxx(b *testing.B) {
    // setup 代码（不计入基准测试时间）

    for i := 0; i < b.N; i++ {
        // 被测代码
        doSomething()
    }
}
```

`b.N` 由 testing 框架自动调整，框架会反复运行被测代码直到获得足够稳定的结果（默认运行至少 1 秒）。

### 计时控制

```go
func BenchmarkWithSetup(b *testing.B) {
    // 昂贵的 setup
    data := loadTestData()

    b.ResetTimer() // 重置计时器，排除 setup 时间

    for i := 0; i < b.N; i++ {
        if i%100 == 0 {
            b.StopTimer()          // 暂停计时
            data = refreshData()   // 不计入基准的操作
            b.StartTimer()         // 恢复计时
        }
        processData(data)
    }
}
```

**注意**：频繁调用 `b.StopTimer/StartTimer` 本身有开销，会影响结果准确性。尽量将 setup 放在循环外 + `b.ResetTimer`。

### 内存分配统计

```go
func BenchmarkAlloc(b *testing.B) {
    b.ReportAllocs() // 报告每次操作的内存分配
    for i := 0; i < b.N; i++ {
        _ = fmt.Sprintf("hello %s", "world")
    }
}
```

### 子基准测试

```go
func BenchmarkEncode(b *testing.B) {
    sizes := []int{1, 100, 10000}
    for _, size := range sizes {
        b.Run(fmt.Sprintf("size=%d", size), func(b *testing.B) {
            data := make([]byte, size)
            b.ResetTimer()
            for i := 0; i < b.N; i++ {
                json.Marshal(data)
            }
        })
    }
}
```

### 并行基准测试

```go
func BenchmarkParallel(b *testing.B) {
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            doWork()
        }
    })
}
```

## 运行基准测试

```bash
# 运行所有基准测试
go test -bench=. -benchmem ./...

# 运行特定基准测试
go test -bench=BenchmarkEncode -benchmem ./pkg/encoding/

# 指定运行次数（用于 benchstat 对比）
go test -bench=. -benchmem -count=10 ./...

# 指定最短运行时间
go test -bench=. -benchtime=5s ./...

# 指定并行度
go test -bench=. -cpu=1,2,4,8 ./...
```

输出解读：

```
BenchmarkEncode/size=1-8      5000000    234 ns/op    48 B/op    2 allocs/op
BenchmarkEncode/size=100-8    1000000   1205 ns/op   384 B/op    3 allocs/op
```

| 字段 | 含义 |
|------|------|
| `-8` | GOMAXPROCS=8 |
| `5000000` | 运行了 5000000 次（b.N） |
| `234 ns/op` | 每次操作耗时 234 纳秒 |
| `48 B/op` | 每次操作分配 48 字节 |
| `2 allocs/op` | 每次操作进行 2 次内存分配 |

## benchstat 统计对比

benchstat 是官方的基准测试结果统计对比工具。它能计算均值、中位数和置信区间，并通过统计检验判断两次结果的差异是否显著。

```bash
# 安装
go install golang.org/x/perf/cmd/benchstat@latest

# 运行两次基准测试，每次 10 轮
go test -bench=BenchmarkEncode -benchmem -count=10 ./... > old.txt
# 修改代码后
go test -bench=BenchmarkEncode -benchmem -count=10 ./... > new.txt

# 对比
benchstat old.txt new.txt
```

输出示例：

```
goos: linux
goarch: amd64
pkg: myproject/encoding
                   │  old.txt   │              new.txt              │
                   │   sec/op   │   sec/op     vs base              │
Encode/size=1-8      234.2n ± 3%   185.6n ± 2%  -20.75% (p=0.000 n=10)
Encode/size=100-8    1.205µ ± 4%   0.892µ ± 3%  -25.98% (p=0.000 n=10)

                   │  old.txt  │            new.txt             │
                   │   B/op    │   B/op     vs base             │
Encode/size=1-8      48.00 ± 0%   32.00 ± 0%  -33.33% (p=0.000 n=10)
```

**p-value 判断**：
- `p < 0.05`：差异有统计学意义（通常认为优化有效）
- `p >= 0.05`：差异可能是噪声，不能确认优化有效
- `~`（tilde）：样本量不足或方差太大，无法判断

## 基准测试陷阱

### 陷阱一：编译器消除死代码

```go
// 错误：编译器可能优化掉整个循环，因为结果没有被使用
func BenchmarkBad(b *testing.B) {
    for i := 0; i < b.N; i++ {
        computeHash("hello") // 返回值被丢弃，可能被优化掉
    }
}

// 正确：用 package-level 的 sink 变量防止优化
var sink interface{}

func BenchmarkGood(b *testing.B) {
    var result []byte
    for i := 0; i < b.N; i++ {
        result = computeHash("hello")
    }
    sink = result // 编译器无法优化掉
}
```

### 陷阱二：GC 干扰

基准测试期间 GC 可能运行并影响结果。尤其是分配密集型基准测试。

```go
// 减少 GC 干扰的方法
func BenchmarkWithGCControl(b *testing.B) {
    // 基准测试前手动触发一次 GC
    runtime.GC()
    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        doWork()
    }
}
```

多次运行（`-count=10`）+ benchstat 可以消除 GC 噪声的影响。

### 陷阱三：初始化偏差

```go
// 第一次调用可能触发懒初始化，比后续调用慢很多
func BenchmarkWithInit(b *testing.B) {
    // 预热
    doWork()

    b.ResetTimer()
    for i := 0; i < b.N; i++ {
        doWork()
    }
}
```

## Prometheus client_golang

### 接入

```go
import (
    "github.com/prometheus/client_golang/prometheus"
    "github.com/prometheus/client_golang/prometheus/promhttp"
)

// Counter：只增不减（请求总数、错误总数）
var httpRequestsTotal = prometheus.NewCounterVec(
    prometheus.CounterOpts{
        Name: "http_requests_total",
        Help: "Total number of HTTP requests",
    },
    []string{"method", "path", "status"},
)

// Gauge：可增可减（goroutine 数量、队列长度）
var activeConnections = prometheus.NewGauge(
    prometheus.GaugeOpts{
        Name: "active_connections",
        Help: "Number of active connections",
    },
)

// Histogram：观测值的分布（请求延迟）
var requestDuration = prometheus.NewHistogramVec(
    prometheus.HistogramOpts{
        Name:    "http_request_duration_seconds",
        Help:    "HTTP request duration in seconds",
        Buckets: prometheus.DefBuckets, // 默认 bucket: .005, .01, .025, .05, .1, .25, .5, 1, 2.5, 5, 10
    },
    []string{"method", "path"},
)

func init() {
    prometheus.MustRegister(httpRequestsTotal, activeConnections, requestDuration)
}

func main() {
    // 暴露 /metrics 端点
    http.Handle("/metrics", promhttp.Handler())
}
```

### 在中间件中使用

```go
func metricsMiddleware(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()

        // 包装 ResponseWriter 以获取状态码
        ww := &responseWriter{ResponseWriter: w, statusCode: 200}
        next.ServeHTTP(ww, r)

        duration := time.Since(start).Seconds()
        status := strconv.Itoa(ww.statusCode)

        httpRequestsTotal.WithLabelValues(r.Method, r.URL.Path, status).Inc()
        requestDuration.WithLabelValues(r.Method, r.URL.Path).Observe(duration)
    })
}
```

## OpenTelemetry Go SDK 接入

```go
import (
    "go.opentelemetry.io/otel"
    "go.opentelemetry.io/otel/exporters/otlp/otlptrace/otlptracegrpc"
    "go.opentelemetry.io/otel/sdk/trace"
)

func initTracer() (*trace.TracerProvider, error) {
    exporter, err := otlptracegrpc.New(context.Background(),
        otlptracegrpc.WithEndpoint("otel-collector:4317"),
        otlptracegrpc.WithInsecure(),
    )
    if err != nil {
        return nil, err
    }

    tp := trace.NewTracerProvider(
        trace.WithBatcher(exporter),
        trace.WithResource(resource.NewWithAttributes(
            semconv.SchemaURL,
            semconv.ServiceName("my-service"),
        )),
    )
    otel.SetTracerProvider(tp)
    return tp, nil
}

// 在业务代码中创建 span
func handleRequest(ctx context.Context) {
    tracer := otel.Tracer("my-service")
    ctx, span := tracer.Start(ctx, "handleRequest")
    defer span.End()

    // 子 span
    ctx, dbSpan := tracer.Start(ctx, "queryDB")
    queryDB(ctx)
    dbSpan.End()
}
```

## Delve 调试器基础

Delve（dlv）是 Go 专用的调试器，理解 goroutine 和 Go 运行时。

```bash
# 安装
go install github.com/go-delve/delve/cmd/dlv@latest

# 调试运行
dlv debug ./cmd/myservice

# 附加到运行中的进程
dlv attach <PID>

# 核心转储分析
dlv core ./myservice core.12345
```

常用命令：

```
(dlv) break main.handleRequest     # 设置断点
(dlv) continue                     # 继续执行
(dlv) next                         # 单步执行（不进入函数）
(dlv) step                         # 单步执行（进入函数）
(dlv) print variableName           # 打印变量值
(dlv) goroutines                   # 列出所有 goroutine
(dlv) goroutine 42                 # 切换到 goroutine 42
(dlv) stack                        # 打印当前栈
(dlv) locals                       # 打印局部变量
(dlv) condition 1 i > 100          # 条件断点
```

**性能排查中的 Delve 使用场景**：
- 确认某个变量在特定时刻的值
- 观察锁的持有者（切换到持有锁的 goroutine 查看栈）
- 分析 goroutine 泄漏时查看各 goroutine 的状态和栈

注意：Delve 会暂停目标进程，不适合在生产环境使用。生产环境排查优先使用 pprof 和 trace。

## 小结

1. 基准测试必须用 `sink` 变量防止编译器优化，用 `-count=10` + benchstat 做统计对比
2. benchstat 的 p-value < 0.05 才能确认优化有效
3. Prometheus 的 Counter/Gauge/Histogram 覆盖绝大多数监控需求
4. OpenTelemetry 提供标准化的分布式链路追踪
5. Delve 在开发环境调试并发问题很有用，但不适用于生产环境
