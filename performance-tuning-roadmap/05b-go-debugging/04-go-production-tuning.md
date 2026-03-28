# Go 生产环境调优

## 概述

从开发环境到生产环境，Go 程序还需要关注运行时配置、编译选项、内存布局和逃逸分析等维度的优化。这些优化通常不涉及业务逻辑修改，但能带来显著的性能提升和资源节省。

## GOMAXPROCS 设置

### 默认行为

`GOMAXPROCS` 决定了同时执行用户态 Go 代码的 OS 线程数（即 P 的数量）。默认等于 CPU 核数。

```go
fmt.Println(runtime.GOMAXPROCS(0)) // 查看当前值（0 表示不修改）
```

### 容器环境问题

在容器环境中，Go 默认读取的是宿主机的 CPU 核数，而非容器的 CPU 限制。例如：
- 宿主机 64 核，容器限制 2 核
- GOMAXPROCS 默认 = 64
- 结果：64 个 P 争抢 2 核 CPU，大量上下文切换，性能反而更差

### 解决方案：automaxprocs

```go
import _ "go.uber.org/automaxprocs"

func main() {
    // automaxprocs 自动读取 cgroup 的 CPU 限制
    // 容器限制 2 核 → GOMAXPROCS = 2
}
```

安装：
```bash
go get go.uber.org/automaxprocs
```

启动日志：
```
maxprocs: Updating GOMAXPROCS=2: determined from CPU quota
```

**这是容器环境部署 Go 服务的必备库**。几乎所有知名 Go 项目（Uber、Grafana 等）都在使用。

## 编译优化

### 减小二进制体积

```bash
# -ldflags='-s' 去掉符号表
# -ldflags='-w' 去掉 DWARF 调试信息
# -trimpath 去掉编译路径信息（安全性 + 可重现构建）
go build -ldflags='-s -w' -trimpath -o myservice ./cmd/myservice
```

体积对比（典型 HTTP 服务）：
```
默认编译：          25MB
-ldflags='-s -w'：  18MB（-28%）
+ UPX 压缩：       7MB（-72%，但启动时需解压）
```

注意：去掉调试信息后 pprof 的 `list` 命令和 Delve 调试会受影响。**生产二进制去掉调试信息，但保留未剥离的版本用于排查问题**。

### 内联控制

```bash
# 查看内联决策
go build -gcflags='-m' ./...

# 输出示例
./handler.go:42:6: can inline processRequest
./handler.go:50:6: cannot inline handleBatch: function too complex

# 禁用内联（用于调试或精确的 pprof 分析）
go build -gcflags='-l' -o myservice-debug ./cmd/myservice
```

### 编译时注入版本信息

```bash
go build -ldflags="-X main.version=1.2.3 -X main.buildTime=$(date -u +%Y%m%d%H%M%S)" \
    -o myservice ./cmd/myservice
```

```go
var (
    version   = "dev"
    buildTime = "unknown"
)

func main() {
    fmt.Printf("version: %s, built: %s\n", version, buildTime)
}
```

## CGO 开销与规避

### CGO 调用的代价

每次 CGO 调用（Go → C 或 C → Go）都有固定开销：
- 需要切换 goroutine 栈到 OS 线程栈
- 需要在 C 调用期间锁定当前 M（OS 线程），该 M 不能执行其他 goroutine
- 单次调用开销约 100-200ns（对比纯 Go 函数调用约 1-5ns）

```go
// #include <math.h>
import "C"

func cgoSqrt(x float64) float64 {
    return float64(C.sqrt(C.double(x))) // 每次调用约 150ns
}

func goSqrt(x float64) float64 {
    return math.Sqrt(x) // 每次调用约 2ns
}
```

### GOMAXPROCS 与 CGO 线程

CGO 调用期间，goroutine 绑定的 M 被锁定。如果大量 goroutine 同时进行 CGO 调用，会创建大量 OS 线程，可能触及 `RLIMIT_NPROC` 或系统线程限制。

```bash
# 查看线程数
GODEBUG=schedtrace=1000 ./myservice
# 输出中的 threads 字段
```

### 纯 Go 替代方案

优先使用纯 Go 实现的库：

| C 依赖 | 纯 Go 替代 |
|--------|-----------|
| SQLite (mattn/go-sqlite3) | modernc.org/sqlite |
| libpcap | github.com/google/gopacket (AF_PACKET) |
| OpenSSL | Go 标准库 crypto/tls |
| zlib | compress/gzip (标准库) |
| librdkafka | github.com/segmentio/kafka-go |

```bash
# 完全禁用 CGO
CGO_ENABLED=0 go build -o myservice ./cmd/myservice
```

禁用 CGO 的好处：
- 静态链接，部署更简单（可以用 scratch 基础镜像）
- 避免 CGO 调用开销
- 交叉编译更容易

## 内存对齐

### struct 字段排列影响大小

Go 编译器会在 struct 字段之间插入 padding 以满足对齐要求：

```go
// 差：64 位系统上占 32 字节
type Bad struct {
    a bool    // 1 byte + 7 padding
    b int64   // 8 bytes
    c bool    // 1 byte + 7 padding
    d int64   // 8 bytes
}

// 好：64 位系统上占 24 字节
type Good struct {
    b int64   // 8 bytes
    d int64   // 8 bytes
    a bool    // 1 byte
    c bool    // 1 byte + 6 padding
}
```

差异：32 vs 24 字节。如果有百万个实例，差距是 8MB。

### fieldalignment 工具

```bash
# 安装
go install golang.org/x/tools/go/analysis/passes/fieldalignment/cmd/fieldalignment@latest

# 检查
fieldalignment ./...
# 输出：
# ./types.go:10:2: struct of size 32 could be 24

# 自动修复
fieldalignment -fix ./...
```

**实际建议**：只在结构体实例数量巨大（如缓存中的对象）时才需要关注。普通业务 struct 不需要为了几个字节的差异牺牲代码可读性。

## 逃逸分析

### 什么是逃逸分析

Go 编译器通过逃逸分析决定变量分配在栈还是堆上：
- **栈分配**：函数返回后自动回收，零 GC 开销
- **堆分配**：需要 GC 回收，有性能开销

### 查看逃逸分析结果

```bash
go build -gcflags='-m' ./...

# 输出示例
./handler.go:15:10: &User{} escapes to heap    # 逃逸到堆
./handler.go:20:12: make([]byte, 1024) does not escape  # 留在栈
```

加 `-m -m` 查看更详细的逃逸原因：
```bash
go build -gcflags='-m -m' ./... 2>&1 | grep "escapes"
```

### 常见逃逸原因与优化

#### 原因一：返回指针

```go
// 逃逸：返回了指向局部变量的指针
func newUser(name string) *User {
    u := User{Name: name}
    return &u // &u escapes to heap
}

// 不逃逸：返回值类型（如果 User 不太大）
func newUser(name string) User {
    return User{Name: name} // 分配在调用者的栈帧上
}
```

**权衡**：返回值类型避免堆分配，但如果结构体很大（> 64 字节），拷贝的开销可能超过堆分配。实际中需要 benchmark 验证。

#### 原因二：赋值给 interface

```go
func logValue(v interface{}) { // v 必须在堆上（通过 interface 间接引用）
    fmt.Println(v)
}

func caller() {
    x := 42
    logValue(x) // x escapes to heap（装箱）
}
```

#### 原因三：闭包捕获

```go
func leakyClosures() func() int {
    x := 0
    return func() int {
        x++ // x 被闭包捕获，必须逃逸到堆
        return x
    }
}
```

#### 原因四：slice/map 扩容

```go
func dynamicSlice() {
    s := make([]int, 0)
    for i := 0; i < 100; i++ {
        s = append(s, i) // 编译器无法确定最终大小，逃逸到堆
    }
}

// 优化：预分配
func fixedSlice() {
    s := make([]int, 0, 100) // 编译器知道大小，可能留在栈上
    for i := 0; i < 100; i++ {
        s = append(s, i)
    }
}
```

### 值接收者 vs 指针接收者的逃逸影响

```go
type Point struct{ X, Y float64 }

// 值接收者：Point 不逃逸
func (p Point) Distance() float64 {
    return math.Sqrt(p.X*p.X + p.Y*p.Y)
}

// 指针接收者：如果 Point 是通过 interface 调用的，会逃逸
func (p *Point) Scale(factor float64) {
    p.X *= factor
    p.Y *= factor
}
```

实际建议：
- 小结构体（< 64 字节）：优先值接收者
- 大结构体或需要修改自身的方法：指针接收者
- 性能关键路径：benchmark 验证

## 生产部署检查清单

```
运行时配置
[ ] GOMAXPROCS：容器环境使用 automaxprocs
[ ] GOMEMLIMIT：设为容器内存限制的 80%
[ ] GOGC：根据 GC 压力调整（默认 100 通常够用）
[ ] GODEBUG=madvdontneed=1：更快归还内存给 OS（Go 1.16+ 默认开启）

编译配置
[ ] -ldflags='-s -w'：去掉调试信息减小体积
[ ] -trimpath：去掉编译路径
[ ] CGO_ENABLED=0：如果不需要 CGO，禁用以获得静态二进制
[ ] 注入版本信息（-X main.version=...）

可观测性
[ ] pprof 端点在独立端口暴露（不要和业务端口混用）
[ ] Prometheus metrics 暴露（go_goroutines, go_gc_duration_seconds 等）
[ ] 结构化日志（JSON 格式，避免 fmt.Sprintf 在热路径的开销）
[ ] OpenTelemetry trace 接入

安全
[ ] pprof 端口不暴露到公网
[ ] 限制 /debug 端点的访问来源
[ ] 使用 Go 最新的 patch 版本（安全修复）

容器
[ ] 使用多阶段构建（builder + scratch/distroless）
[ ] 健康检查端点（/healthz, /readyz）
[ ] 优雅关闭（signal.NotifyContext + server.Shutdown）
```

```dockerfile
# 多阶段构建示例
FROM golang:1.22 AS builder
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -ldflags='-s -w' -trimpath -o /myservice ./cmd/myservice

FROM gcr.io/distroless/static-debian12
COPY --from=builder /myservice /myservice
ENTRYPOINT ["/myservice"]
```

```go
// 优雅关闭
func main() {
    ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGINT, syscall.SIGTERM)
    defer stop()

    srv := &http.Server{Addr: ":8080", Handler: mux}

    go func() {
        if err := srv.ListenAndServe(); err != http.ErrServerClosed {
            log.Fatalf("HTTP server error: %v", err)
        }
    }()

    <-ctx.Done()
    log.Println("shutting down...")

    shutdownCtx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
    defer cancel()
    if err := srv.Shutdown(shutdownCtx); err != nil {
        log.Fatalf("shutdown error: %v", err)
    }
}
```

## 小结

1. 容器环境必须使用 automaxprocs 正确设置 GOMAXPROCS
2. `-ldflags='-s -w' -trimpath` 是生产编译的标准配置
3. CGO 调用开销是纯 Go 调用的 50-100 倍，优先使用纯 Go 库
4. struct 字段按大小降序排列可以减少 padding
5. 逃逸分析：小结构体返回值类型、预分配 slice、避免 interface{} 装箱
6. 生产部署必须有 pprof、metrics、优雅关闭和健康检查
