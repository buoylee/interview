# Socket 与内核网络

> 从网卡收到数据包到应用层 recv() 返回，中间经过了什么？理解内核收包/发包的完整流程，是排查网络性能瓶颈和理解零拷贝技术的前提。

---

## 1. Socket Buffer（sk_buff）

`sk_buff` 是 Linux 内核网络子系统的核心数据结构，每个网络数据包在内核中都表示为一个 `sk_buff`：

```
┌──────────────────────────────────────────────┐
│                  sk_buff                      │
│                                              │
│  ┌──────────┬──────────┬──────────┬────────┐ │
│  │   head   │   data   │   tail   │  end   │ │
│  └──────────┴──────────┴──────────┴────────┘ │
│       ▲          ▲          ▲          ▲      │
│       │          │          │          │      │
│  缓冲区起始  有效数据起始 有效数据结束  缓冲区结束 │
│                                              │
│  其他字段:                                    │
│  - protocol: 协议类型                         │
│  - dev: 网络设备                              │
│  - sk: 关联的 Socket                          │
│  - len: 数据长度                              │
│  - 各层头部指针: mac_header, network_header... │
└──────────────────────────────────────────────┘
```

### 发送缓冲区（wmem）与接收缓冲区（rmem）

每个 TCP Socket 有发送和接收两个缓冲区：

```
应用层                         应用层
  │ send()                       │ recv()
  ▼                              ▲
┌──────────┐               ┌──────────┐
│ 发送缓冲区│               │ 接收缓冲区│
│ (wmem)   │               │ (rmem)   │
│ sk_buff  │               │ sk_buff  │
│ sk_buff  │               │ sk_buff  │
│ sk_buff  │               │ sk_buff  │
└────┬─────┘               └────┬─────┘
     │                          ▲
     ▼                          │
   协议栈发送                  协议栈接收
```

```bash
# 查看 Socket Buffer 大小配置
sysctl net.ipv4.tcp_rmem
# min  default  max
# 4096 131072   6291456
# 最小 4KB，默认 128KB，最大 6MB

sysctl net.ipv4.tcp_wmem
# 4096 16384 4194304
# 最小 4KB，默认 16KB，最大 4MB

# 系统级别的总 Socket Buffer 内存限制
sysctl net.ipv4.tcp_mem
# 单位是页面(4KB)，三个值分别是 low/pressure/high

# 查看单个 Socket 的缓冲区使用
ss -tm dst :8080
# 输出 skmem:(r<rmem>,rb<rmem_alloc>,t<wmem>,tb<wmem_alloc>,...)
```

**调优建议**：高吞吐场景（大文件传输、流式处理）需要增大 `tcp_rmem` 和 `tcp_wmem` 的最大值。TCP 窗口大小受限于缓冲区大小，缓冲区太小会限制吞吐量。

```bash
# 高吞吐场景的推荐配置
sysctl net.ipv4.tcp_rmem="4096 87380 16777216"    # 最大 16MB
sysctl net.ipv4.tcp_wmem="4096 65536 16777216"     # 最大 16MB
sysctl net.core.rmem_max=16777216
sysctl net.core.wmem_max=16777216

# 启用窗口缩放（默认已开启）
sysctl net.ipv4.tcp_window_scaling=1
```

---

## 2. 内核收包完整流程

这是理解网络性能的核心知识点。以下是一个数据包从网卡到应用层的完整旅程：

```
                    ┌─────────────────────────────────────────┐
                    │              应用层                      │
                    │  recv()/read() 从 Socket Buffer 取数据   │
                    └────────────────────┬────────────────────┘
                                         ▲ ⑧
                    ┌────────────────────┴────────────────────┐
                    │           Socket Buffer (rmem)           │
                    └────────────────────┬────────────────────┘
                                         ▲ ⑦
                    ┌────────────────────┴────────────────────┐
                    │         传输层 (TCP/UDP 处理)             │
                    │  校验和验证、查找 Socket、放入接收队列      │
                    └────────────────────┬────────────────────┘
                                         ▲ ⑥
                    ┌────────────────────┴────────────────────┐
                    │         网络层 (IP 处理)                  │
                    │  IP 校验、路由查找、iptables/netfilter    │
                    └────────────────────┬────────────────────┘
                                         ▲ ⑤
                    ┌────────────────────┴────────────────────┐
                    │         NAPI poll 处理                    │
                    │  从 Ring Buffer 取 sk_buff               │
                    │  调用 netif_receive_skb()                │
                    └────────────────────┬────────────────────┘
                                         ▲ ④
                    ┌────────────────────┴────────────────────┐
                    │          NET_RX 软中断                    │
                    │  ksoftirqd 或硬中断返回时执行              │
                    └────────────────────┬────────────────────┘
                                         ▲ ③ 触发软中断
                    ┌────────────────────┴────────────────────┐
                    │          硬中断处理                       │
                    │  快速响应，调度 NAPI                      │
                    └────────────────────┬────────────────────┘
                                         ▲ ② 中断通知 CPU
                    ┌────────────────────┴────────────────────┐
                    │          DMA 传输                         │
                    │  网卡通过 DMA 将数据写入 Ring Buffer       │
                    └────────────────────┬────────────────────┘
                                         ▲ ① 数据到达网卡
                    ┌────────────────────┴────────────────────┐
                    │              物理网卡                     │
                    └─────────────────────────────────────────┘
```

### 详细步骤

1. **网卡收到数据帧**，进行 MAC 地址过滤
2. **DMA 传输**：网卡通过 DMA 将数据写入预先分配的 Ring Buffer（环形缓冲区），无需 CPU 参与
3. **硬中断**：网卡触发硬中断通知 CPU"有数据来了"
4. **硬中断处理**：快速执行（几 us），主要工作是调度 NAPI（关闭网卡中断，防止中断风暴），然后触发 NET_RX 软中断
5. **NAPI poll**：软中断处理函数从 Ring Buffer 批量取出 sk_buff，提交给协议栈
6. **协议栈处理**：IP 层解析、TCP 层处理（序号、确认、流控等）
7. **放入 Socket Buffer**：数据被放入目标 Socket 的接收缓冲区
8. **应用层读取**：`recv()` 系统调用从 Socket Buffer 拷贝数据到用户空间

```bash
# 查看 Ring Buffer 大小
ethtool -g eth0
# Pre-set maximums / Current hardware settings

# 调整 Ring Buffer 大小（增大可减少丢包，但增加延迟）
ethtool -G eth0 rx 4096 tx 4096

# 查看网卡丢包统计
ethtool -S eth0 | grep -i drop
ifconfig eth0 | grep dropped
```

---

## 3. 内核发包流程

```
应用层 send()/write()
    │ ①
    ▼
Socket Buffer (wmem)        用户数据拷贝到内核 sk_buff
    │ ②
    ▼
传输层 (TCP)                 分段、计算校验和、序号管理
    │ ③
    ▼
网络层 (IP)                  路由查找、添加 IP 头、iptables
    │ ④
    ▼
邻居子系统                    ARP 解析 MAC 地址
    │ ⑤
    ▼
设备队列 (qdisc)             排队规则（TC 流控在这里生效）
    │ ⑥
    ▼
网卡驱动                      将 sk_buff 放入 TX Ring Buffer
    │ ⑦ DMA
    ▼
物理网卡                      通过 DMA 读取数据并发送
    │ ⑧
    ▼
网卡发送完成中断              释放 sk_buff
```

```bash
# 查看发送队列长度
ip link show eth0 | grep qlen
# 或
ifconfig eth0 | grep txqueuelen

# 调整发送队列长度
ip link set eth0 txqueuelen 10000
```

---

## 4. 网卡多队列与 RSS

### 问题

单队列网卡的所有中断都由一个 CPU 核心处理，高流量时该核心成为瓶颈：

```
所有网络中断 → CPU 0 (si 100%) ← 瓶颈！
               CPU 1 (空闲)
               CPU 2 (空闲)
               CPU 3 (空闲)
```

### RSS（Receive Side Scaling）

多队列网卡通过 RSS 将不同数据流分配到不同的硬件队列，每个队列绑定不同的 CPU 核心：

```
数据包流 A ─→ Queue 0 ─→ 中断 → CPU 0
数据包流 B ─→ Queue 1 ─→ 中断 → CPU 1
数据包流 C ─→ Queue 2 ─→ 中断 → CPU 2
数据包流 D ─→ Queue 3 ─→ 中断 → CPU 3

分流依据：对源IP+目标IP+源端口+目标端口做 Hash → 同一连接的包始终去同一队列
```

```bash
# 查看网卡队列数
ethtool -l eth0
# Combined: 当前队列数 / 最大队列数

# 设置队列数 = CPU 核心数
ethtool -L eth0 combined 8

# 查看中断亲和性（哪个队列绑定哪个 CPU）
cat /proc/interrupts | grep eth0

# 设置中断亲和性
# 使用 irqbalance 服务自动均衡
systemctl start irqbalance

# 或手动设置
echo 1 > /proc/irq/<irq_number>/smp_affinity  # 绑定到 CPU 0
echo 2 > /proc/irq/<irq_number>/smp_affinity  # 绑定到 CPU 1
```

### RPS/RFS（软件层面的分流）

如果网卡不支持多队列，可以用 RPS（Receive Packet Steering）在软件层面将数据包分散到多个 CPU：

```bash
# 启用 RPS，分散到所有 CPU（8 核 = ff）
echo ff > /sys/class/net/eth0/queues/rx-0/rps_cpus

# 启用 RFS（Receive Flow Steering），保持流与处理它的 CPU 关联
echo 32768 > /proc/sys/net/core/rps_sock_flow_entries
echo 4096 > /sys/class/net/eth0/queues/rx-0/rps_flow_cnt
```

---

## 5. 中断合并（Interrupt Coalescing）

每个数据包触发一次中断效率太低。中断合并让网卡积累多个数据包后再触发一次中断：

```
不合并：  包→中断  包→中断  包→中断  包→中断   (4次中断/4个包)
合并后：  包 包 包 包 → 中断                    (1次中断/4个包)
```

**权衡**：
- 合并更多 → 吞吐量更高，但延迟更大
- 合并更少 → 延迟更低，但 CPU 中断开销更大

```bash
# 查看当前中断合并配置
ethtool -c eth0
# rx-usecs: 接收中断延迟(微秒)
# rx-frames: 接收多少帧后触发中断
# adaptive-rx: 自适应模式

# 低延迟场景（金融交易等）
ethtool -C eth0 rx-usecs 0 rx-frames 1  # 收到即中断

# 高吞吐场景
ethtool -C eth0 rx-usecs 100 rx-frames 64

# 自适应模式（推荐，让驱动自动调整）
ethtool -C eth0 adaptive-rx on adaptive-tx on
```

---

## 6. 零拷贝技术

传统文件传输（read + write/send）需要多次数据拷贝：

```
传统方式（4 次拷贝 + 4 次上下文切换）：

磁盘 ──DMA──► 内核 Page Cache ──CPU──► 用户缓冲区
                                          │
                                       CPU 拷贝
                                          ▼
用户缓冲区 ──CPU──► Socket Buffer ──DMA──► 网卡

4 次拷贝: 磁盘→内核, 内核→用户, 用户→Socket, Socket→网卡
4 次切换: read进内核, read返回, write进内核, write返回
```

### sendfile（最常用的零拷贝）

```
sendfile（2-3 次拷贝，0 次用户态/内核态切换数据拷贝）：

磁盘 ──DMA──► 内核 Page Cache ──CPU/DMA──► Socket Buffer ──DMA──► 网卡

数据不经过用户空间！只需一次系统调用。
支持 DMA Scatter/Gather 的网卡可以再省一次 CPU 拷贝。
```

```c
// sendfile 系统调用
ssize_t sendfile(int out_fd, int in_fd, off_t *offset, size_t count);
// out_fd: Socket fd
// in_fd: 文件 fd
```

应用场景：Nginx 静态文件服务、Kafka 消费者读取日志发送给客户端。

```nginx
# Nginx 开启 sendfile
http {
    sendfile on;
    tcp_nopush on;  # 配合 sendfile，在 sendfile 完成前不发送数据
}
```

### mmap（内存映射）

```
mmap（3 次拷贝，减少 CPU 拷贝）：

磁盘 ──DMA──► 内核 Page Cache ◄── mmap 映射 ──► 用户虚拟地址
                      │
                  CPU 拷贝
                      ▼
              Socket Buffer ──DMA──► 网卡

用户空间和内核共享 Page Cache 页面，省去了 read 的一次 CPU 拷贝。
但 write 时仍需要从 Page Cache 拷贝到 Socket Buffer。
```

### splice（管道零拷贝）

```c
ssize_t splice(int fd_in, off_t *off_in, int fd_out, off_t *off_out, size_t len, unsigned int flags);
```

在两个文件描述符之间移动数据，不经过用户空间。要求至少一端是管道（pipe）。

### io_uring（现代异步 I/O）

Linux 5.1 引入的 io_uring 不仅支持异步 I/O，还支持零拷贝发送（Linux 6.0+）：

```
io_uring 的优势：
1. 通过共享内存的环形队列提交/完成 I/O，减少系统调用
2. 支持 SQE 批量提交
3. 支持固定缓冲区注册，减少内存映射开销
4. Linux 6.0+ 支持 IORING_OP_SEND_ZC（零拷贝发送）
```

### 各技术对比

| 技术 | 拷贝次数 | 系统调用 | 适用场景 |
|------|----------|----------|----------|
| read + write | 4 次 | 2 次 | 通用但低效 |
| mmap + write | 3 次 | 2 次 | 需要处理数据的场景 |
| sendfile | 2-3 次 | 1 次 | 文件直接发网络（最常用）|
| splice | 2 次 | 1 次 | 管道场景 |
| io_uring send_zc | 0-2 次 | 0 次 (共享内存) | 现代高性能网络 |

---

## 7. 实用诊断命令速查

```bash
# 网卡统计（丢包、错误）
ethtool -S eth0 | grep -iE "drop|error|miss"

# Ring Buffer 溢出检查
ethtool -S eth0 | grep rx_missed

# 查看网卡队列和中断分布
cat /proc/interrupts | grep eth0

# 查看软中断处理统计
cat /proc/net/softnet_stat
# 每行对应一个 CPU，第二列是溢出次数

# Socket Buffer 内存使用
cat /proc/net/sockstat

# 查看 TCP 连接的内核参数
ss -tnip dst :80

# 抓包分析
tcpdump -i eth0 -nn -c 1000 port 8080 -w capture.pcap
```

---

## 要点总结

1. **收包流程很长**——网卡 -> DMA -> Ring Buffer -> 硬中断 -> NAPI 软中断 -> 协议栈 -> Socket Buffer -> 用户空间。任何一步都可能成为瓶颈。
2. **Ring Buffer 太小导致丢包**——高流量时第一个要检查的就是 Ring Buffer 溢出，用 `ethtool -S` 查看。
3. **单核软中断瓶颈**——通过 RSS 多队列或 RPS 将网络处理分散到多核。
4. **Socket Buffer 大小限制吞吐量**——高带宽延迟积（BDP）场景需要增大 `tcp_rmem/tcp_wmem` 最大值。
5. **零拷贝减少 CPU 开销**——静态文件用 sendfile，Kafka 用 sendfile + Page Cache，现代应用可以考虑 io_uring。
6. **中断合并是吞吐量与延迟的权衡**——大多数场景用自适应模式即可。
