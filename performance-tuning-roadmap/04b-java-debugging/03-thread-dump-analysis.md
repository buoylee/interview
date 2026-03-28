# Thread Dump 分析

## 概述

Thread Dump（线程转储）是 JVM 中所有线程在某一时刻的栈快照。它是排查线程阻塞、死锁、CPU 飙高、应用卡死等问题的核心手段。不需要任何预先配置，随时可以获取。

---

## 1. 获取 Thread Dump

```bash
# 方式一：jstack（最常用）
jstack <pid> > /tmp/thread-dump.txt

# 强制 dump（当 JVM 没有响应时）
jstack -F <pid> > /tmp/thread-dump.txt

# 方式二：jcmd（推荐，JDK 8+）
jcmd <pid> Thread.print > /tmp/thread-dump.txt

# 方式三：kill -3（Linux/macOS，输出到 stdout/stderr）
kill -3 <pid>
# 注意：输出会打到应用的标准输出或日志文件中

# 方式四：Arthas
[arthas@12345]$ thread > /tmp/thread-dump.txt

# 方式五：JFR 中包含定期线程快照
jcmd <pid> JFR.start duration=60s filename=/tmp/recording.jfr
```

---

## 2. Thread Dump 格式解读

```
"http-nio-8080-exec-23" #156 daemon prio=5 os_prio=0 cpu=12345.67ms elapsed=3600.12s tid=0x00007f8a1c012345 nid=0x1a2b runnable [0x00007f89e4567000]
   java.lang.Thread.State: RUNNABLE
        at com.example.service.DataProcessor.transform(DataProcessor.java:89)
        at com.example.controller.ApiController.process(ApiController.java:42)
        at sun.reflect.NativeMethodAccessorImpl.invoke0(Native Method)
        at sun.reflect.NativeMethodAccessorImpl.invoke(NativeMethodAccessorImpl.java:62)
        at org.apache.tomcat.util.threads.TaskThread$WrappingRunnable.run(TaskThread.java:61)
        at java.lang.Thread.run(Thread.java:750)

   Locked ownable synchronizers:
        - <0x00000007abc12345> (a java.util.concurrent.locks.ReentrantLock$NonfairSync)
```

### 各字段含义

| 字段 | 含义 | 示例值 |
|------|------|--------|
| **线程名** | 自定义名称或框架分配的名称 | `http-nio-8080-exec-23` |
| **#156** | 线程序号 | `#156` |
| **daemon** | 是否守护线程 | `daemon` |
| **prio** | Java 线程优先级 | `prio=5` |
| **os_prio** | 操作系统线程优先级 | `os_prio=0` |
| **cpu** | 线程累计 CPU 时间 | `cpu=12345.67ms` |
| **elapsed** | 线程存活时间 | `elapsed=3600.12s` |
| **tid** | Java 线程 ID（JVM 内部） | `tid=0x00007f8a1c012345` |
| **nid** | Native 线程 ID（OS 层面，十六进制） | `nid=0x1a2b`（= 十进制 6699） |
| **线程状态** | 当前状态 | `runnable` |
| **[0x00007f89...]** | 线程栈地址范围 | |

**nid 的用途**：当 `top -H -p <pid>` 显示某个线程 CPU 高时，将其十进制 PID 转为十六进制，在 Thread Dump 中搜索对应的 nid。

```bash
# 找到 CPU 最高的线程
top -H -p <pid>
# 假设线程 PID 是 6699

# 转换为十六进制
printf '%x\n' 6699
# 输出：1a2b

# 在 Thread Dump 中搜索 nid=0x1a2b
```

---

## 3. 线程状态含义

### RUNNABLE

```
"http-nio-8080-exec-23" ... RUNNABLE
        at com.example.service.DataProcessor.transform(DataProcessor.java:89)
```

线程正在 JVM 中执行，或者等待操作系统分配 CPU 时间。注意：Java 中的 RUNNABLE 包含了操作系统层面的 RUNNING 和 READY 状态。

**也包括阻塞在本地方法上的情况**：

```
"http-nio-8080-exec-1" ... RUNNABLE
        at java.net.SocketInputStream.socketRead0(Native Method)   ← 实际在等待网络 I/O
        at java.net.SocketInputStream.socketRead(SocketInputStream.java:116)
```

这种情况虽然显示 RUNNABLE，但线程实际上在等待网络数据，属于 I/O 阻塞。

### BLOCKED

```
"Thread-1" ... BLOCKED (on object monitor)
        at com.example.service.OrderService.updateStock(OrderService.java:67)
        - waiting to lock <0x00000007abc12345> (a java.lang.Object)
```

线程在等待获取一个 `synchronized` 锁（监视器锁）。如果大量线程处于 BLOCKED 状态，说明存在严重的锁竞争。

### WAITING

```
"pool-1-thread-3" ... WAITING (parking)
        at sun.misc.Unsafe.park(Native Method)
        - parking to wait for <0x00000007def67890> (a java.util.concurrent.locks.AbstractQueuedSynchronizer$ConditionObject)
        at java.util.concurrent.locks.LockSupport.park(LockSupport.java:175)
        at java.util.concurrent.LinkedBlockingQueue.take(LinkedBlockingQueue.java:442)
        at java.util.concurrent.ThreadPoolExecutor.getTask(ThreadPoolExecutor.java:1074)
```

线程在无限期等待。常见触发条件：
- `Object.wait()`：等待 `notify()/notifyAll()`
- `LockSupport.park()`：等待 `unpark()`
- `Thread.join()`：等待目标线程结束
- 线程池的工作线程在等待任务（正常行为）

### TIMED_WAITING

```
"scheduler-thread-1" ... TIMED_WAITING (sleeping)
        at java.lang.Thread.sleep(Native Method)
        at com.example.scheduler.TaskScheduler.run(TaskScheduler.java:34)
```

线程在有限时间内等待。常见触发条件：
- `Thread.sleep(millis)`
- `Object.wait(millis)`
- `LockSupport.parkNanos(nanos)`
- `Thread.join(millis)`

---

## 4. 锁分析

### 找到持有锁的线程

```
# Thread-A 在等锁
"Thread-A" ... BLOCKED (on object monitor)
        at com.example.service.OrderService.process(OrderService.java:45)
        - waiting to lock <0x00000007abc12345> (a com.example.service.OrderService)

# Thread-B 持有锁
"Thread-B" ... RUNNABLE
        at com.example.service.OrderService.heavyCompute(OrderService.java:89)
        - locked <0x00000007abc12345> (a com.example.service.OrderService)    ← 持有锁
```

**分析方法**：
1. 找到 `waiting to lock <address>` 的线程
2. 搜索 `locked <address>` 找到持有该锁的线程
3. 分析持有锁的线程在做什么（为什么不释放锁）

### 死锁检测

JVM 会自动检测 `synchronized` 死锁并在 Thread Dump 末尾报告：

```
Found one Java-level deadlock:
=============================
"Thread-1":
  waiting to lock monitor 0x00007f8a1c034567 (object 0x00000007abc12345, a java.lang.Object),
  which is held by "Thread-2"

"Thread-2":
  waiting to lock monitor 0x00007f8a1c034890 (object 0x00000007abc67890, a java.lang.Object),
  which is held by "Thread-1"

Java stack information for the threads listed above:
===================================================
"Thread-1":
        at com.example.DeadlockDemo.methodA(DeadlockDemo.java:25)
        - waiting to lock <0x00000007abc12345> (a java.lang.Object)
        - locked <0x00000007abc67890> (a java.lang.Object)
"Thread-2":
        at com.example.DeadlockDemo.methodB(DeadlockDemo.java:35)
        - waiting to lock <0x00000007abc67890> (a java.lang.Object)
        - locked <0x00000007abc12345> (a java.lang.Object)

Found 1 deadlock.
```

**注意**：`ReentrantLock` 死锁不会被自动检测。需要看 `Locked ownable synchronizers` 部分手动分析，或使用 Arthas 的 `thread -b` 命令。

---

## 5. fastthread.io 在线分析

[fastthread.io](https://fastthread.io/) 是 Thread Dump 的在线分析工具。

### 使用方法

1. 上传 Thread Dump 文件到 https://fastthread.io/
2. 自动生成分析报告

### 分析报告关键内容

```
Thread Summary:
  Total threads: 256
  NEW: 0  RUNNABLE: 45  BLOCKED: 12  WAITING: 156  TIMED_WAITING: 43

Blocked Thread Groups:
  12 threads blocked on <0x00000007abc12345>
  Held by: "http-nio-8080-exec-1"
  Duration: Since the dump was taken
  Impact: 12 threads waiting → potential throughput issue

Identical Stack Traces:
  89 threads have identical stack:
    at java.net.SocketInputStream.socketRead0(Native Method)
    at com.mysql.cj.protocol.ReadAheadInputStream.read(...)
    → 可能是数据库连接池配置过大或查询太慢

CPU Consuming Threads:
  Thread "data-processor-3" cpu=45678ms
    at com.example.service.DataProcessor.transform(DataProcessor.java:89)

Deadlock Detection:
  No deadlock detected ✓
```

---

## 6. 多次 Thread Dump 对比分析法

**单次 Thread Dump 只能看到一个瞬间的状态**。如果线程只是偶尔执行某个方法，可能恰好被捕获到但不代表是问题。因此需要多次采样对比。

### 采集方法

```bash
#!/bin/bash
# collect_thread_dumps.sh
# 间隔 5 秒，连续采集 3 次

PID=$1
DUMP_DIR="/tmp/thread-dumps"
mkdir -p "$DUMP_DIR"

for i in 1 2 3; do
    echo "Taking thread dump $i..."
    jstack "$PID" > "${DUMP_DIR}/thread-dump-${i}.txt" 2>&1
    if [ $i -lt 3 ]; then
        sleep 5
    fi
done

echo "Thread dumps saved to ${DUMP_DIR}"
```

```bash
# 使用方法
chmod +x collect_thread_dumps.sh
./collect_thread_dumps.sh 12345
```

### 对比分析要点

| 分析维度 | 方法 |
|---------|------|
| **持续卡住的线程** | 如果某个线程在 3 次 dump 中都在同一位置（同一行代码），说明确实卡住了 |
| **锁持有时间** | 如果某个线程在 3 次 dump 中都持有同一把锁，说明持锁时间过长 |
| **线程数量变化** | 线程数持续增加可能是线程泄漏（线程池配置不当） |
| **BLOCKED 线程数量** | 持续增加说明锁竞争在恶化 |

### 实际分析示例

```
=== dump-1.txt (T+0s) ===
"http-nio-8080-exec-23" RUNNABLE
    at com.example.service.ReportService.generateReport(ReportService.java:56)

=== dump-2.txt (T+5s) ===
"http-nio-8080-exec-23" RUNNABLE
    at com.example.service.ReportService.generateReport(ReportService.java:56)  ← 还在同一行

=== dump-3.txt (T+10s) ===
"http-nio-8080-exec-23" RUNNABLE
    at com.example.service.ReportService.generateReport(ReportService.java:56)  ← 10 秒了还在这

结论：ReportService.generateReport() 的第 56 行存在性能问题（可能是死循环、大量计算或 I/O 阻塞）
```

---

## 7. 常见线程问题模式

### 线程池耗尽

```
# 所有线程池的工作线程都在忙碌，新请求无法处理
"http-nio-8080-exec-1" RUNNABLE at com.mysql.cj...socketRead0(Native Method)
"http-nio-8080-exec-2" RUNNABLE at com.mysql.cj...socketRead0(Native Method)
...
"http-nio-8080-exec-200" RUNNABLE at com.mysql.cj...socketRead0(Native Method)

→ 诊断：所有 HTTP 线程都在等待数据库响应
→ 根因：数据库慢查询或连接池不够
→ 修复：优化 SQL / 增加连接池大小 / 设置查询超时
```

### 锁升级 (synchronized → 重量级锁)

```
# 大量线程竞争同一把锁
"Thread-1" BLOCKED at com.example.CacheManager.get(CacheManager.java:23)
    - waiting to lock <0x00000007abc12345>
"Thread-2" BLOCKED at com.example.CacheManager.get(CacheManager.java:23)
    - waiting to lock <0x00000007abc12345>
...（几十个线程都在等同一把锁）

→ 诊断：CacheManager.get() 方法有 synchronized，高并发下成为瓶颈
→ 修复：改用 ConcurrentHashMap 或分段锁
```

### 线程泄漏

```
# 连续多次 dump，线程总数持续增加
dump-1: Total threads: 300
dump-2: Total threads: 450
dump-3: Total threads: 600

# 且增长的线程大部分是某个特定前缀
"custom-pool-thread-301" WAITING
"custom-pool-thread-302" WAITING
...

→ 诊断：线程池配置了无上限的 maximumPoolSize，或每次都创建新的线程池
→ 修复：复用线程池，设置合理的 maximumPoolSize
```

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| 获取方式 | jstack / jcmd / kill -3 / Arthas |
| 关键字段 | 线程名、nid（关联 OS 线程）、线程状态、锁信息 |
| RUNNABLE | 正在执行或就绪（包含 Native I/O 阻塞） |
| BLOCKED | 等待 synchronized 锁 |
| WAITING | 无限期等待（Object.wait / LockSupport.park） |
| 死锁检测 | JVM 自动检测 synchronized 死锁 |
| fastthread.io | 在线分析 Thread Dump |
| 多次对比 | 间隔 5-10 秒取 3 次，看哪些线程持续卡在同一位置 |
