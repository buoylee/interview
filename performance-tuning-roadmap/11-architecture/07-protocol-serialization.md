# 协议与序列化性能

网络通信中，协议决定了数据如何传输，序列化决定了数据如何编码。在微服务架构中，服务间通信的开销可能占总延迟的 30-60%。选错协议或序列化格式，性能差距可达 5-10 倍。本文提供基于实测数据的选型指导。

---

## 一、HTTP 协议版本对比

### 1.1 核心差异

| 特性 | HTTP/1.1 | HTTP/2 | HTTP/3 |
|------|----------|--------|--------|
| 传输层 | TCP | TCP | QUIC（基于 UDP） |
| 多路复用 | 否（一个连接一个请求） | 是（流） | 是 |
| 头部压缩 | 无 | HPACK | QPACK |
| 队头阻塞 | HTTP + TCP 层 | HTTP 层解决，TCP 层仍有 | 完全解决 |
| 连接建立 | TCP + TLS = 3 RTT | TCP + TLS = 3 RTT | 1 RTT（0-RTT 可能） |
| 服务端推送 | 无 | 支持 | 支持 |
| 普及度 | 100% | ~60% 网站 | ~30% 网站 |

### 1.2 队头阻塞问题

```
HTTP/1.1 队头阻塞（Head-of-Line Blocking）：
  连接 1: [请求A 等待响应...] [请求B 被阻塞]
  解决方案：开 6 个 TCP 连接 → 资源浪费

HTTP/2 解决了 HTTP 层的队头阻塞：
  一个 TCP 连接上多路复用：
  Stream 1: [请求A] → [响应A]
  Stream 2: [请求B] → [响应B]   // 并行，不等 A

  但 TCP 层的队头阻塞仍在：
  丢包 → 整个 TCP 连接阻塞 → 所有 Stream 受影响

HTTP/3 (QUIC) 完全解决：
  Stream 1 丢包 → 只影响 Stream 1
  Stream 2 不受影响 → 继续传输
```

### 1.3 性能对比（实测参考）

| 场景 | HTTP/1.1 | HTTP/2 | 提升 |
|------|----------|--------|------|
| 加载 100 个小资源 | 3.2s | 0.8s | 4x |
| 单个大文件下载 | 1.0s | 1.0s | 无 |
| 高延迟网络（200ms RTT） | 5.4s | 1.2s | 4.5x |
| API 调用（少量请求） | 50ms | 45ms | 微小 |

### 1.4 Nginx HTTP/2 配置

```nginx
server {
    listen 443 ssl http2;    # 开启 HTTP/2

    # HTTP/2 特定优化
    http2_max_concurrent_streams 128;   # 最大并发流
    http2_idle_timeout 300s;            # 空闲超时
    http2_max_header_size 32k;          # 最大头部大小

    ssl_certificate /etc/ssl/cert.pem;
    ssl_certificate_key /etc/ssl/key.pem;

    # TLS 优化（HTTP/2 要求 TLS 1.2+）
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_prefer_server_ciphers on;
    ssl_session_cache shared:SSL:10m;
    ssl_session_timeout 1d;
}
```

---

## 二、gRPC 协议优化

### 2.1 gRPC 优势

```
gRPC 基于 HTTP/2 + Protobuf：
- 二进制协议（比 JSON 小 3-10 倍）
- 多路复用（一个连接处理多个请求）
- 双向流式传输
- 强类型 IDL（.proto 文件）
- 自动代码生成
```

### 2.2 四种通信模式

```protobuf
service OrderService {
    // 1. Unary（一请求一响应，类似 REST）
    rpc GetOrder(GetOrderRequest) returns (Order);

    // 2. Server Streaming（服务端流）
    rpc ListOrders(ListOrdersRequest) returns (stream Order);

    // 3. Client Streaming（客户端流）
    rpc BatchCreateOrders(stream CreateOrderRequest) returns (BatchResult);

    // 4. Bidirectional Streaming（双向流）
    rpc Chat(stream ChatMessage) returns (stream ChatMessage);
}
```

### 2.3 性能调优参数

```java
// Java gRPC Server 配置
Server server = ServerBuilder.forPort(9090)
    .addService(new OrderServiceImpl())
    .maxInboundMessageSize(10 * 1024 * 1024)      // 最大接收消息 10MB
    .maxInboundMetadataSize(8 * 1024)              // 最大元数据 8KB
    .executor(Executors.newFixedThreadPool(200))    // 业务线程池
    .keepAliveTime(30, TimeUnit.SECONDS)            // 发送 keepalive ping 间隔
    .keepAliveTimeout(10, TimeUnit.SECONDS)         // keepalive 超时
    .permitKeepAliveTime(10, TimeUnit.SECONDS)      // 客户端最小 keepalive 间隔
    .maxConnectionIdle(300, TimeUnit.SECONDS)       // 空闲连接最大存活
    .build();

// Java gRPC Client 配置
ManagedChannel channel = ManagedChannelBuilder.forTarget("dns:///service:9090")
    .defaultLoadBalancingPolicy("round_robin")      // 客户端负载均衡
    .keepAliveTime(30, TimeUnit.SECONDS)
    .keepAliveTimeout(10, TimeUnit.SECONDS)
    .keepAliveWithoutCalls(true)                    // 空闲时也发 keepalive
    .maxInboundMessageSize(10 * 1024 * 1024)
    .idleTimeout(300, TimeUnit.SECONDS)
    .enableRetry()                                  // 启用重试
    .maxRetryAttempts(3)
    .build();
```

### 2.4 gRPC 负载均衡

```
两种模式：

1. 代理模式（L7 代理）
   Client → Envoy/Nginx → gRPC Server 1
                        → gRPC Server 2
   优点：客户端简单
   缺点：代理是瓶颈

2. 客户端负载均衡（推荐微服务内部）
   Client → DNS/注册中心 → 直连 Server 1
                         → 直连 Server 2
   优点：无中心瓶颈
   缺点：客户端逻辑复杂
```

```go
// Go gRPC 客户端负载均衡
conn, err := grpc.Dial(
    "dns:///my-service.namespace.svc.cluster.local:9090",
    grpc.WithDefaultServiceConfig(`{
        "loadBalancingConfig": [{"round_robin": {}}],
        "methodConfig": [{
            "name": [{"service": "order.OrderService"}],
            "timeout": "3s",
            "retryPolicy": {
                "maxAttempts": 3,
                "initialBackoff": "0.1s",
                "maxBackoff": "1s",
                "backoffMultiplier": 2,
                "retryableStatusCodes": ["UNAVAILABLE"]
            }
        }]
    }`),
    grpc.WithTransportCredentials(insecure.NewCredentials()),
)
```

---

## 三、序列化格式对比

### 3.1 常见格式

| 格式 | 类型 | Schema | 人类可读 | 语言支持 |
|------|------|--------|----------|----------|
| JSON | 文本 | 无（可选 JSON Schema） | 是 | 所有 |
| Protobuf | 二进制 | 必须（.proto） | 否 | 主流语言 |
| Avro | 二进制 | 必须（.avsc） | 否 | 主流语言 |
| MessagePack | 二进制 | 无 | 否 | 主流语言 |
| Thrift | 二进制 | 必须（.thrift） | 否 | 主流语言 |

### 3.2 性能基准（参考值）

```
测试对象：包含 20 个字段的用户订单数据（嵌套结构）

序列化大小（bytes）：
  JSON:       520
  MessagePack: 340  (-35%)
  Protobuf:   210  (-60%)
  Avro:       190  (-63%)

序列化速度（ops/s，越高越好）：
  Protobuf:   3,200,000
  MessagePack: 2,800,000
  Avro:       2,100,000
  JSON(Jackson): 1,500,000

反序列化速度（ops/s）：
  Protobuf:   4,500,000
  MessagePack: 3,200,000
  Avro:       2,500,000
  JSON(Jackson): 1,200,000

注意：实际性能取决于数据结构、字段类型、库的版本等
```

### 3.3 JSON 优化

```java
// Jackson 性能优化
ObjectMapper mapper = new ObjectMapper();

// 1. 复用 ObjectMapper（线程安全，必须单例）
// 错误：每次 new ObjectMapper()

// 2. 使用 afterburner 模块（字节码增强，提速 30%）
mapper.registerModule(new AfterburnerModule());

// 3. 关闭不需要的特性
mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
mapper.disable(DeserializationFeature.FAIL_ON_UNKNOWN_PROPERTIES);

// 4. 使用 Streaming API 处理大 JSON
try (JsonParser parser = mapper.getFactory().createParser(inputStream)) {
    while (parser.nextToken() != null) {
        if ("name".equals(parser.getCurrentName())) {
            parser.nextToken();
            String name = parser.getText();
        }
    }
}
```

### 3.4 Protobuf 使用

```protobuf
// order.proto
syntax = "proto3";
package order;

message Order {
    int64 id = 1;
    int64 user_id = 2;
    repeated OrderItem items = 3;
    OrderStatus status = 4;
    google.protobuf.Timestamp created_at = 5;
    string total_amount = 6;  // 金额用 string 避免精度问题
}

message OrderItem {
    int64 product_id = 1;
    string product_name = 2;
    int32 quantity = 3;
    string unit_price = 4;
}

enum OrderStatus {
    UNKNOWN = 0;
    PENDING = 1;
    PAID = 2;
    SHIPPED = 3;
    COMPLETED = 4;
}
```

```java
// Java 使用
Order order = Order.newBuilder()
    .setId(12345)
    .setUserId(67890)
    .addItems(OrderItem.newBuilder()
        .setProductId(1)
        .setProductName("iPhone")
        .setQuantity(1)
        .setUnitPrice("9999.00"))
    .setStatus(OrderStatus.PAID)
    .build();

// 序列化
byte[] bytes = order.toByteArray();  // 210 bytes vs JSON 520 bytes

// 反序列化
Order parsed = Order.parseFrom(bytes);
```

### 3.5 选型指南

```
你的场景是什么？
│
├── 公开 API / 前端通信
│   └── JSON（通用性 + 可调试性）
│
├── 微服务内部通信
│   ├── 性能敏感 → gRPC + Protobuf
│   └── 通用 → JSON 也够用
│
├── 消息队列
│   ├── 需要 Schema Evolution → Avro（Kafka 推荐）
│   ├── 性能优先 → Protobuf
│   └── 简单场景 → JSON
│
├── 缓存序列化
│   ├── Java 内部 → Kryo（最快）
│   └── 跨语言 → Protobuf / MessagePack
│
└── 日志/配置
    └── JSON（可读性优先）
```

---

## 四、压缩算法选型

### 4.1 性能对比

| 算法 | 压缩率 | 压缩速度 (MB/s) | 解压速度 (MB/s) | CPU 开销 |
|------|--------|-----------------|-----------------|----------|
| lz4 | 2.1:1 | 780 | 4000+ | 最低 |
| snappy | 2.1:1 | 500 | 1500 | 低 |
| zstd (level 1) | 2.9:1 | 500 | 1400 | 低 |
| zstd (level 3) | 3.1:1 | 350 | 1400 | 中 |
| gzip (level 1) | 2.7:1 | 250 | 400 | 中 |
| gzip (level 6) | 3.2:1 | 100 | 400 | 高 |
| brotli (level 4) | 3.5:1 | 60 | 450 | 高 |
| zstd (level 19) | 3.8:1 | 10 | 1400 | 极高 |

### 4.2 场景推荐

```
实时传输（对延迟敏感）：
  → lz4 或 snappy（压缩/解压极快）

API 响应压缩：
  → gzip level 4-6（兼容性最好）
  → zstd level 1-3（新项目推荐，更快更小）

静态资源（可离线预压缩）：
  → brotli level 6-11（压缩率最高）

消息队列：
  → lz4（Kafka 默认推荐）
  → zstd（Kafka 2.1+ 支持，压缩率更好）

日志归档：
  → zstd level 10+（压缩率高 + 解压快）

数据库备份：
  → zstd（压缩率接近 gzip 但速度快 5 倍）
```

### 4.3 Java 中使用 zstd

```java
// 依赖：com.github.luben:zstd-jni

// 压缩
byte[] compressed = Zstd.compress(originalData, 3); // level 3

// 解压
byte[] decompressed = Zstd.decompress(compressed, originalSize);

// 流式压缩
try (ZstdOutputStream zos = new ZstdOutputStream(fileOutputStream, 3)) {
    zos.write(data);
}

// 流式解压
try (ZstdInputStream zis = new ZstdInputStream(fileInputStream)) {
    byte[] buffer = new byte[8192];
    int read;
    while ((read = zis.read(buffer)) != -1) {
        output.write(buffer, 0, read);
    }
}
```

---

## 五、连接复用与长连接

### 5.1 HTTP 连接复用

```
HTTP/1.1 Keep-Alive：
  同一个连接串行处理多个请求（不需要重新建连）

  配置（Nginx）：
  keepalive_timeout 65;        # 空闲连接保持时间
  keepalive_requests 1000;     # 单连接最大请求数

  上游连接池（Nginx → 后端服务）：
  upstream backend {
      server 10.0.0.1:8080;
      server 10.0.0.2:8080;
      keepalive 32;            # 每个 worker 保持 32 个空闲连接
      keepalive_requests 1000;
      keepalive_timeout 60s;
  }

HTTP/2 多路复用：
  一个连接上并行处理多个请求
  减少连接数 = 减少 TLS 握手 + 内存占用
```

### 5.2 数据库长连接

```bash
# MySQL 长连接配置
wait_timeout = 28800          # 空闲连接超时（秒）
max_connections = 500         # 最大连接数
interactive_timeout = 28800   # 交互式连接超时
```

### 5.3 gRPC 长连接管理

```java
// gRPC 默认就是长连接（基于 HTTP/2）
// 关键配置：keepalive 参数

// 服务端
.keepAliveTime(30, TimeUnit.SECONDS)     // 每 30s 发一次 keepalive
.keepAliveTimeout(10, TimeUnit.SECONDS)  // 10s 没响应视为断连
.maxConnectionAge(5, TimeUnit.MINUTES)   // 连接最大存活 5 分钟（强制轮换）
.maxConnectionAgeGrace(30, TimeUnit.SECONDS) // 优雅关闭宽限期

// 客户端
.keepAliveTime(30, TimeUnit.SECONDS)
.keepAliveWithoutCalls(true)             // 空闲时也发 keepalive

// 为什么需要 maxConnectionAge？
// 1. 防止负载不均（新加节点分不到流量）
// 2. 触发客户端重新解析 DNS（发现新节点）
// 3. 定期清理可能有问题的连接
```

---

## 六、协议选型决策树

```
你要通信的是什么？
│
├── 浏览器 / 移动端 → 公开 API
│   ├── RESTful + JSON（通用选择）
│   ├── HTTP/2 + JSON（多请求并行）
│   └── GraphQL + JSON（前端灵活查询）
│
├── 微服务间内部通信
│   ├── 性能敏感（延迟 < 10ms）
│   │   └── gRPC + Protobuf（首选）
│   ├── 通用业务
│   │   ├── gRPC + Protobuf（推荐）
│   │   └── HTTP + JSON（简单够用）
│   └── 事件驱动
│       └── Kafka + Avro/Protobuf
│
├── 实时通信
│   ├── 服务端推送 → SSE（简单）/ WebSocket（双向）
│   └── 流式数据 → gRPC Streaming
│
└── IoT / 边缘设备
    ├── 带宽受限 → MQTT + Protobuf
    └── 低功耗 → CoAP + CBOR
```

---

## 七、总结

### 协议选型速查

| 场景 | 协议 | 序列化 | 压缩 |
|------|------|--------|------|
| Web API | HTTP/2 + REST | JSON | gzip |
| 微服务 RPC | gRPC (HTTP/2) | Protobuf | 无（已够小） |
| 消息队列 | Kafka | Avro / Protobuf | lz4 / zstd |
| 实时推送 | WebSocket / SSE | JSON | 无 |
| 文件传输 | HTTP/2 | 二进制 | zstd |
| 缓存 | Redis 协议 | Protobuf / Kryo | 无 |

### 优化检查清单

| 检查项 | 方法 | 预期收益 |
|--------|------|----------|
| HTTP/2 是否启用 | `curl -I --http2` | 多请求并行 |
| 响应压缩是否开启 | 检查 Content-Encoding | 带宽减少 50-80% |
| 连接是否复用 | 检查 Connection: keep-alive | 减少建连开销 |
| JSON 序列化库是否最优 | Jackson + Afterburner | 序列化提速 30% |
| 是否考虑二进制序列化 | Protobuf 替代 JSON | 体积减少 60%，速度提升 3x |
| gRPC keepalive 是否配置 | 检查 keepalive 参数 | 避免连接断开 |
| 大消息是否分页/流式 | 避免单次传输 > 4MB | 避免 OOM/超时 |
| 是否使用连接池 | 检查上游 keepalive | 减少连接创建开销 |
