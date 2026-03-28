# TCP 核心机制

> 几乎所有后端服务都建立在 TCP 之上。深入理解三次握手、四次挥手、TIME_WAIT 和拥塞控制，是排查网络性能问题的基本功。

---

## 1. TCP/IP 四层模型

```
OSI 七层                  TCP/IP 四层              示例协议/数据
┌────────────┐
│   应用层    │         ┌──────────────┐
├────────────┤         │              │          HTTP, gRPC, DNS
│   表示层    │    ───► │   应用层      │          数据单位: 消息
├────────────┤         │              │
│   会话层    │         └──────┬───────┘
├────────────┤                │
│   传输层    │    ───► ┌──────┴───────┐          TCP, UDP
│            │         │   传输层      │          数据单位: 段(Segment)
├────────────┤         └──────┬───────┘
│   网络层    │    ───► ┌──────┴───────┐          IP, ICMP
│            │         │   网络层      │          数据单位: 包(Packet)
├────────────┤         └──────┬───────┘
│  数据链路层  │   ───► ┌──────┴───────┐          Ethernet, ARP
├────────────┤         │ 网络接口层    │          数据单位: 帧(Frame)
│   物理层    │         └─────────────┘
└────────────┘
```

**为什么要理解分层**：性能问题可能出现在任何一层。应用层超时可能是传输层拥塞、网络层路由问题、甚至链路层的网卡配置问题。分层思考有助于定位根因。

---

## 2. 三次握手详解

```
    客户端                                 服务端
      │                                      │
      │  1. SYN (seq=x)                      │
      │ ────────────────────────────────────► │
      │       客户端进入 SYN_SENT 状态          │ 服务端进入 SYN_RCVD 状态
      │                                      │ (连接放入半连接队列 SYN Queue)
      │  2. SYN+ACK (seq=y, ack=x+1)        │
      │ ◄──────────────────────────────────── │
      │                                      │
      │  3. ACK (ack=y+1)                    │
      │ ────────────────────────────────────► │
      │       客户端进入 ESTABLISHED           │ 服务端进入 ESTABLISHED
      │                                      │ (连接从半连接队列移到全连接队列 Accept Queue)
      │         双方开始传输数据                 │
```

### 各阶段可能的失败与性能影响

**阶段 1：SYN 发出但无响应**

- 原因：服务端不可达、防火墙 DROP、服务端 SYN Queue 满
- 表现：客户端 SYN 重传，间隔 1s, 2s, 4s, 8s...（指数退避）
- 影响：连接建立延迟从 ms 级变成秒级

```bash
# 服务端 SYN Queue 大小
sysctl net.ipv4.tcp_max_syn_backlog
# 默认 128 或 256，高并发场景需要调大

# SYN 重传次数
sysctl net.ipv4.tcp_syn_retries
# 默认 6，即最多等待 ~127 秒

# 启用 SYN Cookie 防 SYN Flood
sysctl net.ipv4.tcp_syncookies
# 1 = 启用（SYN Queue 满时仍可建连）
```

**阶段 2：SYN+ACK 发出但 ACK 未收到**

- 原因：客户端异常、网络丢包
- 服务端 SYN+ACK 重传

```bash
# SYN+ACK 重传次数
sysctl net.ipv4.tcp_synack_retries
# 默认 5
```

**阶段 3：ACK 到达服务端，但 Accept Queue 满**

- 原因：应用 `accept()` 太慢，积压的完成连接超过 backlog
- 表现：新连接被丢弃或重置

```bash
# Accept Queue 大小 = min(backlog 参数, somaxconn)
sysctl net.core.somaxconn
# 默认 128（Linux < 5.4），4096（Linux >= 5.4）
# 高并发必须调大

# 查看 Accept Queue 溢出次数
netstat -s | grep "listen queue"
# 或
nstat -az TcpExtListenOverflows
```

---

## 3. 四次挥手详解

```
    主动关闭方 (客户端)                    被动关闭方 (服务端)
        │                                       │
        │  1. FIN (seq=u)                       │
        │ ────────────────────────────────────►  │
        │      进入 FIN_WAIT_1                   │  进入 CLOSE_WAIT
        │                                       │
        │  2. ACK (ack=u+1)                     │
        │ ◄────────────────────────────────────  │
        │      进入 FIN_WAIT_2                   │  (应用可能还有数据要发)
        │                                       │
        │                         ... 数据传输 ...│
        │                                       │
        │  3. FIN (seq=v)                       │
        │ ◄────────────────────────────────────  │  进入 LAST_ACK
        │                                       │
        │  4. ACK (ack=v+1)                     │
        │ ────────────────────────────────────►  │  进入 CLOSED
        │      进入 TIME_WAIT                    │
        │      (等待 2MSL)                       │
        │      进入 CLOSED                       │
```

**为什么是四次而不是三次**：被动关闭方收到 FIN 后可能还有数据要发送，所以 ACK 和 FIN 分开发送。如果被动方没有待发数据，内核会合并成 FIN+ACK（三次挥手优化）。

---

## 4. TIME_WAIT 状态

### 为什么需要 TIME_WAIT

1. **可靠终止连接**：最后一个 ACK 可能丢失，被动方会重发 FIN，主动方需要保持状态以便重新响应 ACK
2. **防止旧连接的数据干扰新连接**：等待 2MSL（Maximum Segment Lifetime，Linux 默认 60s）确保旧连接的所有数据包过期

### TIME_WAIT 对高并发的影响

TIME_WAIT 状态的连接仍然占用一个**五元组**（源IP、源端口、目标IP、目标端口、协议）。如果短时间内大量短连接关闭：

```
场景：应用频繁连接同一个后端服务
→ 大量 TIME_WAIT 连接
→ 可用源端口（临时端口范围，默认 32768-60999）耗尽
→ 新连接 connect() 失败：Cannot assign requested address
```

```bash
# 查看 TIME_WAIT 连接数
ss -s
# 或
ss -ant state time-wait | wc -l

# 查看各状态的连接数
ss -ant | awk '{print $1}' | sort | uniq -c | sort -rn

# 调整临时端口范围
sysctl net.ipv4.ip_local_port_range
# 默认 "32768 60999" (28232个端口)
# 调大：
sysctl net.ipv4.ip_local_port_range="1024 65535"
```

### TIME_WAIT 优化方案

```bash
# 方案 1：SO_REUSEADDR（最基本）
# 允许绑定 TIME_WAIT 状态的地址，服务端重启时不需要等待
# 代码层面设置：setsockopt(fd, SOL_SOCKET, SO_REUSEADDR, &on, sizeof(on))
# 几乎所有服务端框架默认开启

# 方案 2：SO_REUSEPORT（Linux >= 3.9）
# 多个 Socket 绑定同一端口，内核负载均衡
# Nginx 1.9.1+: listen 80 reuseport;

# 方案 3：tcp_tw_reuse（客户端有效）
sysctl net.ipv4.tcp_tw_reuse=1
# 允许处于 TIME_WAIT 的连接被新连接复用（需要双方都开启 TCP Timestamps）
# 注意：仅对连接发起方（客户端）有效

# 方案 4：减少 TIME_WAIT 持续时间（内核 >= 4.12 可调）
# 一些发行版通过修改 TCP_TIMEWAIT_LEN 内核参数
# 但标准内核写死 60 秒，不建议改内核

# 反面教材：tcp_tw_recycle（已在 Linux 4.12 移除）
# 在 NAT 环境下会导致连接异常，绝对不要使用
```

**最佳实践**：与其优化 TIME_WAIT，不如使用**连接池**（HTTP Keep-Alive、数据库连接池）减少短连接。

---

## 5. 拥塞控制

TCP 拥塞控制决定了发送方的发包速率，直接影响网络吞吐量。

### 四个阶段

```
发送窗口
(cwnd)
   ▲
   │      ┌────────────────────┐
   │     /│                    │
   │    / │    拥塞避免          │     ← 线性增长
   │   /  │   (每RTT增1)        │
   │  /   │                    │
   │ /    │ssthresh            │
   │/     │                    │    快重传+快恢复
   │      │          ┌─────X──┘    cwnd 减半
   │      │         /
   │     慢启动     /  ← 拥塞避免
   │   (指数增长)  /
   │             /
   └──────────────────────────────► 时间
```

| 阶段 | 行为 | cwnd 增长 |
|------|------|-----------|
| 慢启动 | 初始 cwnd=1(或10)，每收到一个 ACK 翻倍 | 指数 |
| 拥塞避免 | cwnd >= ssthresh 后，每个 RTT 增加 1 个 MSS | 线性 |
| 快重传 | 收到 3 个重复 ACK，立即重传（不等超时） | - |
| 快恢复 | 快重传后 ssthresh = cwnd/2，cwnd 减半继续 | 线性 |

### CUBIC vs BBR 对比

| 特性 | CUBIC (Linux 默认) | BBR (Google) |
|------|-------------------|--------------|
| 基于 | 丢包 (loss-based) | 带宽和延迟 (model-based) |
| 优点 | 成熟稳定，公平性好 | 高带宽利用率，低延迟 |
| 缺点 | 浅缓冲区网络利用率低 | 与 CUBIC 共存时可能不公平 |
| 适用 | 通用场景 | 高延迟/高带宽（跨国、CDN） |

```bash
# 查看当前拥塞算法
sysctl net.ipv4.tcp_congestion_control
# 默认 cubic

# 查看可用算法
sysctl net.ipv4.tcp_available_congestion_control

# 启用 BBR
sysctl net.ipv4.tcp_congestion_control=bbr
sysctl net.core.default_qdisc=fq  # BBR 需要 fq 队列

# 验证
sysctl net.ipv4.tcp_congestion_control
```

**实践建议**：
- 内网（低延迟、低丢包）：CUBIC 就够了
- 公网（高延迟、有丢包）：BBR 通常表现更好，特别是跨国传输
- CDN / 长距离传输：强烈推荐 BBR

---

## 6. Nagle 算法与延迟 ACK

### Nagle 算法

目的是减少小包数量：如果有未被 ACK 的数据，新的小数据会被缓冲，等到收到 ACK 或凑够 MSS 再发送。

### 延迟 ACK

接收方不会立即发送 ACK，而是等待 40-200ms，看看有没有数据可以一起发回去（piggyback）。

### 两者叠加的灾难

```
场景：客户端连续发两个小包（如 HTTP Header + Body 分开发送）

客户端发送小包1 ──────────► 服务端收到，启动延迟 ACK 定时器
客户端有小包2要发，但 Nagle 说"等 ACK"
                                    ... 等待 40-200ms ...
                         ◄────────── 服务端延迟 ACK 超时，发送 ACK
客户端收到 ACK，Nagle 释放小包2 ──► 服务端终于收到完整请求

额外延迟: 40-200ms（对在线服务不可接受）
```

### 解决方案

```bash
# 禁用 Nagle 算法
setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, &on, sizeof(on))
```

- **几乎所有 RPC 框架、Web 服务器默认开启 `TCP_NODELAY`**
- gRPC、Nginx、Redis、MySQL 客户端都默认禁用 Nagle
- 如果你在写网络程序，除非明确知道需要 Nagle，否则**一律设置 `TCP_NODELAY`**

```bash
# 查看连接是否启用了 TCP_NODELAY
ss -tnip dst :8080 | grep nodelay
```

---

## 7. 实用诊断命令速查

```bash
# 查看各状态的 TCP 连接统计
ss -s

# 查看特定端口的连接详情
ss -tnp sport = :8080

# 查看 TCP 重传统计
nstat -az | grep -i retrans
# TcpRetransSegs: 重传的段数
# TcpExtTCPSlowStartRetrans: 慢启动阶段重传

# 查看 SYN Queue / Accept Queue 溢出
nstat -az | grep -iE "overflow|drop"

# 抓包分析三次握手耗时
tcpdump -i eth0 -nn -c 100 'tcp[tcpflags] & (tcp-syn) != 0'

# 查看 RTT 和 cwnd
ss -ti dst <server_ip>
# 输出包含 rtt, cwnd, retrans 等信息

# 查看内核 TCP 参数
sysctl -a | grep net.ipv4.tcp
```

---

## 要点总结

1. **三次握手的每个阶段都可能失败**——SYN Queue 和 Accept Queue 的大小是高并发场景下的常见瓶颈。`somaxconn` 和 `tcp_max_syn_backlog` 需要根据并发量调整。
2. **TIME_WAIT 不是 bug，是设计**——通过连接池复用连接才是正道，而不是试图缩短或绕过 TIME_WAIT。
3. **拥塞控制直接影响吞吐量**——公网场景下 BBR 通常优于 CUBIC。
4. **TCP_NODELAY 对低延迟服务至关重要**——Nagle + 延迟 ACK 的组合会引入 40-200ms 的无谓延迟。
5. **排查网络问题先看 `ss -s`**——连接状态分布能快速判断问题方向（大量 TIME_WAIT = 短连接、大量 CLOSE_WAIT = 应用未关闭连接）。
