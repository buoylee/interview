# Go 性能排查案例集

## 概述

性能排查是一项实战技能，理论知识需要通过真实案例才能内化。本文通过 4 个生产环境中的典型案例，展示完整的排查过程：现象 → 假设 → 排查 → 根因 → 修复 → 验证。

---

## 案例 1：Goroutine 泄漏导致 OOM

### 现象

一个订单处理的 HTTP 服务，部署后内存稳步增长，每小时约增长 50MB。运行约 20 小时后被 Kubernetes OOMKill（内存限制 1GB）。重启后问题重复出现。

Grafana 监控显示：
- `go_goroutines` 指标从启动时的 50 线性增长到 50000+
- `go_memstats_alloc_bytes` 同步增长
- CPU 使用率正常

### 假设

goroutine 数量与内存同步线性增长 → 几乎可以确定是 goroutine 泄漏。每个泄漏的 goroutine 至少占用 2-8KB 栈空间，加上引用的堆对象，内存增长明显。

### 排查过程

**第一步：获取 goroutine profile**

```bash
curl http://pod-ip:6060/debug/pprof/goroutine?debug=1 > goroutine.txt
```

输出（摘要）：
```
goroutine profile: total 32847
28903 @ 0x43e1c6 0x44f6b0 ... 0x71c82d
#   0x71c82c    main.callPaymentService.func1+0x8c    /app/service/payment.go:87

3200 @ 0x43e1c6 0x44f6b0 ...
#   0x6f2a1c    net/http.(*Transport).dialConn+0xef    /usr/local/go/src/net/http/transport.go:1625
```

28903 个 goroutine 卡在 `payment.go:87`，是泄漏的主体。

**第二步：查看泄漏代码**

```go
// payment.go
func callPaymentService(ctx context.Context, order *Order) (*PaymentResult, error) {
    resultCh := make(chan *PaymentResult) // 无缓冲 channel

    go func() {
        resp, err := httpClient.Post(paymentURL, "application/json", body)
        if err != nil {
            return // 错误时直接 return，没有向 channel 发送
        }
        defer resp.Body.Close()
        var result PaymentResult
        json.NewDecoder(resp.Body).Decode(&result)
        resultCh <- &result // 第 87 行：如果 ctx 已超时，没人接收
    }()

    select {
    case result := <-resultCh:
        return result, nil
    case <-ctx.Done():
        return nil, ctx.Err() // 超时后返回，但 goroutine 还在等 channel 发送
    }
}
```

### 根因

两个问题叠加：
1. 当 `ctx` 超时时，select 走 `ctx.Done()` 分支返回，但子 goroutine 中的 `resultCh <- &result` 阻塞（无缓冲 channel 无人接收），goroutine 永远不退出
2. 当 HTTP 请求报错时，goroutine 直接 return，调用方在 `resultCh` 上永远等不到数据（不过这个分支被 ctx 超时覆盖了）

### 修复

```go
func callPaymentService(ctx context.Context, order *Order) (*PaymentResult, error) {
    resultCh := make(chan *PaymentResult, 1) // 缓冲为 1，即使没人接收也不阻塞
    errCh := make(chan error, 1)

    go func() {
        req, _ := http.NewRequestWithContext(ctx, "POST", paymentURL, body)
        resp, err := httpClient.Do(req) // 使用 ctx 控制请求生命周期
        if err != nil {
            errCh <- err
            return
        }
        defer resp.Body.Close()
        var result PaymentResult
        if err := json.NewDecoder(resp.Body).Decode(&result); err != nil {
            errCh <- err
            return
        }
        resultCh <- &result
    }()

    select {
    case result := <-resultCh:
        return result, nil
    case err := <-errCh:
        return nil, err
    case <-ctx.Done():
        return nil, ctx.Err()
    }
}
```

关键修复点：
1. `resultCh` 改为带缓冲 channel（容量 1）
2. HTTP 请求使用 `ctx` 创建（`http.NewRequestWithContext`），ctx 取消时请求也会取消
3. 错误通过 `errCh` 传递

### 验证

部署后观察 24 小时：
- `go_goroutines` 稳定在 50-80 之间
- 内存使用稳定在 120MB 左右
- 无 OOMKill

---

## 案例 2：gRPC 连接池耗尽

### 现象

一个 API Gateway 通过 gRPC 调用下游的订单服务。流量高峰时（QPS 从 1000 到 5000），大量请求返回 `context deadline exceeded`，错误率达到 30%。但下游订单服务的 CPU、内存、延迟都正常。

### 假设

1. 网络问题？→ 非高峰期正常，排除
2. 下游超载？→ 下游指标正常，排除
3. 客户端连接问题？→ 需要排查

### 排查过程

**第一步：查看 goroutine profile**

```bash
curl http://gateway-pod:6060/debug/pprof/goroutine?debug=1
```

发现大量 goroutine 阻塞在 gRPC 的连接创建上。

**第二步：检查 gRPC 客户端代码**

```go
// 有问题的代码：每次请求都创建新连接！
func getOrderClient() (pb.OrderServiceClient, error) {
    conn, err := grpc.Dial("order-service:50051",
        grpc.WithTransportCredentials(insecure.NewCredentials()),
    )
    if err != nil {
        return nil, err
    }
    // 没有 defer conn.Close()，也没有连接池管理
    return pb.NewOrderServiceClient(conn), nil
}

func handleRequest(ctx context.Context, req *Request) (*Response, error) {
    client, _ := getOrderClient() // 每次请求创建新连接
    return client.GetOrder(ctx, &pb.GetOrderRequest{Id: req.OrderID})
}
```

**第三步：检查系统资源**

```bash
# Pod 中查看连接数
ss -tn | grep 50051 | wc -l
# 结果：4832 个连接（大量 TIME_WAIT 和 ESTABLISHED）
```

### 根因

每次 RPC 调用都创建新的 gRPC 连接，而不是复用。高峰期 QPS=5000，每秒创建 5000 个 TCP 连接。加上 TIME_WAIT 积累，文件描述符和端口耗尽。

gRPC 基于 HTTP/2，一个连接就能处理大量并发 RPC，完全不需要连接池。

### 修复

```go
var (
    orderConn   *grpc.ClientConn
    orderClient pb.OrderServiceClient
    once        sync.Once
)

func getOrderClient() pb.OrderServiceClient {
    once.Do(func() {
        var err error
        orderConn, err = grpc.Dial("order-service:50051",
            grpc.WithTransportCredentials(insecure.NewCredentials()),
            grpc.WithKeepaliveParams(keepalive.ClientParameters{
                Time:                10 * time.Second,
                Timeout:             3 * time.Second,
                PermitWithoutStream: true,
            }),
            grpc.WithDefaultServiceConfig(`{"loadBalancingConfig": [{"round_robin":{}}]}`),
        )
        if err != nil {
            log.Fatalf("failed to dial order service: %v", err)
        }
        orderClient = pb.NewOrderServiceClient(orderConn)
    })
    return orderClient
}

func handleRequest(ctx context.Context, req *Request) (*Response, error) {
    client := getOrderClient() // 复用同一个连接
    return client.GetOrder(ctx, &pb.GetOrderRequest{Id: req.OrderID})
}
```

如果有多个下游 Pod 需要客户端负载均衡，配合 DNS 解析：

```go
// 使用 dns:/// 前缀，gRPC 会解析所有 A 记录并轮询
conn, err := grpc.Dial("dns:///order-service:50051",
    grpc.WithDefaultServiceConfig(`{"loadBalancingConfig": [{"round_robin":{}}]}`),
)
```

### 验证

- 连接数从 5000+ 降到 3（3 个下游 Pod，各 1 个连接）
- 高峰期错误率从 30% 降到 0
- P99 延迟从 2s 降到 15ms

---

## 案例 3：GC 频繁导致 P99 延迟抖动

### 现象

一个实时报价推送服务，P50 延迟稳定在 2ms，但 P99 延迟在 50-200ms 之间波动。查看 `go_gc_duration_seconds` Prometheus 指标，GC 每秒触发 8-10 次。

### 假设

GC 频率异常高，每次 GC 的 Mark Assist 可能阻塞业务 goroutine，导致 P99 毛刺。

### 排查过程

**第一步：开启 GC trace**

```bash
GODEBUG=gctrace=1 ./quote-service 2>&1 | head -20
```

```
gc 1247 @120.5s 8%: 0.018+3.2+0.015 ms clock, 0.14+1.8/2.9/0+0.12 ms cpu, 12->14->11 MB, 12 MB goal, 8 P
gc 1248 @120.6s 8%: 0.019+3.5+0.016 ms clock, 0.15+2.0/3.1/0+0.13 ms cpu, 12->14->11 MB, 12 MB goal, 8 P
```

关键数据：
- 8% 的 CPU 花在 GC 上（偏高）
- `12->14->11 MB`：GC 前 12MB，GC 时增长到 14MB，GC 后存活 11MB
- `12 MB goal`：GOGC=100 → 目标堆大小 = 11 * 2 = 22MB，但 goal 只有 12MB

每秒 8 次 GC，说明分配速度很快。存活内存只有 11MB，但新分配速度快到 GOGC=100 也无法阻止频繁 GC。

**第二步：Heap Profile 分析分配热点**

```bash
go tool pprof -alloc_space http://localhost:6060/debug/pprof/heap
(pprof) top 5
      flat  flat%   sum%        cum   cum%
    2.8GB 42.00% 42.00%     2.8GB 42.00%  encoding/json.Marshal
    1.5GB 22.50% 64.50%     1.5GB 22.50%  main.buildQuoteMessage
    0.8GB 12.00% 76.50%     0.8GB 12.00%  bytes.(*Buffer).grow
```

`json.Marshal` 和 `buildQuoteMessage` 产生了大量临时对象。

**第三步：查看热点代码**

```go
func pushQuote(conn *websocket.Conn, quote *Quote) error {
    msg := buildQuoteMessage(quote) // 每次构建新的消息对象
    data, _ := json.Marshal(msg)    // 每次序列化分配新 []byte
    return conn.WriteMessage(websocket.TextMessage, data)
}
```

每秒推送 10000 条报价，每条都 `json.Marshal` 一次，每次分配约 500 字节的 `[]byte`，每秒产生约 5MB 的临时分配。

### 修复

```go
var bufPool = sync.Pool{
    New: func() interface{} {
        return bytes.NewBuffer(make([]byte, 0, 1024))
    },
}

var encoderPool = sync.Pool{
    New: func() interface{} {
        return json.NewEncoder(nil)
    },
}

func pushQuote(conn *websocket.Conn, quote *Quote) error {
    buf := bufPool.Get().(*bytes.Buffer)
    buf.Reset()
    defer bufPool.Put(buf)

    // 直接编码到复用的 buffer 中
    enc := json.NewEncoder(buf)
    if err := enc.Encode(buildQuoteMessage(quote)); err != nil {
        return err
    }

    return conn.WriteMessage(websocket.TextMessage, buf.Bytes())
}
```

同时调整 GOGC：

```bash
GOGC=200 GOMEMLIMIT=800MiB ./quote-service
```

### 验证

- GC 频率从 8-10 次/秒 降到 1-2 次/秒
- GC CPU 占比从 8% 降到 2%
- P99 延迟从 50-200ms 稳定到 5-8ms
- `alloc_objects` 下降 70%

---

## 案例 4：Map 大量删除后内存不下降

### 现象

一个会话管理服务，用 `map[string]*Session` 存储在线用户会话。每天早高峰 8:00 有 50 万用户登录，晚 22:00 大部分用户下线。

Grafana 显示：
- 8:00 内存从 200MB 涨到 1.2GB（50 万个 Session 对象）
- 22:00 后虽然活跃会话从 50 万降到 5 万，但内存只从 1.2GB 降到 1GB
- 第二天 8:00 再涨到 1.5GB，内存逐日递增

代码中已经在用户下线时 `delete(sessions, userID)`，且 Session 对象确实被 GC 了（`go_memstats_heap_objects` 下降了），但 `go_memstats_sys_bytes` 居高不下。

### 假设

Go map 只增不缩的特性导致。map 删除 key 只标记 bucket 为空，不会释放 bucket 数组的内存。

### 排查过程

**第一步：确认 Heap Profile**

```bash
go tool pprof -inuse_space http://localhost:6060/debug/pprof/heap
(pprof) top 5
      flat  flat%
    850MB 72.00%  runtime.makemap / runtime.mapassign_faststr
```

大量内存被 map 的内部结构（bucket 数组）占用。

**第二步：写测试验证**

```go
func TestMapMemory(t *testing.T) {
    m := make(map[int][]byte)

    // 插入 50 万个 key
    for i := 0; i < 500_000; i++ {
        m[i] = make([]byte, 1024) // 1KB per entry
    }

    var ms1 runtime.MemStats
    runtime.GC()
    runtime.ReadMemStats(&ms1)
    t.Logf("After insert: Alloc=%dMB, Sys=%dMB", ms1.Alloc/1024/1024, ms1.Sys/1024/1024)

    // 删除 45 万个 key
    for i := 0; i < 450_000; i++ {
        delete(m, i)
    }

    var ms2 runtime.MemStats
    runtime.GC()
    runtime.ReadMemStats(&ms2)
    t.Logf("After delete: Alloc=%dMB, Sys=%dMB", ms2.Alloc/1024/1024, ms2.Sys/1024/1024)
    // Alloc 显著下降（value 的 []byte 被回收），但 Sys 几乎不变（bucket 没释放）
}
```

### 根因

Go map 的实现使用 bucket 数组，bucket 数量只增不减。即使删除了 90% 的 key，bucket 数组仍然保持 50 万个 key 时的大小。这是 Go runtime 的已知行为。

### 修复

方案：定期重建 map。

```go
type SessionManager struct {
    mu       sync.RWMutex
    sessions map[string]*Session
}

// 每小时在低峰期执行一次
func (sm *SessionManager) Compact() {
    sm.mu.Lock()
    defer sm.mu.Unlock()

    newMap := make(map[string]*Session, len(sm.sessions))
    for k, v := range sm.sessions {
        newMap[k] = v
    }
    sm.sessions = newMap
    // 旧 map 在下次 GC 时被回收，包括其 bucket 数组

    runtime.GC() // 可选：立即触发 GC 回收旧 map
}

// 启动定时任务
func (sm *SessionManager) StartCompaction(ctx context.Context) {
    ticker := time.NewTicker(1 * time.Hour)
    defer ticker.Stop()

    for {
        select {
        case <-ctx.Done():
            return
        case <-ticker.C:
            before := runtime.MemStats{}
            runtime.ReadMemStats(&before)

            sm.Compact()

            after := runtime.MemStats{}
            runtime.ReadMemStats(&after)

            log.Printf("map compaction: alloc %dMB → %dMB, sessions=%d",
                before.Alloc/1024/1024, after.Alloc/1024/1024, len(sm.sessions))
        }
    }
}
```

替代方案：使用分片 map（sharded map），每个分片独立重建，降低锁持有时间：

```go
const shardCount = 32

type ShardedSessionManager struct {
    shards [shardCount]struct {
        mu       sync.RWMutex
        sessions map[string]*Session
    }
}

func (sm *ShardedSessionManager) getShard(key string) int {
    h := fnv.New32a()
    h.Write([]byte(key))
    return int(h.Sum32()) % shardCount
}

func (sm *ShardedSessionManager) Compact() {
    for i := 0; i < shardCount; i++ {
        sm.shards[i].mu.Lock()
        newMap := make(map[string]*Session, len(sm.shards[i].sessions))
        for k, v := range sm.shards[i].sessions {
            newMap[k] = v
        }
        sm.shards[i].sessions = newMap
        sm.shards[i].mu.Unlock()
        // 每个分片独立锁定时间短，不阻塞整个服务
    }
}
```

### 验证

部署后观察一周：
- 每日高峰内存仍涨到 1.2GB（正常）
- 低峰期 Compact 后降到 300MB（之前是 1GB+）
- 内存不再逐日递增
- Compact 期间 P99 延迟无明显波动（分片锁持有时间 < 1ms）

---

## 案例总结

| 案例 | 排查工具 | 核心模式 |
|------|---------|---------|
| Goroutine 泄漏 | pprof goroutine profile | channel + context 未配合 |
| gRPC 连接耗尽 | goroutine profile + ss | 每次请求创建新连接 |
| GC 频繁 | gctrace + heap alloc_space | 大量临时对象 + GOGC 默认值 |
| Map 内存不释放 | heap inuse_space + MemStats | Go map 只增不缩 |

排查方法论：
1. **看监控**：goroutine 数、内存趋势、GC 频率、P99 延迟
2. **定位范围**：用 pprof 确定是 CPU/内存/goroutine/锁 哪个维度的问题
3. **下钻细节**：用 top/list 找到具体函数和代码行
4. **理解根因**：结合 Go 运行时知识（GC、map 实现、channel 语义）解释现象
5. **修复并验证**：修复后用相同的监控指标确认效果
