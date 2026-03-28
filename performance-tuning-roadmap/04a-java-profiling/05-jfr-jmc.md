# JFR 与 JMC

## 概述

Java Flight Recorder（JFR）是 JDK 内置的零配置、低开销的持续诊断框架。配合 JDK Mission Control（JMC）的可视化分析，它们构成了 Java 性能分析的"黑匣子"。从 JDK 11 开始 JFR 完全免费开源，是生产环境持续监控的首选工具。

---

## 1. JFR 是什么

JFR 是 HotSpot JVM 内嵌的事件记录引擎：

- **零配置**：不需要安装额外 Agent，JDK 自带
- **低开销**：默认配置下开销 < 1%，可以长期开启
- **全面覆盖**：JVM 内部事件（GC、JIT、类加载、线程）、OS 事件（CPU、内存、I/O）、Java 应用事件（方法采样、对象分配、异常、锁）
- **二进制格式**：高效紧凑的 .jfr 文件，可用 JMC 或编程方式解析

```bash
# JFR 在各 JDK 版本中的状态
# JDK 8u262+：免费提供（之前是商业特性）
# JDK 11+：完全开源免费
# JDK 17+：持续增强，新增更多事件类型
```

---

## 2. JFR 事件体系

JFR 记录的所有数据都以"事件"（Event）为单位，按类别组织：

### 事件类别

| 类别 | 示例事件 | 用途 |
|------|---------|------|
| **Java Application** | Method Profiling、Exception、Thread Sleep | 应用层面的性能分析 |
| **JVM Runtime** | Class Loading、Compilation、Module | JVM 内部运行状况 |
| **GC** | GC Pause、GC Configuration、Object Allocation | 垃圾收集分析 |
| **OS** | CPU Load、Physical Memory、Network | 操作系统资源使用 |
| **I/O** | File Read/Write、Socket Read/Write | I/O 性能分析 |

### 事件类型

| 类型 | 含义 | 示例 |
|------|------|------|
| **Instant Event** | 瞬时事件，记录某个时刻发生的事情 | Exception thrown、Thread start |
| **Duration Event** | 持续事件，有开始和结束时间 | GC Pause、Monitor Wait、File Read |
| **Requestable Event** | 定期采样的事件 | CPU Load、Heap Summary、Thread Dump |

---

## 3. 启动方式

### 方式一：JVM 启动参数

```bash
# 启动时开始录制
java -XX:StartFlightRecording=duration=60s,filename=/tmp/recording.jfr \
     -jar app.jar

# 持续录制（环形缓冲区，保留最近 1 小时）
java -XX:StartFlightRecording=disk=true,maxage=1h,maxsize=500m,dumponexit=true,filename=/tmp/recording.jfr \
     -jar app.jar

# 常用参数
# duration=60s      录制持续时间（不设则持续录制直到停止）
# maxage=1h         环形缓冲区保留的最大时长
# maxsize=500m      环形缓冲区最大大小
# dumponexit=true   JVM 退出时导出录制
# filename=xxx      输出文件路径
# settings=profile  使用 profile 配置文件（采集更多信息，开销稍大）
```

### 方式二：jcmd 动态控制

```bash
# 查看正在运行的录制
jcmd <pid> JFR.check

# 启动录制
jcmd <pid> JFR.start name=myrecording duration=60s filename=/tmp/recording.jfr

# 使用 profile 配置（更详细的采集）
jcmd <pid> JFR.start name=myrecording settings=profile duration=60s filename=/tmp/recording.jfr

# 导出正在进行的录制
jcmd <pid> JFR.dump name=myrecording filename=/tmp/dump.jfr

# 停止录制
jcmd <pid> JFR.stop name=myrecording filename=/tmp/final.jfr

# 查看所有可用事件类型
jcmd <pid> JFR.view events
```

### 方式三：JMC 远程连接

通过 JMX 连接远程 JVM，在 JMC 的 GUI 中启动和管理录制。需要目标 JVM 开启 JMX：

```bash
java -Dcom.sun.management.jmxremote \
     -Dcom.sun.management.jmxremote.port=9999 \
     -Dcom.sun.management.jmxremote.ssl=false \
     -Dcom.sun.management.jmxremote.authenticate=false \
     -jar app.jar
```

**注意**：生产环境应配置 JMX 认证和 SSL，上述无认证配置仅用于测试。

---

## 4. 配置文件

JFR 提供两种内置配置文件：

### default.jfc vs profile.jfc

| 配置 | 开销 | 特点 | 适用场景 |
|------|------|------|---------|
| **default** | < 1% | 基础事件，较高的阈值过滤 | 生产环境持续监控 |
| **profile** | < 2% | 更多事件类型，更低的阈值（方法采样频率更高，记录更多对象分配） | 定向排查问题 |

### 自定义配置

配置文件是 XML 格式（.jfc），可以精细控制每种事件的采集策略：

```xml
<!-- custom.jfc -->
<?xml version="1.0" encoding="UTF-8"?>
<configuration version="2.0">
  <event name="jdk.ExecutionSample">
    <setting name="enabled">true</setting>
    <setting name="period">10 ms</setting>  <!-- 方法采样间隔 -->
  </event>

  <event name="jdk.ObjectAllocationInNewTLAB">
    <setting name="enabled">true</setting>
    <setting name="stackTrace">true</setting>
  </event>

  <event name="jdk.FileRead">
    <setting name="enabled">true</setting>
    <setting name="stackTrace">true</setting>
    <setting name="threshold">1 ms</setting>  <!-- 只记录超过 1ms 的文件读取 -->
  </event>

  <event name="jdk.JavaMonitorWait">
    <setting name="enabled">true</setting>
    <setting name="stackTrace">true</setting>
    <setting name="threshold">10 ms</setting>  <!-- 只记录等待超过 10ms 的锁 -->
  </event>
</configuration>
```

```bash
# 使用自定义配置
jcmd <pid> JFR.start settings=/path/to/custom.jfc duration=60s filename=/tmp/recording.jfr
```

**修改配置的推荐方式**：在 JMC 中打开 `Template Manager`（Window → Flight Recording Template Manager），可视化编辑每个事件的阈值和开关，然后导出为 .jfc 文件。

---

## 5. JMC 分析界面

JMC（JDK Mission Control）是分析 JFR 文件的标准工具。

### 安装

```bash
# JDK 自带版本（JDK 8-10 内置，JDK 11+ 需单独下载）
# 从 https://jdk.java.net/jmc/ 下载
# 或使用 SDKMAN
sdk install jmc
```

### 核心分析视图

#### Automated Analysis（自动分析）

JMC 打开 JFR 文件后首先展示自动分析结果，按严重程度标注问题：

```
[!] HIGH: Hot Methods
    → com.example.service.DataProcessor.transform() 占 CPU 采样的 45%

[!] MEDIUM: Garbage Collection
    → GC 暂停总时间占运行时间的 8.5%

[i] LOW: Thrown Exceptions
    → NumberFormatException 被抛出 12,345 次
```

#### Method Profiling（方法分析）

- **Hot Methods**：CPU 采样中最频繁出现在栈顶的方法（自身消耗 CPU 最多）
- **Call Tree**：完整调用树，可展开查看每个方法的采样占比
- **火焰图视图**（JMC 8+）：与 async-profiler 的火焰图类似

#### Memory（内存分析）

- **TLAB 分配**：在 TLAB 中分配的对象统计（按类型和调用栈）
- **Outside TLAB**：TLAB 外分配的大对象
- **Heap Summary**：堆使用量随时间的变化曲线
- **GC 分析**：各次 GC 的停顿时间、回收量、触发原因

#### Thread（线程分析）

- **线程活动时间线**：每个线程的状态随时间的变化（Running/Sleeping/Waiting/Blocked）
- **锁等待**：哪些线程在等哪些锁，持锁线程是谁
- **线程转储**：定期采集的线程快照

#### I/O（I/O 分析）

- **File I/O**：文件读写的耗时和大小
- **Socket I/O**：网络读写的耗时、远端地址、数据量

#### GC（GC 分析）

- **GC 暂停时间分布**：直方图 + 时间线
- **GC 配置**：当前使用的 GC 算法和参数
- **堆占用趋势**：GC 后堆使用量是否持续增长（泄漏信号）

---

## 6. 持续监控方案

在生产环境中，推荐以"永远开启"的方式运行 JFR：

### 启动参数配置

```bash
# 生产环境推荐配置
java -XX:StartFlightRecording=disk=true,maxage=6h,maxsize=1g,dumponexit=true,filename=/var/log/app/jfr/recording.jfr \
     -jar app.jar
```

### 定时导出脚本

```bash
#!/bin/bash
# cron_jfr_dump.sh - 每小时导出一次 JFR 录制
# crontab: 0 * * * * /opt/scripts/cron_jfr_dump.sh

PID=$(pgrep -f "app.jar")
DUMP_DIR="/var/log/app/jfr/dumps"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

mkdir -p "$DUMP_DIR"

# 导出当前录制
jcmd "$PID" JFR.dump filename="${DUMP_DIR}/recording_${TIMESTAMP}.jfr"

# 清理 7 天前的 dump 文件
find "$DUMP_DIR" -name "*.jfr" -mtime +7 -delete

echo "[$(date)] JFR dump completed: recording_${TIMESTAMP}.jfr"
```

### 告警集成

```bash
# 使用 jfr 命令行工具（JDK 17+）分析 JFR 文件
jfr summary recording.jfr

# 打印特定事件
jfr print --events jdk.GCPhasePause recording.jfr

# 查看 GC 暂停
jfr view gc-pauses recording.jfr

# 查看热点方法
jfr view hot-methods recording.jfr
```

---

## 7. 自定义 JFR 事件

JDK 提供 API 让你在应用代码中定义自己的 JFR 事件，用于追踪业务级别的性能指标。

```java
import jdk.jfr.*;

@Name("com.example.OrderProcessed")
@Label("Order Processed")
@Category({"Business", "Order"})
@Description("An order has been processed")
@StackTrace(false)  // 不需要记录栈追踪
public class OrderProcessedEvent extends Event {

    @Label("Order ID")
    long orderId;

    @Label("Processing Time (ms)")
    long processingTimeMs;

    @Label("Item Count")
    int itemCount;

    @Label("Total Amount")
    double totalAmount;
}
```

### 在业务代码中使用

```java
public OrderResult processOrder(Order order) {
    OrderProcessedEvent event = new OrderProcessedEvent();
    event.begin();  // 开始计时

    try {
        // 业务逻辑
        OrderResult result = doProcess(order);

        event.orderId = order.getId();
        event.processingTimeMs = event.duration().toMillis();
        event.itemCount = order.getItems().size();
        event.totalAmount = result.getTotalAmount();

        return result;
    } finally {
        event.end();
        event.commit();  // 提交事件到 JFR
        // 注意：如果事件被禁用（在 .jfc 配置中），commit() 不会有任何开销
    }
}
```

### 带阈值的事件

```java
@Name("com.example.SlowQuery")
@Label("Slow Database Query")
@Category({"Database"})
@Threshold("10 ms")  // 只记录超过 10ms 的事件
public class SlowQueryEvent extends Event {

    @Label("SQL")
    String sql;

    @Label("Execution Time (ms)")
    long executionTimeMs;

    @Label("Row Count")
    int rowCount;
}
```

### 注册和配置自定义事件

自定义事件在第一次 `commit()` 时自动注册。可以在 .jfc 配置文件中控制：

```xml
<event name="com.example.OrderProcessed">
  <setting name="enabled">true</setting>
  <setting name="threshold">0 ms</setting>  <!-- 记录所有事件 -->
  <setting name="stackTrace">false</setting>
</event>

<event name="com.example.SlowQuery">
  <setting name="enabled">true</setting>
  <setting name="threshold">10 ms</setting>
  <setting name="stackTrace">true</setting>  <!-- 记录慢查询的调用栈 -->
</event>
```

---

## JFR vs async-profiler 选择

| 维度 | JFR | async-profiler |
|------|-----|---------------|
| **安装** | JDK 内置，无需额外安装 | 需要下载部署 |
| **覆盖面** | 全面（GC、I/O、线程、锁、JIT...） | 专注于 CPU/Alloc/Lock/Wall |
| **开销** | default < 1%, profile < 2% | < 2% |
| **输出** | .jfr 文件（需 JMC 或工具解析） | 直接输出火焰图 HTML |
| **自定义事件** | 支持（代码埋点） | 不支持 |
| **持续监控** | 天然适合（环形缓冲区） | 按需采集 |
| **推荐用法** | 生产环境持续开启 | 定向排查热点问题 |

**实践建议**：两者不冲突，生产环境长期开启 JFR，遇到具体性能问题时用 async-profiler 采集火焰图做精准定位。

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| JFR | JDK 内置、低开销、全面覆盖、生产可用 |
| 启动方式 | 启动参数 / jcmd 动态 / JMC 远程 |
| 配置文件 | default（日常）vs profile（排查），支持自定义 .jfc |
| JMC 分析 | 自动分析 + Method/Memory/Thread/IO/GC 分视图 |
| 持续监控 | maxage + maxsize 环形缓冲 + 定时 dump |
| 自定义事件 | 继承 Event 类，业务级性能追踪 |
