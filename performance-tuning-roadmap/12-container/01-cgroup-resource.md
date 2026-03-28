# cgroup 与资源限制

容器并不是虚拟机。容器本质上是一个受 cgroup 和 namespace 约束的普通 Linux 进程。理解 cgroup 的工作机制，是排查容器性能问题的根基——你会遇到 CPU 节流导致的延迟飙升、OOM Killer 杀掉关键进程、应用看到的 CPU 核数与实际可用资源不符等一系列问题，这些都直接指向 cgroup。

---

## 一、cgroups v1 vs v2 架构差异

### 1.1 cgroups v1：多层级树

cgroups v1 为每种资源（cpu、memory、blkio、cpuset 等）维护一棵独立的层级树：

```
/sys/fs/cgroup/
├── cpu/
│   └── docker/
│       └── <container-id>/
│           ├── cpu.cfs_quota_us
│           ├── cpu.cfs_period_us
│           └── cpu.shares
├── memory/
│   └── docker/
│       └── <container-id>/
│           ├── memory.limit_in_bytes
│           ├── memory.usage_in_bytes
│           └── memory.oom_control
├── cpuset/
│   └── docker/
│       └── <container-id>/
│           ├── cpuset.cpus
│           └── cpuset.mems
└── blkio/
    └── docker/
        └── <container-id>/
```

v1 的核心问题：

| 问题 | 说明 |
|------|------|
| 多层级不一致 | 一个进程在 cpu 和 memory 层级中的位置可能不同 |
| 委托困难 | 非 root 用户难以安全地管理子 cgroup |
| 控制器交互差 | cpu 和 memory 是独立管理的，无法做联合决策 |
| 线程粒度受限 | v1 的线程模式支持有限 |

### 1.2 cgroups v2：统一层级

cgroups v2 使用单一层级树，所有控制器挂载在同一个层级下：

```
/sys/fs/cgroup/
└── system.slice/
    └── docker-<container-id>.scope/
        ├── cgroup.controllers    # 可用控制器列表
        ├── cgroup.subtree_control
        ├── cpu.max               # 替代 cfs_quota + cfs_period
        ├── cpu.weight            # 替代 cpu.shares
        ├── memory.max            # 替代 memory.limit_in_bytes
        ├── memory.current        # 替代 memory.usage_in_bytes
        └── io.max                # 替代 blkio
```

```bash
# 查看当前系统使用的 cgroup 版本
stat -fc %T /sys/fs/cgroup/
# cgroup2fs → v2
# tmpfs → v1

# 或者直接看挂载信息
mount | grep cgroup
```

### 1.3 v1 与 v2 关键文件对照

| 功能 | cgroups v1 | cgroups v2 |
|------|-----------|-----------|
| CPU 配额 | `cpu.cfs_quota_us` + `cpu.cfs_period_us` | `cpu.max`（格式：`quota period`） |
| CPU 权重 | `cpu.shares`（默认 1024） | `cpu.weight`（默认 100，范围 1-10000） |
| 内存限制 | `memory.limit_in_bytes` | `memory.max` |
| 内存用量 | `memory.usage_in_bytes` | `memory.current` |
| OOM 控制 | `memory.oom_control` | `memory.events`（含 oom_kill 计数） |
| IO 限制 | `blkio.throttle.*` | `io.max` |

---

## 二、CPU 限制详解

### 2.1 CFS quota/period 机制

Linux CFS（Completely Fair Scheduler）通过 quota 和 period 实现 CPU 时间限制：

```
period = 100ms（默认）
quota  = 可用 CPU 时间

例：2 核 CPU
quota = 200000（200ms）, period = 100000（100ms）
→ 每 100ms 可使用 200ms CPU 时间 = 2 核
```

```bash
# Docker 设置 CPU 限制
docker run --cpus=1.5 myapp
# 等价于 --cpu-quota=150000 --cpu-period=100000

# Kubernetes 中
resources:
  limits:
    cpu: "1500m"    # 1.5 核 → quota=150000, period=100000
  requests:
    cpu: "500m"     # 用于调度决策和 cpu.shares 计算
```

### 2.2 cpu.shares（权重）

`cpu.shares` 控制的是 CPU 时间的相对权重，只在竞争时生效：

```bash
# 容器 A: cpu.shares = 1024
# 容器 B: cpu.shares = 512
# 当两者都需要 CPU 时，A 获得 2/3，B 获得 1/3
# 当只有 A 需要 CPU 时，A 可以使用全部可用 CPU

# Kubernetes 的 request 会被转换为 cpu.shares
# 1 CPU request = 1024 shares
# 500m request = 512 shares
```

### 2.3 cpuset：CPU 绑核

```bash
# 将容器绑定到 CPU 0 和 CPU 1
docker run --cpuset-cpus="0,1" myapp

# Kubernetes 中通过 CPU Manager 的 static 策略实现
# kubelet 配置
--cpu-manager-policy=static
--reserved-cpus="0-1"  # 系统保留

# 只有 Guaranteed QoS 且 CPU request 为整数的 Pod 才会被分配独占 CPU
```

---

## 三、CPU 节流（Throttling）的表现与排查

CPU 节流是容器环境中最隐蔽的性能问题之一。你的应用延迟突然飙升，但 CPU 利用率看起来并不高——这往往就是节流。

### 3.1 节流的原理

```
时间线（period = 100ms, quota = 50ms = 0.5 核）:

|-------- 100ms period --------|-------- 100ms period --------|
|== 用完 50ms ==|  被节流 50ms  |== 用完 50ms ==|  被节流 50ms  |
```

即使平均 CPU 利用率只有 50%，在 quota 用完的那 50ms 内，进程被完全暂停。如果一个请求恰好在这个窗口期到达，它的延迟会增加 50ms。

### 3.2 查看节流统计

```bash
# cgroups v1
cat /sys/fs/cgroup/cpu/docker/<container-id>/cpu.stat
# nr_periods 5765428        # 总周期数
# nr_throttled 2341892      # 被节流的周期数
# throttled_time 89023841923  # 总节流时间（纳秒）

# cgroups v2
cat /sys/fs/cgroup/system.slice/docker-<id>.scope/cpu.stat
# usage_usec 384728341
# user_usec 302847123
# system_usec 81881218
# nr_periods 5765428
# nr_throttled 2341892
# throttled_usec 89023841    # 微秒

# 计算节流率
# throttle_rate = nr_throttled / nr_periods
# 上面的例子：2341892 / 5765428 = 40.6%  ← 严重节流！
```

### 3.3 Prometheus 监控节流

```promql
# 容器 CPU 节流率
rate(container_cpu_cfs_throttled_periods_total[5m])
/
rate(container_cpu_cfs_periods_total[5m])

# 节流率 > 25% 触发告警
# 节流率 > 5% 应引起关注
```

### 3.4 解决节流的策略

```yaml
# 策略一：增大 CPU limit
resources:
  requests:
    cpu: "500m"
  limits:
    cpu: "2000m"   # 从 1000m 增大到 2000m

# 策略二：不设 CPU limit（只设 request）
# 许多团队（包括 Google 内部）推荐这种做法
resources:
  requests:
    cpu: "500m"
  # 不设 limits.cpu → 无 quota 限制，不会被节流

# 策略三：调整 CFS period（不推荐，除非你理解副作用）
# 更小的 period 意味着更频繁的调度，节流更"平滑"但开销更大
```

---

## 四、内存限制与 OOM

### 4.1 内存限制机制

```bash
# cgroups v1
cat /sys/fs/cgroup/memory/docker/<id>/memory.limit_in_bytes
# 4294967296  → 4GB

cat /sys/fs/cgroup/memory/docker/<id>/memory.usage_in_bytes
# 3221225472  → 3GB 已使用

# cgroups v2
cat /sys/fs/cgroup/system.slice/docker-<id>.scope/memory.max
# 4294967296

cat /sys/fs/cgroup/system.slice/docker-<id>.scope/memory.current
# 3221225472
```

### 4.2 容器中的 OOM Killer 行为

容器 OOM 与宿主机 OOM 有关键区别：

```bash
# 宿主机 OOM：内核根据 oom_score_adj 选择进程杀掉
# 容器 OOM：当 cgroup 内存达到 limit 时，只杀 cgroup 内的进程

# 查看 OOM 事件
# cgroups v1
cat /sys/fs/cgroup/memory/docker/<id>/memory.oom_control
# oom_kill_disable 0
# under_oom 0
# oom_kill 3        ← 已经被 OOM 杀了 3 次

# cgroups v2
cat /sys/fs/cgroup/system.slice/docker-<id>.scope/memory.events
# low 0
# high 0
# max 12            ← 达到 max 限制的次数
# oom 3             ← OOM 次数
# oom_kill 3        ← 被 OOM 杀掉的进程数

# Kubernetes 中查看 OOM 事件
kubectl get pods -o wide | grep OOMKilled
kubectl describe pod <pod-name> | grep -A 5 "Last State"
#     Last State:  Terminated
#       Reason:    OOMKilled
#       Exit Code: 137
```

### 4.3 内存统计中的陷阱

```bash
# container_memory_usage_bytes 包含 page cache！
# 真正的 RSS 内存要看 container_memory_rss 或 memory.stat 中的 rss

# cgroups v1
cat /sys/fs/cgroup/memory/docker/<id>/memory.stat
# rss 2147483648          # 实际进程内存
# cache 1073741824        # page cache（可回收）
# mapped_file 536870912   # mmap 文件

# 正确的内存使用指标
# 实际工作内存 = usage - inactive_file（v1）
# 实际工作内存 = memory.current - inactive_file（v2）
```

---

## 五、容器内观测差异

这是容器环境中最容易踩的坑之一：容器内的 `/proc` 文件系统显示的是宿主机信息。

### 5.1 问题表现

```bash
# 宿主机：64 核 CPU、256GB 内存
# 容器限制：2 核 CPU、4GB 内存

# 容器内执行
cat /proc/cpuinfo | grep processor | wc -l
# 64    ← 显示的是宿主机的 64 核！

cat /proc/meminfo | head -1
# MemTotal:     263061540 kB    ← 显示的是宿主机的 256GB！

nproc
# 64    ← 同样是宿主机信息

free -h
#               total        used        free
# Mem:          251Gi        187Gi       12Gi    ← 宿主机数据
```

### 5.2 影响

| 运行时/语言 | 受影响的行为 |
|------------|------------|
| JVM | `Runtime.getRuntime().availableProcessors()` 返回 64 核，导致线程池过大 |
| Go | `runtime.NumCPU()` 返回 64，GOMAXPROCS 默认设为 64 |
| Python | `multiprocessing.cpu_count()` 返回 64，fork 出 64 个工作进程 |
| Node.js | `os.cpus().length` 返回 64 |
| Nginx | `worker_processes auto` 启动 64 个 worker |

### 5.3 lxcfs 解决方案

lxcfs 通过 FUSE 文件系统将 cgroup 信息映射到 `/proc` 下：

```bash
# 安装 lxcfs
apt-get install lxcfs
systemctl start lxcfs

# 使用 lxcfs 运行容器
docker run -it \
  -v /var/lib/lxcfs/proc/cpuinfo:/proc/cpuinfo:rw \
  -v /var/lib/lxcfs/proc/diskstats:/proc/diskstats:rw \
  -v /var/lib/lxcfs/proc/meminfo:/proc/meminfo:rw \
  -v /var/lib/lxcfs/proc/stat:/proc/stat:rw \
  -v /var/lib/lxcfs/proc/swaps:/proc/swaps:rw \
  -v /var/lib/lxcfs/proc/uptime:/proc/uptime:rw \
  --cpus=2 --memory=4g \
  myapp

# 现在容器内 cat /proc/cpuinfo 只显示 2 核
# cat /proc/meminfo 只显示 4GB
```

---

## 六、JVM 容器感知

### 6.1 JVM 容器支持历史

| JDK 版本 | 支持情况 |
|---------|---------|
| JDK 8u131+ | 实验性支持（需手动开启） |
| JDK 8u191+ | 默认启用 `UseContainerSupport` |
| JDK 10+ | 完整支持，默认启用 |
| JDK 11+ | 支持 cgroups v2 |
| JDK 15+ | 完善的 cgroups v2 支持 |

### 6.2 关键参数

```bash
# JDK 8u131-8u190
java -XX:+UnlockExperimentalVMOptions \
     -XX:+UseCGroupMemoryLimitForHeap \
     -XX:MaxRAMFraction=2 \
     -jar app.jar

# JDK 8u191+ / JDK 11+（默认开启）
java -XX:+UseContainerSupport \
     -XX:MaxRAMPercentage=75.0 \
     -XX:InitialRAMPercentage=50.0 \
     -XX:MinRAMPercentage=50.0 \
     -jar app.jar

# 手动覆盖 CPU 核数（当自动检测不准确时）
java -XX:ActiveProcessorCount=2 -jar app.jar

# 验证 JVM 看到的资源
java -XX:+PrintContainerInfo -version
# 输出示例：
# OSContainer::active_processor_count: 2
# Memory Limit is: 4294967296
# Memory and Swap Limit is: 8589934592
```

### 6.3 堆内存设置建议

```
容器内存 limit = 4GB
  ├── JVM 堆（-Xmx）: 3GB（75%）
  ├── Metaspace: ~256MB
  ├── 线程栈: 线程数 × 1MB
  ├── Direct Memory / NIO buffers
  ├── JIT 编译代码缓存
  └── 操作系统 / native 内存

# 不要把 MaxRAMPercentage 设成 90% 以上，否则容易 OOM
# 75% 是一个安全的起点，根据实际 native 内存用量调整
```

---

## 七、Go/Python 在容器中的 CPU 感知问题

### 7.1 Go 的 GOMAXPROCS 问题

```go
// Go 默认：GOMAXPROCS = runtime.NumCPU()
// 在 64 核宿主机上，即使容器限制 2 核，GOMAXPROCS 也是 64
// 这导致：64 个 OS 线程竞争 2 核 CPU → 大量上下文切换

// 解决方案：使用 uber-go/automaxprocs
import _ "go.uber.org/automaxprocs"

// 它会读取 cgroup 的 CPU quota 并自动设置 GOMAXPROCS
// 输出：maxprocs: Updating GOMAXPROCS=2: determined from CPU quota
```

```bash
# 或手动设置环境变量
docker run -e GOMAXPROCS=2 --cpus=2 my-go-app
```

### 7.2 Python 的 cpu_count 问题

```python
import multiprocessing
print(multiprocessing.cpu_count())  # 返回 64（宿主机核数）

import os
print(os.cpu_count())  # 同样返回 64

# 在 Gunicorn 中尤其危险：
# gunicorn --workers $(( 2 * $(nproc) + 1 )) app:app
# 在 64 核宿主机上 → 129 个 worker！在 2 核容器中是灾难

# 解决方案一：手动指定
gunicorn --workers 4 app:app

# 解决方案二：从 cgroup 读取（Python 3.13+ 开始支持）
# Python 3.13 新增了 os.process_cpu_count() 读取 cgroup 限制

# 解决方案三：自定义函数读取 cgroup
def get_container_cpu_limit():
    """从 cgroup 读取容器 CPU 限制"""
    try:
        # cgroups v2
        with open("/sys/fs/cgroup/cpu.max") as f:
            parts = f.read().strip().split()
            if parts[0] == "max":
                return os.cpu_count()
            quota = int(parts[0])
            period = int(parts[1])
            return max(1, quota // period)
    except FileNotFoundError:
        pass
    try:
        # cgroups v1
        with open("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") as f:
            quota = int(f.read().strip())
        with open("/sys/fs/cgroup/cpu/cpu.cfs_period_us") as f:
            period = int(f.read().strip())
        if quota == -1:
            return os.cpu_count()
        return max(1, quota // period)
    except FileNotFoundError:
        return os.cpu_count()
```

---

## 八、排查清单与总结

### 容器资源问题排查清单

```
□ CPU 节流排查
  ├─ 查看 cpu.stat 中 nr_throttled / nr_periods 比例
  ├─ 节流率 > 25% → 增大 CPU limit 或去掉 limit
  ├─ 检查应用线程数是否远超 CPU limit
  └─ 确认应用是否正确感知 CPU 核数

□ OOM 排查
  ├─ kubectl describe pod 查看 OOMKilled 记录
  ├─ 区分 RSS 和 page cache（container_memory_working_set_bytes）
  ├─ 检查 JVM 堆内存 + native 内存是否超过 limit
  └─ 检查是否有内存泄漏（内存持续增长不回落）

□ 容器内观测
  ├─ 确认应用运行时是否正确感知 CPU/内存限制
  ├─ JVM: -XX:+UseContainerSupport（JDK 8u191+ 默认开启）
  ├─ Go: 使用 automaxprocs 库
  └─ Python: 手动设置 worker 数或从 cgroup 读取
```

### 关键指标对照表

| 指标 | 正常范围 | 告警阈值 | 采集来源 |
|------|---------|---------|---------|
| CPU 节流率 | < 5% | > 25% | cpu.stat |
| 内存使用率 | < 80% limit | > 90% limit | memory.current / memory.max |
| OOM Kill 次数 | 0 | > 0 | memory.events |
| GOMAXPROCS | = CPU limit | ≠ CPU limit | 运行时日志 |
| JVM 可用处理器数 | = CPU limit | = 宿主机核数 | PrintContainerInfo |
