# gRPC vs REST 选型

## 一句话回答

**内部服务间用 gRPC,对外/浏览器/第三方用 REST/JSON**,要兼得用 **gRPC-gateway**(从 proto 生成 REST 反代)。gRPC = protobuf(强类型契约 + 二进制)+ HTTP/2(多路复用/头压缩)+ 代码生成,所以**快、契约强、支持四种流**(unary/server/client/bidi);REST/JSON = 文本、人可读、浏览器原生、生态广但契约松、更慢。gRPC 横切靠**拦截器**(≈ HTTP 中间件),错误用 **status code**(`codes.NotFound`…,边界翻译内部错误不泄漏,客户端按 code 判断),调用带 ctx+deadline 超时穿透(`DeadlineExceeded`)。

## 选型表

| | gRPC | REST/JSON |
|---|---|---|
| 性能/契约/流 | 高 / 强(protobuf)/ 四种流 | 中 / 松(OpenAPI)/ 无 |
| 浏览器/通用 | 弱(需 grpc-web) | 原生 |
| 适合 | 内部服务间 | 对外/公开 API |

## 证据链接

- 正文:[`01 gRPC vs REST`](../01-grpc-rest/README.md);错误码边界 [`error-handling/04`](../../error-handling/04-error-design/README.md);ctx [`concurrency/07`](../../concurrency/07-context/README.md)

## 易追问的延伸

- **protobuf 兼容规则?** 字段编号不可复用/不可改类型;加用新编号、删 reserved;CI 用 buf breaking 检查。
- **gRPC 连接复用?** ClientConn 是长连接+多路复用,全局复用别每次 Dial。
- **错误怎么不泄漏?** 边界把内部错误翻译成合适 code + 安全 message,细节进日志/trace。
- **别为性能过早上 gRPC**:增运维复杂度;全 REST 够用就别折腾。
