# 丢包与延迟分析

## 概述

丢包和高延迟是网络性能问题中最常见的两类。它们直接表现为应用层的"请求慢"或"偶发超时"。定位这类问题需要从应用层深入到网络层和传输层，区分是网络本身的问题还是主机配置的问题。

---

## 一、丢包分析方法

### 查看内核统计

```bash
# 方法 1：/proc/net/snmp 看 TCP 统计
cat /proc/net/snmp | grep Tcp
# Tcp: ... InSegs OutSegs RetransSegs InErrs OutRsts ...
# 关键字段：
#   RetransSegs — TCP 重传的段数
#   InErrs      — 接收到的错误段数
#   OutRsts     — 发出的 RST 段数

# 计算重传率
# 重传率 = RetransSegs / OutSegs
# 正常环境 < 0.1%，超过 1% 需要关注，超过 5% 是严重问题
```

```bash
# 方法 2：netstat -s 看详细统计
netstat -s | grep -i retrans
#   123456 segments retransmitted         ← 重传总次数
#   789 fast retransmits                  ← 快速重传次数
#   234 retransmits in slow start         ← 慢启动阶段重传
#   56 SACK retransmits failed            ← SACK 重传失败

# 持续监控重传增量
watch -d -n 1 'netstat -s | grep -i retrans'
# -d 高亮变化的部分
```

```bash
# 方法 3：ss -ti 看单连接级别的重传
ss -ti dst 10.0.1.50
# 输出类似：
# ESTAB 0 0 10.0.1.1:54321 10.0.1.50:8080
#   cubic wscale:7,7 rto:204 rtt:1.5/0.5 ato:40 mss:1460
#   cwnd:10 ssthresh:7 send 77.9Mbps retrans:0/5 rcv_space:29200
#                                      ↑
#                                retrans:当前未确认的重传/历史总重传

# retrans:3/50 表示当前有 3 个段在等待重传确认，历史共重传过 50 次
```

### 区分超时重传和快速重传

```
超时重传（Timeout Retransmission）：
  发送数据后等待 ACK，超过 RTO（Retransmission Timeout）仍未收到
  → 比较"重"，会触发拥塞窗口减半甚至重置
  → 通常意味着网络严重丢包或中断

快速重传（Fast Retransmission）：
  发送方收到 3 个重复 ACK，推断某个包丢了
  → 比较"轻"，不需要等超时
  → 通常是偶发丢包，网络整体可用

查看区分：
netstat -s | grep -E "fast retransmit|timeout"
```

### 各层丢包检查

```bash
# 网卡层丢包
ip -s link show eth0
# 关注：
# RX errors / dropped / overruns / frame
# TX errors / dropped / carrier / collisions

# 如果 RX dropped 增长 → 内核来不及处理（ring buffer 满）
ethtool -g eth0        # 查看 ring buffer 大小
ethtool -G eth0 rx 4096  # 增大 ring buffer

# 网卡流量统计
ethtool -S eth0 | grep -i drop
ethtool -S eth0 | grep -i error

# 内核网络栈丢包
cat /proc/net/softnet_stat
# 每行对应一个 CPU 核，第二列是丢包数（backlog 满导致）
# 如果第二列增长 → 需要增大 netdev_max_backlog
```

---

## 二、MTU 与分片问题

### Path MTU Discovery

```
MTU（Maximum Transmission Unit）：链路层一个帧能承载的最大数据大小
以太网默认 MTU = 1500 字节

TCP MSS = MTU - IP Header(20) - TCP Header(20) = 1460 字节

问题场景：
  Client (MTU=1500) → Router (MTU=1400) → Server (MTU=1500)

  如果客户端发了 1500 字节的包，到路由器时超过了 1400 的 MTU
  → 如果设了 DF（Don't Fragment）标志 → 路由器丢弃并回 ICMP
    "Fragmentation Needed"
  → 如果没设 DF → 路由器做分片（增加开销和风险）
```

### 检测 MTU 问题

```bash
# 用 ping 检测 Path MTU
# 发送指定大小的包并设置 DF 标志
ping -M do -s 1472 10.0.1.50
# -M do   设置 DF（Don't Fragment）
# -s 1472 数据部分大小（1472 + 8 ICMP header + 20 IP header = 1500）

# 如果收到 "Frag needed and DF set (mtu = 1400)"
# 说明路径上某处 MTU 是 1400

# 逐步减小大小找到 Path MTU
ping -M do -s 1400 10.0.1.50   # 成功
ping -M do -s 1450 10.0.1.50   # 失败 → Path MTU 在 1400-1450 之间
ping -M do -s 1420 10.0.1.50   # 二分查找...

# 查看系统缓存的 Path MTU
ip route get 10.0.1.50
# 输出中可能包含 mtu 值
```

### 常见 MTU 问题场景

```
1. VPN/隧道环境
   原始 MTU: 1500
   VPN 封装开销: ~50-60 字节
   实际可用 MTU: ~1440-1450
   → 如果 ICMP 被防火墙阻止，Path MTU Discovery 失效
   → TCP 大包被静默丢弃（黑洞路由）

2. Docker / Kubernetes 网络
   宿主机 MTU: 1500
   Overlay 网络（如 VXLAN）封装开销: 50 字节
   容器实际 MTU: 1450
   → 需要在 CNI 配置中正确设置 MTU

3. 症状识别
   - 小包（如健康检查、简单 GET）正常
   - 大包（如 POST 大 JSON、文件传输）卡住或超时
   → 高度怀疑 MTU 问题
```

### 修复 MTU 问题

```bash
# 临时修改接口 MTU
ip link set eth0 mtu 1400

# 永久修改（systemd-networkd）
# /etc/systemd/network/10-eth0.network
# [Link]
# MTUBytes=1400

# TCP 层面自动处理：MSS Clamping
iptables -t mangle -A FORWARD -p tcp --tcp-flags SYN,RST SYN \
  -j TCPMSS --clamp-mss-to-pmtu
# 在 SYN 包中自动调整 MSS 为 Path MTU 对应的值
```

---

## 三、网络延迟定位

### traceroute

```bash
# 基本用法
traceroute 10.0.1.50
# 显示从源到目标的每一跳路由器及延迟

# 输出示例：
# 1  gateway (192.168.1.1)     0.5ms  0.4ms  0.5ms
# 2  isp-router (10.10.0.1)   5.2ms  5.1ms  5.3ms
# 3  * * *                                         ← 某跳不响应
# 4  datacenter (10.0.0.1)    15.1ms 15.0ms 15.2ms
# 5  target (10.0.1.50)       15.5ms 15.3ms 15.6ms

# 解读：
# 每跳显示 3 次探测的 RTT
# * * * 表示该跳路由器不响应 ICMP/UDP，不一定是问题
# 看延迟的跳变：如果第 2→3 跳突然从 5ms 变成 50ms，瓶颈在那段链路

# 使用 TCP 避免 ICMP 被过滤
traceroute -T -p 8080 10.0.1.50
```

### mtr（持续的 traceroute）

```bash
# mtr = traceroute + ping 的结合
mtr 10.0.1.50

# 实时输出：
# Host              Loss%  Snt   Last  Avg   Best  Wrst  StDev
# 1. gateway         0.0%  100   0.5   0.5   0.3   1.2   0.1
# 2. isp-router      0.0%  100   5.1   5.2   4.8   8.1   0.5
# 3. ???             100.0  100   0.0   0.0   0.0   0.0   0.0
# 4. datacenter      0.5%  100  15.2  15.3  14.9  22.1   1.2
# 5. target          0.5%  100  15.5  15.6  15.1  25.3   1.5

# 关键指标：
# Loss% — 丢包率
# Avg   — 平均延迟
# StDev — 延迟抖动（标准差）

# 重要：某跳 Loss% 高但后续跳 Loss% 正常 → 那一跳只是不回 ICMP，不是真丢包
# 真正的丢包会导致该跳及后续所有跳的 Loss% 都高

# 生成报告
mtr --report -c 100 10.0.1.50
# -c 100  发送 100 个探测包
```

### ping flood 检测丢包

```bash
# flood ping（需要 root）
sudo ping -f -c 10000 10.0.1.50
# -f  以最快速度发送（每秒数千个）
# -c 10000  共发送 10000 个

# 输出：
# 10000 packets transmitted, 9950 received, 0.5% packet loss
# rtt min/avg/max/mdev = 0.5/1.2/15.3/0.8 ms

# 0.5% 丢包在互联网上是正常的
# 局域网/数据中心内应该是 0%
# 超过 1% 需要排查
```

---

## 四、内核网络参数调优

### 缓冲区调优

```bash
# Socket 缓冲区（影响单连接吞吐）
sysctl net.core.rmem_max         # 接收缓冲区最大值（默认 212992）
sysctl net.core.wmem_max         # 发送缓冲区最大值（默认 212992）

# 调大（高带宽链路需要更大的缓冲区）
sudo sysctl -w net.core.rmem_max=16777216    # 16MB
sudo sysctl -w net.core.wmem_max=16777216    # 16MB

# TCP 自动调优范围（min, default, max 三个值）
sysctl net.ipv4.tcp_rmem    # 默认 4096 131072 6291456
sysctl net.ipv4.tcp_wmem    # 默认 4096 16384 4194304

# 调大（适用于高延迟高带宽链路）
sudo sysctl -w net.ipv4.tcp_rmem="4096 87380 16777216"
sudo sysctl -w net.ipv4.tcp_wmem="4096 65536 16777216"

# BDP（Bandwidth-Delay Product）公式：
# 需要的缓冲区 = 带宽 × RTT
# 例：1Gbps 带宽，10ms RTT
# BDP = 1000Mbps × 0.01s = 10Mbit = 1.25MB
# 缓冲区至少需要 1.25MB
```

### 连接队列调优

```bash
# 全连接队列大小
sysctl net.core.somaxconn
# 默认 128（Linux 5.4+ 默认 4096）
sudo sysctl -w net.core.somaxconn=4096

# 网卡接收队列大小
sysctl net.core.netdev_max_backlog
# 默认 1000，网卡收包速率高时需要调大
sudo sysctl -w net.core.netdev_max_backlog=5000

# 检查是否因 backlog 满而丢包
cat /proc/net/softnet_stat
# 第一列：处理的包数
# 第二列：因 backlog 满丢弃的包数 ← 这个值增长说明需要调大
# 第三列：time_squeeze 次数（CPU 来不及处理网络包）
```

### 综合调优配置

```bash
# /etc/sysctl.d/99-network-tuning.conf
# 高性能 Web 服务器推荐配置

# 缓冲区
net.core.rmem_max = 16777216
net.core.wmem_max = 16777216
net.ipv4.tcp_rmem = 4096 87380 16777216
net.ipv4.tcp_wmem = 4096 65536 16777216

# 连接队列
net.core.somaxconn = 4096
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_max_syn_backlog = 4096

# TIME_WAIT 处理
net.ipv4.tcp_tw_reuse = 1
net.ipv4.tcp_timestamps = 1

# 端口范围
net.ipv4.ip_local_port_range = 1024 65535

# Keepalive
net.ipv4.tcp_keepalive_time = 60
net.ipv4.tcp_keepalive_intvl = 10
net.ipv4.tcp_keepalive_probes = 6

# TCP 拥塞控制（BBR 通常比 cubic 更好）
net.core.default_qdisc = fq
net.ipv4.tcp_congestion_control = bbr
```

```bash
# 应用配置
sudo sysctl -p /etc/sysctl.d/99-network-tuning.conf

# 验证
sysctl net.core.somaxconn
sysctl net.ipv4.tcp_congestion_control
```

---

## 五、排查流程总结

```
应用报"请求慢"或"偶发超时"
  │
  ├── Step 1: 确认是网络问题还是应用问题
  │    └── curl -w 看 time_connect vs time_starttransfer
  │         ├── connect 慢 → 网络问题
  │         └── firstbyte 慢 → 应用处理慢
  │
  ├── Step 2: 检查丢包
  │    ├── netstat -s | grep retrans（重传统计）
  │    ├── ss -ti dst <ip>（单连接重传）
  │    └── ip -s link（网卡层丢包）
  │
  ├── Step 3: 定位延迟来源
  │    ├── mtr <target>（逐跳延迟 + 丢包率）
  │    └── traceroute -T -p <port>（TCP traceroute）
  │
  ├── Step 4: 检查 MTU 问题
  │    └── ping -M do -s 1472 <target>
  │
  └── Step 5: 检查内核参数
       ├── 缓冲区是否足够
       ├── 队列是否溢出
       └── 是否使用了 BBR 拥塞控制
```

---

## 总结

丢包和延迟问题的排查需要分层思考：

1. **网卡层**：ring buffer 满、网卡错误 → `ip -s link`, `ethtool -S`
2. **内核网络栈**：backlog 满、缓冲区不足 → `/proc/net/softnet_stat`, `sysctl`
3. **传输层**：TCP 重传、窗口问题 → `ss -ti`, `netstat -s`
4. **网络路径**：中间设备丢包、MTU 不匹配 → `mtr`, `traceroute`, `ping -M do`

大多数情况下，内核默认参数对中小流量够用。只有在高并发高吞吐场景下，才需要系统性调优内核网络参数。**调优前先量化问题，调优后验证效果**。
