# 阶段 2：Linux 性能观测工具链学习指南

> 本阶段目标：把阶段 0 的 OS 概念和阶段 1 的 USE 方法落到具体命令。学完后，能在 5 分钟内完成一轮主机级性能巡检。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-cpu-tools.md](./01-cpu-tools.md) | CPU 利用率、运行队列、进程/线程 CPU |
| 2 | [02-memory-tools.md](./02-memory-tools.md) | available、RSS、Swap、OOM、进程内存 |
| 3 | [03-disk-tools.md](./03-disk-tools.md) | iostat、await、util、fio 基准 |
| 4 | [04-network-tools.md](./04-network-tools.md) | ss、tcpdump、网卡错误、连接状态 |
| 5 | [05-tracing-profiling.md](./05-tracing-profiling.md) | strace、perf、ftrace，进入调用和系统调用层面 |
| 6 | [06-ebpf-bcc-bpftrace.md](./06-ebpf-bcc-bpftrace.md) | 进阶动态观测，按需学习 |

---

## 推荐巡检顺序

遇到“机器慢了”时，先按这个顺序快速判断：

```text
uptime/load
→ vmstat
→ mpstat / pidstat
→ free / pidstat -r
→ iostat
→ ss / ip -s link
→ dmesg
```

目标是先定位瓶颈资源，不要一上来就 `perf record`。

---

## 最小完成标准

学完后应该能做到：

- 看懂 `top`、`vmstat`、`mpstat`、`pidstat` 的关键列
- 看懂 `free -h` 中 `available` 的意义
- 用 `iostat -xz` 判断磁盘是否排队
- 用 `ss -s` 和 `ss -tan` 判断连接状态分布
- 用 `strace -c` 判断进程主要系统调用开销
- 知道什么时候该升级到 `perf` 或 eBPF

---

## 本阶段产物

输出一份 5 分钟巡检记录：

```text
时间：
服务：
CPU：
内存：
磁盘：
网络：
错误日志：
初步结论：
下一步要用的更细工具：
```

---

## 常见卡点

| 卡点 | 处理方式 |
|------|----------|
| 命令太多记不住 | 先记 USE 对应的最小命令集 |
| 输出列太多 | 每个工具先只关注 2-3 个关键列 |
| perf 权限不够 | 先用 pidstat/strace，后续再处理内核参数 |
| macOS 环境缺少 Linux 工具 | 尽量在 Linux VM、容器或云主机上练习 |

---

## 下一阶段衔接

阶段 2 解决“主机怎么看”。阶段 3 会把观察能力扩展到服务级：日志、指标、Trace 和告警。

