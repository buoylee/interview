# 01 · gRPC vs REST

> 服务间怎么通信?两大选择:**gRPC**(protobuf + HTTP/2,强类型契约、高性能、支持流)和 **REST/JSON**(通用、人可读、浏览器友好)。面试常考**选型**和 gRPC 的细节(拦截器、status code 映射)。
>
> 桥接锚点:Java 的 gRPC-java / Spring gRPC、Spring MVC REST;protobuf 编译生成代码 ≈ Java 的 protoc-gen-java。

---

## 1. 核心问题

- 内部服务间调用用 gRPC 还是 REST?对外 API 呢?
- protobuf 是什么?为什么 gRPC 比 JSON 快?
- gRPC 怎么加横切逻辑(日志/认证)?错误怎么跨服务传?

---

## 2. 直觉理解

### gRPC = protobuf 契约 + HTTP/2 + 代码生成

```protobuf
service UserService {
    rpc GetUser(GetUserRequest) returns (User);   // 强类型契约,protoc 生成 client/server 代码
}
message User { int64 id = 1; string name = 2; }
```

- **protobuf**:接口定义语言(IDL)+ 二进制序列化。`protoc` 从 `.proto` **生成** client/server 代码(强类型,见 [`generics/02`](../../generics/02-when-to-use/README.md) 代码生成)。
- **快**:二进制(比 JSON 文本小)+ HTTP/2(多路复用、头压缩)+ 无反射序列化。
- **强契约**:`.proto` 是双方共享的合同,字段有编号、向后兼容规则明确。

### REST/JSON = 通用、人可读、浏览器友好

- 文本 JSON、HTTP/1.1、无需代码生成、curl/浏览器直接调、生态最广。
- 代价:文本更大更慢、契约松散(靠文档/OpenAPI)。

### 选型:内部 gRPC,对外 REST

| | gRPC | REST/JSON |
|---|---|---|
| 性能 | 高(二进制+HTTP/2) | 中(文本) |
| 契约 | 强(protobuf) | 松(OpenAPI) |
| 流式 | ✅ 四种流 | ❌(SSE/WebSocket 另说) |
| 浏览器/通用 | 弱(需 grpc-web) | ✅ 原生 |
| 适合 | **内部服务间**、低延迟、流 | **对外/公开 API**、浏览器、第三方 |

经验:**内部服务间用 gRPC**(性能 + 强契约),**对外/面向浏览器用 REST**;两者要兼得用 **gRPC-gateway**(从 proto 生成 REST 反向代理)。

---

## 3. 原理深入

### 3.1 gRPC 四种通信模式

```protobuf
rpc Unary(Req) returns (Resp);                      // 一问一答(最常见)
rpc ServerStream(Req) returns (stream Resp);        // 服务端流(如推送列表)
rpc ClientStream(stream Req) returns (Resp);        // 客户端流(如上传)
rpc BiDi(stream Req) returns (stream Resp);         // 双向流(如聊天)
```

流基于 HTTP/2 的多路复用——这是 REST 难做的(承接 [`concurrency`](../../concurrency/) 的 channel/stream 思维)。

### 3.2 拦截器 = gRPC 的中间件

```go
// gRPC 的横切逻辑靠拦截器(≈ HTTP 中间件,见 stdlib/01)
func loggingInterceptor(ctx, req, info, handler) (resp, err) {
    log.Println(info.FullMethod)
    return handler(ctx, req)        // 调用实际处理
}
```

拦截器(unary / stream)做日志/认证/recover/metrics/限流——和 HTTP 中间件同一思想(见 [`02 中间件`](../02-middleware/README.md))。

### 3.3 错误:status code 映射(跨服务错误传递)

gRPC 用 **status code**(`codes.NotFound`、`codes.InvalidArgument`、`codes.DeadlineExceeded`…)传错误,而非 HTTP 状态码:

```go
return nil, status.Error(codes.NotFound, "user not found")
// 客户端:
st, _ := status.FromError(err)
if st.Code() == codes.NotFound { ... }
```

设计要点(呼应 [`error-handling/04`](../../error-handling/04-error-design/README.md) 边界翻译):**在服务边界把内部错误翻译成合适的 gRPC code**,别把内部 error 原文泄漏;客户端按 code 判断、不解析 message 字符串。REST 端则映射成 HTTP 状态码(404/400/503)。

### 3.4 protobuf 兼容性规则

- **字段编号不可复用/不可改**(编号是线上格式的一部分);
- 加字段用新编号(向后兼容);删字段保留编号(`reserved`);
- 不要改字段类型。
这套规则让 proto 契约能安全演进(类似 [`engineering/00`](../../engineering/00-modules/README.md) 的版本兼容思维)。

### 3.5 ctx 与超时穿透

gRPC 调用都带 `ctx`:客户端设 deadline,**穿透到服务端**(服务端能看到剩余时间、取消会传播,见 [`concurrency/07`](../../concurrency/07-context/README.md))。`codes.DeadlineExceeded` 就是超时。

---

## 4. 日常开发应用

- **内部服务间 gRPC**(强契约 + 性能 + 流);**对外/浏览器 REST**;要兼得用 gRPC-gateway。
- **proto 是契约**:集中管理 `.proto`、用 buf 等工具校验兼容性;字段编号别乱动。
- **横切用拦截器**(日志/认证/recover/metrics),别在每个 handler 重复。
- **错误用 status code**:边界翻译成合适 code,客户端按 code 判断。
- **调用带 ctx + deadline**,让超时穿透。

---

## 5. 生产&调优实战

- **gRPC 连接要复用**(像 HTTP client,见 [`stdlib/01`](../../stdlib/01-net-http/README.md)):`grpc.ClientConn` 是长连接 + 多路复用,全局复用、别每次 Dial。
- **超时/重试**:每个 gRPC 调用设 deadline(`codes.DeadlineExceeded`),重试要配合幂等 + 退避(见 [`02`](../02-middleware/README.md));gRPC 内置重试策略(service config)。
- **错误码不泄漏内部**:边界把 DB/内部错误翻译成 gRPC code + 安全 message,内部细节进日志/trace(见 [`error-handling/04`](../../error-handling/04-error-design/README.md))。
- **proto 演进事故**:复用/改字段编号会导致线上数据错乱(老服务按旧编号解);严守兼容规则,用 buf breaking 检查进 CI。
- **gRPC vs REST 不是非此即彼**:很多系统内部 gRPC、边缘 gRPC-gateway 出 REST;也有全 REST 够用的(别为性能过早上 gRPC 增加运维复杂度)。
- **可观测性**:拦截器统一注入 trace/metrics(见 [`03`](../03-observability/README.md)),ctx 跨服务传 trace_id。

## 6. 面试高频考点

- **gRPC vs REST 怎么选?** 内部服务间用 gRPC(二进制+HTTP/2 高性能、protobuf 强契约、支持流);对外/浏览器/第三方用 REST/JSON(通用、人可读);要兼得用 gRPC-gateway。
- **gRPC 为什么快?** protobuf 二进制(比 JSON 小)+ HTTP/2 多路复用/头压缩 + 生成代码无反射序列化。
- **protobuf 兼容规则?** 字段编号不可复用/不可改类型;加字段用新编号、删字段 reserved;让契约安全演进。
- **gRPC 怎么加横切?** 拦截器(unary/stream),≈ HTTP 中间件(日志/认证/recover/metrics)。
- **gRPC 错误怎么传?** status code(codes.NotFound 等)+ message;边界翻译内部错误成合适 code、不泄漏;客户端按 code 判断。
- **gRPC 四种流?** unary / server-stream / client-stream / bidi,基于 HTTP/2 多路复用。
- **超时怎么穿透?** 调用带 ctx + deadline,穿透到服务端,超时是 codes.DeadlineExceeded。

## 7. 一句话总结

> **gRPC(protobuf IDL + HTTP/2 + 代码生成)vs REST/JSON(文本 + HTTP/1 + 通用)**:gRPC 二进制+多路复用更快、protobuf 强契约、支持四种流(unary/server/client/bidi),适合**内部服务间**;REST 人可读、浏览器友好、生态广,适合**对外/公开 API**;兼得用 **gRPC-gateway**。gRPC 横切靠**拦截器**(≈ HTTP 中间件),错误用 **status code**(`codes.NotFound`…,边界翻译内部错误、不泄漏、客户端按 code 判断,呼应 error-handling/04),调用带 **ctx+deadline 超时穿透**(`DeadlineExceeded`)。protobuf 严守字段编号兼容规则。连接像 HTTP client 一样复用。

← 上一章 [`00 服务骨架`](../00-service-skeleton/README.md) ｜ 下一章 → [`02 中间件与横切`](../02-middleware/README.md):日志/认证/限流/重试/熔断这些横切关注点怎么实现、有什么坑。｜ 回 [`service-design` 索引](../README.md)
