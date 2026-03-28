# GC 算法对比

## 概述

垃圾收集（Garbage Collection）是 JVM 自动管理内存的核心机制。选错 GC 算法可能导致应用出现长时间停顿、吞吐量下降甚至 OOM。本文系统对比各种 GC 算法的原理与适用场景，帮助你做出正确的选型。

---

## 1. GC Roots 与可达性分析

### 哪些对象可以作为 GC Root

GC 的第一步是确定哪些对象还"活着"。JVM 使用可达性分析算法，从一组 GC Roots 出发，沿引用链遍历，不可达的对象即为垃圾。

**GC Roots 包括**：
- 虚拟机栈（栈帧中的局部变量表）中引用的对象
- 方法区中类静态属性引用的对象
- 方法区中常量引用的对象
- 本地方法栈中 JNI（Native 方法）引用的对象
- JVM 内部引用（如基本类型对应的 Class 对象、系统类加载器等）
- 被 synchronized 持有的对象
- JMXBean、JVMTI 中注册的回调、本地代码缓存等

### 可达性分析算法

```
GC Root Set
    │
    ├──→ Object A ──→ Object D
    │                    │
    ├──→ Object B ──→ Object E (可达，存活)
    │
    └──→ Object C

Object F ──→ Object G    ← 无法从 GC Root 到达，不可达，可回收
         ↑       │
         └───────┘       ← 循环引用不影响判定，这是比引用计数的优势
```

---

## 2. 基础 GC 算法

### 标记-清除（Mark-Sweep）

```
标记阶段：从 GC Roots 遍历，标记所有可达对象
清除阶段：遍历堆，回收未标记的对象

Before:  [A][B][ ][C][ ][D][ ][ ][E]
After:   [A][B][_][C][_][D][_][_][E]   ← 空闲区域碎片化
```

- **优点**：实现简单，不需要移动对象
- **缺点**：产生内存碎片，导致大对象无法分配；标记和清除效率都不高

### 复制算法（Copying）

```
Eden + S0(From)  →  S1(To)

GC前：
Eden:  [A][B][C][D][E]    S0(From): [F][G]    S1(To): [空]

GC后（A、C、E 存活）：
Eden:  [空]               S0(From): [空]       S1(To): [A][C][E][F]

下次 GC，S0 和 S1 角色互换
```

- **优点**：没有碎片问题，分配只需移动指针
- **缺点**：需要双倍空间（但 Eden:S0:S1 = 8:1:1 的设计极大缓解了这个问题）
- **适用**：Young Generation（因为大多数对象朝生夕灭，复制的存活对象很少）

### 标记-整理（Mark-Compact）

```
标记阶段：同标记-清除
整理阶段：将存活对象向一端移动，然后清理边界外的内存

Before:  [A][ ][B][ ][ ][C][ ][D]
After:   [A][B][C][D][          ]   ← 连续空闲空间
```

- **优点**：没有碎片，内存利用率高
- **缺点**：移动对象成本高，需要更新所有引用
- **适用**：Old Generation（对象存活率高，复制算法效率低，而碎片问题需要解决）

---

## 3. 分代假设

### 为什么要分代

分代 GC 基于一个经验观察（弱分代假设）：**绝大多数对象都是短命的**。

```
对象数量
  ↑
  │████
  │████
  │████░░
  │████░░░░
  │████░░░░░░░░░░░░░░░░░░
  └──────────────────────→ 对象年龄
   短命      中等        长寿
   (大多数)   (少量)     (极少)
```

- **弱分代假设**：大多数对象很快变得不可达（Young Gen 用复制算法高效回收）
- **强分代假设**：存活越久的对象越不容易死亡（Old Gen 不需要频繁回收）
- **跨代引用假设**：跨代引用相对于同代引用占比极少（通过记忆集 Remembered Set 处理，不需要全堆扫描）

---

## 4. G1 详解

G1（Garbage-First）是 JDK 9+ 的默认收集器，目标是在可控停顿时间内获得最高吞吐量。

### Region 化设计

```
+---+---+---+---+---+---+---+---+
| E | O | S | E | H | H | O |   |
+---+---+---+---+---+---+---+---+
| O | E | E |   | O | O | S | E |
+---+---+---+---+---+---+---+---+

E = Eden    S = Survivor    O = Old    H = Humongous    空 = Free
每个 Region 大小相同（1-32MB，由 -XX:G1HeapRegionSize 控制）
```

### G1 的 GC 模式

| 模式 | 触发条件 | 回收范围 |
|------|---------|---------|
| **Young GC** | Eden 区满 | 所有 Young Region |
| **Mixed GC** | 并发标记完成后 | Young Region + 部分 Old Region（回收价值最高的） |
| **Full GC** | Mixed GC 跟不上分配速度 | 全堆（退化为串行，性能灾难） |

### 关键参数

```bash
-XX:+UseG1GC                       # 启用 G1（JDK 9+ 默认）
-XX:MaxGCPauseMillis=200           # 目标停顿时间（默认 200ms）
-XX:G1HeapRegionSize=4m            # Region 大小
-XX:InitiatingHeapOccupancyPercent=45  # 触发并发标记的堆占用比例
-XX:G1MixedGCLiveThresholdPercent=85   # Region 存活率低于此才纳入 Mixed GC
-XX:G1ReservePercent=10            # 预留空间防止 promotion failure
```

### Humongous 对象

大小超过 Region 50% 的对象被视为 Humongous 对象，直接分配在连续的 Humongous Region 中。这类对象分配和回收代价都很高。

```java
// 如果 Region 大小是 4MB，那么 > 2MB 的数组就是 Humongous 对象
byte[] huge = new byte[3 * 1024 * 1024];  // 3MB -> Humongous
```

**调优建议**：如果 GC 日志中频繁出现 Humongous allocation，考虑增大 `G1HeapRegionSize` 或减少大数组的分配。

---

## 5. ZGC 详解

ZGC 是低延迟收集器，从 JDK 15 开始可用于生产环境（JDK 21 为分代 ZGC）。

### 核心技术

**着色指针（Colored Pointers）**：ZGC 在对象指针中利用几个 bit 存储 GC 状态信息（Marked0、Marked1、Remapped、Finalizable），无需在对象头中维护 GC 标记。

```
64位指针布局（ZGC）：
[  unused  ][  4 bits: GC metadata  ][  44 bits: object address  ]
                                       ← 支持最大 16TB 堆
```

**读屏障（Load Barrier）**：应用线程在读取对象引用时，如果发现引用指向的是旧地址（正在被 GC 移动），会自动修正为新地址。这使得 GC 可以和应用线程完全并发。

### 性能特征

```bash
# ZGC 启用
-XX:+UseZGC                        # JDK 15+
-XX:+ZGenerational                 # JDK 21: 分代 ZGC（JDK 23+ 默认）

# 典型表现
# 停顿时间：< 1ms（与堆大小无关）
# 吞吐量：略低于 G1（约 5-10% 的读屏障开销）
# 堆大小：支持 8MB 到 16TB
```

### 适用场景

- 对延迟极其敏感的系统（交易系统、实时竞价）
- 超大堆（数十 GB 到 TB 级别）
- 不能容忍长时间 STW 的场景

---

## 6. Shenandoah 简介

Shenandoah 是 Red Hat 贡献的低停顿收集器（OpenJDK 12+，不在 Oracle JDK 中）：

- 使用 Brooks Pointer（转发指针）实现并发压缩
- 停顿时间同样在亚毫秒级别
- 与 ZGC 定位类似，但实现机制不同
- 在 Red Hat 的 JDK 发行版中使用较多

```bash
-XX:+UseShenandoahGC              # 启用 Shenandoah
```

---

## 7. GC 选型决策树

```
你的应用对延迟敏感吗？
    │
    ├─ 是：需要亚毫秒级停顿？
    │   │
    │   ├─ 是 ──→ ZGC（推荐 JDK 21+ 分代 ZGC）
    │   │         或 Shenandoah（OpenJDK）
    │   │
    │   └─ 否（几十到几百毫秒可接受）──→ G1
    │         设置 -XX:MaxGCPauseMillis
    │
    └─ 否：追求最大吞吐量？
        │
        ├─ 是 ──→ Parallel GC（-XX:+UseParallelGC）
        │         服务器端批处理、大数据计算
        │
        └─ 堆很小（< 256MB）──→ Serial GC（-XX:+UseSerialGC）
                               嵌入式 / 客户端应用
```

### 各 GC 对比速查表

| GC | 停顿时间 | 吞吐量 | 堆大小 | JDK 版本 | 适用场景 |
|----|---------|--------|--------|---------|---------|
| Serial | 长 | 低 | 小 | 全版本 | 客户端、嵌入式 |
| Parallel | 中等 | **最高** | 中大 | 全版本 | 批处理、计算密集 |
| G1 | 可控 | 高 | 中大 | 9+ 默认 | 通用 Web 应用 |
| ZGC | **< 1ms** | 较高 | 大到超大 | 15+ | 低延迟、大堆 |
| Shenandoah | **< 1ms** | 较高 | 中大 | 12+(OpenJDK) | 低延迟 |

---

## 实践建议

1. **JDK 17/21 的项目**：直接用 G1（默认），如果延迟要求极高就换 ZGC
2. **不要过早调优 GC**：先用默认配置跑，出现问题再针对性调整
3. **关注 Full GC**：任何收集器出现 Full GC 都意味着问题——要么是内存不够，要么是参数不当
4. **避免 Humongous 分配**：检查代码中是否有大数组分配可以优化（比如复用 buffer）

```bash
# 快速查看当前 JVM 使用的 GC
java -XX:+PrintCommandLineFlags -version 2>&1 | grep -i gc

# JDK 17 输出示例：
# -XX:+UseG1GC
```

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| GC Roots | 栈帧引用、静态属性、JNI 引用等，循环引用不影响回收 |
| 标记-清除 | 简单但碎片化 |
| 复制算法 | 高效但需双倍空间，适合 Young Gen |
| 标记-整理 | 无碎片但移动代价高，适合 Old Gen |
| G1 | Region 化 + 可控停顿时间，通用首选 |
| ZGC | 着色指针 + 读屏障，亚毫秒停顿，大堆首选 |
| 选型 | 延迟敏感选 ZGC/G1，吞吐优先选 Parallel |
