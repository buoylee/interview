# CPU 架构与调度

> 理解 CPU 的硬件结构和操作系统调度策略，是性能调优的第一块基石。很多性能问题的根因最终都指向 CPU 缓存、上下文切换或调度策略。

---

## 1. 多核 CPU 架构与缓存层级

现代服务器 CPU 是多核心设计，每个核心有自己的私有缓存，同时共享更大的缓存：

```
┌─────────────────────────────────────────────────────────┐
│                      CPU Package (Socket)                │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │  Core 0  │  │  Core 1  │  │  Core 2  │  │  Core 3  │ │
│  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │ │
│  │ │L1 I/D│ │  │ │L1 I/D│ │  │ │L1 I/D│ │  │ │L1 I/D│ │ │
│  │ │ 64KB │ │  │ │ 64KB │ │  │ │ 64KB │ │  │ │ 64KB │ │ │
│  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │ │
│  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │  │ ┌──────┐ │ │
│  │ │  L2  │ │  │ │  L2  │ │  │ │  L2  │ │  │ │  L2  │ │ │
│  │ │256KB │ │  │ │256KB │ │  │ │256KB │ │  │ │256KB │ │ │
│  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │  │ └──────┘ │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │
│  ┌──────────────────────────────────────────────────────┐│
│  │                   L3 Cache (共享)                     ││
│  │                    8MB - 64MB                         ││
│  └──────────────────────────────────────────────────────┘│
│  ┌──────────────────────────────────────────────────────┐│
│  │                 Memory Controller                     ││
│  └──────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────┘
                          │
                    ┌─────┴─────┐
                    │   DRAM    │
                    │  (内存)   │
                    └───────────┘
```

### 访问延迟对比（典型值）

| 层级 | 大小（典型） | 延迟 | 相对倍数 |
|------|-------------|------|----------|
| L1 Cache | 32-64 KB | ~1 ns | 1x |
| L2 Cache | 256 KB - 1 MB | ~4 ns | 4x |
| L3 Cache | 8-64 MB | ~12 ns | 12x |
| 主内存 (Local NUMA) | GB 级 | ~65 ns | 65x |
| 主内存 (Remote NUMA) | GB 级 | ~120 ns | 120x |

**性能启示**：数据局部性（Locality）是 CPU 性能的关键。频繁访问的数据如果能留在 L1/L2 缓存中，性能比每次去内存取快几十倍。

---

## 2. NUMA 架构

NUMA（Non-Uniform Memory Access）是多路服务器的标准架构。每个 CPU Socket 有自己的本地内存，访问远端 Socket 的内存需要跨总线，延迟翻倍：

```
┌─────────────────┐            ┌─────────────────┐
│   NUMA Node 0   │            │   NUMA Node 1   │
│  ┌───────────┐  │   QPI/UPI  │  ┌───────────┐  │
│  │  CPU 0    │◄─┼────────────┼─►│  CPU 1    │  │
│  └───────────┘  │            │  └───────────┘  │
│  ┌───────────┐  │            │  ┌───────────┐  │
│  │ Local Mem │  │            │  │ Local Mem │  │
│  │   64GB    │  │            │  │   64GB    │  │
│  └───────────┘  │            │  └───────────┘  │
└─────────────────┘            └─────────────────┘
   访问本地: ~65ns                访问远端: ~120ns
```

```bash
# 查看 NUMA 拓扑
numactl --hardware

# 绑定进程到指定 NUMA Node
numactl --cpunodebind=0 --membind=0 java -jar app.jar

# 查看 NUMA 内存分配统计
numastat -c
```

**生产经验**：JVM 大堆（>32GB）在 NUMA 机器上，如果不绑定 NUMA 节点，GC 时会频繁跨节点访问，GC 耗时可能增加 30-50%。

---

## 3. 用户态 vs 内核态

CPU 有特权级别（Ring 0-3），Linux 使用 Ring 0（内核态）和 Ring 3（用户态）。

```
┌─────────────────────────────────────┐
│            用户态 (Ring 3)           │
│  应用代码、库函数                     │
│         │                           │
│    系统调用 (syscall)                │
│    ─────┼───────────────────────    │
│         ▼                           │
│            内核态 (Ring 0)           │
│  进程调度、内存管理、设备驱动、网络栈   │
└─────────────────────────────────────┘
```

**系统调用的代价**：
- 每次 `syscall` 涉及 CPU 模式切换，保存/恢复寄存器，约 100-200ns
- Spectre/Meltdown 补丁（KPTI）后，代价增加到 ~1us
- 高频小 I/O（每次 read 几字节）会被 syscall 开销淹没

```bash
# 统计进程的系统调用频率
strace -c -p <pid>

# 查看系统调用耗时
strace -T -e trace=read,write -p <pid> 2>&1 | head -20
```

**优化思路**：减少 syscall 次数，用 buffered I/O 代替逐字节 read，用 `writev` 代替多次 `write`，用 `epoll` 代替 `select`。

---

## 4. 上下文切换

上下文切换是 CPU 从一个执行流切换到另一个执行流的过程，需要保存和恢复寄存器、栈指针等状态。

### 三种切换的代价对比

| 切换类型 | 需要保存/恢复的内容 | 典型代价 |
|----------|---------------------|----------|
| 进程切换 | 寄存器 + 栈 + 页表（TLB 刷新）+ 文件描述符表 | 3-5 us |
| 线程切换 | 寄存器 + 栈（共享地址空间，无需切换页表） | 1-3 us |
| 协程切换 | 寄存器子集 + 栈指针（用户态完成，无 syscall） | 100-200 ns |

```bash
# 查看系统上下文切换频率
vmstat 1
# cs 列表示每秒上下文切换次数，正常服务器 < 50000/s

# 查看某进程的上下文切换
pidstat -w -p <pid> 1
# cswch/s: 自愿切换（I/O 阻塞等）
# nvcswch/s: 非自愿切换（时间片用完，被抢占）
```

**性能警示**：
- 自愿切换高 -> 进程频繁等待 I/O，需要优化 I/O
- 非自愿切换高 -> CPU 竞争激烈，线程数过多或 CPU 不足

---

## 5. 中断与软中断

### 硬中断

硬件设备通过中断通知 CPU 事件发生（网卡收到数据包、磁盘完成 I/O、时钟中断等）。硬中断优先级高，会打断当前执行的代码。

### 软中断（SoftIRQ）

硬中断处理必须快速完成（不能做耗时操作），所以把后续处理交给软中断。网络收包是典型例子：

```
网卡收到数据 → 硬中断(快速)：把包放入 Ring Buffer → 触发 NET_RX 软中断
→ 软中断(NAPI)：从 Ring Buffer 取包 → 协议栈处理 → 放入 Socket Buffer
```

```bash
# 查看中断分布（每个 CPU 核心的中断计数）
cat /proc/interrupts

# 查看软中断统计
cat /proc/softirqs

# 实时观察软中断
watch -n 1 cat /proc/softirqs
```

**生产问题**：单核软中断打满（si 100%）是常见的网络性能瓶颈。通过 RSS（Receive Side Scaling）或 RPS 把中断分散到多个核心来解决。

---

## 6. CFS 调度器

Linux 默认使用 CFS（Completely Fair Scheduler），核心思想是**完全公平**——每个进程获得等比例的 CPU 时间。

### 关键概念

- **vruntime**：虚拟运行时间，CFS 总是选择 vruntime 最小的进程运行
- **时间片**：CFS 没有固定时间片，而是根据进程数动态计算调度周期
- **nice 值**：-20 到 19，nice 值越小优先级越高，获得的 CPU 时间权重越大

```
nice 值    权重      相对 nice 0 的 CPU 占比
  -20     88761     约 nice 0 的 87 倍
  -10      9548     约 nice 0 的 9.4 倍
    0      1024     基准
   10       110     约 nice 0 的 1/9
   19        15     约 nice 0 的 1/68
```

```bash
# 查看进程的 nice 值和调度策略
ps -eo pid,ni,cls,comm | head

# 修改进程 nice 值（降低优先级）
renice 10 -p <pid>

# 以低优先级启动进程
nice -n 19 ./batch-job

# 对于延迟敏感的服务，可以考虑实时调度策略
chrt -f 50 ./low-latency-server   # SCHED_FIFO，优先级 50
```

---

## 7. CPU 缓存行与 False Sharing

CPU 缓存以**缓存行（Cache Line）**为最小单位读写，通常 64 字节。False Sharing 是多核性能的隐形杀手：

```
                  一个缓存行 (64 bytes)
┌────────────────────────────────────────────────┐
│  变量 A (Thread 1 写)  │  变量 B (Thread 2 写)  │
└────────────────────────────────────────────────┘
           ▲                        ▲
           │                        │
     Core 0 的 L1               Core 1 的 L1

Thread 1 写 A → 整个缓存行在 Core 1 的 L1 失效
Thread 2 写 B → 整个缓存行在 Core 0 的 L1 失效
两个核心不断互相"抢夺"同一条缓存行 → 性能暴跌
```

### False Sharing 的代价

两个线程修改的是不同变量，逻辑上没有竞争，但因为这两个变量碰巧在同一个缓存行中，导致缓存行不断失效。真实场景中可能导致**性能下降 2-10 倍**。

### 解决方法：缓存行填充（Padding）

**Java 示例**：

```java
// 有 False Sharing 风险
class Counter {
    volatile long value;  // Thread 1 修改
}

// 解决方案 1：@Contended 注解（JDK 8+）
// 需要 JVM 参数 -XX:-RestrictContended
@sun.misc.Contended
class Counter {
    volatile long value;
}

// 解决方案 2：手动填充
class PaddedCounter {
    long p1, p2, p3, p4, p5, p6, p7;  // 填充 56 字节
    volatile long value;                // 8 字节 → 独占一个缓存行
    long p8, p9, p10, p11, p12, p13, p14;
}
```

**Go 示例**：

```go
// 有 False Sharing
type Counters struct {
    counter1 int64  // 可能和 counter2 在同一缓存行
    counter2 int64
}

// 解决：填充到 64 字节
type Counters struct {
    counter1 int64
    _        [56]byte  // padding
    counter2 int64
    _        [56]byte
}
```

```bash
# 用 perf 检测 False Sharing
perf c2c record -p <pid> -- sleep 10
perf c2c report
```

---

## 8. 实用诊断命令速查

```bash
# CPU 整体使用率
mpstat -P ALL 1

# 每个进程的 CPU 使用
pidstat -u 1

# 查看 CPU 缓存命中率（需要 perf）
perf stat -e cache-references,cache-misses,L1-dcache-load-misses ./your-program

# 查看调度延迟
perf sched latency

# 查看 NUMA 跨节点访问统计
numastat

# CPU 频率（是否降频）
cat /proc/cpuinfo | grep "MHz"
# 或
cpupower frequency-info
```

---

## 要点总结

1. **缓存层级决定了数据访问性能**——相差两个数量级。写高性能代码要考虑数据局部性。
2. **NUMA 对大内存应用影响显著**——JVM、Redis 等大内存进程应绑定 NUMA 节点。
3. **上下文切换有明确代价**——协程 < 线程 < 进程。线程数不是越多越好。
4. **CFS 是公平调度器**——latency-sensitive 的服务可以调低 nice 值或使用实时调度。
5. **False Sharing 是多线程的隐形杀手**——高并发计数器、原子变量要注意缓存行对齐。
