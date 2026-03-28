# Race Detector 与并发分析

## 概述

Go 的并发模型（goroutine + channel）极大降低了并发编程的门槛，但也让数据竞争 bug 更容易被引入。数据竞争是最难排查的 bug 类型之一——它可能在开发环境完全正常，但在生产环境偶发地导致数据损坏或崩溃。Go 内置的 Race Detector 是排查数据竞争的利器。

## 什么是数据竞争

数据竞争（Data Race）发生在以下条件同时满足时：
1. 两个或更多 goroutine **并发**访问同一个内存地址
2. 至少一个访问是**写操作**
3. 没有同步机制保护（mutex、channel、atomic 等）

```go
// 典型的数据竞争
var counter int

func main() {
    for i := 0; i < 1000; i++ {
        go func() {
            counter++ // 多个 goroutine 同时读写 counter
        }()
    }
    time.Sleep(time.Second)
    fmt.Println(counter) // 结果不确定
}
```

数据竞争不同于竞态条件（Race Condition）。竞态条件是逻辑层面的时序问题，数据竞争是内存层面的未同步访问。Go 的 Race Detector 检测的是数据竞争。

## Race Detector 使用

使用极其简单，在 go 命令后加 `-race` 标志即可：

```bash
# 运行时检测
go run -race main.go

# 测试时检测（强烈推荐，CI 中必开）
go test -race ./...

# 编译时注入检测代码
go build -race -o myservice

# 然后运行编译后的二进制
./myservice
```

检测到数据竞争时的输出：

```
==================
WARNING: DATA RACE
Read at 0x00c0000b4010 by goroutine 7:
  main.main.func1()
      /path/to/main.go:12 +0x38

Previous write at 0x00c0000b4010 by goroutine 8:
  main.main.func1()
      /path/to/main.go:12 +0x4e

Goroutine 7 (running) created at:
  main.main()
      /path/to/main.go:11 +0x5c

Goroutine 8 (running) created at:
  main.main()
      /path/to/main.go:11 +0x5c
==================
```

报告清楚地告诉你：
- 发生竞争的内存地址
- 哪两个 goroutine 发生了竞争
- 各自的调用栈和源码位置

## Race Detector 原理

Race Detector 基于 Google 的 **ThreadSanitizer (TSan)** 算法：

- 编译时在每个内存访问指令前后注入检测代码
- 运行时维护一个"happens-before"关系图
- 当检测到不在 happens-before 关系中的并发内存访问时，报告数据竞争

**性能开销**：
- CPU：约 2-10x 的运行时开销
- 内存：约 5-10x 的内存开销

因此：
- **开发/测试环境**：始终开启（`go test -race`）
- **CI 管道**：必须开启
- **生产环境**：不建议开启（可以部署一个 canary 实例开启）

## 数据竞争排查案例

### 案例：并发 map 写入

```go
// 有问题的代码
var cache = make(map[string]string)

func SetCache(key, value string) {
    cache[key] = value // 并发写 map → panic: concurrent map writes
}

func GetCache(key string) string {
    return cache[key] // 并发读写 map → 数据竞争
}
```

修复方案一：使用 sync.RWMutex

```go
var (
    cache = make(map[string]string)
    mu    sync.RWMutex
)

func SetCache(key, value string) {
    mu.Lock()
    cache[key] = value
    mu.Unlock()
}

func GetCache(key string) string {
    mu.RLock()
    v := cache[key]
    mu.RUnlock()
    return v
}
```

修复方案二：使用 sync.Map（适用于特定场景，见后文）

```go
var cache sync.Map

func SetCache(key, value string) {
    cache.Store(key, value)
}

func GetCache(key string) string {
    v, ok := cache.Load(key)
    if !ok {
        return ""
    }
    return v.(string)
}
```

## Channel vs Mutex 性能对比

### 何时用 Channel

- 传递数据所有权（"不要通过共享内存来通信，而要通过通信来共享内存"）
- 协调多个 goroutine 的执行顺序
- 实现 fan-out/fan-in 模式
- 实现 pipeline 模式

### 何时用 Mutex

- 保护共享状态（计数器、缓存、配置）
- 简单的读写保护，不涉及数据传递
- 性能敏感的热路径

### Benchmark 对比

```go
func BenchmarkMutexCounter(b *testing.B) {
    var mu sync.Mutex
    var counter int
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            mu.Lock()
            counter++
            mu.Unlock()
        }
    })
}

func BenchmarkChannelCounter(b *testing.B) {
    ch := make(chan int, 1)
    ch <- 0
    b.RunParallel(func(pb *testing.PB) {
        for pb.Next() {
            v := <-ch
            v++
            ch <- v
        }
    })
}
```

典型结果（8 核机器）：
```
BenchmarkMutexCounter-8     50000000    25.6 ns/op
BenchmarkChannelCounter-8    5000000   312.0 ns/op
```

Mutex 在简单共享状态保护的场景下比 channel 快 10x+。Channel 的开销包含 goroutine 调度和内存拷贝，用于简单的计数器是过度设计。

## sync.Pool

### 原理

sync.Pool 是一个临时对象池，用于复用已分配的对象，减少 GC 压力：

- `Put`：将对象放回池中
- `Get`：从池中取出对象（如果池为空，调用 New 函数创建）
- 池中的对象**随时可能被 GC 回收**（每次 GC 后清理一半）

```go
var bufPool = sync.Pool{
    New: func() interface{} {
        return new(bytes.Buffer)
    },
}

func processRequest(data []byte) string {
    buf := bufPool.Get().(*bytes.Buffer)
    buf.Reset() // 重要：使用前清空
    defer bufPool.Put(buf)

    buf.Write(data)
    // ... 处理
    return buf.String()
}
```

### 注意事项

1. **使用前必须 Reset**：从池中取出的对象可能包含上次使用的残留数据
2. **不要池化需要精确生命周期管理的对象**：如数据库连接、文件句柄
3. **不要放太大的对象**：否则 GC 压力反而增大
4. **不要假设 Put 的对象一定能 Get 到**：GC 随时可能清理

```go
// 优化建议：限制放回池中的对象大小
var bufPool = sync.Pool{
    New: func() interface{} {
        return bytes.NewBuffer(make([]byte, 0, 1024))
    },
}

func returnToPool(buf *bytes.Buffer) {
    if buf.Cap() > 64*1024 { // 超过 64KB 不放回池
        return
    }
    buf.Reset()
    bufPool.Put(buf)
}
```

### Benchmark 效果

```go
func BenchmarkWithPool(b *testing.B) {
    for i := 0; i < b.N; i++ {
        buf := bufPool.Get().(*bytes.Buffer)
        buf.Reset()
        buf.WriteString("hello world")
        bufPool.Put(buf)
    }
}

func BenchmarkWithoutPool(b *testing.B) {
    for i := 0; i < b.N; i++ {
        buf := new(bytes.Buffer)
        buf.WriteString("hello world")
    }
}
```

典型结果：
```
BenchmarkWithPool-8      30000000    42 ns/op     0 B/op    0 allocs/op
BenchmarkWithoutPool-8   20000000    85 ns/op    64 B/op    1 allocs/op
```

## sync.Map 适用场景

sync.Map 并不是 map + mutex 的通用替代。它针对两种特定场景做了优化：

1. **Key 基本稳定，读多写少**：如配置缓存、路由表
2. **不同 goroutine 操作不同的 key 集合**：如以 goroutine ID 为 key 的局部存储

其他场景用 `sync.RWMutex + map` 性能更好：

```go
// 读多写少 → sync.Map 适合
var config sync.Map
config.Store("timeout", 30)
v, _ := config.Load("timeout")

// 读写比例接近 → RWMutex + map 更好
type SafeMap struct {
    mu sync.RWMutex
    m  map[string]string
}
```

## atomic 包使用场景

对于简单的整数计数器、标志位等，`sync/atomic` 比 mutex 更轻量：

```go
var requestCount atomic.Int64 // Go 1.19+ 泛型 atomic 类型

func handleRequest() {
    requestCount.Add(1)
}

func getCount() int64 {
    return requestCount.Load()
}
```

常用类型：
- `atomic.Int32` / `atomic.Int64`：原子整数
- `atomic.Bool`：原子布尔值
- `atomic.Pointer[T]`：原子指针（Go 1.19+）
- `atomic.Value`：存储任意类型（常用于配置热更新）

```go
// atomic.Value 实现配置热更新
var currentConfig atomic.Value

func loadConfig() {
    cfg := readConfigFromFile()
    currentConfig.Store(cfg)
}

func getConfig() *Config {
    return currentConfig.Load().(*Config)
}
```

## 并发原语选择决策树

```
需要并发安全？
├── 简单计数器/标志位 → atomic
├── 共享数据保护
│   ├── 读多写少，key 稳定 → sync.Map
│   └── 其他 → sync.RWMutex + map
├── 传递数据所有权 → channel
├── 协调执行顺序 → channel / sync.WaitGroup
├── 限制并发数 → semaphore (channel 或 golang.org/x/sync/semaphore)
└── 单次初始化 → sync.Once
```

## 小结

1. 数据竞争是并发编程中最危险的 bug，`go test -race` 是 CI 中的必备项
2. Race Detector 有 2-10x 的性能开销，不适合生产环境长期开启
3. 简单的共享状态保护用 mutex，比 channel 快一个数量级
4. sync.Pool 减少临时对象分配和 GC 压力，但使用前必须 Reset
5. sync.Map 只适合"读多写少 + key 稳定"的场景
6. 简单计数器和标志位用 atomic，比 mutex 更轻量
