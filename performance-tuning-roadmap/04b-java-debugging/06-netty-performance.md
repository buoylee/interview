# Netty 性能排查

## 概述

Netty 是 Java 生态中使用最广泛的高性能网络框架，Dubbo、gRPC-Java、Elasticsearch、RocketMQ 等都基于 Netty。它的性能问题往往不是 Netty 本身的瓶颈，而是使用方式不当导致的。本文覆盖 Netty 线程模型、Pipeline 排查、ByteBuf 泄漏检测、EventLoop 阻塞等核心问题的排查方法。

---

## 1. Netty 线程模型

```
                        ┌─────────────────────────┐
                        │      Client Connections   │
                        └───────────┬─────────────┘
                                    │
                        ┌───────────▼─────────────┐
                        │    Boss Group (1 thread)  │  ← 只负责 accept 新连接
                        │    ┌─────────────────┐    │
                        │    │  NioEventLoop    │    │
                        │    │  (Selector)      │    │
                        │    └─────────────────┘    │
                        └───────────┬─────────────┘
                                    │ 分配连接
                    ┌───────────────┼───────────────┐
                    ▼               ▼               ▼
          ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
          │ Worker Group │  │ Worker Group │  │ Worker Group │
          │ EventLoop-1  │  │ EventLoop-2  │  │ EventLoop-N  │
          │ (Selector)   │  │ (Selector)   │  │ (Selector)   │
          │              │  │              │  │              │
          │ Channel-A    │  │ Channel-C    │  │ Channel-E    │
          │ Channel-B    │  │ Channel-D    │  │ Channel-F    │
          └─────────────┘  └─────────────┘  └─────────────┘
```

### 线程模型要点

- **Boss Group**：通常 1 个线程，负责接受（accept）新连接，然后将连接注册到某个 Worker EventLoop
- **Worker Group**：通常 CPU 核心数 * 2 个线程，每个 EventLoop 绑定一个线程，负责处理多个 Channel 的 I/O 事件
- **一个 Channel 绑定一个 EventLoop**：一个 Channel 的所有 I/O 事件始终在同一个 EventLoop 线程处理，天然线程安全
- **一个 EventLoop 可以绑定多个 Channel**：一个线程用 Selector 管理多个连接

```java
// 标准 Netty Server 初始化
EventLoopGroup bossGroup = new NioEventLoopGroup(1);       // 1 个线程
EventLoopGroup workerGroup = new NioEventLoopGroup();      // 默认 CPU 核心数 * 2
// 如果有耗时的业务逻辑，使用独立的业务线程池
EventExecutorGroup businessGroup = new DefaultEventExecutorGroup(16);

ServerBootstrap b = new ServerBootstrap();
b.group(bossGroup, workerGroup)
 .channel(NioServerSocketChannel.class)
 .childHandler(new ChannelInitializer<SocketChannel>() {
     @Override
     protected void initChannel(SocketChannel ch) {
         ChannelPipeline p = ch.pipeline();
         p.addLast(new LengthFieldBasedFrameDecoder(1024 * 1024, 0, 4, 0, 4));
         p.addLast(new LengthFieldPrepender(4));
         p.addLast(new MessageDecoder());
         // 耗时业务 Handler 使用独立线程池
         p.addLast(businessGroup, new BusinessHandler());
     }
 });
```

---

## 2. Pipeline 排查方法

当消息处理出现问题时（消息丢失、处理异常、数据错误），需要观察消息在 Pipeline 中的流转。

### 添加 LoggingHandler

```java
// 开发环境：在 Pipeline 中添加 LoggingHandler 观察消息流转
ChannelPipeline p = ch.pipeline();
p.addLast("logger-in", new LoggingHandler(LogLevel.DEBUG));  // 入站日志
p.addLast(new LengthFieldBasedFrameDecoder(1024 * 1024, 0, 4, 0, 4));
p.addLast(new LengthFieldPrepender(4));
p.addLast("logger-mid", new LoggingHandler(LogLevel.DEBUG));  // 解码后日志
p.addLast(new MessageDecoder());
p.addLast(new BusinessHandler());
p.addLast("logger-out", new LoggingHandler(LogLevel.DEBUG));  // 出站日志
```

### LoggingHandler 输出解读

```
// 日志输出示例：
DEBUG logger-in - [id: 0xabcdef, L:/127.0.0.1:8080 - R:/127.0.0.1:54321] READ: 256B
         +-------------------------------------------------+
         |  0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f |
+--------+-------------------------------------------------+
|00000000| 00 00 00 fc 7b 22 6f 72 64 65 72 49 64 22 3a 31 |
|00000010| 30 30 31 2c 22 61 6d 6f 75 6e 74 22 3a 39 39 2e |
+--------+-------------------------------------------------+

// 可以看到：
// - Channel ID (0xabcdef)
// - 本地地址和远端地址
// - 事件类型 (READ/WRITE/FLUSH)
// - 数据内容的十六进制和 ASCII 表示
```

### 排查 Pipeline 的常见问题

```java
// 问题1：Handler 顺序错误
// 编码器/解码器的顺序必须正确
p.addLast(new StringDecoder());           // 先解码 ByteBuf → String
p.addLast(new BusinessHandler());         // 再处理 String
// 如果顺序反了，BusinessHandler 收到的是 ByteBuf 而不是 String

// 问题2：忘记调用 ctx.fireChannelRead(msg) 传递消息
@Override
public void channelRead(ChannelHandlerContext ctx, Object msg) {
    // 处理消息...
    ctx.fireChannelRead(msg);  // 必须调用！否则后续 Handler 收不到消息
    // 或者如果不再需要传递，必须释放 ByteBuf：ReferenceCountUtil.release(msg)
}

// 问题3：异常没有处理
@Override
public void exceptionCaught(ChannelHandlerContext ctx, Throwable cause) {
    log.error("Channel error: {}", ctx.channel().remoteAddress(), cause);
    ctx.close();  // 关闭连接
}
```

---

## 3. ChannelFuture 监听

### 问题：忽略写操作的结果

```java
// 反模式：不检查写操作是否成功
ctx.writeAndFlush(response);
// 如果写失败了（比如对端已断开），你不知道！
// 数据可能丢失，且不会有任何错误提示
```

### 正确做法

```java
// 方式一：添加 ChannelFutureListener
ctx.writeAndFlush(response).addListener((ChannelFutureListener) future -> {
    if (!future.isSuccess()) {
        Throwable cause = future.cause();
        log.error("Write failed to {}: {}",
            ctx.channel().remoteAddress(), cause.getMessage());
        ctx.close();
    }
});

// 方式二：使用内置 Listener
ctx.writeAndFlush(response).addListener(ChannelFutureListener.CLOSE);  // 写完关闭
ctx.writeAndFlush(response).addListener(ChannelFutureListener.CLOSE_ON_FAILURE);  // 失败时关闭

// 方式三：批量检查
ChannelFuture f1 = ctx.write(msg1);
ChannelFuture f2 = ctx.write(msg2);
ctx.flush();

f2.addListener((ChannelFutureListener) future -> {
    if (!future.isSuccess()) {
        log.error("Batch write failed", future.cause());
    }
});
```

---

## 4. ByteBuf 内存泄漏检测

Netty 的 ByteBuf 使用引用计数（Reference Counting）管理内存。忘记 `release()` 会导致内存泄漏。

### ResourceLeakDetector 四个级别

```java
// 通过 JVM 参数设置
// -Dio.netty.leakDetection.level=PARANOID

// 或代码设置
ResourceLeakDetector.setLevel(ResourceLeakDetector.Level.PARANOID);
```

| 级别 | 采样率 | 开销 | 适用场景 |
|------|--------|------|---------|
| **DISABLED** | 不检测 | 无 | 确认没有泄漏后的生产环境 |
| **SIMPLE** | 1% 采样 | 极低 | 生产环境默认级别 |
| **ADVANCED** | 1% 采样 + 详细访问记录 | 低 | 排查泄漏时使用 |
| **PARANOID** | 100% 采样 + 详细记录 | 高 | 开发/测试环境 |

### 泄漏日志

```
# SIMPLE 级别的泄漏报告：
ERROR ResourceLeakDetector - LEAK: ByteBuf.release() was not called before it's garbage-collected.
See https://netty.io/wiki/reference-counted-objects.html for more information.

# ADVANCED/PARANOID 级别：额外显示 ByteBuf 的访问记录
ERROR ResourceLeakDetector - LEAK: ByteBuf.release() was not called before it's garbage-collected.
Recent access records:
#1: io.netty.handler.codec.ByteToMessageDecoder.channelRead(ByteToMessageDecoder.java:295)
#2: com.example.handler.MessageDecoder.decode(MessageDecoder.java:45)
#3: com.example.handler.MessageDecoder.decode(MessageDecoder.java:38)
Created at:
    io.netty.buffer.PooledByteBufAllocator.newDirectBuffer(PooledByteBufAllocator.java:402)
    io.netty.buffer.AbstractByteBufAllocator.directBuffer(AbstractByteBufAllocator.java:188)
```

### ByteBuf 正确使用

```java
// 规则："谁最后使用，谁负责 release"

// 场景1：Decoder 中
@Override
protected void decode(ChannelHandlerContext ctx, ByteBuf in, List<Object> out) {
    // ByteToMessageDecoder 会自动释放 in，你不需要手动释放
    // 但如果你从 in 中拷贝了数据到新的 ByteBuf，需要确保新的 ByteBuf 被传递或释放
    byte[] bytes = new byte[in.readableBytes()];
    in.readBytes(bytes);
    out.add(new Message(bytes));  // 传递给下一个 Handler
}

// 场景2：业务 Handler 中
@Override
public void channelRead(ChannelHandlerContext ctx, Object msg) {
    ByteBuf buf = (ByteBuf) msg;
    try {
        // 处理数据...
    } finally {
        buf.release();  // 如果不再传递给下一个 Handler，必须释放
        // 或使用 ReferenceCountUtil.release(msg);
    }
}

// 场景3：写出时
ByteBuf response = ctx.alloc().buffer(256);
response.writeBytes(data);
ctx.writeAndFlush(response);  // writeAndFlush 成功后会自动 release
// 不需要手动 release！但如果 writeAndFlush 抛异常，需要手动 release
```

---

## 5. EventLoop 阻塞排查

**EventLoop 阻塞是 Netty 性能问题的头号元凶**。一个 EventLoop 线程管理多个 Channel，如果被阻塞，所有这些 Channel 都会受影响。

### 常见的阻塞行为

```java
// 反模式1：在 EventLoop 中做同步数据库查询
@Override
public void channelRead(ChannelHandlerContext ctx, Object msg) {
    // 这会阻塞 EventLoop 线程！
    User user = userDao.findById(msg.getUserId());  // 同步 JDBC 查询
    ctx.writeAndFlush(user);
}

// 反模式2：在 EventLoop 中调用外部 HTTP 接口（同步）
@Override
public void channelRead(ChannelHandlerContext ctx, Object msg) {
    // 同步 HTTP 调用会阻塞 EventLoop
    String result = HttpClient.get("http://api.example.com/check");
    ctx.writeAndFlush(result);
}

// 反模式3：在 EventLoop 中做 CPU 密集计算
@Override
public void channelRead(ChannelHandlerContext ctx, Object msg) {
    // 大量计算阻塞 EventLoop
    BigInteger result = computeFactorial(10000);
    ctx.writeAndFlush(result);
}

// 反模式4：Thread.sleep 或 Object.wait
@Override
public void channelRead(ChannelHandlerContext ctx, Object msg) {
    Thread.sleep(1000);  // 绝对不能这样做！
}
```

### 检测方法

```java
// 方法一：Netty 内置的阻塞检测
// Netty 会检测 EventLoop 是否被长时间阻塞并打印警告日志

// 设置阻塞告警阈值（默认 100ms）
// -Dio.netty.eventLoop.maxPendingTasks=16
// 日志中出现：
// WARN  BlockingOperationException - An I/O thread was blocked for xxx ms
```

```bash
# 方法二：Thread Dump 检查 EventLoop 线程状态
jstack <pid> | grep -A 20 "nioEventLoopGroup"

# 如果 EventLoop 线程状态是 RUNNABLE 且栈顶是业务代码 → CPU 密集操作阻塞
# 如果是 TIMED_WAITING 且栈顶是 sleep/wait → 明确的阻塞
# 如果是 RUNNABLE 且栈顶是 JDBC/HTTP → I/O 阻塞

# 方法三：async-profiler wall 模式
./asprof -e wall -d 30 -t -I 'nioEventLoopGroup*' -f /tmp/netty-wall.html <pid>
# 查看 EventLoop 线程在做什么（包括阻塞时间）
```

### 正确做法

```java
// 方案一：将耗时操作交给业务线程池
EventExecutorGroup businessGroup = new DefaultEventExecutorGroup(16);

// 在 Pipeline 中指定 Handler 使用业务线程池
p.addLast(businessGroup, new BusinessHandler());

// 方案二：在 Handler 中手动提交到线程池
@Override
public void channelRead(ChannelHandlerContext ctx, Object msg) {
    businessExecutor.submit(() -> {
        User user = userDao.findById(msg.getUserId());
        // 注意：回写必须通过 ctx，Netty 会自动调度到 EventLoop 线程
        ctx.writeAndFlush(user);
    });
}

// 方案三：使用异步客户端
// 使用异步数据库驱动（R2DBC、Vert.x MySQL Client）
// 使用异步 HTTP 客户端（Netty 的 HTTP Client、AsyncHttpClient）
```

---

## 6. 水位线 WriteBufferWaterMark

### 问题：写缓冲区堆积

当发送速率高于网络传输速率时，数据会在 Netty 的写缓冲区（ChannelOutboundBuffer）中堆积，最终导致内存溢出。

```java
// 危险代码：不检查可写性就疯狂写入
for (int i = 0; i < 1000000; i++) {
    ctx.writeAndFlush(generateMessage(i));
    // 如果网络慢，100 万条消息全部堆积在写缓冲区中 → OOM
}
```

### WriteBufferWaterMark 机制

```java
// 设置水位线
ServerBootstrap b = new ServerBootstrap();
b.childOption(ChannelOption.WRITE_BUFFER_WATER_MARK,
    new WriteBufferWaterMark(32 * 1024, 64 * 1024));
// 低水位线：32KB - 写缓冲区降到此值以下，channel 变为 writable
// 高水位线：64KB - 写缓冲区超过此值，channel 变为 not writable
```

### 正确的写入方式

```java
// 方式一：检查 isWritable()
public void sendMessages(ChannelHandlerContext ctx, List<Message> messages) {
    for (Message msg : messages) {
        if (ctx.channel().isWritable()) {
            ctx.writeAndFlush(msg);
        } else {
            // 写缓冲区已满，等待或做背压处理
            log.warn("Channel not writable, buffered bytes: {}",
                ((NioSocketChannel) ctx.channel()).unsafe().outboundBuffer().totalPendingWriteBytes());
            // 可以选择：暂停发送、缓存到本地队列、通知上游降速
            break;
        }
    }
}

// 方式二：监听可写性变化事件
@Override
public void channelWritabilityChanged(ChannelHandlerContext ctx) {
    if (ctx.channel().isWritable()) {
        // 写缓冲区降到低水位线以下，可以恢复发送
        log.info("Channel writable again, resume sending");
        resumeSending(ctx);
    } else {
        // 写缓冲区超过高水位线，暂停发送
        log.warn("Channel not writable, pause sending");
        pauseSending();
    }
}
```

---

## 7. 常见性能问题总结

| 问题 | 现象 | 排查方法 | 修复 |
|------|------|---------|------|
| **EventLoop 阻塞** | 部分连接响应慢、超时 | Thread Dump 看 EventLoop 线程 | 耗时操作移到业务线程池 |
| **ByteBuf 泄漏** | 直接内存持续增长、OOM | ResourceLeakDetector=PARANOID | 确保 release() 或 ReferenceCountUtil.release() |
| **写缓冲区堆积** | 堆内存持续增长、OOM | 监控 channel.isWritable() | 设置 WriteBufferWaterMark + 背压控制 |
| **对象分配过多** | Young GC 频繁 | async-profiler alloc 模式 | 复用 ByteBuf、对象池 |
| **ChannelFuture 未检查** | 消息静默丢失 | 添加 listener 记录失败 | addListener 检查 isSuccess |
| **Pipeline Handler 顺序错误** | 消息解析异常、类型转换错误 | LoggingHandler 插入观察 | 调整 Handler 顺序 |
| **连接数过多** | fd 耗尽、EventLoop 响应慢 | `ss -s` 统计连接数 | 限制最大连接数、优化连接复用 |

### Netty 性能调优 checklist

```bash
# 1. 系统层面
ulimit -n 65535                    # 提高文件描述符限制
sysctl -w net.core.somaxconn=65535 # 提高 TCP 连接队列

# 2. Netty 参数
-Dio.netty.leakDetection.level=SIMPLE       # 生产环境的泄漏检测
-Dio.netty.recycler.maxCapacityPerThread=4096  # 对象池大小
-Dio.netty.allocator.type=pooled             # 使用池化分配器（默认）

# 3. Channel 配置
b.childOption(ChannelOption.TCP_NODELAY, true);        // 禁用 Nagle 算法（低延迟）
b.childOption(ChannelOption.SO_KEEPALIVE, true);       // TCP 保活
b.childOption(ChannelOption.ALLOCATOR, PooledByteBufAllocator.DEFAULT);  // 池化分配器
```

---

## 实践建议

1. **永远不要在 EventLoop 中做阻塞操作** —— 这是 Netty 性能问题的首要原因
2. **开发测试阶段使用 PARANOID 级别的泄漏检测** —— 在问题进入生产之前发现它
3. **所有 writeAndFlush 都应该添加 listener** —— 静默的写失败比异常更难排查
4. **监控写缓冲区大小** —— 写堆积是常见的内存溢出原因

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| 线程模型 | Boss(accept) + Worker(I/O) + Business(业务逻辑) 三级线程模型 |
| Pipeline | LoggingHandler 观察消息流转，注意 Handler 顺序和消息传递 |
| ChannelFuture | writeAndFlush 必须加 listener 检查结果 |
| ByteBuf 泄漏 | ResourceLeakDetector 四级检测，遵循"谁最后使用谁释放" |
| EventLoop 阻塞 | 最常见问题，通过 Thread Dump 和 wall-clock profiling 检测 |
| WriteBufferWaterMark | 防止写缓冲区 OOM，用 isWritable() 做背压控制 |

---

## 8. EventLoop pending 任务监控

Thread Dump 和 wall-clock profiling 能定性地发现 EventLoop 被阻塞，但无法持续量化。`SingleThreadEventExecutor.pendingTasks()` 返回当前排队等待执行的任务数，可以作为实时指标接入监控：

```java
// 每个 EventLoop 是单线程，绝不能在 handler 里阻塞；监控 pending 任务堆积：
for (EventExecutor e : group) {
    if (e instanceof SingleThreadEventExecutor ste) {
        meterRegistry.gauge("netty.eventloop.pending.tasks", ste, SingleThreadEventExecutor::pendingTasks);  // meterRegistry 由 Spring 注入
    }
}
```

**告警含义**：`pendingTasks()` 持续增长 = EventLoop 被某个慢/阻塞 handler 拖住。所有绑定到该 EventLoop 的 Channel 都会受影响，表现为连接响应延迟集体升高。这对应 [并发资源饱和 capstone §6](../03-observability/07-concurrent-resource-saturation.md) 的「事件循环被阻塞」分支——修复路径：把耗时操作移交给独立业务线程池（见本文第 5 节）。

---

## 9. 实战案例：高峰期单条长连接偶发发送超时

### 9.1 现场与结论边界

某自研 Netty RPC 客户端与服务端之间维护 10 条长 TCP 连接。请求量升高后，每分钟出现数次发送超时，同一时刻通常只有一条连接异常。已知：

- GC 已排除。
- 发送端抓包没有找到对应请求。
- 业务代码确认异步调用过 `flush()`，但没有保存 write promise 的最终结果。

这些证据**不足以断言根因**。`flush()` 被调用只说明发起过刷新动作，不等于 EventLoop 已执行、不等于数据已写入 socket，更不等于对端已 ACK。发送端抓不到请求也只能把怀疑范围前移，仍需先排除抓包所在 network namespace、网卡、过滤条件，以及 TCP 拆包/合包造成的识别误差。

此案例的目标不是猜出历史事故，而是建立一套下次能拿到闭环证据的排查方法。

### 9.2 按边界拆开“发送”

```text
RPC submit
  → 连接池选中某条 Channel / 等待槽位
  → EventLoop task queue
  → outbound Pipeline / encoder
  → ChannelOutboundBuffer
  → SocketChannel.write
  → kernel TCP Send-Q
  → qdisc / NIC
  → 网络
  → 对端 read / RPC handler
```

笼统的 `send timeout` 无法说明卡在哪层。至少拆成四类：

1. `channel_acquire_timeout`：等待可用连接或 per-channel in-flight 槽位。
2. `eventloop_queue_timeout`：任务已提交，但 EventLoop 尚未执行。
3. `write_timeout`：outbound write/flush 已执行，但 write promise 未完成。
4. `response_timeout`：write 已成功，等待响应超时。

### 9.3 最小可观测闭环

#### 每个请求保留阶段时间线

耗时统一用 `System.nanoTime()` 计算；墙上时间只用于跨进程日志关联。

```text
t0 rpc_submit
t1 eventloop_enter
t2 transport_write       # 编码完成，进入 transport 前
t3 transport_flush
t4 write_future_done
t5 response_received | timeout
```

必须监听本次 write 返回的原始 `ChannelFuture`，不能只记录“调用过 flush”：

```java
long submitNanos = System.nanoTime();
ChannelFuture future = channel.writeAndFlush(frame);

future.addListener(f -> recordWriteResult(
    requestId,
    channel.id().asShortText(),
    System.nanoTime() - submitNanos,
    f.isSuccess(),
    f.isCancelled(),
    f.cause()
));
```

在 promise 由标准 Netty transport 正确完成的前提下，future `success` 表示该 write 已离开 `ChannelOutboundBuffer` 并交给 kernel socket buffer；它不表示 TCP ACK、对端收到或业务处理完成。自研 outbound handler 还要审计是否错误地提前完成、替换或吞掉 promise。基础用法见本文第 3 节。

#### timeout 时输出一条结构化快照

不要在 EventLoop 为每个阶段同步写磁盘。阶段数据先保存在请求上下文和有界环形缓冲区；仅对 slow/failure/timeout 全量输出。快照至少包含：

- 请求：`requestId`、frame bytes、deadline、当前 timeout 类型、各阶段时间与分段耗时。
- 连接：固定 `channelSlot`（0–9）、`channelId`、connection generation、local/remote IP 和 port、per-channel sequence。
- 负载：该 Channel 的 in-flight 数、最老请求 age、连接选择前的等待队列深度。
- 状态：`isOpen()`、`isActive()`、`isWritable()`、`bytesBeforeWritable()`、`bytesBeforeUnwritable()`。
- 写结果：future 的 `pending/success/failure/cancelled`、`cause`；失败时保留 exception class 和 stack trace。
- EventLoop：线程名/编号、`pendingTasks()`、最近一次 loop lag。
- 定时器：deadline 预期触发时间、实际触发时间、timer 所属 executor；防止把 timer 自身延迟误判为网络慢。

`pending_write_bytes` 优先由自建 outbound probe 维护。直接读取 `channel.unsafe().outboundBuffer()` 属于 Netty internal API；若必须使用，应固定 Netty 版本并只在对应 EventLoop 上访问。

#### 持续记录 Channel 与 EventLoop 饱和度

```text
rpc.client.send.stage.duration{stage}
rpc.client.timeout.total{stage,cause}
rpc.client.channel.inflight{peer,slot}
rpc.client.channel.oldest.inflight{peer,slot}
netty.channel.writable{peer,slot}
netty.channel.pending.write.bytes{peer,slot}
netty.eventloop.pending.tasks{loop}
netty.eventloop.lag{loop}
```

- 在 `channelWritabilityChanged` 记录 writable 前后状态、pending bytes、水位线、不可写持续时间。
- 在 `exceptionCaught`、`channelInactive`、`closeFuture` 和 write failure 记录 Channel 身份及未完成请求数。
- 从独立 scheduler 每 100ms 向每个 EventLoop enqueue sentinel；`executeNanos - enqueueNanos` 就是 queue lag。持续增长时再限频抓 thread dump/JFR。
- 指标 label 只使用 `peer`、稳定的 `slot`、`loop`、`stage`、有限枚举 `cause`。`requestId`、`channelId` 只进入日志，避免高基数。

#### 保存每条 TCP 的短期历史

只有 10 条连接时，可以每秒采样一次、保留最近 30–60 秒，timeout 时随快照输出：

- `Send-Q` / `wmem_queued` / `notsent`
- `unacked` / `retrans`
- `rtt` / `rto` / `cwnd`
- 启动时的 `SO_SNDBUF`、`TCP_NODELAY`

native epoll 可读取 `EpollSocketChannel.tcpInfo()`；其他 transport 可按快照中的 local port 用 `ss -tinm` 对应 socket。字段语义见 [`metrics-decoder/04-network.md`](../../metrics-decoder/04-network.md)，单连接重传分析见 [`08-network-io/03-packet-loss-latency.md`](../08-network-io/03-packet-loss-latency.md)。

### 9.4 用证据定位，再选择修复

| 证据签名 | 故障边界 | 确认后的修复 |
|---|---|---|
| `t1-t0` 高，EventLoop lag / `pendingTasks` 同时升高；共享该 EventLoop 的其他 Channel 也变慢 | EventLoop 排队或阻塞 | 阻塞 I/O、长计算、锁等待移出 EventLoop；给业务线程池设置有界队列与拒绝策略；不要靠增加连接掩盖阻塞 |
| 有 `t1`，没有 `t2` | encoder/outbound handler 或其自定义 executor | 查异常和慢 handler；确保 handler 调用 `ctx.write(msg, promise)` 并正确传递 promise |
| 有 `t2`，没有 `t3` | flush 未继续传播 | 查批量 flush 逻辑和 outbound handler；确保调用 `ctx.flush()`，并用 per-channel `writeSeq/flushSeq` 关联批次 |
| 有 `t3`，future 长期 pending，pending bytes 上升且 `isWritable=false` | ChannelOutboundBuffer / socket backpressure | 对单 Channel 设置有界 pending bytes/in-flight；连接选择时跳过不可写 Channel；在 `channelWritabilityChanged` 恢复；不要先盲目调高水位线 |
| future success，但 `Send-Q`/notsent 持续高 | 数据已交给 kernel，但 TCP 尚未排空 | 查对端是否停止读取、receive window、拥塞窗口；小包延迟经证据确认后再评估 `TCP_NODELAY`，不要先扩大 buffer |
| `unacked`/`retrans` 增长 | 数据曾经发出，但未及时 ACK | 查两端抓包、丢包、MTU、路由、主机/NIC drop；此时“发送端完全没发包”的判断需要重新验证 |
| future failure | Netty / socket 明确失败 | 直接按 `cause` 处理 closed channel、reset、编码异常等；只看 `exceptionCaught` 不够，outbound 失败可能只落在 promise |
| future success，随后 response timeout | 服务端处理、返回网络或客户端 read path | 将调查方向移出 send path，沿 response 方向继续分段计时 |
| 只有某个 slot 的 in-flight、oldest age 或 pending bytes 明显高于其他 9 条 | 负载分配倾斜或 head-of-line blocking | 改为 writable + least-inflight/least-pending 选路；限制单连接并发；若协议一问一答，避免慢请求独占整条连接 |

这里的 9 条健康连接是天然对照组。事故时同时比较 10 条连接的 EventLoop 映射、in-flight、pending bytes 和 TCP_INFO，比只看异常连接更快：

- 同一 EventLoop 上多条连接一起慢，更像 EventLoop 问题。
- 只有一个 Channel 异常，更像 per-Channel 队列、socket 或对端单连接读停顿。
- 每次都是同一个固定 slot 异常，更要检查选路、连接代次和服务端连接级状态。

### 9.5 抓包校验

```bash
nsenter -t "$PID" -n tcpdump -i any -nn -s 0 -B 32768 \
  'tcp and host <B-IP> and port <PORT>'
```

- 必须在服务实际 network namespace 内抓，并保存 local port 对应 Channel。
- 用 TCP 四元组和 sequence number 判断，不要只搜索完整 request payload；TCP 可能拆包、合包。
- 检查 tcpdump 退出统计中的 `packets dropped by kernel`。
- 必要时同时抓 `any` 与实际 egress/bond/veth。TSO/GSO 会改变包的外观和大小，但通常不会让正确抓包点完全看不到 outbound skb。

容器抓包与 Wireshark 模式识别见 [`08-network-io/01-tcpdump-wireshark.md`](../08-network-io/01-tcpdump-wireshark.md)。若应用快照仍无法区分“没调用 kernel”还是“kernel 没下发”，再短时使用 eBPF 按 PID/cgroup + 四元组跟踪 `tcp_sendmsg`、`tcp_write_xmit`、`net_dev_queue`、`tcp_retransmit_skb`，不要一开始就上最重的工具。

### 9.6 值班排查顺序

1. 先确认 timeout 分类、`requestId`、`channelSlot/channelId`、connection generation、local port。
2. 看 `t0..t5`，找第一个缺失或异常变长的阶段。
3. 比较异常 Channel 与其余 9 条健康连接；同时检查共享 EventLoop 的其他 Channel。
4. 看 writable、pending bytes、in-flight、EventLoop lag/queue，再看同一 socket 的 `Send-Q`/TCP_INFO。
5. 校验抓包点和 request 识别方法；不要因为“没看到 payload”直接判定网络或应用无责。
6. 一次只提出一个根因假设，用最小实验验证后再修复。

### 9.7 生产环境无值守保留

本节定义 Netty 专属阶段、Channel 和 EventLoop 证据。随机 timeout 的长期运行方式——Tail Sampling、eBPF 事件、Docker/Kubernetes 网络层、pcap ring 自动 pin、quota/TTL 和 incident bundle——统一见 [`08-network-io/06-intermittent-timeout-forensics.md`](../08-network-io/06-intermittent-timeout-forensics.md)，避免在业务 EventLoop 同步写大量诊断日志。

### 9.8 上线前故障注入

在测试环境制造四种可控故障，确认日志能产生不同签名：

1. EventLoop handler 人为阻塞：应看到 `t1-t0`、loop lag、`pendingTasks` 上升。
2. 对端暂停读取：应看到 pending bytes、不可写持续时间、`Send-Q` 上升。
3. outbound handler 抛异常或故意不转发：应看到阶段缺失或 future failure。
4. `tc netem` 注入丢包/延迟：应在抓包和 `retrans/rtt` 看到网络层证据，而不是 EventLoop queue lag。

只有这些签名在测试环境被验证过，线上 timeout 快照才真正具备判因能力。
