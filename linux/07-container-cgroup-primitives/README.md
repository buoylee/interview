# 07 容器与 cgroup 原语

> **这章解决什么问题**
>
> 容器不是一台小虚拟机。它本质上还是宿主机上的 Linux 进程，只是被 namespace 改变了「看见什么」，被 cgroup 限制了「能用多少」。如果这一层不清楚，就很难解释 Kubernetes 里的 CPU throttling、OOMKilled、容器内 `/proc` 误判、JVM/Go runtime 资源识别问题。

**依赖**：

- 虚拟地址空间、RSS、page cache → [`linux/01-memory-primitives`](../01-memory-primitives/README.md)
- 进程、线程、调度、上下文切换 → [`linux/02-execution-primitives`](../02-execution-primitives/README.md)
- fd、mount、文件系统视角 → [`linux/03-io-primitives`](../03-io-primitives/README.md)
- 容器动手课 → [`linux-handson/09-containers-from-linux`](../../linux-handson/09-containers-from-linux/README.md)

**三层怎么读：**

- **① 你视角** — 从 Docker/Kubernetes 里看到的 container、pod、limit、request 搭桥。
- **② 黑盒内部** — namespace、cgroup、overlayfs 分别解决什么问题。
- **③ 砸实** — 用 `/proc/self/ns`、`/proc/self/cgroup`、`/sys/fs/cgroup` 看真实限制。

---

## 原语一：容器首先是宿主机上的普通进程

### ① 你视角

你在 Docker 里运行：

```bash
docker run nginx
```

看起来像启动了一台轻量机器。但从宿主机内核看，它只是启动了一个或多个进程。

### ② 黑盒内部

虚拟机和容器的边界不同：

| 技术 | 边界 |
|---|---|
| 虚拟机 | 有独立 guest kernel，通过 hypervisor 虚拟硬件 |
| 容器 | 共享宿主机 kernel，通过 namespace/cgroup 隔离进程 |

容器运行时做的事情大致是：

```text
create process
  → put process into namespaces
  → put process into cgroups
  → set root filesystem / mounts
  → apply capabilities / seccomp / LSM policy
  → exec container entrypoint
```

所以容器里的 Java/Go 进程，最终仍然由同一个 Linux scheduler 调度，仍然用同一个内核的 page fault、fd、socket、futex、signal。

### ③ 砸实

```bash
ps -ef | grep nginx
cat /proc/self/status | grep -E 'NSpid|NStgid'
```

看点：

- 宿主机上能看到容器进程，只是 PID 可能和容器内看到的不一样。
- `NSpid` 会显示当前进程在嵌套 PID namespace 中的不同 PID。

---

## 原语二：namespace 改变的是「看见什么」

### ① 你视角

容器里执行 `ps`，通常只看到容器内进程；执行 `hostname`，看到容器自己的 hostname；看网络接口，也像是自己有一套网络。这些都来自 namespace。

### ② 黑盒内部

namespace 是 Linux 对全局资源视图做隔离的机制。常见类型：

| namespace | 隔离什么 |
|---|---|
| PID | 进程号空间，容器内 PID 1 不一定是宿主机 PID 1 |
| Mount | 挂载点视图，容器可以有自己的 rootfs |
| Network | 网卡、IP、路由表、端口空间 |
| UTS | hostname、domain name |
| IPC | System V IPC、POSIX message queue |
| User | UID/GID 映射，支持容器内 root 映射到宿主普通用户 |
| Cgroup | cgroup 层级视图 |

namespace 不负责限制 CPU/内存用量。它只改变进程看到的世界：

```text
same host kernel
  process A in namespace X sees PID 1, eth0, /
  process B in namespace Y sees PID 1, eth0, /
```

两边都可能以为自己有 PID 1、自己的网络、自己的文件系统视角，但底下仍然是同一个内核。

### ③ 砸实

```bash
ls -l /proc/self/ns
readlink /proc/self/ns/pid
readlink /proc/self/ns/net
```

看点：

- `/proc/<pid>/ns/*` 是 namespace 句柄。
- 两个进程对应 namespace inode 相同，表示它们在同一个 namespace。
- `nsenter` 可以进入某个进程的 namespace 视角排查问题。

---

## 原语三：cgroup 限制的是「能用多少」

### ① 你视角

Kubernetes 里你写：

```yaml
resources:
  limits:
    cpu: "1"
    memory: 512Mi
```

这不是给容器创建了专属 CPU 或专属内存条，而是把进程放进 cgroup，并设置资源控制规则。

### ② 黑盒内部

cgroup 是 Linux 对进程组施加资源控制和统计的机制。它的核心对象不是「容器」，而是 **一组进程**。

常见 controller：

| controller | 控制什么 |
|---|---|
| cpu | CPU quota、权重、throttling 统计 |
| memory | 内存上限、当前用量、OOM 事件 |
| pids | 进程/线程数量上限 |
| io | 块设备 IO 权重/限制 |
| cpuset | 绑定可用 CPU / NUMA node |

cgroup v2 常见文件：

```text
/sys/fs/cgroup/
  cgroup.controllers
  cgroup.procs
  cpu.max
  cpu.stat
  memory.max
  memory.current
  memory.events
  pids.max
  pids.current
```

### ③ 砸实

```bash
cat /proc/self/cgroup
cat /sys/fs/cgroup/cpu.max
cat /sys/fs/cgroup/memory.max
cat /sys/fs/cgroup/memory.current
cat /sys/fs/cgroup/memory.events
```

看点：

- `max` 通常表示没有设置硬上限。
- 容器内读到的路径取决于 runtime、cgroup v1/v2、挂载方式。
- 排查时要确认你看的 cgroup 文件确实对应目标进程。

---

## 原语四：CPU limit 不是分配一个 CPU，而是 quota + period

### ① 你视角

Pod 设置 `cpu: 1` 后，你可能以为它独占 1 个 CPU。实际不是。它只是被限制在一个周期内最多用多少 CPU 时间。

这解释了一个常见现象：服务平均 CPU 不高，但延迟突然飙升，因为它在某些时间片被 throttled。

### ② 黑盒内部

cgroup v2 用 `cpu.max` 表示 CPU 上限：

```text
quota period
```

例如：

```text
100000 100000
```

表示每 100ms 周期最多用 100ms CPU 时间，相当于 1 core 的 quota。

```text
200000 100000
```

表示每 100ms 周期最多用 200ms CPU 时间，相当于 2 cores 的 quota。

如果一个 cgroup 在周期内把 quota 用完，里面的 runnable 线程即使还有工作，也会被 throttled 到下个周期：

```text
period starts
  threads run and consume quota
  quota exhausted
    → throttled
  next period
    → runnable again
```

所以 CPU limit 影响的不是「有没有线程可运行」，而是「调度器是否允许这个 cgroup 继续消耗 CPU 时间」。

### ③ 砸实

```bash
cat /sys/fs/cgroup/cpu.max
cat /sys/fs/cgroup/cpu.stat
```

常见字段：

| 字段 | 意思 |
|---|---|
| `usage_usec` | cgroup 已消耗 CPU 时间 |
| `nr_periods` | 经历了多少 quota 周期 |
| `nr_throttled` | 有多少周期发生过 throttling |
| `throttled_usec` | 总共被 throttle 的时间 |

排查延迟时，不要只看 CPU 使用率。还要看 `nr_throttled` 和 `throttled_usec` 是否在增长。

---

## 原语五：memory limit 包含匿名内存，也可能包含 page cache

### ① 你视角

容器设置 `memory: 512Mi` 后，Java 进程不一定只因为 heap 大才 OOM。文件读写带来的 page cache、native memory、线程栈、direct buffer、mmap 区域都可能算进 cgroup 内存。

### ② 黑盒内部

cgroup memory 统计的是这个进程组对内存资源的占用，不等于 JVM heap。

常见组成：

```text
memory.current
  anonymous memory
  file cache / page cache
  tmpfs
  kernel memory accounting
  thread stacks
  mmap/direct buffer/native allocations
```

当 `memory.current` 接近 `memory.max`，内核会先尝试回收可回收页。如果无法回收到足够空间，就触发 cgroup OOM，在这个 cgroup 内选择进程杀掉。

```text
allocation request
  → memory.current would exceed memory.max
  → reclaim
  → still not enough
  → cgroup OOM
  → kill process in cgroup
```

Kubernetes 看到的 `OOMKilled`，很多时候就是这个路径的结果。

### ③ 砸实

```bash
cat /sys/fs/cgroup/memory.current
cat /sys/fs/cgroup/memory.max
cat /sys/fs/cgroup/memory.events
cat /proc/self/status | grep -E 'VmRSS|VmSize|Threads'
```

看点：

- `memory.events` 里的 `oom` / `oom_kill` 增长，说明发生过 cgroup OOM。
- `VmRSS` 是进程视角；`memory.current` 是 cgroup 视角。两者不是同一个口径。
- 容器里 page cache 也可能推动 `memory.current` 上升。

---

## 原语六：容器内 `/proc` 可能让 runtime 误判资源

### ① 你视角

老版本 JVM、Go runtime 或应用库在容器里可能把宿主机 CPU 核数/内存当成可用资源，导致：

- JVM heap 算太大，被 cgroup OOMKill。
- 线程池按宿主机核数开太大，CPU quota 下反而频繁抢占和 throttling。
- metrics 里看到的内存/CPU 口径和 Kubernetes 不一致。

### ② 黑盒内部

`/proc` 是内核导出的进程/系统视图，但它不天然等于「当前容器的资源上限」。

例如：

```text
/proc/cpuinfo      可能显示宿主机 CPU 信息
/proc/meminfo      可能显示宿主机内存信息
/proc/self/status  当前进程状态
/proc/self/cgroup  当前进程所属 cgroup
/sys/fs/cgroup/*   cgroup 真实限制与统计
```

现代 runtime 通常会做 cgroup-aware 适配，但你仍然需要知道差异来源：namespace 改变视图，cgroup 记录限制，`/proc` 里的不同文件口径不一定一致。

### ③ 砸实

```bash
nproc
grep -c '^processor' /proc/cpuinfo
cat /proc/meminfo | head
cat /proc/self/cgroup
cat /sys/fs/cgroup/cpu.max
cat /sys/fs/cgroup/memory.max
```

看点：

- `nproc`、`/proc/cpuinfo`、`cpu.max` 可能给出不同口径。
- 对容器资源排查，优先回到 cgroup 文件确认上限和当前值。

---

## 原语七：overlayfs 让镜像层看起来像一个文件系统

### ① 你视角

Docker 镜像是一层层 build 出来的，但容器里看起来像一个普通目录树。你在容器里写文件，也不会直接改掉只读镜像层。

### ② 黑盒内部

overlayfs 把多个目录叠成一个统一视图：

```text
lowerdir 只读镜像层
upperdir 容器可写层
workdir  overlayfs 工作目录
merged   容器看到的合并视图
```

读文件时：

- 如果 upperdir 有修改后的版本，读 upperdir。
- 否则读 lowerdir。

写文件时：

- 原来只在 lowerdir 的文件会先 copy-up 到 upperdir。
- 后续修改发生在 upperdir。

这解释了为什么容器写大量小文件可能比你想象中贵，也解释了为什么镜像层不可变、容器层可丢弃。

### ③ 砸实

```bash
mount | grep overlay
df -h
```

看点：

- 容器内 rootfs 常见类型是 overlay。
- 存储性能问题要区分 overlayfs、宿主机文件系统、volume、网络盘。

---

## 本章速查

| 问题 | 回到哪个原语 |
|---|---|
| 容器是不是 VM | 容器是宿主机进程，共享 kernel |
| 容器里为什么看不到宿主进程 | PID namespace 改变进程视图 |
| CPU limit 为什么导致延迟 | cgroup CPU quota 用完后 throttling |
| memory limit 为什么杀进程 | cgroup memory 触顶后 OOMKill |
| JVM heap 明明不大为什么 OOM | cgroup 内存包括 heap 之外的 native/page cache/stack 等 |
| `/proc` 和 K8s 指标不一致 | `/proc` 与 cgroup 口径不同 |

**最小心智模型**：

```text
container = process
  + namespaces  改变看见什么
  + cgroups     限制能用多少
  + overlayfs   提供镜像/可写层文件系统视图
  + security policy 限制能做什么
```

下一章：[`08 权限与安全原语`](../08-permission-security-primitives/README.md)
