# Heap Dump 与内存泄漏分析

## 概述

内存泄漏是 Java 应用中最棘手的问题之一 —— 它不会立刻崩溃，而是在数小时甚至数天后才导致 OOM。Heap Dump 是分析内存泄漏的核心手段：获取堆的完整快照，然后用 MAT 等工具分析谁占了内存、为什么没有被回收。本文覆盖 Heap Dump 的获取、MAT 分析、以及直接内存和 Metaspace 溢出的排查。

---

## 1. Heap Dump 获取方式

### 方式一：jmap（最常用）

```bash
# 生成 Heap Dump
jmap -dump:format=b,file=/tmp/heap.hprof <pid>

# 只 dump 存活对象（先触发一次 Full GC）
jmap -dump:live,format=b,file=/tmp/heap.hprof <pid>

# 注意：
# 1. dump 过程会 STW（Stop The World），堆越大耗时越长
# 2. 4GB 堆的 dump 大约需要 30-60 秒
# 3. 确保磁盘空间充足（dump 文件大约是堆使用量的大小）
```

### 方式二：OOM 时自动 Dump（推荐生产环境配置）

```bash
# JVM 启动参数（强烈建议所有生产应用都加上）
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/var/log/app/heap-oom.hprof

# 配合 OOM 后自动重启（容器环境）
-XX:+ExitOnOutOfMemoryError
```

### 方式三：jcmd

```bash
# jcmd 方式（JDK 8+推荐）
jcmd <pid> GC.heap_dump /tmp/heap.hprof

# 只 dump 存活对象
jcmd <pid> GC.heap_dump -all=false /tmp/heap.hprof
```

### 方式四：Arthas

```bash
[arthas@12345]$ heapdump /tmp/heap.hprof

# 只 dump 存活对象
[arthas@12345]$ heapdump --live /tmp/heap.hprof
```

### 获取 Dump 的注意事项

| 注意点 | 说明 |
|--------|------|
| **STW 影响** | Dump 过程中应用会暂停，大堆可能暂停数十秒 |
| **磁盘空间** | 确保目标路径有足够空间（至少等于堆使用量） |
| **文件传输** | Dump 文件可能很大，考虑先压缩再传输 |
| **多次 Dump** | 怀疑内存泄漏时，间隔一段时间取多次 Dump 做对比 |

---

## 2. MAT 使用详解

Eclipse Memory Analyzer Tool（MAT）是分析 Heap Dump 最强大的工具。

### 安装

```bash
# 下载地址：https://eclipse.dev/mat/downloads.php
# 独立版本（推荐，不需要 Eclipse IDE）

# 分析大 Dump 文件时调大 MAT 自身的内存
# 编辑 MemoryAnalyzer.ini：
-Xmx8g    # 建议设为 Dump 文件大小的 1.5-2 倍
```

### Leak Suspects - 自动泄漏分析

打开 Dump 文件后，MAT 自动运行泄漏嫌疑分析：

```
Leak Suspect Report:

Problem Suspect 1:
  One instance of "com.example.cache.LocalCache" loaded by
  "org.springframework.boot.loader.LaunchedURLClassLoader"
  occupies 1,234,567,890 (85.6%) bytes.
  The memory is accumulated in one instance of "java.util.HashMap"
  loaded by "<system class loader>".

  Keywords: com.example.cache.LocalCache
            java.util.HashMap

  → 点击 "Details" 查看完整引用链
```

**这是分析的第一步**：先看自动分析结果，大多数场景它能直接定位到问题。

### Dominator Tree - 谁占了最多内存

Dominator Tree 按对象支配的内存大小排序（Retained Heap = 该对象被回收后能释放的内存总量）：

```
Dominator Tree:
─────────────────────────────────────────────────────────────────────
Class Name                          | Shallow Heap | Retained Heap |
─────────────────────────────────────────────────────────────────────
com.example.cache.LocalCache        |          48  | 1,234,567,890 |
├─ java.util.HashMap                |          48  | 1,234,567,800 |
│  ├─ java.util.HashMap$Node[]      |    16,777,216|   890,123,456 |
│  │  ├─ java.util.HashMap$Node     |          32  |       234,567 |
│  │  │  └─ com.example.model.Order |         128  |       234,535 |
│  │  │     └─ byte[]               |     234,400  |       234,400 |
...
```

**Shallow Heap vs Retained Heap**：
- Shallow Heap：对象自身占用的内存
- Retained Heap：对象被 GC 回收后能释放的全部内存（含直接和间接引用的对象）

### Histogram - 类实例统计

按类统计实例数量和占用内存：

```
Histogram:
───────────────────────────────────────────────────────────────
Class Name                     | Objects |  Shallow Heap    |
───────────────────────────────────────────────────────────────
byte[]                         | 345,678 |    890,123,456   |  ← 可疑：大量 byte[]
java.lang.String               | 234,567 |      5,629,608   |
java.util.HashMap$Node         | 123,456 |      3,950,592   |
com.example.model.Order        |  89,012 |     11,393,536   |  ← 可疑：为什么有这么多?
char[]                         |  67,890 |      4,567,890   |
───────────────────────────────────────────────────────────────

# 右键 → List Objects → with incoming references（谁引用了这些对象）
# 右键 → List Objects → with outgoing references（这些对象引用了谁）
```

### Path to GC Roots - 引用链分析

这是定位内存泄漏根因的关键操作 —— 找出一个对象为什么没有被回收：

```
# 在 Histogram 或 Dominator Tree 中，右键某个对象
# → Path to GC Roots → exclude all phantom/weak/soft etc. references

Path to GC Roots:
com.example.model.Order @ 0x7f8a12345678
  └─ referent in java.util.HashMap$Node @ 0x7f8a12345600
     └─ [1234] in java.util.HashMap$Node[] @ 0x7f8a12340000
        └─ table in java.util.HashMap @ 0x7f8a1233ff00
           └─ cache in com.example.cache.LocalCache @ 0x7f8a1233fe00
              └─ localCache in com.example.service.OrderService @ 0x7f8a1233fd00  ← 泄漏根因！
                 └─ <static field> INSTANCE in com.example.service.OrderService
                    [GC Root: Class loaded by LaunchedURLClassLoader]
```

分析结果：`OrderService` 中的 `localCache` 字段（一个 `HashMap`）持续往里添加 `Order` 对象但从未清理，导致内存泄漏。

### OQL - 对象查询语言

MAT 支持类 SQL 语法查询堆中的对象：

```sql
-- 查找大小超过 1MB 的 byte 数组
SELECT * FROM byte[] b WHERE b.@length > 1048576

-- 查找所有 Order 对象的 ID
SELECT o.id, o.amount FROM com.example.model.Order o

-- 查找引用了某个类实例的所有对象
SELECT OBJECTS inbounds(o) FROM com.example.model.Order o

-- 查找所有 HashMap 中 entry 数量超过 10000 的
SELECT m, m.size FROM java.util.HashMap m WHERE m.size > 10000

-- 查找特定字符串
SELECT * FROM java.lang.String s WHERE s.toString() = "ERROR"
```

---

## 3. VisualVM 简单分析

VisualVM 比 MAT 轻量，适合快速分析小型 Dump 文件：

```bash
# 启动 VisualVM（JDK 自带或独立下载）
jvisualvm

# 或使用独立版本
visualvm --jdkhome /path/to/jdk

# 功能：
# - 打开 .hprof 文件
# - 查看 Summary（基本信息）
# - Classes 视图（类似 MAT 的 Histogram）
# - Instances 视图（查看某个类的所有实例）
# - 支持 OQL 查询
```

**选择建议**：小堆（< 1GB）用 VisualVM 快速查看；大堆或复杂泄漏问题用 MAT。

---

## 4. 直接内存泄漏排查

直接内存（Direct Memory）不在 Java 堆中，Heap Dump 中看不到，需要特别的排查方法。

### 常见直接内存泄漏场景

```java
// 场景1：ByteBuffer 泄漏
ByteBuffer buffer = ByteBuffer.allocateDirect(10 * 1024 * 1024);  // 10MB 直接内存
// 如果 buffer 的引用一直被持有，直接内存不会释放

// 场景2：Netty ByteBuf 泄漏
ByteBuf buf = ctx.alloc().directBuffer(1024);
// 忘记调用 buf.release()，导致直接内存泄漏
```

### 排查方法

```bash
# 1. 查看直接内存使用量
jcmd <pid> VM.native_memory summary

# 输出关键部分：
# -                    Internal (reserved=345MB, committed=345MB)
#                             (malloc=345MB #56789)
# 如果 Internal 持续增长，可能是直接内存泄漏

# 2. 设置直接内存上限（默认等于 -Xmx）
-XX:MaxDirectMemorySize=256m

# 3. 使用 Netty 的内存泄漏检测
-Dio.netty.leakDetection.level=PARANOID
# 级别：DISABLED < SIMPLE < ADVANCED < PARANOID

# 4. 查看 NIO DirectByteBuffer 的数量和大小
# 在 MAT 中搜索 java.nio.DirectByteBuffer，查看实例数量
# 或使用 Arthas：
[arthas@12345]$ ognl '@sun.misc.SharedSecrets@getJavaNioAccess().getDirectBufferPool().getMemoryUsed()'
```

### Netty ByteBuf 泄漏排查

```java
// 开启 Netty 详细泄漏检测
ResourceLeakDetector.setLevel(ResourceLeakDetector.Level.PARANOID);

// 泄漏报告示例（日志中会出现）：
// LEAK: ByteBuf.release() was not called before it's garbage-collected.
// See https://netty.io/wiki/reference-counted-objects.html for more information.
// Recent access records:
// #1: io.netty.buffer.AdvancedLeakAwareByteBuf.readBytes(...)
//     at com.example.handler.MessageDecoder.decode(MessageDecoder.java:45)
// #2: io.netty.buffer.AdvancedLeakAwareByteBuf.writeBytes(...)
//     at com.example.handler.MessageDecoder.decode(MessageDecoder.java:38)
// Created at:
//     io.netty.buffer.PooledByteBufAllocator.newDirectBuffer(...)
//     at com.example.handler.MessageDecoder.decode(MessageDecoder.java:30)
```

---

## 5. Metaspace 溢出排查

`java.lang.OutOfMemoryError: Metaspace` 通常由类加载器泄漏或动态生成类过多导致。

### 常见原因

| 原因 | 说明 |
|------|------|
| **类加载器泄漏** | 热部署场景下旧 ClassLoader 未被回收 |
| **动态代理过多** | CGLIB/Javassist/反射代理生成大量类 |
| **Groovy/脚本引擎** | 每次执行脚本都创建新的类 |
| **OSGi/模块化框架** | 频繁安装卸载 bundle |

### 排查步骤

```bash
# 1. 查看已加载类的数量趋势
jcmd <pid> VM.classloader_stats

# 2. 查看类加载器层级
jcmd <pid> GC.class_stats

# 3. 在 MAT 中分析
# 打开 Heap Dump → Histogram → 按 ClassLoader 分组
# 查看哪个 ClassLoader 加载了最多的类
# 如果看到大量 DelegatingClassLoader 或 GeneratedXxx 类，就是动态代理问题

# 4. 使用 Arthas
[arthas@12345]$ classloader -t    # 树形展示类加载器层级
[arthas@12345]$ classloader -l    # 列出所有类加载器及加载的类数量

# 输出示例：
# name                                        numberOfInstances  loadedCountTotal
# BootstrapClassLoader                        1                  3456
# sun.misc.Launcher$AppClassLoader            1                  2345
# org.springframework.boot.loader...          1                  1234
# sun.reflect.DelegatingClassLoader           8901               8901  ← 可疑！

# 5. 检查反射调用
# 如果 DelegatingClassLoader 数量很大，说明有大量反射调用
# 通过 -Dsun.reflect.inflationThreshold=2147483647 可以禁止反射 inflation（但会影响性能）
```

### 修复方案

```java
// 问题：每次请求都编译 Groovy 脚本
public Object executeScript(String script) {
    GroovyShell shell = new GroovyShell();  // 每次创建新的 ClassLoader
    return shell.evaluate(script);          // 每次生成新的类
}

// 修复：缓存编译后的脚本
private final Map<String, Script> scriptCache = new ConcurrentHashMap<>();

public Object executeScript(String scriptText) {
    Script script = scriptCache.computeIfAbsent(scriptText, key -> {
        GroovyShell shell = new GroovyShell();
        return shell.parse(key);
    });
    return script.run();
}
```

---

## 分析流程总结

```
OOM 或内存持续增长
    │
    ├─ 获取 Heap Dump（jmap / jcmd / OOM 自动 dump）
    │
    ├─ MAT 打开 Dump 文件
    │   │
    │   ├─ 1. 看 Leak Suspects（自动分析）
    │   │
    │   ├─ 2. 看 Dominator Tree（谁占内存最多）
    │   │
    │   ├─ 3. 看 Histogram（哪些类实例最多）
    │   │
    │   └─ 4. Path to GC Roots（为什么没被回收）
    │
    ├─ 如果堆内看不到问题 → 排查直接内存（NMT + Netty LeakDetector）
    │
    └─ 如果是 Metaspace OOM → 排查类加载器泄漏
```

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| Heap Dump 获取 | jmap / OOM 自动 dump / jcmd / Arthas，注意 STW 影响 |
| MAT Leak Suspects | 自动分析泄漏嫌疑，第一优先查看 |
| Dominator Tree | 按 Retained Heap 排序，找最大内存占用者 |
| Path to GC Roots | 追踪引用链，定位泄漏根因 |
| OQL | 类 SQL 查询堆中对象 |
| 直接内存 | 堆外内存，用 NMT 和 Netty LeakDetector 排查 |
| Metaspace | 类加载器泄漏、动态代理过多是主因 |
