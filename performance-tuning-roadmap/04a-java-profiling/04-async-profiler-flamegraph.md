# async-profiler 与火焰图

## 概述

async-profiler 是 Java 生态中最实用的低开销采样分析器（Profiler），能在生产环境中安全使用。它输出的火焰图是定位 CPU 热点、内存分配热点、锁竞争的利器。本文详解 async-profiler 的四种模式、火焰图的正确解读方法，以及实际排查案例。

---

## 1. async-profiler 是什么

async-profiler 是一个开源的低开销 Java 采样分析器，具有以下特点：

- **低开销**：基于 perf_events（Linux）或 DTrace（macOS），采样开销通常 < 2%
- **无需 Agent**：通过 attach API 动态连接到运行中的 JVM
- **无安全点偏差**：不像 JVM 内置的采样只在安全点采样，async-profiler 可以在任意时刻采样，结果更准确
- **多种输出格式**：火焰图（HTML）、JFR、折叠栈（collapsed）等

---

## 2. 安装方法

```bash
# Linux/macOS - 下载最新版
wget https://github.com/async-profiler/async-profiler/releases/download/v3.0/async-profiler-3.0-linux-x64.tar.gz
tar xzf async-profiler-3.0-linux-x64.tar.gz
cd async-profiler-3.0-linux-x64

# 查看帮助
./asprof --help

# Linux 需要设置内核参数（否则只能以 root 运行）
echo 1 > /proc/sys/kernel/perf_event_paranoid
echo 0 > /proc/sys/kernel/kptr_restrict

# 容器中使用需要：
# 1. --cap-add SYS_ADMIN（或 --privileged）
# 2. --pid=host（如果目标进程在宿主机）
```

---

## 3. 四种模式详解

### CPU 模式（热点方法分析）

采样正在 CPU 上执行的线程栈，找出消耗 CPU 最多的代码路径。

```bash
# 基本用法：采样 30 秒，输出火焰图
./asprof -d 30 -f cpu.html <pid>

# 指定采样频率（默认每秒 100 次）
./asprof -d 30 -i 5ms -f cpu.html <pid>

# 只采样特定线程
./asprof -d 30 -t -f cpu.html <pid>

# 排除特定包（减少噪音）
./asprof -d 30 --exclude 'java.*' --exclude 'sun.*' -f cpu.html <pid>
```

**适用场景**：CPU 使用率高、某些接口耗时长、想知道 CPU 时间花在哪里。

### Alloc 模式（分配热点分析）

采样对象分配事件，找出哪些代码路径分配了最多的内存。

```bash
# 采样堆内存分配
./asprof -e alloc -d 30 -f alloc.html <pid>

# 按分配字节数显示（默认是按分配次数）
./asprof -e alloc -d 30 --total -f alloc.html <pid>

# 设置分配采样间隔（每分配 512KB 采样一次）
./asprof -e alloc -d 30 -i 512k -f alloc.html <pid>
```

**适用场景**：Young GC 频繁（分配速率高）、想定位对象分配热点。

### Lock 模式（锁竞争分析）

采样线程在锁上的等待事件，找出竞争最激烈的锁。

```bash
# 采样锁竞争
./asprof -e lock -d 30 -f lock.html <pid>

# 设置锁等待阈值（只记录等待超过 10us 的锁事件）
./asprof -e lock -d 30 -i 10us -f lock.html <pid>
```

**适用场景**：线程大量 BLOCKED、吞吐量上不去但 CPU 使用率不高。

### Wall 模式（全量分析，含阻塞时间）

无论线程是在 CPU 上执行还是阻塞等待，都进行采样。

```bash
# Wall-clock 采样
./asprof -e wall -d 30 -f wall.html <pid>

# 只看特定线程（推荐，否则会包含 GC 线程等噪音）
./asprof -e wall -d 30 -t -I 'http-nio-*' -f wall.html <pid>
```

**适用场景**：接口响应慢但 CPU 不高（可能在等 I/O、等锁、等网络）。Wall 模式能揭示线程"在等什么"。

---

## 4. 命令行用法汇总

```bash
# 基本模式
./asprof -d <duration> -f <output> <pid>

# 常用参数
-d <seconds>         # 采样持续时间
-f <filename>        # 输出文件（.html=火焰图, .jfr=JFR格式, .txt=文本）
-e <event>           # 事件类型: cpu, alloc, lock, wall, cache-misses, etc.
-i <interval>        # 采样间隔
-t                   # 按线程分组
-I <pattern>         # 只包含匹配的线程/方法
-X <pattern>         # 排除匹配的线程/方法
--total              # 按总量而非样本数排序
--reverse            # 反转火焰图（从底部向上看调用者）
-o <format>          # 输出格式: flamegraph, tree, flat, jfr

# 启动/停止模式（适合长时间监控）
./asprof start -e cpu <pid>
# ... 等待 ...
./asprof stop -f output.html <pid>

# 列出支持的事件
./asprof list <pid>
```

---

## 5. 火焰图解读方法

火焰图（Flame Graph）是一种栈追踪的可视化方式：

```
    ┌─────────────────────────────────────────────────────────┐
    │                    main()                               │  ← 调用栈底部
    ├──────────────────────────┬──────────────────────────────┤
    │    handleRequest()       │      processQueue()          │
    ├────────────┬─────────────┤──────────────────────────────┤
    │ parseJSON()│ queryDB()   │      serialize()             │
    ├────────────┤─────────────┤──────────┬───────────────────┤
    │ Jackson    │ HikariCP    │ Jackson  │ writeBytes()      │
    │ readTree() │ getConn()   │ writeVal │                   │  ← 调用栈顶部
    └────────────┴─────────────┴──────────┴───────────────────┘
```

### 关键解读规则

| 维度 | 含义 | 注意 |
|------|------|------|
| **X 轴宽度** | 该函数在采样中出现的比例（占总采样的百分比） | **不是时间轴！** 左右顺序无意义（按字母排序） |
| **Y 轴高度** | 调用栈深度，底部是调用者，顶部是被调用者 | 越高 = 越深的调用层级 |
| **顶部宽帧** | 这就是热点！栈顶宽意味着该函数自身消耗了大量 CPU | 这是你要优化的目标 |
| **颜色** | 默认按包名或帧类型着色（绿色=Java，黄色=C++，红色=kernel） | 颜色本身不表示性能好坏 |

### 如何找到热点

1. **看栈顶**：找最宽的栈顶帧，那就是直接消耗资源最多的方法
2. **看"平台"**：如果某一层很宽，说明它下面的所有调用累计消耗了大量资源
3. **对比**：采集优化前后的火焰图，对比同一路径的宽度变化
4. **搜索**：火焰图支持搜索（Ctrl+F），高亮所有匹配的帧

---

## 6. On-CPU vs Off-CPU 火焰图

| 类型 | 含义 | 对应模式 | 适用场景 |
|------|------|---------|---------|
| **On-CPU** | 线程正在 CPU 上执行 | `cpu` | CPU 使用率高 |
| **Off-CPU** | 线程不在 CPU 上（等待 I/O、锁、sleep） | `wall` - `cpu` | CPU 不高但响应慢 |

```bash
# 实践中的选择：
# 场景1：CPU 飙到 90% → 用 cpu 模式
./asprof -e cpu -d 30 -f cpu.html <pid>

# 场景2：CPU 只有 20% 但接口很慢 → 用 wall 模式
./asprof -e wall -d 30 -t -I 'http-nio-*' -f wall.html <pid>
# wall 模式会显示线程在等什么：数据库查询、Redis 调用、锁等待...
```

---

## 7. 实操案例：用 CPU 模式找到 JSON 序列化热点

### 问题现象

某 API 服务在压测时 CPU 使用率 95%，单机 QPS 只有 2000，预期应该达到 5000+。

### 排查过程

**Step 1：采集 CPU 火焰图**

```bash
# 找到 Java 进程 PID
jps -l
# 12345 com.example.ApiApplication

# 采样 30 秒
./asprof -d 30 -f /tmp/cpu-profile.html 12345
```

**Step 2：分析火焰图**

打开 `cpu-profile.html`，看到栈顶最宽的帧：

```
com.fasterxml.jackson.databind.ser.BeanSerializer.serialize()     ← 占 35%
com.fasterxml.jackson.core.json.WriterBasedJsonGenerator.writeString() ← 占 12%
java.text.SimpleDateFormat.format()                                ← 占 8%
```

Jackson 序列化 + 日期格式化占了 CPU 的 55%。

**Step 3：定位具体代码**

Ctrl+F 搜索业务代码包名 `com.example`，发现热点路径：

```
handleRequest() → getOrderDetail() → toResponse() → ObjectMapper.writeValueAsString()
```

**Step 4：分析问题**

```java
// 问题代码
@GetMapping("/order/{id}")
public String getOrder(@PathVariable Long id) {
    Order order = orderService.getById(id);
    OrderVO vo = convertToVO(order);
    // 问题：每次请求都创建新的 ObjectMapper
    ObjectMapper mapper = new ObjectMapper();
    mapper.setDateFormat(new SimpleDateFormat("yyyy-MM-dd HH:mm:ss"));
    return mapper.writeValueAsString(vo);
}
```

问题有两个：
1. 每次请求创建新的 `ObjectMapper`（ObjectMapper 创建成本高，包含大量内部缓存初始化）
2. 每次创建新的 `SimpleDateFormat`

**Step 5：优化**

```java
// 优化后：复用 ObjectMapper（线程安全）
private static final ObjectMapper MAPPER = new ObjectMapper()
    .registerModule(new JavaTimeModule())
    .disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);

@GetMapping("/order/{id}")
public String getOrder(@PathVariable Long id) {
    Order order = orderService.getById(id);
    OrderVO vo = convertToVO(order);
    return MAPPER.writeValueAsString(vo);
}
```

**Step 6：验证**

```bash
# 再次采集火焰图确认热点消失
./asprof -d 30 -f /tmp/cpu-profile-after.html 12345

# 压测结果：
# 优化前：QPS 2000, CPU 95%, P99 50ms
# 优化后：QPS 5500, CPU 60%, P99 18ms
```

Jackson 序列化的占比从 35% 降到 8%（ObjectMapper 内部缓存生效后效率大幅提升）。

---

## 实践建议

1. **生产环境可以放心用**：async-profiler 的采样开销通常 < 2%，不影响线上服务
2. **先 CPU 后 Wall**：大多数性能问题先用 CPU 模式排查，如果 CPU 不高但延迟高再用 Wall 模式
3. **结合 Alloc 模式**：如果 GC 频繁，用 Alloc 模式找分配热点比盲目调 GC 参数更有效
4. **多次采样取平均**：一次采样可能受偶发因素影响，建议多采几次确认热点稳定
5. **对比分析**：优化前后各采一份火焰图，量化优化效果

---

## 小结

| 知识点 | 核心要点 |
|--------|---------|
| async-profiler | 低开销采样分析器，生产可用，无安全点偏差 |
| CPU 模式 | 找 CPU 热点方法，适用于 CPU 高的场景 |
| Alloc 模式 | 找内存分配热点，适用于 GC 频繁的场景 |
| Lock 模式 | 找锁竞争热点，适用于线程 BLOCKED 多的场景 |
| Wall 模式 | 全量采样含阻塞，适用于 CPU 不高但响应慢的场景 |
| 火焰图 | X 轴=采样比例（非时间），Y 轴=栈深度，栈顶宽帧=热点 |
