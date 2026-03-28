# 结构化日志

## 为什么结构化日志对排查至关重要

### 文本日志 vs 结构化日志

传统文本日志的典型形态：

```
2024-03-15 14:23:45.123 INFO  OrderService - User 12345 placed order 67890, total=299.00, payment=ALIPAY
2024-03-15 14:23:45.456 ERROR OrderService - Failed to process order 67890 for user 12345: insufficient inventory for SKU-ABC
```

结构化日志（JSON 格式）的等价表示：

```json
{
  "timestamp": "2024-03-15T14:23:45.123Z",
  "level": "INFO",
  "service": "order-service",
  "traceId": "a1b2c3d4e5f6",
  "spanId": "f6e5d4c3b2a1",
  "logger": "OrderService",
  "message": "User placed order",
  "userId": 12345,
  "orderId": 67890,
  "total": 299.00,
  "payment": "ALIPAY"
}
```

**核心差异不在格式，而在可查询性。** 文本日志要 grep + 正则才能提取字段，结构化日志每个字段都是独立可查的维度。当你在 Kibana 里需要查"某用户过去一小时所有失败订单"时：

- 文本日志：`message: "Failed" AND message: "user 12345"` —— 模糊匹配，容易误命中
- 结构化日志：`userId: 12345 AND level: ERROR AND logger: OrderService` —— 精确过滤，零噪声

---

## 日志级别规范

日志级别不是随意选择的，每个级别有明确的语义约定：

| 级别 | 含义 | 什么时候用 | 生产环境是否开启 |
|------|------|-----------|----------------|
| **TRACE** | 最细粒度的追踪 | 方法入参出参、循环迭代细节 | 否，仅本地调试 |
| **DEBUG** | 调试辅助信息 | SQL 执行详情、缓存命中/未命中、条件分支判断 | 默认关，按需动态开启 |
| **INFO** | 业务关键事件 | 请求处理完成、状态变迁、定时任务执行 | 是 |
| **WARN** | 潜在问题但未影响功能 | 重试成功、降级触发、资源使用率超阈值 | 是 |
| **ERROR** | 确实出错且需要关注 | 请求处理失败、外部服务不可达、数据不一致 | 是 |

**常见错误用法：**

```java
// 错误：把正常业务逻辑用 ERROR 打
log.error("User {} not found", userId);  // 用户不存在是正常业务场景，应该用 INFO 或 WARN

// 错误：catch 了异常但只打 INFO
try { ... } catch (Exception e) {
    log.info("Something happened: {}", e.getMessage());  // 丢失了堆栈，应该用 error
}

// 正确做法
log.warn("User not found, userId={}", userId);
log.error("Order processing failed, orderId={}", orderId, e);  // 传入异常对象保留堆栈
```

---

## MDC 与 TraceID 注入

MDC（Mapped Diagnostic Context）是在日志中自动注入上下文信息的关键机制。

### Java（SLF4J MDC）

```java
// Filter 或 Interceptor 中注入
public class TraceFilter implements Filter {
    @Override
    public void doFilter(ServletRequest req, ServletResponse res, FilterChain chain) {
        try {
            MDC.put("traceId", getOrCreateTraceId(req));
            MDC.put("userId", extractUserId(req));
            MDC.put("clientIp", req.getRemoteAddr());
            chain.doFilter(req, res);
        } finally {
            MDC.clear();  // 必须清理，否则线程复用导致上下文污染
        }
    }
}

// logback.xml 中引用 MDC 字段
// pattern 中用 %X{traceId} 引用
```

### Go（context 传递）

```go
// Go 没有 MDC，靠 context + 结构化日志库实现
func HandleRequest(w http.ResponseWriter, r *http.Request) {
    ctx := r.Context()
    logger := slog.With(
        "traceId", r.Header.Get("X-Trace-Id"),
        "method",  r.Method,
        "path",    r.URL.Path,
    )
    logger.InfoContext(ctx, "request received")
}
```

### Python（logging extra / Filter）

```python
import logging
import uuid
from contextvars import ContextVar

trace_id_var: ContextVar[str] = ContextVar('trace_id', default='')

class TraceIdFilter(logging.Filter):
    def filter(self, record):
        record.traceId = trace_id_var.get('')
        return True

# 在请求入口设置
trace_id_var.set(str(uuid.uuid4()))

# logging 配置
handler = logging.StreamHandler()
handler.addFilter(TraceIdFilter())
formatter = logging.Formatter(
    '{"timestamp":"%(asctime)s","level":"%(levelname)s",'
    '"traceId":"%(traceId)s","message":"%(message)s"}'
)
handler.setFormatter(formatter)
```

---

## 日志格式设计：JSON 标准字段

推荐的 JSON 日志标准字段集：

```json
{
  "timestamp": "2024-03-15T14:23:45.123Z",  // ISO 8601，带时区
  "level": "INFO",                            // 大写
  "service": "order-service",                 // 服务名
  "instance": "order-service-7b8f9-xk2j4",   // 实例标识（Pod 名/主机名）
  "traceId": "a1b2c3d4e5f6",                 // 分布式追踪 ID
  "spanId": "f6e5d4c3b2a1",                  // Span ID
  "logger": "com.example.OrderService",       // 日志器名
  "message": "Order created successfully",    // 人可读的消息
  "orderId": 67890,                           // 业务字段（按需）
  "duration_ms": 45,                          // 耗时（按需）
  "error": {                                  // 异常信息（仅 ERROR 时）
    "type": "java.lang.NullPointerException",
    "message": "...",
    "stacktrace": "..."
  }
}
```

**关键原则：**
- `timestamp` 必须包含时区信息，多机房部署时避免时间错乱
- `service` + `instance` 用于定位到具体节点
- `traceId` 贯穿整个请求链路
- 业务字段扁平化放在顶层，不要嵌套过深

---

## 日志对性能的影响

### 同步 vs 异步 Appender

```
同步写日志：业务线程 → 格式化 → 写磁盘/网络 → 返回
异步写日志：业务线程 → 放入队列 → 返回（后台线程消费队列并写出）
```

**Logback 异步 Appender 配置：**

```xml
<appender name="ASYNC" class="ch.qos.logback.classic.AsyncAppender">
    <queueSize>1024</queueSize>           <!-- 队列大小 -->
    <discardingThreshold>0</discardingThreshold>  <!-- 0 表示不丢弃任何级别 -->
    <neverBlock>true</neverBlock>         <!-- 队列满时不阻塞业务线程 -->
    <appender-ref ref="FILE"/>
</appender>
```

**性能对比（参考数据）：**

| 模式 | 单条日志耗时 | 吞吐量影响 |
|------|-------------|-----------|
| 同步写文件 | 5-50 us | 高并发下显著 |
| 异步队列 | < 1 us | 几乎无影响 |
| 同步写网络（TCP） | 100-500 us | 严重影响 |

**注意事项：**
- 异步 appender 在 JVM 关闭时可能丢失队列中的日志，需配置 shutdown hook
- `neverBlock=true` 意味着队列满时丢日志，在极端情况下要接受这个 trade-off
- 日志量大时 JSON 序列化本身也有 CPU 开销，避免在日志中做复杂对象 toString

---

## 框架调试日志配置速查

排查框架层面问题时，需要临时开启框架内部日志：

### Netty LoggingHandler

```java
// 在 Channel Pipeline 中添加
pipeline.addLast("logger", new LoggingHandler(LogLevel.DEBUG));

// 或在 Spring Boot 中配置
// application.yml
logging:
  level:
    io.netty: DEBUG
    io.netty.handler.logging: DEBUG
```

### HikariCP 连接池

```yaml
# application.yml
logging:
  level:
    com.zaxxer.hikari: DEBUG          # 连接池生命周期
    com.zaxxer.hikari.HikariConfig: DEBUG  # 配置信息
# HikariCP 自带的 debug 配置
spring:
  datasource:
    hikari:
      leak-detection-threshold: 60000  # 连接泄漏检测（ms）
```

### Spring 各级日志

```yaml
logging:
  level:
    org.springframework.web: DEBUG           # MVC 请求处理
    org.springframework.web.client: DEBUG     # RestTemplate
    org.springframework.data.jpa: DEBUG       # JPA 查询
    org.hibernate.SQL: DEBUG                  # 显示 SQL
    org.hibernate.type.descriptor.sql: TRACE  # 显示 SQL 参数绑定
    org.springframework.transaction: DEBUG    # 事务管理
    org.springframework.security: DEBUG       # 安全框架
```

### Go GODEBUG 环境变量

```bash
# HTTP/2 调试
GODEBUG=http2debug=1 ./myapp

# GC 调试
GODEBUG=gctrace=1 ./myapp

# 调度器调试
GODEBUG=schedtrace=1000 ./myapp   # 每 1000ms 打印一次调度信息

# TLS 调试
GODEBUG=tls13=1 ./myapp
```

### Python logging 按模块配置

```python
import logging

# 按模块精细控制
logging.getLogger('urllib3').setLevel(logging.DEBUG)        # HTTP 客户端
logging.getLogger('sqlalchemy.engine').setLevel(logging.DEBUG)  # SQL 语句
logging.getLogger('celery').setLevel(logging.DEBUG)         # 任务队列
logging.getLogger('redis').setLevel(logging.DEBUG)          # Redis 操作

# Django 设置
LOGGING = {
    'version': 1,
    'loggers': {
        'django.db.backends': {
            'level': 'DEBUG',   # 显示所有 SQL
            'handlers': ['console'],
        },
    },
}
```

---

## 小结

```
结构化日志核心要点
├── 用 JSON 格式，每个字段独立可查
├── 通过 MDC / context 自动注入 traceId
├── 日志级别要有明确的语义规范
├── 生产环境必须用异步 Appender
└── 框架调试日志：知道怎么开、用完记得关
```

结构化日志是可观测性的基础。没有良好的日志，后续的指标和链路追踪都缺少了最关键的"现场细节"。下一节我们将讨论如何把这些日志高效地收集、存储和查询 —— 日志基础设施。
