# JVM 生产调优

JVM 调优的核心原则：基于数据而非猜测。在没有 GC 日志分析之前谈调优都是空谈。生产环境 JVM 配置的目标是：GC 停顿时间可控、吞吐量满足 SLA、不发生 OOM。本文提供一套可以直接用的生产参数模板，以及基于 GC 日志的科学调优方法。

---

## 一、生产 JVM 参数模板

### 1.1 通用模板（JDK 17+，G1 GC）

```bash
# === 堆内存 ===
-Xms4g -Xmx4g                          # 堆大小（固定，避免动态扩缩）
-XX:MetaspaceSize=256m                  # 元空间初始大小
-XX:MaxMetaspaceSize=512m               # 元空间最大值

# === GC 选择 ===
-XX:+UseG1GC                            # G1 垃圾收集器
-XX:MaxGCPauseMillis=200                # 目标最大 GC 停顿时间（ms）
-XX:G1HeapRegionSize=8m                 # Region 大小（堆 / 2048 ~ 堆 / 1）
-XX:InitiatingHeapOccupancyPercent=45   # 触发并发标记的堆占用比例

# === GC 日志 ===
-Xlog:gc*,gc+phases=debug,gc+age=trace,safepoint:file=/var/log/app/gc.log:utctime,pid,tags:filecount=10,filesize=100m

# === OOM 处理 ===
-XX:+HeapDumpOnOutOfMemoryError
-XX:HeapDumpPath=/var/log/app/heapdump/
-XX:+ExitOnOutOfMemoryError             # OOM 时直接退出（让容器重启）

# === 其他 ===
-XX:+UseStringDeduplication             # G1 字符串去重
-XX:-OmitStackTraceInFastThrow          # 不省略重复异常的堆栈
-XX:+AlwaysPreTouch                     # 启动时预分配内存页（避免运行时缺页中断）
```

### 1.2 低延迟模板（JDK 17+，ZGC）

```bash
-Xms8g -Xmx8g
-XX:+UseZGC
-XX:+ZGenerational                      # JDK 21+：分代 ZGC（强烈推荐）
-XX:SoftMaxHeapSize=6g                  # 软上限，GC 尽量控制在此以下

# ZGC 特点：停顿时间 < 1ms（与堆大小无关）
# 适用：对延迟敏感的交易系统、实时计算
```

### 1.3 大吞吐模板（批处理/离线任务）

```bash
-Xms16g -Xmx16g
-XX:+UseG1GC
-XX:MaxGCPauseMillis=500                # 允许较长停顿换取吞吐量
-XX:G1HeapRegionSize=16m
-XX:ConcGCThreads=4                     # 并发 GC 线程数
-XX:ParallelGCThreads=8                 # 并行 GC 线程数
-XX:+UseNUMA                            # 多 CPU 架构优化
```

---

## 二、堆大小选择方法

### 2.1 基于 GC 日志的科学方法

```
步骤：
1. 先用默认参数（或估算值）运行，开启 GC 日志
2. 在生产流量下运行至少 24 小时
3. 分析 GC 日志，得到以下数据：
   - Full GC 后存活对象大小 = Live Data Size（LDS）
   - Young GC 频率和耗时
   - Old Gen 增长速率

4. 堆大小建议：
   - 总堆 = LDS × 3~4
   - 新生代 = LDS × 1~1.5
   - 老年代 = LDS × 2~3
   - 元空间 = 初始 256m，上限根据实际使用设
```

### 2.2 分析 GC 日志

```bash
# 使用 GCViewer 分析
java -jar gcviewer.jar gc.log

# 使用 gceasy.io（在线分析，推荐）
# 上传 gc.log 文件，自动生成报告

# 关键指标
# 1. GC 吞吐量（Throughput）: > 95% 为健康
# 2. 最大停顿时间（Max Pause）: 是否满足 SLA
# 3. Full GC 频率: 0 次为最佳，每天 < 1 次可接受
# 4. GC 后老年代占用: 持续增长说明有内存泄漏
```

### 2.3 常见错误

```bash
# 错误 1：堆设得太大
-Xmx32g  # 大堆 + G1 = GC 停顿时间长
# 如果没有 32G 的数据需求，不要设这么大

# 错误 2：-Xms 和 -Xmx 不一致
-Xms1g -Xmx8g  # 堆动态扩缩导致额外 GC
# 生产环境应该设为一样

# 错误 3：没开 GC 日志
# GC 日志几乎不影响性能（< 1%），永远开着

# 错误 4：直觉式调优
"感觉慢了，加大堆吧"  # 没有数据支撑的调优都是赌博
```

---

## 三、GC 选择决策树

```
你的 JDK 版本？
│
├── JDK 8
│   ├── 堆 < 4G → ParNew + CMS（传统选择）
│   └── 堆 ≥ 4G → G1（-XX:+UseG1GC）
│
├── JDK 11/17
│   ├── 延迟要求 < 10ms → ZGC（实验性 → 生产可用）
│   ├── 通用场景 → G1（默认，成熟稳定）
│   └── 吞吐优先 → Parallel GC
│
└── JDK 21+
    ├── 延迟要求 < 1ms → ZGC Generational（首选！）
    ├── 通用场景 → G1（默认）
    └── 大堆低延迟 → Shenandoah

GC 选型速查：
┌─────────────┬──────────────┬──────────────┬──────────────┐
│ GC          │ 适用堆大小   │ 停顿时间     │ 吞吐量       │
├─────────────┼──────────────┼──────────────┼──────────────┤
│ G1          │ 4G - 64G     │ 10-200ms     │ 高           │
│ ZGC         │ 8G - 16TB    │ < 1ms        │ 中高         │
│ Shenandoah  │ 4G - 几百G   │ < 10ms       │ 中高         │
│ Parallel    │ < 8G         │ 较长         │ 最高         │
└─────────────┴──────────────┴──────────────┴──────────────┘
```

### G1 关键参数

```bash
-XX:+UseG1GC
-XX:MaxGCPauseMillis=200          # 目标停顿时间（G1 尽力达到）
-XX:G1HeapRegionSize=8m           # Region 大小，堆 / 2048
-XX:G1NewSizePercent=25           # 新生代最小比例
-XX:G1MaxNewSizePercent=60        # 新生代最大比例
-XX:InitiatingHeapOccupancyPercent=45  # 触发并发标记的堆占用
-XX:G1MixedGCCountTarget=8       # Mixed GC 目标次数
-XX:G1ReservePercent=10           # 预留空间防止 to-space exhausted
```

### ZGC 关键参数

```bash
-XX:+UseZGC
-XX:+ZGenerational                # JDK 21+，分代 ZGC
-XX:SoftMaxHeapSize=6g            # 软上限（ZGC 尽力维持在此以下）
-XX:ZAllocationSpikeTolerance=5   # 分配突增容忍度
-XX:ZCollectionInterval=0         # 强制 GC 间隔（0=自动）
# ZGC 几乎不需要调参，开箱即用
```

---

## 四、容器环境 JVM 配置

### 4.1 核心问题

```
问题：JVM 默认通过 /proc/meminfo 获取系统内存
      在容器中，这可能返回宿主机内存而非容器限制
      导致 JVM 分配过多内存 → 被 OOM Killer 杀死

解决：JDK 8u191+ / JDK 10+ 支持容器感知
```

### 4.2 容器化参数模板

```bash
# JDK 17+ 容器化参数
-XX:+UseContainerSupport             # 默认开启，识别容器内存/CPU 限制
-XX:MaxRAMPercentage=75.0            # 堆最大占容器内存的 75%
-XX:InitialRAMPercentage=75.0        # 初始堆也是 75%（固定大小）
-XX:MinRAMPercentage=50.0            # 小内存容器的堆百分比

# 不要再用 -Xms/-Xmx 的绝对值！用百分比更灵活
# 容器 4G 内存 → 堆 3G
# 容器 8G 内存 → 堆 6G
```

### 4.3 Kubernetes 配置示例

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: app
          image: app:latest
          resources:
            requests:
              memory: "4Gi"
              cpu: "2"
            limits:
              memory: "4Gi"   # request = limit，避免被驱逐
              cpu: "4"        # CPU 可以设 limit > request
          env:
            - name: JAVA_OPTS
              value: >-
                -XX:+UseContainerSupport
                -XX:MaxRAMPercentage=75.0
                -XX:InitialRAMPercentage=75.0
                -XX:+UseG1GC
                -XX:MaxGCPauseMillis=200
                -Xlog:gc*:file=/var/log/gc.log:time,tags:filecount=5,filesize=50m
                -XX:+HeapDumpOnOutOfMemoryError
                -XX:HeapDumpPath=/var/log/heapdump/
                -XX:+ExitOnOutOfMemoryError
```

### 4.4 内存预算分配

```
容器总内存 4G：
├── JVM 堆（-XX:MaxRAMPercentage=75%）    3072 MB
├── 元空间（Metaspace）                     256 MB
├── 线程栈（200 线程 × 1MB）               200 MB
├── JIT 代码缓存                           128 MB
├── 直接内存（DirectByteBuffer）            128 MB
├── Native 内存（JNI/操作系统）             200 MB
└── 预留                                    ~16 MB
                                          ──────
                                          ~4000 MB

注意：如果 Non-Heap 使用较多，MaxRAMPercentage 需要调低
```

---

## 五、JVM 启动优化

### 5.1 Class Data Sharing (CDS)

```bash
# 步骤 1：生成共享类列表
java -XX:DumpLoadedClassList=classes.lst -jar app.jar

# 步骤 2：生成共享归档
java -Xshare:dump -XX:SharedClassListFile=classes.lst \
     -XX:SharedArchiveFile=app-cds.jsa -jar app.jar

# 步骤 3：使用共享归档启动（启动时间减少 20-30%）
java -Xshare:on -XX:SharedArchiveFile=app-cds.jsa -jar app.jar

# JDK 13+：动态 CDS（自动）
java -XX:ArchiveClassesAtExit=app-dynamic.jsa -jar app.jar  # 首次运行
java -XX:SharedArchiveFile=app-dynamic.jsa -jar app.jar     # 后续启动
```

### 5.2 分层编译优化

```bash
# 默认分层编译（C1 快速编译 + C2 优化编译）
-XX:+TieredCompilation              # 默认开启

# 快速启动模式（只用 C1，牺牲峰值性能换启动速度）
-XX:TieredStopAtLevel=1             # 只编译到 Level 1（C1）
# 适用场景：Serverless/Lambda 等对冷启动敏感的环境

# 预热 JIT
# 通过模拟请求触发热点方法编译
@PostConstruct
public void warmUp() {
    for (int i = 0; i < 10000; i++) {
        processOrder(MockOrder.random()); // 触发 JIT 编译
    }
}
```

### 5.3 GraalVM Native Image

```bash
# 编译为原生镜像（启动时间 < 100ms）
native-image -jar app.jar -o app-native \
    --no-fallback \
    -H:+ReportUnsupportedElementsAtRuntime

# 适用场景：
# - CLI 工具
# - Serverless / Lambda
# - 对启动时间极度敏感

# 不适用：
# - 大量反射的框架（Spring 需要额外配置）
# - 动态代理
# - 长时间运行的服务（JIT 编译后的峰值性能更高）
```

---

## 六、实际调优案例

### 案例 1：频繁 Full GC

```
现象：每隔 10 分钟一次 Full GC，每次停顿 3-5 秒
环境：JDK 11，G1 GC，-Xmx4g

分析 GC 日志：
[GC pause (G1 Humongous Allocation) 3847M->3201M(4096M), 4.123s]

原因：大对象直接进老年代（Humongous Allocation）
      大量 SQL 结果集一次性加载到内存

解决：
1. 增大 G1HeapRegionSize（让更多对象不算 Humongous）
   -XX:G1HeapRegionSize=16m  # Region 大小翻倍
2. 优化 SQL，分页查询替代全量加载
3. 加大堆到 8G（如果数据量确实大）

结果：Full GC 消失，Young GC 频率 2-3 次/分钟，每次 < 50ms
```

### 案例 2：内存泄漏

```
现象：运行 3-5 天后 OOM
环境：JDK 17，G1，-Xmx8g

分析：
1. 观察 GC 日志，每次 Full GC 后 Old Gen 存活越来越大
   Day 1: Full GC 后 2.1G
   Day 3: Full GC 后 4.5G
   Day 5: Full GC 后 7.8G → OOM

2. 分析 Heap Dump
   jmap -dump:live,format=b,file=heap.hprof <pid>

   MAT 分析发现：
   HashMap 实例持有 500 万个 Entry
   → 一个自定义缓存没有淘汰策略

3. 代码问题：
   private static Map<String, Object> cache = new HashMap<>();
   // 只 put 不 remove！

解决：
   替换为 Caffeine Cache，设置 maximumSize 和 expireAfterAccess

结果：内存稳定在 3-4G，再无 OOM
```

### 案例 3：容器 OOM Killed

```
现象：Pod 被 OOM Killed，但 JVM 没有 HeapDumpOnOutOfMemoryError 的输出
环境：K8s，容器 2G 内存，-Xmx1500m

分析：
  容器 2G - JVM 堆 1500M = 只剩 500M
  元空间 256M + 200 线程 × 1M 栈 = 456M
  直接内存 + Native 内存 → 超出容器限制 → OOM Killed

  注意：这不是 JVM OOM，是操作系统 OOM Killer 杀的进程

解决：
1. 改用百分比配置
   -XX:MaxRAMPercentage=65.0  # 给 Non-Heap 留足空间
2. 限制线程栈大小
   -Xss512k                   # 默认 1M，减半
3. 限制直接内存
   -XX:MaxDirectMemorySize=128m

结果：容器内存使用稳定在 1.6-1.8G，不再被 Kill
```

---

## 七、JVM 参数速查表

### 内存参数

| 参数 | 说明 | 建议值 |
|------|------|--------|
| -Xms / -Xmx | 堆大小 | 设为相同值 |
| -XX:MaxRAMPercentage | 堆占容器内存百分比 | 65-75% |
| -XX:MetaspaceSize | 元空间初始大小 | 256m |
| -XX:MaxMetaspaceSize | 元空间最大值 | 512m |
| -Xss | 线程栈大小 | 512k-1m |
| -XX:MaxDirectMemorySize | 直接内存上限 | 128m-256m |

### GC 参数

| 参数 | 说明 | G1 建议 | ZGC 建议 |
|------|------|---------|----------|
| -XX:MaxGCPauseMillis | 目标停顿时间 | 100-200ms | 不需要设 |
| -XX:G1HeapRegionSize | Region 大小 | 堆/2048 | N/A |
| -XX:InitiatingHeapOccupancyPercent | 并发标记触发 | 45 | N/A |
| -XX:ConcGCThreads | 并发 GC 线程 | CPU/4 | 自动 |
| -XX:ParallelGCThreads | 并行 GC 线程 | CPU 核数 | 自动 |

### 诊断参数

| 参数 | 说明 | 建议 |
|------|------|------|
| -Xlog:gc* | GC 日志 | 始终开启 |
| -XX:+HeapDumpOnOutOfMemoryError | OOM 时自动 dump | 始终开启 |
| -XX:+ExitOnOutOfMemoryError | OOM 时退出进程 | 容器环境开启 |
| -XX:-OmitStackTraceInFastThrow | 保留完整异常栈 | 始终开启 |
| -XX:+AlwaysPreTouch | 启动时预分配内存 | 生产环境开启 |
| -XX:NativeMemoryTracking=summary | Native 内存追踪 | 排查时开启 |

### 快速排查命令

```bash
# 查看 JVM 参数
jcmd <pid> VM.flags

# 查看堆使用情况
jcmd <pid> GC.heap_info

# 触发 GC
jcmd <pid> GC.run

# 生成 Heap Dump
jcmd <pid> GC.heap_dump /tmp/heap.hprof

# Native 内存报告（需启动时加 -XX:NativeMemoryTracking=summary）
jcmd <pid> VM.native_memory summary

# 查看线程数
jcmd <pid> Thread.print | grep -c "tid="
```
