# GC 日志与调优

## 概述

GC 日志是诊断 Java 内存问题的第一手数据。能不能读懂 GC 日志、能不能从日志中提取关键指标，直接决定了你排查内存问题的效率。本文覆盖 GC 日志配置、格式解读、工具分析以及实际调优案例。

---

## 1. 开启 GC 日志

### JDK 8

```bash
java -verbose:gc \
     -XX:+PrintGCDetails \
     -XX:+PrintGCDateStamps \
     -XX:+PrintGCTimeStamps \
     -XX:+PrintHeapAtGC \
     -XX:+PrintTenuringDistribution \
     -XX:+PrintGCApplicationStoppedTime \
     -Xloggc:/var/log/app/gc.log \
     -XX:+UseGCLogFileRotation \
     -XX:NumberOfGCLogFiles=10 \
     -XX:GCLogFileSize=50M \
     -jar app.jar
```

### JDK 11+（统一日志框架 Unified Logging）

```bash
java -Xlog:gc*,gc+age=trace,gc+heap=debug:file=/var/log/app/gc.log:time,uptime,level,tags:filecount=10,filesize=50m \
     -jar app.jar

# 参数格式说明：
# -Xlog:[what]:[output]:[decorators]:[output-options]
#
# what:       gc*              所有 gc 相关的日志
#             gc+age=trace     对象年龄分布（详细）
#             gc+heap=debug    GC 前后的堆信息
# output:     file=xxx         输出到文件
# decorators: time,uptime      时间戳格式
# options:    filecount,filesize 日志轮转
```

**重要提示**：生产环境必须开启 GC 日志。GC 日志的性能开销可以忽略不计（< 1%），但排查问题时没有 GC 日志将非常被动。

---

## 2. GC 日志格式解读

### JDK 8 G1 GC 日志示例

```
2024-01-15T10:23:45.123+0800: 1234.567: [GC pause (G1 Evacuation Pause) (young), 0.0234567 secs]
   [Parallel Time: 18.5 ms, GC Workers: 8]
      [GC Worker Start (ms): Min: 1234567.0, Avg: 1234567.1, Max: 1234567.2, Diff: 0.2]
      [Ext Root Scanning (ms): Min: 0.5, Avg: 1.2, Max: 2.1, Diff: 1.6]
      [Update RS (ms): Min: 0.3, Avg: 0.8, Max: 1.5, Diff: 1.2]
      [Scan RS (ms): Min: 0.1, Avg: 0.3, Max: 0.5, Diff: 0.4]
      [Code Root Scanning (ms): Min: 0.0, Avg: 0.1, Max: 0.2, Diff: 0.2]
      [Object Copy (ms): Min: 12.0, Avg: 14.5, Max: 16.1, Diff: 4.1]
      [Termination (ms): Min: 0.0, Avg: 0.1, Max: 0.3, Diff: 0.3]
   [Code Root Fixup: 0.3 ms]
   [Code Root Purge: 0.1 ms]
   [Clear CT: 0.2 ms]
   [Other: 4.2 ms]
      [Choose CSet: 0.0 ms]
      [Ref Proc: 2.5 ms]
      [Ref Enq: 0.1 ms]
      [Redirty Cards: 0.1 ms]
      [Humongous Register: 0.0 ms]
      [Humongous Reclaim: 0.0 ms]
      [Free CSet: 0.5 ms]
   [Eden: 1024.0M(1024.0M)->0.0B(960.0M) Survivors: 64.0M->128.0M Heap: 2048.0M(4096.0M)->1152.0M(4096.0M)]
 [Times: user=0.15 sys=0.01, real=0.02 secs]
```

### 关键字段解读

| 字段 | 含义 |
|------|------|
| `GC pause (G1 Evacuation Pause) (young)` | GC 类型：Young GC |
| `0.0234567 secs` | 本次 GC 总停顿时间 |
| `Parallel Time: 18.5 ms` | 并行阶段耗时（GC 线程工作的时间） |
| `Object Copy` | 复制存活对象的时间（通常是最耗时的） |
| `Ref Proc` | 处理软/弱/虚/幽灵引用的时间 |
| `Eden: 1024M->0B` | Eden 区从 1024MB 被清空 |
| `Survivors: 64M->128M` | Survivor 区从 64MB 增长到 128MB |
| `Heap: 2048M->1152M` | 堆总使用从 2048MB 降到 1152MB |
| `user=0.15 sys=0.01 real=0.02` | 用户态/内核态/实际墙钟时间 |

### JDK 17 统一日志格式

```
[2024-01-15T10:23:45.123+0800][1234.567s][info][gc] GC(42) Pause Young (Normal) (G1 Evacuation Pause) 2048M->1152M(4096M) 23.456ms
[2024-01-15T10:23:45.123+0800][1234.567s][info][gc,phases] GC(42)   Pre Evacuate Collection Set: 0.3ms
[2024-01-15T10:23:45.123+0800][1234.567s][info][gc,phases] GC(42)   Merge Heap Roots: 0.5ms
[2024-01-15T10:23:45.123+0800][1234.567s][info][gc,phases] GC(42)   Evacuate Collection Set: 18.5ms
[2024-01-15T10:23:45.123+0800][1234.567s][info][gc,phases] GC(42)   Post Evacuate Collection Set: 3.2ms
[2024-01-15T10:23:45.123+0800][1234.567s][info][gc,phases] GC(42)   Other: 1.0ms
```

---

## 3. 关键指标

分析 GC 日志时重点关注以下指标：

| 指标 | 健康范围 | 问题信号 |
|------|---------|---------|
| **GC 暂停时间** | Young GC < 50ms，Full GC < 1s | 单次 Young GC > 200ms 或出现 Full GC |
| **GC 频率** | Young GC：每几秒到几十秒一次 | Young GC 每秒多次（分配速率过高） |
| **GC 吞吐量** | > 95%（应用时间占比） | < 90% 说明 GC 占用了太多 CPU |
| **堆使用趋势** | GC 后堆使用量稳定 | GC 后堆使用量持续上升 = 内存泄漏 |
| **晋升速率** | 低且稳定 | 突然增高可能导致 Old Gen 快速填满 |

### 吞吐量计算

```
GC 吞吐量 = 1 - (GC 总耗时 / 应用运行总时间)

例如：运行 1 小时，GC 总耗时 60 秒
吞吐量 = 1 - 60/3600 = 98.3%  ✓ 健康
```

---

## 4. GCEasy 在线分析

[GCEasy](https://gceasy.io/) 是最常用的 GC 日志在线分析工具。

### 使用方法

1. 上传 GC 日志文件到 https://gceasy.io/
2. 自动识别 GC 算法和 JDK 版本
3. 生成可视化报告

### GCEasy 报告关键部分

- **GC Statistics**：停顿时间分布（P50/P90/P99/Max）
- **GC Duration**：每次 GC 的停顿时间走势图
- **Heap After GC**：GC 后堆使用量趋势（判断是否有内存泄漏）
- **GC Causes**：各种 GC 触发原因的统计
- **Object Stats**：对象分配速率、晋升速率
- **Recommendations**：调优建议

**其他分析工具**：
- **GCViewer**：开源桌面工具（`java -jar gcviewer.jar gc.log`）
- **JClarity Censum**：商业工具，分析更深入
- **Elasticsearch + Kibana**：将 GC 日志导入做长期趋势分析

---

## 5. 常见 GC 参数大全

### 堆大小参数

```bash
-Xms4g                             # 初始堆大小（建议与 -Xmx 相同，避免动态扩展）
-Xmx4g                             # 最大堆大小
-Xmn1g                             # Young Generation 大小（G1 中不建议设置）
-XX:NewRatio=2                     # Old/Young 比例（默认 2，即 Old:Young = 2:1）
-XX:SurvivorRatio=8                # Eden/Survivor 比例（默认 8，即 Eden:S0:S1 = 8:1:1）
```

### G1 参数

```bash
-XX:+UseG1GC                       # 启用 G1
-XX:MaxGCPauseMillis=200           # 目标最大停顿时间（默认 200ms）
-XX:G1HeapRegionSize=4m            # Region 大小（1~32MB，2的幂）
-XX:InitiatingHeapOccupancyPercent=45  # 触发并发标记的堆占用比（默认 45%）
-XX:G1MixedGCCountTarget=8        # Mixed GC 目标次数
-XX:G1ReservePercent=10            # 预留空间百分比
-XX:ConcGCThreads=4                # 并发标记线程数
-XX:ParallelGCThreads=8            # STW 阶段 GC 线程数
```

### ZGC 参数

```bash
-XX:+UseZGC                        # 启用 ZGC
-XX:+ZGenerational                 # 分代 ZGC（JDK 21+）
-XX:SoftMaxHeapSize=3g             # 软堆上限（ZGC 尽量不超过此值）
```

### 诊断参数

```bash
-XX:+HeapDumpOnOutOfMemoryError            # OOM 时自动 dump 堆
-XX:HeapDumpPath=/var/log/app/heap.hprof   # dump 文件路径
-XX:OnOutOfMemoryError="kill -9 %p"        # OOM 时执行的命令
-XX:+ExitOnOutOfMemoryError                # OOM 时直接退出（容器环境推荐）
```

---

## 6. GC 调优思路

### 调优流程

```
1. 是否需要调优？
   └─ GC 停顿影响了 SLA？吞吐量不达标？出现 OOM？
      └─ 否 → 不需要调优，别折腾

2. 确定调优目标
   └─ 降低延迟？提高吞吐量？减少 Full GC？

3. 收集数据
   └─ 开启 GC 日志 → 用 GCEasy 分析 → 定位瓶颈

4. 调整参数（一次只改一个参数）
   └─ 跑同样的负载 → 对比调优前后的指标

5. 验证
   └─ 在预发布环境跑压测 → 确认效果 → 上线
```

### 关键原则

- **-Xms 和 -Xmx 设为相同值**：避免堆动态扩缩容引起的停顿
- **不要手动设置 Young Gen 大小**（使用 G1 时）：G1 会自适应调整
- **先用默认参数**：JVM 的自适应策略通常比手动调优更好
- **关注应用代码**：80% 的 GC 问题根因在应用代码（分配过多、对象生命周期不合理），而不是 GC 参数

---

## 7. 实际案例：频繁 Young GC 的调优

### 问题现象

某订单服务在高峰期出现频繁 Young GC（每秒 2-3 次），每次停顿 30-50ms，导致 P99 延迟飙升。

### 排查过程

**Step 1：分析 GC 日志**

```bash
# 上传 gc.log 到 GCEasy，发现：
# - Young GC 频率：2.5 次/秒
# - 平均停顿：35ms
# - 对象分配速率：800MB/s（异常偏高）
# - 晋升速率：正常
```

**Step 2：定位分配热点**

```bash
# 使用 async-profiler 的 alloc 模式
./asprof -e alloc -d 30 -f alloc.html <pid>
```

火焰图显示：`com.example.order.converter.OrderConverter.toDTO()` 方法占分配量的 40%。

**Step 3：分析代码**

```java
// 问题代码：每次转换都创建大量临时对象
public OrderDTO toDTO(Order order) {
    OrderDTO dto = new OrderDTO();
    // 问题1：每次都创建新的 SimpleDateFormat
    SimpleDateFormat sdf = new SimpleDateFormat("yyyy-MM-dd HH:mm:ss");
    dto.setCreateTime(sdf.format(order.getCreateTime()));

    // 问题2：循环中频繁创建临时 List
    List<ItemDTO> items = new ArrayList<>();
    for (OrderItem item : order.getItems()) {
        ItemDTO itemDTO = new ItemDTO();
        // 问题3：toString() 产生大量临时字符串
        itemDTO.setProperties(item.getProperties().toString());
        items.add(itemDTO);
    }
    dto.setItems(items);
    return dto;
}
```

**Step 4：优化代码**

```java
// 优化后
private static final DateTimeFormatter FORMATTER =
    DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss");

public OrderDTO toDTO(Order order) {
    OrderDTO dto = new OrderDTO();
    // 使用线程安全的 DateTimeFormatter（不可变对象，可复用）
    dto.setCreateTime(FORMATTER.format(order.getCreateTime()));

    // 预估容量，减少 ArrayList 扩容
    List<ItemDTO> items = new ArrayList<>(order.getItems().size());
    for (OrderItem item : order.getItems()) {
        ItemDTO itemDTO = new ItemDTO();
        // 直接使用 JSON 序列化而不是 toString
        itemDTO.setProperties(item.getPropertiesJson());
        items.add(itemDTO);
    }
    dto.setItems(items);
    return dto;
}
```

**Step 5：验证结果**

```
调优前：Young GC 2.5 次/秒，分配速率 800MB/s
调优后：Young GC 0.4 次/秒，分配速率 150MB/s
P99 延迟：从 180ms 降至 45ms
```

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| GC 日志 | 生产环境必须开启，开销可忽略 |
| 日志格式 | 关注停顿时间、Eden/Survivor/Heap 变化、GC 原因 |
| 关键指标 | 停顿时间、频率、吞吐量、堆使用趋势 |
| GCEasy | 上传日志文件即可获得可视化分析报告 |
| 调优原则 | 先看是否需要调，一次改一个参数，大部分问题在代码不在 GC |
| 频繁 Young GC | 根因通常是对象分配速率过高，用 alloc profiling 定位热点 |
