# JVM 内存模型

## 概述

理解 JVM 内存模型是 Java 性能调优的根基。内存问题（泄漏、溢出、GC 压力）是生产环境最常见的性能瓶颈之一。本文从堆结构、方法区、栈帧、对象布局、分配策略到逃逸分析，系统梳理 JVM 内存的核心知识。

---

## 0. JVM 内存建立在 OS 进程虚拟地址空间上

JVM 不是脱离操作系统单独存在的内存世界。OS 看到的是一个普通的 `java` 进程:一整片虚拟地址空间、若干 native thread、若干 `mmap` / `malloc` 出来的内存区域。JVM 在这片地址空间里再划出 Java Heap、线程栈、Metaspace、Code Cache、Direct Memory 等运行时区域。

```text
OS 视角: java 进程的虚拟地址空间

高地址
┌──────────────────────────────────────┐
│ Thread stack: Java main thread        │  ← OS native thread stack
│ Thread stack: GC / JIT / worker       │
├──────────────────────────────────────┤
│ Shared libs / libjvm.so / libc        │
├──────────────────────────────────────┤
│ Code Cache                            │  ← JIT 编译后的机器码
├──────────────────────────────────────┤
│ Metaspace                             │  ← 类元数据,native memory
├──────────────────────────────────────┤
│ Direct Memory / mmap                  │  ← DirectByteBuffer、Netty 等常见
├──────────────────────────────────────┤
│ Java Heap                             │  ← JVM 自管对象区,GC 管
├──────────────────────────────────────┤
│ Native heap                           │  ← JVM / JNI / libc malloc
└──────────────────────────────────────┘
低地址
```

### Java Heap 不是 OS heap 的简单包装

OS 里的 `[heap]` 通常指进程通过 `brk` 扩展出来、给 libc `malloc/free` 使用的 native heap。Java Heap 更准确地说是 JVM 向 OS 申请的一大片虚拟内存区域（常见实现会用 `mmap` / reserve / commit），然后 JVM 自己在里面做对象分配、分代/region 管理、GC 移动和压缩。

```text
new User()
  → JVM 在 Java Heap 里分配 User 对象
  → OS 只看到 java 进程某些虚拟页被映射/触碰/RSS 增加
```

OS 不知道 `User`、`String`、对象头、引用关系和 GC root。OS 只按 page / mapping / RSS 管内存;JVM 才知道 Java 对象能不能回收、能不能搬家。

### Java Stack 通常建立在 OS native thread stack 上

HotSpot 的普通 Java platform thread 基本对应一个 OS native thread。创建 Java 线程时,JVM 底层会创建 native thread,OS 为这条线程准备 native stack;Java 方法调用产生的 Java frame、JVM runtime frame、JNI/native frame 通常都落在这条 native stack 上。

```text
OS native thread stack
┌──────────────────────────────┐
│ native frame: libc / JNI      │
│ JVM runtime frame             │
│ Java frame: main()            │
│ Java frame: service()         │
│ Java frame: dao()             │
└──────────────────────────────┘
```

所以可以这样记:

- **Stack 侧**:Java stack 通常是 JVM 在 OS native thread stack 上定义的 Java 方法栈格式。同一块内存,OS/CPU 只认识栈指针、返回地址、寄存器保存;JVM 才认识局部变量表、操作数栈、动态链接、返回地址等 Java frame 结构。
- **Heap 侧**:Java Heap 不是 OS heap 的简单包装,而是 JVM 在 OS 虚拟内存里自管的一片对象区。
- **排查侧**:`-Xmx` 只限制 Java Heap;进程 RSS 还包括 Metaspace、Code Cache、Direct Memory、线程栈、native heap、共享库和 page cache 影响。所以容器 memory limit 不能只按 `-Xmx` 估。

> OS 虚拟地址空间、`[heap]` / `[stack]` / `mmap` 的底层图见 [`../../linux/01-memory-primitives/README.md`](../../linux/01-memory-primitives/README.md);OS 线程栈和栈帧怎么工作见 [`../../linux/02-execution-primitives/README.md`](../../linux/02-execution-primitives/README.md)。

---

## 1. 堆结构详解

JVM 堆（Heap）是对象分配的主战场，采用分代设计：

```
+-------------------------------------------+
|                  Heap                      |
|  +-------+-------+-------+  +-----------+ |
|  | Eden  |  S0   |  S1   |  |  Old Gen  | |
|  | (80%) | (10%) | (10%) |  |           | |
|  +-------+-------+-------+  +-----------+ |
|       Young Generation        Old Generation|
+-------------------------------------------+
```

### 各区域作用

| 区域 | 作用 | 典型大小比例 |
|------|------|-------------|
| **Eden** | 新对象首先分配在这里，Minor GC 的主要回收区域 | Young Gen 的 80% |
| **Survivor 0/1 (S0/S1)** | Eden 存活对象复制到此，两个 Survivor 交替使用，每次 GC 后只有一个有数据 | 各占 Young Gen 的 10% |
| **Old Gen** | 经过多次 Minor GC 仍存活的对象晋升到此（默认年龄阈值 15，由 `-XX:MaxTenuringThreshold` 控制） | 堆的 2/3 |

### 对象晋升规则

1. **年龄阈值晋升**：对象在 Survivor 区每熬过一次 Minor GC，年龄 +1，达到阈值后晋升到 Old Gen
2. **动态年龄判定**：如果 Survivor 中相同年龄所有对象大小总和 > Survivor 空间的 50%，则年龄 >= 该年龄的对象直接晋升
3. **大对象直接进入 Old Gen**：超过 `-XX:PretenureSizeThreshold` 的对象跳过 Young Gen

```bash
# 查看运行时堆各区域大小
jcmd <pid> GC.heap_info

# 输出示例：
# garbage-first heap   total 4194304K, used 2621440K
#   region size 2048K, 512 young (1048576K), 64 survivors (131072K)
# Metaspace       used 85320K, committed 86528K
```

---

## 2. 方法区与 Metaspace

### JDK 8 之前：PermGen（永久代）

方法区在 HotSpot JVM 中曾用永久代实现，存放类的元数据、常量池、静态变量。它有固定大小上限（`-XX:MaxPermSize`），容易因加载类过多导致 `java.lang.OutOfMemoryError: PermGen space`。

### JDK 8 及之后：Metaspace

JDK 8 移除永久代，改用 Metaspace，直接使用本地内存（Native Memory）：

```bash
# Metaspace 相关参数
-XX:MetaspaceSize=256m          # 初始阈值，达到后触发 Full GC
-XX:MaxMetaspaceSize=512m       # 最大值，不设则仅受系统内存限制
-XX:MinMetaspaceFreeRatio=40    # GC 后最小空闲比例
-XX:MaxMetaspaceFreeRatio=70    # GC 后最大空闲比例
```

**关键变化**：
- 字符串常量池从 PermGen 移到了堆中（JDK 7 已完成）
- 类的元数据移到 Metaspace（本地内存）
- 静态变量移到堆中的 Class 对象里

### Metaspace 内部结构

Metaspace 按 ClassLoader 分配内存块，每个 ClassLoader 有自己的 chunk。当 ClassLoader 被回收时，其 Metaspace 整体释放。这意味着类加载器泄漏会直接导致 Metaspace 泄漏。

---

## 3. 栈帧结构

每个线程拥有独立的虚拟机栈，每次方法调用创建一个栈帧（Stack Frame）：

```
+---------------------------+
|      栈帧 (Stack Frame)    |
|  +---------------------+  |
|  | 局部变量表            |  |  <- 存放方法参数和局部变量
|  | (Local Variable Table)|  |     slot 为单位，long/double 占 2 个 slot
|  +---------------------+  |
|  | 操作数栈              |  |  <- 字节码指令的工作区
|  | (Operand Stack)      |  |     例如 iadd 从栈顶弹出两个 int 相加后压栈
|  +---------------------+  |
|  | 动态链接              |  |  <- 指向运行时常量池中该方法的引用
|  | (Dynamic Linking)    |  |     支持多态（虚方法表 vtable）
|  +---------------------+  |
|  | 返回地址              |  |  <- 方法正常返回或异常退出后的 PC 位置
|  | (Return Address)     |  |
|  +---------------------+  |
+---------------------------+
```

```bash
# 线程栈大小配置
-Xss512k    # 每个线程的栈大小，默认 1MB（64 位 Linux）
            # 线程数多时适当调小可以节省内存
            # 但过小会导致 StackOverflowError
```

**实际意义**：如果应用有 500 个线程，每个线程栈 1MB，那么仅线程栈就占用 500MB 内存。这不在堆内，但属于进程内存。

---

## 4. 对象内存布局

HotSpot JVM 中，一个对象在内存中的布局：

```
+--------------------------------------------------+
|                 对象头 (Header)                    |
|  +--------------------+------------------------+  |
|  |  Mark Word (8 bytes)|  Klass Pointer (4/8 B) |  |
|  +--------------------+------------------------+  |
+--------------------------------------------------+
|              实例数据 (Instance Data)              |
|  字段按照 long/double → int/float → short/char    |
|  → byte/boolean → reference 的顺序排列           |
+--------------------------------------------------+
|              对齐填充 (Padding)                    |
|  对象大小必须是 8 字节的整数倍                     |
+--------------------------------------------------+
```

### Mark Word 详解（64 位 JVM）

```
|----------------------------------------------------------------------|
|                     Mark Word (64 bits)                                |
|----------------------------------------------------------------------|
| 状态        | 内容                                                    |
|-------------|--------------------------------------------------------|
| 无锁        | hashcode(31) | age(4) | biased_lock(1) | lock(2)=01    |
| 偏向锁      | thread_id(54) | epoch(2) | age(4) | biased(1)=1 | 01  |
| 轻量级锁    | ptr_to_lock_record(62) | lock(2)=00                    |
| 重量级锁    | ptr_to_heavyweight_monitor(62) | lock(2)=10            |
| GC 标记     | 空 | lock(2)=11                                        |
|----------------------------------------------------------------------|
```

### 使用 JOL 查看对象布局

```java
// 添加依赖: org.openjdk.jol:jol-core:0.17
import org.openjdk.jol.info.ClassLayout;

public class ObjectLayoutDemo {
    int a;       // 4 bytes
    long b;      // 8 bytes
    boolean c;   // 1 byte

    public static void main(String[] args) {
        System.out.println(ClassLayout.parseInstance(new ObjectLayoutDemo()).toPrintable());
    }
}
```

```
# 输出示例（开启压缩指针 -XX:+UseCompressedOops）
ObjectLayoutDemo object internals:
OFF  SZ      TYPE DESCRIPTION               VALUE
  0   8           (object header: mark)      0x0000000000000001
  8   4           (object header: class)     0x00c33a00
 12   4       int ObjectLayoutDemo.a         0
 16   8      long ObjectLayoutDemo.b         0
 24   1   boolean ObjectLayoutDemo.c         false
 25   7           (alignment/padding gap)
SIZE: 32 bytes (object header 12 + fields 13 + padding 7)
```

---

## 5. 内存分配策略

### TLAB（Thread Local Allocation Buffer）

为了避免多线程分配对象时的锁竞争，JVM 为每个线程在 Eden 区预分配一块私有缓冲区：

```
Eden 区:
+--------------------------------------------------+
|  [Thread-1 TLAB] [Thread-2 TLAB] [Thread-3 TLAB] |
|  [  分配指针→  ]  [  分配指针→  ]  [  分配指针→  ]  |
|                   [  共享区域  ]                   |
+--------------------------------------------------+
```

- **快速分配**（Fast Path）：在 TLAB 内，分配对象只需移动指针（Bump the Pointer），无需加锁
- **慢速分配**（Slow Path）：TLAB 用完后，申请新 TLAB 或在共享区域分配（需要 CAS）

```bash
# TLAB 相关参数
-XX:+UseTLAB                # 默认开启
-XX:TLABSize=512k           # 初始 TLAB 大小（JVM 会自适应调整）
-XX:+PrintTLAB              # JDK8: 打印 TLAB 分配信息
-Xlog:gc+tlab=trace         # JDK11+: TLAB 跟踪日志
```

### 分配路径总结

```
对象分配请求
    │
    ├─ 是否开启逃逸分析且不逃逸？──是──→ 栈上分配 / 标量替换
    │
    ├─ 对象是否过大？──是──→ Old Gen 直接分配
    │
    ├─ TLAB 是否有空间？──是──→ TLAB 内指针碰撞（无锁）
    │
    └─ Eden 共享区域 CAS 分配
```

---

## 6. 逃逸分析

逃逸分析（Escape Analysis）是 JIT 编译器的重要优化。JVM 分析对象的作用域，判断对象是否"逃逸"出方法或线程。

### 三种优化

#### 标量替换（Scalar Replacement）

```java
// 优化前
public long calculate() {
    Point p = new Point(3, 5);  // p 不逃逸出方法
    return p.x + p.y;
}

// JIT 优化后（等价于）
public long calculate() {
    int x = 3;  // 对象被拆解为标量
    int y = 5;
    return x + y;  // 没有对象分配！
}
```

#### 栈上分配（Stack Allocation）

不逃逸的对象可以在栈上分配，方法返回时自动回收，不需要 GC。HotSpot 实际上通过标量替换来实现这个效果，而不是真正的栈上分配。

#### 同步消除（Lock Elision）

```java
// 优化前
public String concat(String s1, String s2) {
    StringBuffer sb = new StringBuffer();  // sb 不逃逸
    sb.append(s1);  // StringBuffer.append 是 synchronized 方法
    sb.append(s2);
    return sb.toString();
}

// JIT 优化后：锁被消除，因为 sb 只在当前线程可见
```

```bash
# 逃逸分析相关参数（JDK 8+ 默认全部开启）
-XX:+DoEscapeAnalysis           # 开启逃逸分析
-XX:+EliminateAllocations       # 开启标量替换
-XX:+EliminateLocks             # 开启同步消除
```

---

## 实用诊断命令

```bash
# 查看进程的内存区域配置
jcmd <pid> VM.flags | grep -E "Heap|Metaspace|NewSize|Xm"

# 查看运行时内存使用
jcmd <pid> GC.heap_info

# 查看 NMT（Native Memory Tracking）详情
# 需要先以 -XX:NativeMemoryTracking=summary 启动
jcmd <pid> VM.native_memory summary

# NMT 输出示例：
# Total: reserved=5678MB, committed=3456MB
# -                 Java Heap (reserved=4096MB, committed=2048MB)
# -                     Class (reserved=1100MB, committed=95MB)
# -                    Thread (reserved=512MB, committed=512MB)
# -                      Code (reserved=256MB, committed=64MB)
# -                        GC (reserved=200MB, committed=180MB)
# -                  Internal (reserved=32MB, committed=32MB)
```

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| 堆分代 | Eden → Survivor → Old Gen，年龄阈值 + 动态年龄判定 |
| Metaspace | JDK 8 取代 PermGen，使用本地内存，按 ClassLoader 管理 |
| 栈帧 | 每线程独立，含局部变量表/操作数栈/动态链接/返回地址 |
| 对象布局 | Header(Mark Word + Klass Pointer) + Instance Data + Padding |
| TLAB | 线程私有 Eden 区缓冲，指针碰撞实现快速分配 |
| 逃逸分析 | 标量替换、栈上分配、同步消除，减少堆分配和锁开销 |

理解这些内存基础，才能在面对 OOM、GC 频繁、内存泄漏时快速定位问题的根因。
