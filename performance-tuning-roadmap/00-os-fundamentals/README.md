# 阶段 0：操作系统基础学习指南

> 本阶段目标：建立性能排查的底层语言。学完后，看到 CPU、内存、磁盘、网络相关指标时，能知道它们背后的 OS 机制，而不是只记命令。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [05-process-thread-coroutine.md](./05-process-thread-coroutine.md) | 先理解进程、线程、协程和文件描述符，建立运行单元模型 |
| 2 | [01-cpu-architecture-scheduling.md](./01-cpu-architecture-scheduling.md) | 理解 CPU、调度、上下文切换、中断 |
| 3 | [02-memory-management.md](./02-memory-management.md) | 理解虚拟内存、Page Fault、Swap、OOM |
| 4 | [04a-network-tcp-core.md](./04a-network-tcp-core.md) | 理解 TCP 状态、拥塞控制、TIME_WAIT |
| 5 | [04b-network-socket-kernel.md](./04b-network-socket-kernel.md) | 理解 Socket Buffer、内核收发包、网卡队列 |
| 6 | [03-disk-io-filesystem.md](./03-disk-io-filesystem.md) | 理解 Page Cache、I/O 调度、fsync |

原编号按知识领域组织；初学时建议先学进程/线程，再学 CPU、内存、网络和磁盘。

---

## 本阶段主线

性能问题最终会落到四类资源：

```text
CPU：执行不过来，或者调度/上下文切换太多
内存：放不下，或者频繁换页、OOM、GC 压力高
磁盘：读写慢、队列长、fsync 阻塞
网络：连接慢、丢包、重传、Socket 队列堆积
```

阶段 0 不要求立即调优，只要求能解释“指标为什么会变差”。

---

## 最小完成标准

学完后应该能做到：

- 解释 load average 和 CPU 使用率为什么不是同一个东西
- 解释 RSS、VIRT、Page Cache、Swap、OOM 的区别
- 解释 ESTABLISHED、TIME_WAIT、CLOSE_WAIT 的意义
- 解释 iowait 高和磁盘真的慢之间的关系
- 能把一个性能现象归类到 CPU、内存、磁盘、网络或调度问题

---

## 本阶段练习

选择一个正在运行的服务，完成：

```text
进程 PID：
线程数量：
打开文件描述符数量：
TCP 连接状态分布：
RSS / VIRT：
是否使用 Swap：
观察到的异常：
我的解释：
```

建议命令：

```bash
cat /proc/<pid>/status
ls /proc/<pid>/fd | wc -l
ss -tan | awk '{print $1}' | sort | uniq -c
```

---

## 常见误区

| 误区 | 正确理解 |
|------|----------|
| CPU 使用率高一定是坏事 | 要结合运行队列和延迟判断是否饱和 |
| free 很低说明内存不够 | Linux 会把空闲内存用于 Page Cache，要看 available |
| TIME_WAIT 多一定要调内核参数 | 优先检查是否大量短连接，先用连接池解决 |
| iowait 高一定是磁盘坏了 | 也可能是应用阻塞在慢 I/O 或队列堆积 |

---

## 下一阶段衔接

阶段 0 解决“指标背后的机制”。阶段 1 会教你如何组织排查过程，阶段 2 会把这些机制落到具体 Linux 工具。

