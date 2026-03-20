# 02 — 读懂系统指标

## 目标

服务出问题时，能在 60 秒内用命令行工具做出初步判断：是 CPU、内存、I/O 还是网络的问题。

## 数据源头：`/proc` 文件系统

Linux 所有监控工具的数据最终来自 `/proc`，理解这一点能帮助你看透工具背后的含义。

```bash
/proc/cpuinfo          # CPU 硬件信息
/proc/stat             # CPU 累计使用统计
/proc/meminfo          # 内存详细信息
/proc/net/dev          # 网络接口统计
/proc/{pid}/status     # 某进程状态
/proc/{pid}/fd/        # 进程打开的文件描述符
/proc/{pid}/maps       # 进程内存映射
```

## CPU 指标

### 工具
```bash
top / htop             # 实时总览
mpstat -P ALL 1        # 每核 CPU 使用率（需要 sysstat）
pidstat -u 1           # 按进程看 CPU
```

### 关键字段含义

| 字段 | 含义 | 异常信号 |
|------|------|---------|
| `us` | 用户态 CPU | 高 → 业务代码消耗 |
| `sy` | 内核态 CPU | 高 → 系统调用频繁（I/O、网络） |
| `wa` | 等待 I/O | 高 → 磁盘/网络 I/O 瓶颈 |
| `si` | 软中断 | 高 → 网络收包压力大 |
| `st` | 被虚拟机偷走 | 高 → 宿主机资源争抢（容器环境注意） |

### 知识点
- [ ] CPU 上下文切换：`vmstat 1` 看 `cs` 列
- [ ] 进程 vs 线程的调度单元区别
- [ ] Python GIL 对多线程 CPU 的影响

## 内存指标

### 工具
```bash
free -h                # 总览
vmstat 1               # 动态观察（关注 si/so swap）
/proc/meminfo          # 详细分解
```

### 关键字段含义

| 字段 | 含义 |
|------|------|
| RSS (Resident Set Size) | 实际占用物理内存 |
| VSZ (Virtual Size) | 虚拟地址空间大小，通常远大于 RSS |
| Cached | 文件系统缓存，可被回收 |
| Buffers | 块设备缓冲区 |
| Swap used | 用到 Swap → 内存不足，性能必然下降 |

### 知识点
- [ ] OOM Killer：进程被 kill 时如何确认（`dmesg | grep -i oom`）
- [ ] 内存泄漏特征：RSS 只增不减
- [ ] Python 内存：引用计数 + 循环引用 GC

## I/O 指标

### 工具
```bash
iostat -x 1            # 磁盘 I/O 详情
iotop -o               # 按进程看 I/O（需要 root）
```

### 关键字段含义

| 字段 | 含义 | 健康参考 |
|------|------|---------|
| `await` | I/O 平均等待时间 (ms) | HDD < 10ms，SSD < 1ms |
| `%util` | 磁盘利用率 | 持续 > 80% 需关注 |
| `r/s` `w/s` | 每秒读写次数 | 对比磁盘 IOPS 上限 |
| `rkB/s` `wkB/s` | 读写吞吐 | 对比磁盘带宽上限 |

### 知识点
- [ ] 随机 I/O vs 顺序 I/O 的性能差异（影响数据库选型）
- [ ] `sync` 调用对 `wa` 的影响
- [ ] 容器挂载卷的 I/O 性能损耗

## 网络指标

### 工具
```bash
ss -s                  # 连接状态汇总（替代 netstat）
ss -tnp                # 查看具体连接（进程、端口）
iftop -i eth0          # 实时带宽（需要安装）
```

### TCP 连接状态机（关键状态）

```
ESTABLISHED  → 正常连接
TIME_WAIT    → 主动关闭端等待，大量出现说明短连接频繁
CLOSE_WAIT   → 对端关闭但本端没关，通常是代码 bug（未关闭连接）
SYN_RECV     → 半连接队列，大量出现可能是 SYN flood
LISTEN       → 监听中
```

### 知识点
- [ ] `TIME_WAIT` 的作用与影响（`tcp_tw_reuse` 参数）
- [ ] 全连接队列（accept queue）vs 半连接队列（syn queue）
- [ ] `ss -ln` 查看 `Recv-Q` / `Send-Q`：队列满 = 服务处理不过来

## 文件描述符

```bash
lsof -p {pid} | wc -l      # 某进程打开的 fd 数量
cat /proc/{pid}/limits     # 该进程的 fd 限制
ulimit -n                  # 当前 shell 的 fd 软限制
```

### 知识点
- [ ] fd 泄漏的排查流程
- [ ] `ulimit -n 65535` 的正确设置位置（容器 vs 物理机）
- [ ] 每个 TCP 连接消耗 1 个 fd

## 用 Python 暴露系统指标

在 FastAPI 中集成 `psutil`，将系统指标以 JSON 形式暴露：

```python
import psutil

@router.get("/metrics/system")
async def system_metrics():
    return {
        "cpu_percent": psutil.cpu_percent(interval=0.1),
        "memory": psutil.virtual_memory()._asdict(),
        "disk_io": psutil.disk_io_counters()._asdict(),
        "net_io": psutil.net_io_counters()._asdict(),
        "open_files": len(psutil.Process().open_files()),
        "connections": len(psutil.Process().connections()),
    }
```

## 60 秒排查流程（速查）

```
1. top → 看 CPU 是 us/sy/wa 哪类高，找出高消耗进程
2. free -h → Swap 用了多少
3. iostat -x 1 → await 和 util 是否异常
4. ss -s → TIME_WAIT / CLOSE_WAIT 数量
5. lsof -p {pid} | wc -l → fd 数量是否接近上限
```

## 关键问题

1. `wa` 高但磁盘 `%util` 低，可能是什么原因？
2. 大量 `CLOSE_WAIT` 说明什么问题，在代码层面怎么定位？
3. Python 进程 RSS 持续增长，排查思路是什么？
