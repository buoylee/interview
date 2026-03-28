# 排查能力自测

## 为什么需要自测

做完演练不代表真正掌握了。生产环境中的问题不会告诉你"这是一道 GC 题"——它只会扔给你一堆告警和用户投诉，你需要从现象出发，判断方向、选择工具、定位根因。这 20 道场景题模拟了真实的排查情境，每道题只给你现象描述，考验你能否快速构建排查思路并找到根因。

---

## 一、题目说明

- 每道题 5 分，共 100 分
- 评分维度：排查方向是否正确（2 分）、使用工具是否合理（1 分）、根因分析是否准确（2 分）
- 建议先独立作答，再对照参考答案评分
- 限时：每道题 5 分钟思考时间

---

## 二、OS / 系统层（题目 1-4）

### 题目 1：CPU 使用率 100%，但 load average 不高

**现象描述：**

一台 4 核 Linux 服务器，`top` 显示 CPU 使用率接近 400%（4 核打满），但 `uptime` 显示 load average 只有 3.8。应用日志中没有明显错误，但用户反馈响应变慢。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 确认 CPU 占用分布
top -H    # 查看哪些线程占 CPU

# 2. 确认是用户态还是内核态
mpstat -P ALL 1 5
# 看 %usr vs %sys

# 3. 如果是用户态 CPU 高
# Java 进程：
jstack <pid> > thread_dump.txt
printf "%x\n" <tid>   # top -H 看到的高 CPU 线程 ID 转 16 进制
grep <hex_tid> thread_dump.txt -A 20

# Go 进程：
go tool pprof http://localhost:port/debug/pprof/profile?seconds=30

# 4. 如果是内核态 CPU 高
perf top   # 查看内核热点函数
strace -c -p <pid>   # 统计系统调用
```

**可能根因：**

- 用户态 CPU 高：死循环、正则回溯（ReDoS）、密集计算（加密/序列化）、频繁 GC
- load 不高但 CPU 满：说明**没有大量的 I/O 等待和不可中断睡眠进程**，纯 CPU 计算密集型问题
- load = 3.8 < 4 核，说明没有等待队列，4 个核都在忙但没有排队

**关键知识点：** load average 衡量的是运行队列长度（R + D 状态进程数），而非 CPU 使用率。CPU 打满但 load 不高说明是计算密集而非 I/O 密集。

**评分标准：**
- 知道用 `top -H` 或 `mpstat` 定位 CPU 消耗来源（1 分）
- 知道区分用户态/内核态（0.5 分）
- 知道 load 和 CPU 使用率的区别（1 分）
- 能说出合理的根因（CPU 密集计算/死循环等）（1.5 分）
- 选择了正确的 profiling 工具（1 分）

</details>

---

### 题目 2：OOM Killer 杀掉进程

**现象描述：**

一个 Java 应用运行在 8GB 内存的容器中，`-Xmx` 设为 6GB。某天凌晨进程被杀，`dmesg` 显示 `Out of memory: Kill process`。但应用的 Heap 使用监控显示高峰时也只用了 4GB。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 确认 OOM Killer 详细信息
dmesg | grep -i "oom\|kill"
# 查看被杀进程的 RSS（实际物理内存使用）

# 2. 分析 Java 进程的实际内存占用（不只是 Heap）
# Java 的内存 = Heap + MetaSpace + Thread Stacks + Direct Buffer
#              + Codecache + 内部 JVM 结构 + Native 内存

# 3. 检查 Native Memory
# 如果开启了 NativeMemoryTracking：
jcmd <pid> VM.native_memory summary

# 4. 检查各区域
jcmd <pid> VM.info   # 全量 JVM 信息
cat /proc/<pid>/status | grep -E "VmRSS|VmSize|Threads"

# 5. 检查是否有 Direct Buffer 泄漏
jcmd <pid> VM.native_memory detail | grep "Internal\|Direct"
```

**可能根因：**

- Heap 4GB + MetaSpace（默认无上限）+ Thread Stacks（每线程 1MB × 500 线程 = 500MB）+ Direct Buffer + Code Cache + JVM 自身 ≈ 超过 8GB 容器限制
- 最常见：**Direct Buffer 泄漏**（Netty 框架使用堆外内存）、**线程数过多**、**MetaSpace 膨胀**（动态类加载）
- 容器 cgroup 限制 8GB，JVM Heap 6GB 留给其余部分只有 2GB，不够用

**关键知识点：** JVM 的实际内存远不止 `-Xmx`。生产中应遵循 `Xmx ≤ 容器内存 × 0.6-0.75`，给 off-heap 留足空间。

**评分标准：**
- 知道查 `dmesg` 和 OOM Killer 日志（1 分）
- 知道 Java 内存不只有 Heap（1 分）
- 能列举 Heap 以外的内存区域（1 分）
- 能给出合理的修复建议（Xmx 调低或容器内存调大）（1 分）
- 知道用 NativeMemoryTracking 排查（1 分）

</details>

---

### 题目 3：Load Average 很高但 CPU 使用率不高

**现象描述：**

一台 8 核服务器，`uptime` 显示 load average 为 25，但 `top` 显示 CPU 总使用率只有 30%。系统响应极慢，SSH 操作也卡顿。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 查看进程状态分布
ps aux | awk '{print $8}' | sort | uniq -c | sort -rn
# 关注 D 状态（不可中断睡眠）进程数量

# 2. 查看 I/O 等待
iostat -xz 1 5
# 关注 %util、await、avgqu-sz

# 3. 查看磁盘队列
vmstat 1 5
# 关注 wa（I/O wait）和 b（blocked processes）

# 4. 找到 D 状态进程
ps -eo pid,stat,wchan,cmd | grep "^.*D"

# 5. 查看具体 I/O 来源
iotop -P   # 哪个进程在做 I/O

# 6. 如果是磁盘问题
dmesg | grep -i "error\|reset\|timeout"  # 磁盘硬件错误
smartctl -a /dev/sda  # 磁盘健康检查
```

**可能根因：**

- **大量 D 状态进程**：进程等待 I/O 完成，不占 CPU 但计入 load average
- 磁盘 I/O 瓶颈：磁盘故障、RAID 重建、swap 频繁（内存不足导致 swap thrashing）
- NFS 挂载点无响应：NFS 服务器故障导致所有访问该挂载点的进程进入 D 状态
- 内存不足导致大量换页：`free -h` 看 swap 使用

**评分标准：**
- 知道 load 包含 D 状态进程（2 分）
- 知道用 `iostat`/`vmstat` 检查 I/O（1 分）
- 知道用 `ps` 查找 D 状态进程（1 分）
- 给出合理的根因（磁盘/NFS/swap）（1 分）

</details>

---

### 题目 4：系统 TIME_WAIT 连接数过多

**现象描述：**

`ss -s` 显示有 28000 个 TIME_WAIT 状态的 TCP 连接。应用偶尔报 `Cannot assign requested address` 错误。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 确认 TIME_WAIT 分布
ss -tan state time-wait | awk '{print $4}' | cut -d: -f1 | sort | uniq -c | sort -rn
# 看是连接哪个目标 IP 产生的 TIME_WAIT

# 2. 检查端口范围
sysctl net.ipv4.ip_local_port_range
# 默认 32768-60999 ≈ 28000 个端口，已经快用完了

# 3. 确认是谁在频繁建连
ss -tan state time-wait | awk '{print $4":"$5}' | head -20

# 4. 检查应用是否使用了连接池
# 如果大量 TIME_WAIT 连向同一个下游 → 没有使用连接池/连接池太小

# 5. 检查 HTTP keep-alive 设置
curl -v http://downstream-service/health
# 看 Connection: keep-alive 是否生效
```

**可能根因：**

- 应用大量短连接访问下游服务（没有连接复用/连接池）
- HTTP Client 没有启用 Keep-Alive，或服务端强制关闭（`Connection: close`）
- 连接池配置过小，高并发时大量新建连接
- `Cannot assign requested address`：本地可用端口耗尽

**修复方向：**

```bash
# 临时缓解
sysctl -w net.ipv4.ip_local_port_range="1024 65535"   # 扩大端口范围
sysctl -w net.ipv4.tcp_tw_reuse=1                      # 允许复用 TIME_WAIT

# 根本解决：启用连接池和 Keep-Alive
```

**评分标准：**
- 知道 TIME_WAIT 的 TCP 含义和 2MSL（1 分）
- 知道检查端口范围和连接目标分布（1 分）
- 知道根因是短连接/缺少连接复用（2 分）
- 给出正确的修复方向（1 分）

</details>

---

## 三、Java / JVM（题目 5-8）

### 题目 5：Java 应用频繁出现 GC 暂停，P99 延迟毛刺

**现象描述：**

一个 Spring Boot 应用使用 G1 GC，`-Xmx4g`。正常 P99 是 20ms，但每隔 2-3 分钟出现一次 P99 飙到 800ms 的毛刺。GC 日志中可以看到对应时间点有 Mixed GC，且 `To-space exhausted`。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 分析 GC 日志
# 搜索 "To-space exhausted" 出现的上下文
grep -B5 -A10 "To-space exhausted" gc.log

# 2. 用 GCEasy 或 GCViewer 分析
# 上传 gc.log 到 gceasy.io
# 关注：Humongous Allocation、Region 大小、Mixed GC 耗时

# 3. Arthas 实时查看
dashboard    # 看 Heap 分区使用情况
heapdump /tmp/heap.hprof  # 抓快照

# 4. 检查大对象分配
jcmd <pid> GC.heap_info
# 看 Humongous regions 数量
```

**可能根因：**

- G1 的 Region 默认大小可能为 2MB，大于 Region 一半（1MB）的对象会被标记为 Humongous Object
- Humongous Object 直接分配在老年代，占据连续 Region
- Mixed GC 回收老年代时，如果存活对象太多，Survivor/To-space 空间不足
- `To-space exhausted` 触发 Full GC 退化（G1 退化为 Serial Old GC），暂停时间暴增

**修复：**

```bash
# 增大 Region 大小，减少 Humongous 分配
-XX:G1HeapRegionSize=8m

# 增加预留空间
-XX:G1ReservePercent=15

# 更早触发 Mixed GC
-XX:InitiatingHeapOccupancyPercent=35
```

**评分标准：**
- 知道分析 GC 日志（1 分）
- 理解 G1 的 Region 和 Humongous Object 概念（2 分）
- 知道 To-space exhausted 的含义（1 分）
- 给出正确的调优参数（1 分）

</details>

---

### 题目 6：Java 应用内存持续增长，但 Heap 使用正常

**现象描述：**

一个使用 Netty 的 Java 微服务，容器 RSS 持续增长（从 2GB 涨到 5GB），但 JVM Heap 使用稳定在 1.5GB 左右。重启后 RSS 恢复正常，几天后又增长。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 开启 Native Memory Tracking
# 启动参数加 -XX:NativeMemoryTracking=detail
jcmd <pid> VM.native_memory summary scale=MB

# 2. 对比两次快照
jcmd <pid> VM.native_memory baseline
# 等待几小时
jcmd <pid> VM.native_memory summary.diff scale=MB

# 3. 检查 Direct Buffer 使用
jcmd <pid> VM.info | grep "Direct"
# 或用 JMX: java.nio:type=BufferPool,name=direct

# 4. 使用 jemalloc/tcmalloc 做 native 内存分析
# 启动时 LD_PRELOAD=libjemalloc.so MALLOC_CONF=prof:true
jeprof --show_bytes /path/to/java /tmp/jeprof.*.heap
```

**可能根因：**

- **Netty Direct Buffer 泄漏**：ByteBuf 没有正确 release，引用计数不归零
- **JNI 内存泄漏**：本地方法分配的内存未释放
- **线程数增长**：每个线程默认 1MB 栈空间
- **MetaSpace 增长**：动态代理/反射大量生成类

**评分标准：**
- 知道 Heap 之外还有 off-heap 内存（1 分）
- 知道用 NativeMemoryTracking 排查（2 分）
- 能识别 Netty Direct Buffer 泄漏的可能（1 分）
- 知道排查 MetaSpace 和线程栈（1 分）

</details>

---

### 题目 7：Java 应用响应突然卡死，线程 Dump 显示大量 BLOCKED

**现象描述：**

一个 Spring Boot 应用突然所有接口超时无响应。`jstack` 抓了 3 次 Thread Dump，发现大量线程 BLOCKED 在同一个锁上，持有锁的线程处于 RUNNABLE 状态但在做 I/O 操作。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. jstack 抓多次 Thread Dump（间隔 5 秒，抓 3 次）
for i in 1 2 3; do
    jstack <pid> > thread_dump_$i.txt
    sleep 5
done

# 2. 分析锁持有关系
grep -A 30 "BLOCKED" thread_dump_1.txt
# 找到 "waiting to lock <0x00000007abc12345>"
# 再找 "locked <0x00000007abc12345>" → 找到锁的持有者

# 3. 分析持有者在做什么
# 如果持有者是 RUNNABLE 但在做 I/O（Socket read / File read）
# 说明它在等待外部资源，且持有锁不释放

# 4. Arthas 分析
thread -b   # 直接查找阻塞线程
```

**可能根因：**

- 持有 `synchronized` 锁的线程在做**网络 I/O**（如调用下游服务/数据库查询）
- 下游服务变慢 → 持锁线程等待 → 其他线程全部 BLOCKED
- 典型场景：在 `synchronized` 块中调用 Redis/MySQL/HTTP

**修复：**

```java
// 错误写法：在 synchronized 中做 I/O
synchronized(lock) {
    String result = httpClient.get(url); // 如果这里慢，所有线程都被阻塞
    cache.put(key, result);
}

// 正确写法：缩小锁粒度
String result = httpClient.get(url); // I/O 不在锁内
synchronized(lock) {
    cache.put(key, result);  // 只锁内存操作
}

// 更好的写法：用并发数据结构替代锁
ConcurrentHashMap<String, String> cache = new ConcurrentHashMap<>();
cache.computeIfAbsent(key, k -> httpClient.get(url));
```

**评分标准：**
- 知道用 `jstack` 多次抓 Thread Dump 对比（1 分）
- 能分析锁持有/等待关系（1 分）
- 识别出在锁内做 I/O 的问题（2 分）
- 给出正确的修复方案（缩小锁粒度）（1 分）

</details>

---

### 题目 8：Arthas trace 一个方法调用链

**现象描述：**

一个接口正常应该 50ms 返回，最近 P99 变成了 500ms。已知入口方法是 `OrderService.createOrder()`，但内部调用了 5 个子方法，不知道哪个慢了。

**请写出：** 使用 Arthas 定位慢方法的完整操作步骤。

<details>
<summary>参考答案</summary>

**操作步骤：**

```bash
# 1. 连接 Arthas
java -jar arthas-boot.jar

# 2. 使用 trace 追踪方法调用链
trace com.perfshop.service.OrderService createOrder '#cost > 200'
# 只显示耗时 > 200ms 的调用，减少干扰

# 输出示例：
# `---ts=2026-03-28 10:30:15;thread_name=http-nio-8080-exec-5;
# `---[487ms] com.perfshop.service.OrderService:createOrder()
#     +---[2ms] com.perfshop.service.OrderService:validateOrder()
#     +---[3ms] com.perfshop.service.InventoryService:checkStock()
#     +---[5ms] com.perfshop.service.OrderService:saveOrder()
#     +---[465ms] com.perfshop.service.PaymentService:processPayment()  ← 这里慢
#     `---[8ms] com.perfshop.service.NotificationService:sendConfirmation()

# 3. 继续下钻慢方法
trace com.perfshop.service.PaymentService processPayment '#cost > 200'
# `---[465ms] com.perfshop.service.PaymentService:processPayment()
#     +---[1ms] com.perfshop.service.PaymentService:buildRequest()
#     +---[460ms] com.perfshop.client.BankClient:charge()  ← 银行接口慢
#     `---[2ms] com.perfshop.service.PaymentService:saveResult()

# 4. 用 watch 看具体参数和返回值
watch com.perfshop.client.BankClient charge '{params, returnObj, throwExp}' '#cost > 200' -x 3

# 5. 用 monitor 统计方法执行指标
monitor -c 10 com.perfshop.client.BankClient charge
# 输出每 10 秒的调用次数、成功率、平均 RT
```

**评分标准：**
- 知道用 `trace` 命令追踪调用链（2 分）
- 知道用 `#cost > N` 过滤条件（1 分）
- 知道逐层下钻定位慢方法（1 分）
- 知道用 `watch`/`monitor` 进一步分析（1 分）

</details>

---

## 四、Go 语言（题目 9-11）

### 题目 9：Go 服务内存持续增长

**现象描述：**

一个 Go HTTP 服务运行 3 天后内存从 100MB 涨到 2GB，`runtime.ReadMemStats` 显示 `HeapInuse` 只有 300MB，但 `Sys` 达到了 2.1GB。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 抓取 heap profile
go tool pprof http://localhost:8081/debug/pprof/heap

# 2. 对比两次 heap profile（间隔几小时）
go tool pprof -base heap_t1.pb.gz heap_t2.pb.gz

# 3. 查看 inuse_space vs alloc_space
go tool pprof -inuse_space http://localhost:8081/debug/pprof/heap
go tool pprof -alloc_space http://localhost:8081/debug/pprof/heap

# 4. 检查 goroutine 数量（goroutine 泄漏也会占内存）
curl http://localhost:8081/debug/pprof/goroutine?debug=1 | head -1

# 5. 检查 mmap/CGO 内存（如果用了 CGO）
cat /proc/<pid>/smaps | grep -E "Rss|Size" | awk '{sum+=$2} END {print sum/1024 "MB"}'
```

**可能根因：**

- `HeapInuse` 300MB 但 `Sys` 2.1GB：Go runtime 向 OS 申请了 2.1GB 但只在用 300MB
- Go 的 `madvise` 策略：Go 1.12+ 默认用 `MADV_FREE`，释放的内存不会立即归还 OS
- 可能的真正泄漏：goroutine 泄漏（每个 goroutine 至少 2KB 栈），或大量 `sync.Pool` 缓存
- 如果用了 CGO：C 代码中的 malloc 泄漏不会体现在 Go heap 统计中

**修复：**

```bash
# 让 Go runtime 积极归还内存
GODEBUG=madvdontneed=1 ./app   # Go 1.12-1.15
# Go 1.16+ 默认已改回 MADV_DONTNEED

# 或手动触发
runtime.debug.FreeOSMemory()
```

**评分标准：**
- 知道用 pprof 分析 heap（1 分）
- 理解 HeapInuse vs Sys 的区别（2 分）
- 知道 Go 的内存归还策略（MADV_FREE vs MADV_DONTNEED）（1 分）
- 能排查 goroutine 泄漏和 CGO 内存（1 分）

</details>

---

### 题目 10：Go 服务 GC 暂停影响延迟

**现象描述：**

一个高频交易的 Go 服务，P99 延迟要求 < 1ms。大部分时间满足，但每隔几秒出现 2-5ms 的延迟毛刺。`GODEBUG=gctrace=1` 显示 GC 暂停约 1-3ms。

**请写出：** Go GC 调优的排查和优化步骤。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 开启 GC trace
GODEBUG=gctrace=1 ./app 2>&1 | tee gc.log
# gc 1 @0.012s 1%: 0.023+1.45+0.034 ms clock, 0.18+0.29/1.2/0.0+0.27 ms cpu

# 2. 分析 GC 频率和暂停时间
# 格式：wall clock STW1 + concurrent + STW2
# 关注 STW1（标记开始）和 STW2（标记终止）的时间

# 3. 查看 heap profile 分析分配热点
go tool pprof -alloc_objects http://localhost:8081/debug/pprof/heap
# 找到分配最频繁的代码位置

# 4. 使用 trace 工具精细分析
curl http://localhost:8081/debug/pprof/trace?seconds=5 -o trace.out
go tool trace trace.out
# 在 Goroutine Analysis 中查看 GC 相关的 goroutine
```

**优化方案：**

```bash
# 方案 1：调整 GOGC（减少 GC 频率，代价是用更多内存）
GOGC=200 ./app   # 默认 100，设为 200 → 内存翻倍但 GC 频率减半

# 方案 2：使用 memory ballast（Go 1.19 前）
var ballast = make([]byte, 1<<30)  // 1GB 的 ballast
// 让 Go 认为堆很大，减少 GC 触发频率

# 方案 3：使用 GOMEMLIMIT（Go 1.19+，推荐）
GOMEMLIMIT=4GiB ./app
# 让 GC 以内存上限为目标，而非 GOGC 比例

# 方案 4：减少分配（根本方案）
# 对象复用：sync.Pool
# 预分配 slice：make([]T, 0, expectedCap)
# 避免不必要的 string/[]byte 转换
```

**评分标准：**
- 知道用 `gctrace` 分析 GC 暂停（1 分）
- 知道用 pprof 分析分配热点（1 分）
- 理解 GOGC 和 GOMEMLIMIT 的作用（1 分）
- 能给出减少分配的具体方案（sync.Pool/预分配）（1 分）
- 知道 STW 的两个阶段（1 分）

</details>

---

### 题目 11：Go 程序 pprof 显示 CPU 被 runtime.futex 占满

**现象描述：**

一个 Go 服务的 CPU Profile 中，`runtime.futex` 和 `runtime.lock2` 占了 60% 的 CPU。服务吞吐量很低，但 CPU 使用率不低。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 抓取 CPU profile
go tool pprof http://localhost:8081/debug/pprof/profile?seconds=30
top 20
# 看 runtime.futex、runtime.lock2 的占比

# 2. 查看互斥锁竞争 profile
go tool pprof http://localhost:8081/debug/pprof/mutex
top 20

# 3. 查看阻塞 profile
go tool pprof http://localhost:8081/debug/pprof/block
top 20

# 4. 确认锁竞争的代码位置
go tool pprof -source 'lock' http://localhost:8081/debug/pprof/mutex
```

**可能根因：**

- **高并发锁竞争**：`sync.Mutex` 在高并发下争抢严重
- 典型场景：全局 map 加锁读写、全局计数器用 Mutex 而非 atomic
- `runtime.futex` 是 Linux 上实现 Mutex 的系统调用，占 CPU 高说明大量 goroutine 在 spin/wait

**修复：**

```go
// 错误：全局 Mutex 保护 map
var mu sync.Mutex
var cache = make(map[string]string)

func Get(key string) string {
    mu.Lock()
    defer mu.Unlock()
    return cache[key]
}

// 修复 1：用 sync.RWMutex（读多写少场景）
var mu sync.RWMutex
func Get(key string) string {
    mu.RLock()
    defer mu.RUnlock()
    return cache[key]
}

// 修复 2：用 sync.Map（适合读多写少、key 稳定）
var cache sync.Map
func Get(key string) string {
    v, _ := cache.Load(key)
    return v.(string)
}

// 修复 3：分片锁（通用方案）
type ShardedMap struct {
    shards [256]struct {
        mu sync.RWMutex
        m  map[string]string
    }
}
func (s *ShardedMap) getShard(key string) *struct{ mu sync.RWMutex; m map[string]string } {
    h := fnv.New32a()
    h.Write([]byte(key))
    return &s.shards[h.Sum32()%256]
}
```

**评分标准：**
- 知道用 mutex profile 分析锁竞争（2 分）
- 理解 `runtime.futex` 的含义（1 分）
- 能给出减少锁竞争的具体方案（2 分）

</details>

---

## 五、Python（题目 12-13）

### 题目 12：Python Web 服务多核 CPU 只用了一个核

**现象描述：**

一个 Flask 应用部署在 8 核服务器上，`top` 显示 Python 进程只用了 100% CPU（即一个核）。增加并发请求后吞吐量没有提升，反而延迟增加了。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 确认进程数
ps aux | grep python
# 只有 1 个 Python 进程

# 2. 确认是否使用了多进程/多线程
# Flask 开发服务器默认单进程单线程

# 3. 确认是 CPU 密集还是 I/O 密集
py-spy top --pid <pid>
# 如果 CPU 密集：GIL 限制了多线程
```

**根因：**

- Python 的 **GIL（Global Interpreter Lock）**确保同一时刻只有一个线程执行 Python 字节码
- 即使开了多线程，CPU 密集型任务也只能用一个核
- Flask 开发服务器是单进程的，不适合生产

**修复：**

```bash
# 方案 1：使用 Gunicorn 多 worker 进程
gunicorn -w 8 -b 0.0.0.0:8082 app:app
# worker 数量建议 = CPU 核数 × 2 + 1

# 方案 2：如果是 I/O 密集型，用 asyncio
# 切换到 FastAPI + uvicorn
uvicorn app:app --workers 8

# 方案 3：CPU 密集型计算用 multiprocessing 或 C 扩展
from multiprocessing import Pool
with Pool(8) as p:
    results = p.map(cpu_heavy_func, data)
```

**评分标准：**
- 知道 GIL 的存在和影响（2 分）
- 知道多进程是绕过 GIL 的标准方案（1 分）
- 知道用 Gunicorn/uvicorn 部署（1 分）
- 区分 CPU 密集和 I/O 密集的解决方案（1 分）

</details>

---

### 题目 13：Python asyncio 服务偶发长延迟

**现象描述：**

一个 FastAPI 服务使用 asyncio，正常 P50 是 5ms，但 P99 偶尔飙到 2000ms。用 `py-spy` 看到长延迟期间主线程在执行一个同步的 DNS 解析调用。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 用 py-spy 找到阻塞调用
py-spy dump --pid <pid>
# 看到 socket.getaddrinfo() ← 同步 DNS 解析

# 2. 确认哪些代码路径触发了同步调用
grep -r "socket\.\|requests\.\|urllib" app/
# 找到在 async 函数中调用了同步库

# 3. 用 asyncio debug 模式检测阻塞
PYTHONASYNCIODEBUG=1 python app.py
# 会警告 > 100ms 的阻塞调用
```

**根因：**

- asyncio 是**单线程事件循环**，所有 coroutine 共享一个线程
- 在 async 函数中调用了**同步阻塞的 DNS 解析**（`socket.getaddrinfo`）
- DNS 解析可能耗时几百毫秒到几秒（DNS 服务器慢/超时重试）
- 阻塞期间整个事件循环停止，所有请求都被卡住

**修复：**

```python
# 错误：在 async 函数中使用同步 HTTP 库
async def get_price(product_id: int):
    response = requests.get(f"http://price-service/api/{product_id}")  # 同步阻塞!
    return response.json()

# 修复 1：使用 async HTTP 客户端
import httpx

async def get_price(product_id: int):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"http://price-service/api/{product_id}")
        return response.json()

# 修复 2：如果必须用同步库，放到线程池
import asyncio

async def get_price(product_id: int):
    loop = asyncio.get_event_loop()
    response = await loop.run_in_executor(
        None,  # 默认线程池
        lambda: requests.get(f"http://price-service/api/{product_id}")
    )
    return response.json()
```

**评分标准：**
- 知道 asyncio 是单线程事件循环（1 分）
- 知道同步阻塞调用会卡住整个事件循环（2 分）
- 知道用 async HTTP 库替代同步库（1 分）
- 知道 `run_in_executor` 作为临时方案（1 分）

</details>

---

## 六、数据库（题目 14-16）

### 题目 14：MySQL 死锁导致事务回滚

**现象描述：**

应用日志中频繁出现 `Deadlock found when trying to get lock; try restarting transaction` 错误。发生在高并发下单场景中，两个事务同时修改同一批商品的库存。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```sql
-- 1. 查看最近的死锁信息
SHOW ENGINE INNODB STATUS\G
-- 找到 LATEST DETECTED DEADLOCK 部分
-- 记录两个事务持有和等待的锁

-- 2. 分析死锁中的 SQL
-- 通常会看到两个事务的 SQL 和锁信息：
-- Transaction 1: UPDATE inventory SET stock=stock-1 WHERE product_id=100
-- Transaction 2: UPDATE inventory SET stock=stock-1 WHERE product_id=200
-- 但它们按不同顺序加锁导致死锁

-- 3. 开启死锁日志
SET GLOBAL innodb_print_all_deadlocks = ON;
-- 后续死锁都会记录到 error log
```

**根因：**

```
事务 A:                          事务 B:
BEGIN;                           BEGIN;
UPDATE inventory                 UPDATE inventory
  WHERE product_id = 100;          WHERE product_id = 200;
  (获得 100 的行锁)                (获得 200 的行锁)

UPDATE inventory                 UPDATE inventory
  WHERE product_id = 200;          WHERE product_id = 100;
  (等待 200 的行锁 ← 被 B 持有)    (等待 100 的行锁 ← 被 A 持有)

→ 死锁！MySQL 选择回滚其中一个事务
```

**修复：**

```java
// 修复：对同一批 product_id 按固定顺序加锁
public void deductStock(List<Long> productIds, List<Integer> quantities) {
    // 按 product_id 排序，保证所有事务加锁顺序一致
    List<Long> sorted = new ArrayList<>(productIds);
    Collections.sort(sorted);

    for (int i = 0; i < sorted.size(); i++) {
        Long productId = sorted.get(i);
        int qty = quantities.get(productIds.indexOf(productId));
        inventoryRepository.deductStock(productId, qty);
    }
}
```

**评分标准：**
- 知道用 `SHOW ENGINE INNODB STATUS` 查看死锁（2 分）
- 理解死锁的加锁顺序问题（1 分）
- 给出固定加锁顺序的修复方案（2 分）

</details>

---

### 题目 15：数据库连接池耗尽

**现象描述：**

应用日志报 `HikariPool-1 - Connection is not available, request timed out after 30000ms`。`SHOW PROCESSLIST` 显示 MySQL 有 50 个连接（HikariCP 的 maximumPoolSize），大部分处于 Sleep 状态。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 查看 HikariCP 指标
curl http://localhost:8080/actuator/metrics/hikaricp.connections.active
curl http://localhost:8080/actuator/metrics/hikaricp.connections.pending

# 2. 查看 MySQL 连接状态
mysql -e "SHOW PROCESSLIST\G" | grep -E "State|Time|Info" | head -60
# 注意 Time 列：如果连接 Sleep 了很久（> 60s），说明连接被借出但没归还

# 3. Thread Dump 分析
jstack <pid> | grep -A20 "HikariPool"
# 看哪些线程持有连接

# 4. 检查代码中的事务边界
grep -rn "@Transactional" src/
# 找是否有长事务
```

**可能根因：**

- **连接泄漏**：代码获取连接后异常路径没有释放（try-finally 没写对）
- **长事务**：`@Transactional` 方法内做了 HTTP 调用等耗时操作
- **慢查询**：某些 SQL 执行很慢，连接长时间被占用
- Sleep 状态说明连接在应用侧被持有但没在执行 SQL → 可能是连接泄漏或长事务

**修复：**

```yaml
# HikariCP 配置加上泄漏检测
spring:
  datasource:
    hikari:
      leak-detection-threshold: 10000  # 10s，连接借出超过 10s 打印警告
      maximum-pool-size: 50
      connection-timeout: 5000  # 5s 获取不到连接就报错（别设 30s 那么长）
```

**评分标准：**
- 知道查看 HikariCP 指标和 `SHOW PROCESSLIST`（1 分）
- 知道 Sleep 状态连接意味着被应用持有但未使用（1 分）
- 知道用 `leak-detection-threshold` 检测泄漏（1 分）
- 能识别长事务和连接泄漏问题（2 分）

</details>

---

### 题目 16：Redis 缓存穿透导致数据库压力大

**现象描述：**

MySQL 的 QPS 突然从 500 飙升到 5000。Redis 监控显示命中率从 95% 降到 20%。应用刚刚上线了一个新功能，允许用户按"收藏商品ID"查询商品详情。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 确认 Redis 命中率下降
redis-cli info stats | grep "keyspace_hits\|keyspace_misses"
# 计算命中率

# 2. 查看 Redis 中是否有对应的 key
redis-cli exists "product:999999999"
# (integer) 0  ← 不存在的商品 ID，Redis 中没有缓存

# 3. 分析请求日志
# 看是否有大量请求查询不存在的商品 ID
grep "product_id" access.log | awk '{print $NF}' | sort | uniq -c | sort -rn | head
# 大量不存在的 product_id

# 4. 确认是恶意攻击还是业务逻辑问题
# "收藏商品"功能可能缓存了用户很久以前的收藏，那些商品已经下架/删除
```

**根因：**

- 用户收藏了已下架的商品（ID 不存在于数据库）
- 每次查询：先查 Redis → miss → 查 MySQL → 查不到 → 不缓存结果
- 下次查同一个不存在的 ID → 又 miss → 又查 MySQL
- 这就是**缓存穿透**：大量请求穿过缓存直达数据库

**修复：**

```python
# 方案 1：缓存空值
async def get_product(product_id: int):
    cached = await redis.get(f"product:{product_id}")
    if cached is not None:
        if cached == "NULL":
            return None  # 缓存的空值
        return json.loads(cached)

    product = await db.query_product(product_id)
    if product is None:
        # 缓存空值，设置短 TTL
        await redis.set(f"product:{product_id}", "NULL", ex=300)  # 5 分钟
        return None

    await redis.set(f"product:{product_id}", json.dumps(product), ex=3600)
    return product

# 方案 2：布隆过滤器（大量不存在 ID 的场景）
from pybloom_live import BloomFilter

product_bloom = BloomFilter(capacity=10000000, error_rate=0.001)
# 启动时加载所有有效 product_id 到布隆过滤器

async def get_product(product_id: int):
    if product_id not in product_bloom:
        return None  # 一定不存在，直接返回
    # 可能存在，继续查缓存和数据库
    ...
```

**评分标准：**
- 能识别出缓存穿透的模式（2 分）
- 知道缓存空值方案（1 分）
- 知道布隆过滤器方案（1 分）
- 空值缓存设置短 TTL 避免脏数据（1 分）

</details>

---

## 七、网络（题目 17）

### 题目 17：服务间调用偶发超时，但双方日志都正常

**现象描述：**

Go 服务调用 Java 服务，偶发（约 1%）超时错误。Java 服务日志显示这些请求都在 50ms 内正常处理了。Go 服务设置的超时是 3s。两个服务部署在同一个 Kubernetes 集群的不同节点。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 确认网络层面的延迟
# 在 Go 服务 Pod 里 ping Java 服务 Pod
kubectl exec -it go-pod -- ping java-pod-ip
# 看是否有丢包或高延迟

# 2. 抓包分析
kubectl exec -it go-pod -- tcpdump -i eth0 host java-pod-ip -w /tmp/cap.pcap
# 找超时请求对应的 TCP 包，看是否有重传

# 3. 检查 DNS 解析
kubectl exec -it go-pod -- nslookup java-service.namespace.svc.cluster.local
# DNS 解析偶尔慢也会导致超时

# 4. 检查 kube-proxy / iptables 规则
kubectl get endpoints java-service
# 确认 Service 背后的 Pod 都健康

# 5. 检查节点网络
# conntrack 表满
dmesg | grep "conntrack"
cat /proc/sys/net/netfilter/nf_conntrack_count
cat /proc/sys/net/netfilter/nf_conntrack_max
```

**可能根因：**

- **TCP 重传**：网络丢包导致 TCP 重传，Linux 默认首次重传等待 1s（RTO），如果连续丢 2 个包就超过 3s 超时
- **conntrack 表满**：Kubernetes 使用 iptables/IPVS，conntrack 表满了会丢包
- **DNS 解析慢**：Service 域名解析偶尔超时（CoreDNS 问题）
- **节点间网络抖动**：跨节点通信经过 VXLAN/Flannel 等 CNI 可能有额外延迟

**评分标准：**
- 知道抓包分析（1 分）
- 知道检查 TCP 重传和 DNS（1 分）
- 知道 Kubernetes 网络链路（kube-proxy、conntrack）（1 分）
- 给出合理的根因（2 分）

</details>

---

## 八、分布式系统（题目 18-19）

### 题目 18：重试风暴导致雪崩

**现象描述：**

某天下午一个数据库从库出现了几秒的延迟毛刺。紧接着，整个微服务集群的请求量暴增 10 倍，多个服务依次过载崩溃，最终用了 30 分钟才恢复。

**请写出：** 排查步骤和可能的根因链条。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 按时间线还原事件
# 查看监控：数据库延迟毛刺的时间点
# 查看各服务的请求量、错误率、延迟变化

# 2. 分析请求放大
# Service A 一次请求失败 → 重试 3 次
# Service B 调 A，A 的每次重试又可能让 B 重试
# 如果有 3 层调用链，每层重试 3 次 → 3^3 = 27 倍请求量

# 3. 检查各服务的重试配置
grep -r "retry\|Retry\|maxRetries" configs/

# 4. 检查是否有断路器
grep -r "circuit\|breaker\|CircuitBreaker" src/
```

**根因链条：**

```
时间线：
T+0s:   数据库从库延迟 3s（可能是主从同步延迟）
T+1s:   Service C 查询超时，返回错误
T+2s:   Service B 收到 C 的错误，重试 3 次（请求量 x3）
T+3s:   Service A 收到 B 的超时，重试 3 次（请求量 x9）
T+5s:   Gateway 收到 A 的超时，重试 2 次（请求量 x18）
T+8s:   叠加正常流量，数据库连接池被打满
T+10s:  Service C 彻底不可用
T+15s:  级联故障向上传播，Service B、A 依次过载
T+60s:  整个集群不可用

根因：
1. 各层重试没有限制总重试次数（没有 retry budget）
2. 重试之间没有退避（全部立即重试）
3. 没有断路器保护
4. 重试的请求量呈指数级放大
```

**修复：**

```go
// 1. 限制重试次数 + 指数退避
retryPolicy := retry.WithMaxRetries(2, retry.NewExponential(100*time.Millisecond))

// 2. 添加 Retry Budget：整个集群的重试率不超过 10%
// 如果当前错误率 > 50%，停止重试

// 3. 添加断路器
// 错误率 > 50% 时熔断，停止发送请求

// 4. 添加请求对冲（Hedged Request）替代重试
// 不是失败后重试，而是超过 P95 延迟后并发发第二个请求
```

**评分标准：**
- 能还原重试放大的链条（2 分）
- 知道 retry budget 和指数退避（1 分）
- 知道断路器的作用（1 分）
- 给出系统性的防雪崩方案（1 分）

</details>

---

### 题目 19：分布式缓存一致性问题

**现象描述：**

用户在 PerfShop 上修改了商品价格，但有些用户看到的还是旧价格。系统使用 MySQL 为数据源，Redis 为缓存，缓存 TTL 为 1 小时。

**请写出：** 排查步骤和可能的根因。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. 确认 MySQL 中的数据
mysql -e "SELECT price FROM products WHERE id = 123"
# 新价格：99.00

# 2. 确认 Redis 中的数据
redis-cli get "product:123"
# 旧价格：199.00 ← 缓存还是旧的

# 3. 确认缓存更新逻辑
# 是先更新 DB 再删缓存？还是先删缓存再更新 DB？
# 还是更新 DB 后更新缓存？

# 4. 检查是否有多个 Redis 实例（主从延迟）
redis-cli info replication
```

**根因分析：**

```
常见的缓存更新策略问题：

策略 1: 先更新 DB，再删缓存（Cache-Aside，推荐）
问题：删缓存失败 → 脏数据直到 TTL 过期
修复：用消息队列保证最终删除

策略 2: 先删缓存，再更新 DB
问题：并发场景下，删缓存后、更新 DB 前，另一个请求把旧数据重新加载到缓存
这是最常见的一致性 bug

策略 3: 更新 DB 后更新缓存（而非删除）
问题：两个并发更新，后写 DB 的先写缓存 → 缓存是旧值
```

**修复：**

```java
// 推荐方案：Cache-Aside + 延迟双删
public void updatePrice(Long productId, BigDecimal newPrice) {
    String cacheKey = "product:" + productId;

    // 1. 先删缓存
    redis.del(cacheKey);

    // 2. 更新数据库
    productRepository.updatePrice(productId, newPrice);

    // 3. 延迟再删一次（防止并发加载旧数据到缓存）
    scheduler.schedule(() -> redis.del(cacheKey), 500, TimeUnit.MILLISECONDS);
}

// 更可靠的方案：基于 Binlog 的缓存更新
// 用 Canal/Debezium 监听 MySQL binlog → 发消息到 Kafka → 消费者删缓存
// 这样缓存更新与业务代码解耦，且不会遗漏
```

**评分标准：**
- 知道检查 DB 和 Redis 的数据差异（1 分）
- 理解 Cache-Aside 模式和并发问题（2 分）
- 知道延迟双删方案（1 分）
- 知道 Binlog 驱动的方案（1 分）

</details>

---

## 九、架构层（题目 20）

### 题目 20：序列化开销成为瓶颈

**现象描述：**

一个 Go 微服务使用 JSON 进行服务间通信。CPU Profile 显示 `encoding/json.Marshal` 和 `encoding/json.Unmarshal` 占了 35% 的 CPU。每个请求需要序列化/反序列化 5 次（与 5 个下游服务通信）。

**请写出：** 排查步骤和优化方案。

<details>
<summary>参考答案</summary>

**排查步骤：**

```bash
# 1. CPU Profile 确认序列化开销
go tool pprof http://localhost:8081/debug/pprof/profile?seconds=30
top 20
# encoding/json.Marshal  22.3%
# encoding/json.Unmarshal  13.1%

# 2. 分析序列化的数据量
# 在代码中加 metrics，统计每次序列化的数据大小
# 可能每次序列化 50-100KB 的结构体

# 3. 分析调用频率
# 5 次序列化 × QPS → 每秒序列化次数
```

**优化方案（从简单到复杂）：**

```go
// 方案 1：使用更快的 JSON 库（改动最小）
// encoding/json → github.com/json-iterator/go（兼容标准库，快 3-5 倍）
import jsoniter "github.com/json-iterator/go"
var json = jsoniter.ConfigCompatibleWithStandardLibrary

data, err := json.Marshal(obj)  // 接口不变，性能提升 3-5x

// 方案 2：使用 Protocol Buffers（内部服务间通信推荐）
// 比 JSON 快 5-10 倍，数据体积小 3-5 倍
// 需要定义 .proto 文件并生成代码
syntax = "proto3";
message ProductResponse {
    int64 id = 1;
    string name = 2;
    double price = 3;
    repeated string tags = 4;
}

// 方案 3：减少序列化次数（架构优化）
// 合并多个下游调用为一个（BFF 模式/GraphQL）
// 或缓存序列化结果（如果同一对象被多次序列化）

// 方案 4：对象复用，减少 GC 压力
var bufPool = sync.Pool{
    New: func() interface{} {
        return new(bytes.Buffer)
    },
}

func marshalToPool(v interface{}) ([]byte, error) {
    buf := bufPool.Get().(*bytes.Buffer)
    buf.Reset()
    defer bufPool.Put(buf)

    enc := json.NewEncoder(buf)
    if err := enc.Encode(v); err != nil {
        return nil, err
    }
    return append([]byte(nil), buf.Bytes()...), nil
}
```

**各方案对比：**

| 方案 | 改动量 | 性能提升 | 适用场景 |
|------|--------|---------|---------|
| json-iterator | 低 | 3-5x | 快速优化，兼容已有代码 |
| Protobuf | 中 | 5-10x | 内部微服务通信 |
| 减少调用次数 | 高 | N 倍 | 架构层面优化 |
| 对象复用 | 低 | 1.5-2x | 减少 GC 压力 |

**评分标准：**
- 知道用 CPU Profile 确认瓶颈（1 分）
- 知道替换 JSON 库方案（json-iterator 等）（1 分）
- 知道 Protobuf 方案（1 分）
- 从架构角度思考减少序列化次数（1 分）
- 方案有层次（短期/长期）（1 分）

</details>

---

## 十、能力雷达图自评模板

完成所有题目后，按各维度的得分绘制雷达图，找到自己的短板。

### 10.1 评分汇总表

| 维度 | 题号 | 满分 | 得分 | 得分率 |
|------|------|------|------|--------|
| OS/系统层 | 1-4 | 20 | ____ | ___% |
| Java/JVM | 5-8 | 20 | ____ | ___% |
| Go | 9-11 | 15 | ____ | ___% |
| Python | 12-13 | 10 | ____ | ___% |
| 数据库 | 14-16 | 15 | ____ | ___% |
| 网络 | 17 | 5 | ____ | ___% |
| 分布式系统 | 18-19 | 10 | ____ | ___% |
| 架构 | 20 | 5 | ____ | ___% |
| **总计** | | **100** | ____ | ___% |

### 10.2 雷达图模板

```
                    OS/系统层 (20)
                         ▲
                    5    |    5
                   ╱     |     ╲
          架构 (5)╱      |      ╲ Java/JVM (20)
                ╱   4    |   4    ╲
               ╱    ╱    |    ╲    ╲
              ╱   ╱  3   |  3  ╲   ╲
              ╱ ╱    ╱   |   ╲  ╲  ╲ ╲
    分布式 (10)─── 2 ─ ─ ┼ ─ ─ 2 ───── Go (15)
              ╲ ╲    ╲   |   ╱  ╱  ╱ ╱
              ╲   ╲  1   |  1  ╱   ╱
               ╲    ╲    |    ╱    ╱
                ╲   0    |   0    ╱
                 ╲       |       ╱
          网络 (5) ╲     |      ╱ Python (10)
                    ╲    |    ╱
                         ▼
                    数据库 (15)

得分率标注：
5 = 100%（精通）
4 = 80%（熟练）
3 = 60%（掌握）
2 = 40%（了解）
1 = 20%（入门）
0 = 0%（空白）

在雷达图上标出你各维度的得分率位置，连线即为你的能力轮廓。
凹陷的维度就是需要重点补强的方向。
```

### 10.3 等级评定

| 总分区间 | 等级 | 建议 |
|---------|------|------|
| 90-100 | S - 专家 | 可以指导他人，关注前沿技术 |
| 75-89 | A - 高级 | 继续深化弱项，多做生产实战 |
| 60-74 | B - 中级 | 重点突破 2-3 个弱项维度 |
| 45-59 | C - 初级 | 需要系统学习，建议从 Phase 0 重新过一遍 |
| < 45 | D - 入门 | 建议先打好 OS 和编程语言基础 |

### 10.4 提升路径建议

根据雷达图的凹陷方向，对照路线图中的阶段重点复习：

| 弱项维度 | 建议复习阶段 |
|---------|-------------|
| OS/系统层 | Phase 0 (OS 基础) + Phase 2 (Linux 工具) |
| Java/JVM | Phase 4a (Java Profiling) + Phase 4b (Java Debugging) |
| Go | Phase 5a (Go Profiling) + Phase 5b (Go Debugging) |
| Python | Phase 6a (Python Profiling) + Phase 6b (Python Debugging) |
| 数据库 | Phase 9a (Database) |
| 网络 | Phase 8 (Network I/O) |
| 分布式系统 | Phase 10 (Distributed) |
| 架构 | Phase 11 (Architecture) |

完成复习后，重新做一遍自测题，验证提升效果。
