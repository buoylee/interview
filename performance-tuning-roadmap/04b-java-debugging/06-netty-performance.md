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
