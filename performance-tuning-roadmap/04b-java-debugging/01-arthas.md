# Arthas 实战

## 概述

Arthas 是阿里巴巴开源的 Java 诊断工具，能在不修改代码、不重启应用的情况下对运行中的 JVM 进行实时诊断。它解决了传统诊断工具需要提前埋点或重启的痛点，是线上问题排查的瑞士军刀。

---

## 1. 安装与连接

### 安装

```bash
# 方式一：一键安装（推荐）
curl -O https://arthas.aliyun.com/arthas-boot.jar

# 方式二：全量安装
curl -O https://arthas.aliyun.com/math-game.jar  # 示例应用
java -jar arthas-boot.jar

# 方式三：使用 as.sh（Linux）
curl -L https://arthas.aliyun.com/install.sh | sh
```

### 连接到目标进程

```bash
# 启动 Arthas，会自动列出 Java 进程
java -jar arthas-boot.jar

# 输出：
# [INFO] arthas-boot version: 3.7.2
# [INFO] Found existing java process, please choose one and input the serial number:
# * [1]: 12345 com.example.Application
#   [2]: 23456 org.apache.kafka.Kafka
# 输入序号 1，回车连接

# 直接指定 PID
java -jar arthas-boot.jar 12345

# 连接远程 Arthas Tunnel
java -jar arthas-boot.jar --tunnel-server 'ws://tunnel.example.com/ws' --agent-id app01
```

---

## 2. 核心命令详解

### dashboard - 实时面板

```bash
[arthas@12345]$ dashboard

# 输出实时刷新的面板：
# ┌─────────────────────────────────────────────────────────────┐
# │ Threads: 156    Daemon: 142    Peak: 162    Started: 1234   │
# │ Memory           used     total    max      usage           │
# │ heap             1.2G     2.0G     4.0G     30.0%           │
# │ ps_eden_space    450M     800M     800M     56.2%           │
# │ ps_old_gen       700M     1.2G     2.8G     25.0%           │
# │ nonheap          120M     135M     -1       88.9%           │
# │ metaspace        95M      105M     256M     37.1%           │
# │                                                             │
# │ GC                count    time(ms)                         │
# │ ps_scavenge       234      4567                             │
# │ ps_marksweep      3        890                              │
# │                                                             │
# │ Runtime: OpenJDK 17.0.9   OS: Linux 5.15.0   CPU: 4 cores │
# └─────────────────────────────────────────────────────────────┘

# 按 q 或 Ctrl+C 退出
```

**用途**：快速了解应用整体状态 —— 堆使用率、GC 次数和耗时、线程数、CPU 使用。

### thread - 线程排查

```bash
# 查看所有线程信息
[arthas@12345]$ thread

# 查看 CPU 使用最高的 5 个线程（排查 CPU 飙高问题）
[arthas@12345]$ thread -n 5

# 输出：
# "http-nio-8080-exec-23" Id=156 cpuUsage=45.3% deltaTime=453ms time=12345ms RUNNABLE
#     at com.example.service.DataProcessor.heavyCompute(DataProcessor.java:89)
#     at com.example.controller.ApiController.process(ApiController.java:42)
#     ...

# 检测死锁
[arthas@12345]$ thread -b

# 输出（如果有死锁）：
# "Thread-1" Id=23 BLOCKED on java.util.concurrent.locks.ReentrantLock
#     owned by "Thread-2" Id=24
#     at com.example.service.OrderService.updateStock(OrderService.java:67)
# "Thread-2" Id=24 BLOCKED on java.util.concurrent.locks.ReentrantLock
#     owned by "Thread-1" Id=23
#     at com.example.service.StockService.updateOrder(StockService.java:45)

# 查看指定线程的栈
[arthas@12345]$ thread 156

# 查看状态为 BLOCKED 的线程
[arthas@12345]$ thread --state BLOCKED
```

### watch - 观察方法入参出参异常

```bash
# 观察方法返回值
[arthas@12345]$ watch com.example.service.OrderService createOrder returnObj

# 观察入参和返回值
[arthas@12345]$ watch com.example.service.OrderService createOrder '{params, returnObj}'

# 观察异常信息
[arthas@12345]$ watch com.example.service.OrderService createOrder '{params, throwExp}' -e

# 使用 OGNL 表达式过滤（只看金额 > 1000 的订单）
[arthas@12345]$ watch com.example.service.OrderService createOrder '{params[0].amount, returnObj}' 'params[0].amount > 1000'

# 输出示例：
# ts=2024-01-15 10:23:45; [cost=23.456ms] result=@ArrayList[
#     @BigDecimal[1500.00],
#     @OrderResult[OrderResult{orderId=12345, status=SUCCESS}],
# ]

# 查看方法调用的前后 5 次
[arthas@12345]$ watch com.example.service.OrderService createOrder returnObj -n 5

# 观察方法执行时间超过 100ms 的调用
[arthas@12345]$ watch com.example.service.OrderService createOrder '{params, returnObj}' '#cost > 100'
```

### trace - 方法调用链耗时分析

```bash
# 追踪方法内部调用链的耗时
[arthas@12345]$ trace com.example.service.OrderService createOrder

# 输出（树形展示每个子调用的耗时）：
# `---ts=2024-01-15 10:23:45;thread_name=http-nio-8080-exec-1;
#     `---[234.567ms] com.example.service.OrderService:createOrder()
#         +---[1.234ms] com.example.service.OrderService:validateOrder()
#         +---[180.123ms] com.example.dao.OrderDao:insert()          ← 瓶颈！
#         +---[45.678ms] com.example.service.StockService:deductStock()
#         `---[5.432ms] com.example.mq.OrderMessageSender:send()

# 过滤耗时超过 100ms 的调用
[arthas@12345]$ trace com.example.service.OrderService createOrder '#cost > 100'

# 追踪多层调用（默认只追踪一层，设置层数）
[arthas@12345]$ trace com.example.service.OrderService createOrder --skipJDKMethod false -j 2
```

**这是最常用的命令之一**。当某个接口响应慢时，用 trace 可以快速定位到底是哪一步耗时最长。

### stack - 方法被谁调用

```bash
# 查看某个方法的调用栈（方法被谁调用的）
[arthas@12345]$ stack com.example.dao.OrderDao insert

# 输出：
# ts=2024-01-15 10:23:45;thread_name=http-nio-8080-exec-1;
# @com.example.dao.OrderDao.insert()
#     at com.example.service.OrderService.createOrder(OrderService.java:45)
#     at com.example.controller.OrderController.create(OrderController.java:23)
#     at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
#     ...
```

**用途**：当你不知道某个方法是被谁调用的（比如一个 DAO 方法被多处调用），用 stack 直接看调用链。

### jad - 在线反编译

```bash
# 反编译某个类
[arthas@12345]$ jad com.example.service.OrderService

# 只反编译某个方法
[arthas@12345]$ jad com.example.service.OrderService createOrder

# 输出源码（包含行号），确认线上运行的代码是否是预期版本
# ClassLoader: org.springframework.boot.loader.LaunchedURLClassLoader
# Location: /app/lib/order-service-1.0.jar
```

**用途**：确认线上代码版本（是否发布了正确的代码）、理解三方库的内部实现。

### mc + redefine - 热更新代码

```bash
# Step 1：反编译获取源码
[arthas@12345]$ jad --source-only com.example.service.OrderService > /tmp/OrderService.java

# Step 2：编辑源码（修复 bug）
# 在 /tmp/OrderService.java 中修改代码

# Step 3：编译
[arthas@12345]$ mc -c <classLoaderHash> /tmp/OrderService.java -d /tmp/output

# Step 4：热更新
[arthas@12345]$ redefine /tmp/output/com/example/service/OrderService.class
```

### ognl - 执行表达式

```bash
# 调用静态方法
[arthas@12345]$ ognl '@java.lang.System@getProperty("java.version")'

# 查看 Spring 容器中的 Bean
[arthas@12345]$ ognl '#context=@com.example.util.SpringContextHolder@getApplicationContext(), #context.getBean("orderService").toString()'

# 查看某个对象的字段值
[arthas@12345]$ ognl '@com.example.config.AppConfig@MAX_RETRY_COUNT'

# 修改日志级别（临时调整，不需要重启）
[arthas@12345]$ ognl '#logger=@org.slf4j.LoggerFactory@getLogger("com.example.service"), @ch.qos.logback.classic.Level@DEBUG, #logger.setLevel(@ch.qos.logback.classic.Level@DEBUG)'
```

---

## 3. 其他实用命令

```bash
# 查看类加载信息
[arthas@12345]$ sc com.example.service.*        # 搜索已加载的类
[arthas@12345]$ sc -d com.example.service.OrderService  # 详细信息（ClassLoader、jar 路径）

# 搜索方法
[arthas@12345]$ sm com.example.service.OrderService *   # 列出所有方法

# JVM 信息
[arthas@12345]$ jvm                              # JVM 系统属性、内存、GC 信息

# 监控方法调用统计
[arthas@12345]$ monitor com.example.service.OrderService createOrder -c 5
# 每 5 秒输出一次统计：
# timestamp     class                          method        total  success  fail  avg-rt(ms)  fail-rate
# 2024-01-15    c.e.service.OrderService       createOrder   125    120      5     45.67       4.00%

# 生成堆 dump
[arthas@12345]$ heapdump /tmp/heap.hprof

# 查看 logger 配置
[arthas@12345]$ logger                           # 列出所有 logger 和级别
[arthas@12345]$ logger --name com.example --level debug  # 动态修改日志级别

# 退出 Arthas（不影响目标进程）
[arthas@12345]$ quit    # 退出当前会话
[arthas@12345]$ stop    # 完全卸载 Arthas
```

---

## 4. 使用边界与风险

Arthas 功能强大但也有风险，必须了解边界：

### 生产环境注意事项

| 操作 | 风险级别 | 说明 |
|------|---------|------|
| `dashboard` / `thread` / `jvm` | **低** | 只读操作，可以随时使用 |
| `watch` / `trace` / `stack` | **中** | 会增加方法调用开销。条件表达式写错可能导致性能问题（比如没加 `-n` 限制次数） |
| `jad` / `sc` / `sm` | **低** | 只读操作 |
| `redefine` | **高** | 热更新代码，可能导致不可预期的行为。不要在生产环境随意使用 |
| `ognl`（修改类操作） | **高** | 可以修改任意对象状态，操作不当可能破坏业务数据 |

### 最佳实践

```bash
# 1. 始终设置 -n 参数限制采集次数（避免持续影响性能）
watch com.example.service.OrderService createOrder returnObj -n 5

# 2. 使用条件表达式精确过滤，减少采集量
trace com.example.service.OrderService createOrder '#cost > 100'

# 3. 排查完毕后及时退出 Arthas
stop

# 4. 不要长时间运行 trace/watch（几分钟即可）
# 5. redefine 仅用于紧急 hotfix，修复后尽快走正常发布流程
# 6. 在生产环境使用前，先在预发布环境验证命令
```

---

## 5. 实战场景速查

| 场景 | 推荐命令 |
|------|---------|
| CPU 飙高，定位热点线程 | `thread -n 5` |
| 接口响应慢，定位耗时环节 | `trace <class> <method>` |
| 确认方法入参和返回值 | `watch <class> <method> '{params, returnObj}'` |
| 确认线上代码版本 | `jad <class>` |
| 排查死锁 | `thread -b` |
| 确认方法被谁调用 | `stack <class> <method>` |
| 动态调整日志级别 | `logger --name <package> --level debug` |
| 获取堆转储 | `heapdump /tmp/heap.hprof` |
| 查看方法调用统计 | `monitor <class> <method> -c 5` |

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| Arthas 定位 | 运行时 Java 诊断工具，无需修改代码和重启 |
| dashboard | 实时查看堆/GC/线程/CPU 概况 |
| thread | CPU 热点线程（-n 5）、死锁检测（-b） |
| watch | 观察方法入参出参，OGNL 表达式过滤 |
| trace | 方法调用链耗时分析，定位慢调用 |
| jad | 在线反编译确认代码版本 |
| redefine | 热更新代码，高风险操作 |
| 风险控制 | 限制采集次数、条件过滤、及时退出 |
