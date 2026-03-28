# net/http 与 gRPC 性能

## 概述

后端服务的性能很大程度上取决于网络通信层。Go 的 `net/http` 和 gRPC 是最常用的两个网络框架。掌握连接池配置、超时设置和性能调优是避免生产事故的基础。

## net/http 连接池

### Transport 核心配置

`http.Client` 底层使用 `http.Transport` 管理连接池。默认的 `http.DefaultTransport` 配置如下：

```go
var DefaultTransport = &http.Transport{
    MaxIdleConns:          100,
    MaxIdleConnsPerHost:   2,   // 注意：默认只有 2！
    IdleConnTimeout:       90 * time.Second,
}
```

**生产环境推荐配置**：

```go
transport := &http.Transport{
    MaxIdleConns:        200,              // 所有 host 的空闲连接总数上限
    MaxIdleConnsPerHost: 100,              // 每个 host 的空闲连接上限（关键！）
    MaxConnsPerHost:     200,              // 每个 host 的最大连接数（含活跃+空闲）
    IdleConnTimeout:     90 * time.Second, // 空闲连接的超时时间
    TLSHandshakeTimeout: 10 * time.Second,
    ResponseHeaderTimeout: 30 * time.Second,
    DialContext: (&net.Dialer{
        Timeout:   5 * time.Second,   // 连接超时
        KeepAlive: 30 * time.Second,  // TCP keepalive 间隔
    }).DialContext,
}

client := &http.Client{
    Transport: transport,
    Timeout:   60 * time.Second, // 整体请求超时（含 Body 读取）
}
```

关键参数详解：

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `MaxIdleConnsPerHost` | 2 | **这是最常见的瓶颈**。如果你的服务高频调用同一个下游，默认值 2 会导致大量连接重建 |
| `MaxConnsPerHost` | 0（无限制） | 限制到同一 host 的总连接数，防止连接风暴 |
| `MaxIdleConns` | 100 | 所有 host 的空闲连接总数 |
| `IdleConnTimeout` | 90s | 空闲连接存活时间 |

### 常见错误一：不读 Body 导致连接无法复用

```go
// 错误：只读了状态码，没有读完 Body
resp, err := client.Get(url)
if err != nil { return err }
if resp.StatusCode != 200 {
    return fmt.Errorf("status: %d", resp.StatusCode)
    // resp.Body 没有被读取和关闭！连接无法复用
}
```

HTTP/1.1 连接复用的前提是当前请求的 Body 被完全读取并 Close。否则连接被废弃，下次需要重新建立 TCP 连接（甚至 TLS 握手），延迟急剧增加。

```go
// 正确：始终读完 Body 并 Close
resp, err := client.Get(url)
if err != nil { return err }
defer resp.Body.Close()

if resp.StatusCode != 200 {
    io.Copy(io.Discard, resp.Body) // 读完丢弃
    return fmt.Errorf("status: %d", resp.StatusCode)
}

data, err := io.ReadAll(resp.Body)
```

### 常见错误二：自定义 Transport 忘记设置超时

```go
// 危险：没有任何超时设置
client := &http.Client{}

// 如果下游服务挂了或极慢，这个请求会永远等待，最终耗尽 goroutine
resp, err := client.Get(url)
```

**必须设置超时**。选择哪个超时取决于需求：

```go
// 方式一：Client.Timeout — 最简单，覆盖整个请求生命周期
client := &http.Client{Timeout: 30 * time.Second}

// 方式二：Context — 更灵活，可以和业务逻辑联动
ctx, cancel := context.WithTimeout(context.Background(), 30*time.Second)
defer cancel()
req, _ := http.NewRequestWithContext(ctx, "GET", url, nil)
resp, err := client.Do(req)
```

### httptrace：跟踪请求各阶段耗时

```go
import "net/http/httptrace"

func traceRequest(req *http.Request) *http.Request {
    var dnsStart, connStart, tlsStart time.Time

    trace := &httptrace.ClientTrace{
        DNSStart: func(info httptrace.DNSStartInfo) {
            dnsStart = time.Now()
        },
        DNSDone: func(info httptrace.DNSDoneInfo) {
            fmt.Printf("DNS: %v\n", time.Since(dnsStart))
        },
        ConnectStart: func(network, addr string) {
            connStart = time.Now()
        },
        ConnectDone: func(network, addr string, err error) {
            fmt.Printf("Connect: %v\n", time.Since(connStart))
        },
        TLSHandshakeStart: func() {
            tlsStart = time.Now()
        },
        TLSHandshakeDone: func(state tls.ConnectionState, err error) {
            fmt.Printf("TLS: %v\n", time.Since(tlsStart))
        },
        GotFirstResponseByte: func() {
            fmt.Printf("TTFB: %v\n", time.Since(connStart))
        },
    }

    return req.WithContext(httptrace.WithClientTrace(req.Context(), trace))
}
```

输出示例：
```
DNS: 2.3ms
Connect: 5.1ms
TLS: 12.8ms
TTFB: 45.2ms
```

如果 DNS 很慢 → 检查 DNS 解析配置或本地缓存。
如果 Connect 很慢 → 网络问题或目标服务器过载。
如果 TTFB 很慢但 Connect 快 → 服务端处理慢。

## gRPC 性能优化

### Unary vs Streaming

**Unary RPC**：一请求一响应，最简单。

**Streaming RPC**：适用于需要传输大量数据或多个消息的场景：
- **Server Streaming**：客户端发一个请求，服务端返回消息流
- **Client Streaming**：客户端发消息流，服务端返回一个响应
- **Bidirectional Streaming**：双向消息流

Streaming 的性能优势：
- 减少序列化/反序列化次数（每条消息独立序列化，比一个巨大的 Unary 消息更高效）
- 减少 RTT（只需一次连接建立，后续消息直接复用）
- 支持流式处理，降低内存占用

```go
// Server Streaming 示例
func (s *server) ListOrders(req *pb.ListRequest, stream pb.OrderService_ListOrdersServer) error {
    for _, order := range getOrders(req) {
        if err := stream.Send(order); err != nil {
            return err
        }
    }
    return nil
}
```

### 连接复用

gRPC 基于 HTTP/2，天然支持多路复用：
- 一个 TCP 连接上可以并发多个 RPC 请求
- 不需要像 HTTP/1.1 那样维护连接池
- 默认就是连接复用的

```go
// 创建一个连接，所有 RPC 共享
conn, err := grpc.Dial("server:50051",
    grpc.WithTransportCredentials(insecure.NewCredentials()),
)
defer conn.Close()

client := pb.NewOrderServiceClient(conn)
// client 可以并发使用，底层共享一个 HTTP/2 连接
```

### Keepalive 配置

keepalive 防止连接因长时间空闲被中间网络设备断开：

```go
import "google.golang.org/grpc/keepalive"

// 客户端配置
conn, err := grpc.Dial("server:50051",
    grpc.WithKeepaliveParams(keepalive.ClientParameters{
        Time:                10 * time.Second, // 空闲多久发一次 ping
        Timeout:             3 * time.Second,  // ping 超时时间
        PermitWithoutStream: true,             // 没有活跃 stream 时也发 ping
    }),
)

// 服务端配置
server := grpc.NewServer(
    grpc.KeepaliveParams(keepalive.ServerParameters{
        MaxConnectionIdle:     15 * time.Minute, // 空闲连接最长存活时间
        MaxConnectionAge:      30 * time.Minute, // 连接最长存活时间（用于优雅轮转）
        MaxConnectionAgeGrace: 5 * time.Second,  // 关闭前的宽限期
        Time:                  5 * time.Second,
        Timeout:               1 * time.Second,
    }),
    grpc.KeepaliveEnforcementPolicy(keepalive.EnforcementPolicy{
        MinTime:             5 * time.Second, // 客户端 ping 的最小间隔
        PermitWithoutStream: true,
    }),
)
```

**MaxConnectionAge 的妙用**：设置最大连接寿命，强制客户端定期重新连接。这样在部署新版本时，客户端会自然地重新解析 DNS，连接到新的 Pod 上。

### 负载均衡

**服务端负载均衡**（通过 LB 代理如 Envoy/Nginx）：
- 简单，客户端无需感知后端
- 但 HTTP/2 多路复用下，LB 只能在连接级别均衡，同一连接上的所有请求都去同一后端

**客户端负载均衡**（gRPC 原生支持）：
- 客户端直接连接多个后端
- 每个 RPC 独立选择后端
- 更精细的负载均衡

```go
import (
    "google.golang.org/grpc/resolver"
    _ "google.golang.org/grpc/balancer/roundrobin"
)

conn, err := grpc.Dial(
    "dns:///myservice.svc.cluster.local:50051",
    grpc.WithDefaultServiceConfig(`{"loadBalancingConfig": [{"round_robin":{}}]}`),
)
```

### gRPC 性能调优清单

```
1. 连接管理
   [ ] 复用连接，不要每次 RPC 都新建连接
   [ ] 配置 keepalive 防止连接被中间设备断开
   [ ] 设置 MaxConnectionAge 便于滚动更新
   [ ] 使用客户端负载均衡而非 L4 代理（如果可能）

2. 序列化
   [ ] 使用 proto3 而非 proto2
   [ ] 避免嵌套过深的 protobuf 消息
   [ ] 大量数据传输使用 streaming 而非单个巨大 message

3. 超时和重试
   [ ] 每个 RPC 调用设置 context deadline
   [ ] 配置合理的重试策略（retry on UNAVAILABLE）
   [ ] 设置 MaxRecvMsgSize / MaxSendMsgSize（默认 4MB）

4. 性能
   [ ] 启用 gzip 压缩（网络带宽是瓶颈时）
   [ ] 使用 Unary Interceptor 记录 RPC 延迟
   [ ] 监控 grpc_server_handled_total 等 metrics
```

```go
// 超时设置
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
defer cancel()
resp, err := client.GetOrder(ctx, req)

// 增大消息大小限制（默认 4MB）
conn, err := grpc.Dial("server:50051",
    grpc.WithDefaultCallOptions(
        grpc.MaxCallRecvMsgSize(50*1024*1024), // 50MB
    ),
)
```

## net/http vs gRPC 选择

| 维度 | net/http (REST/JSON) | gRPC (Protobuf) |
|------|---------------------|-----------------|
| 序列化性能 | JSON 较慢 | Protobuf 快 3-10x |
| 包大小 | JSON 较大（文本格式） | Protobuf 紧凑（二进制） |
| 连接复用 | HTTP/1.1 需连接池管理 | HTTP/2 天然多路复用 |
| 流式传输 | 需要 WebSocket/SSE | 原生 Streaming |
| 浏览器兼容 | 天然兼容 | 需要 gRPC-Web 代理 |
| 调试便利性 | curl 直接测试 | 需要 grpcurl 等工具 |

内部微服务间通信优先考虑 gRPC，面向外部的 API 使用 REST/JSON。

## 小结

1. `MaxIdleConnsPerHost` 默认只有 2，高频调用同一下游时必须调大
2. HTTP 响应 Body 必须读完并 Close，否则连接无法复用
3. 所有 HTTP 请求必须设置超时
4. gRPC 基于 HTTP/2，天然连接复用，不需要连接池
5. gRPC keepalive 和 MaxConnectionAge 在容器环境中非常重要
6. 大数据传输优先用 gRPC Streaming
