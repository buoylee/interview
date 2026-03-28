# 连接问题排查

## 概述

网络连接问题是后端服务最高频的故障类型之一。"连不上"、"连接超时"、"连接被拒绝"——这些模糊的描述背后，每一种都有不同的根因和排查路径。本文按照从建立连接到维持连接的顺序，系统讲解各类连接问题的排查方法。

---

## 一、连接超时排查

### connect timeout vs read timeout

这两种超时完全不同，排查方向也不同。

```
connect timeout（连接超时）：
  TCP 三次握手阶段没在指定时间内完成
  → 对端不可达、防火墙 DROP 了 SYN、端口不通

read timeout（读超时）：
  TCP 连接已建立，但在指定时间内没有收到响应数据
  → 对端处理慢、网络拥塞导致数据传输慢
```

### 快速测试

```bash
# 方法 1：telnet 测试端口连通性
telnet 10.0.1.50 8080
# 成功：显示 Connected to 10.0.1.50
# 失败：Connection refused（端口未监听）或 超时（网络不通）

# 方法 2：nc（netcat）测试，更可控
nc -zv -w 3 10.0.1.50 8080
# -z  只测连通性，不发数据
# -v  详细输出
# -w 3 超时 3 秒

# 方法 3：curl 分阶段计时
curl -o /dev/null -s -w \
  "DNS: %{time_namelookup}s\nConnect: %{time_connect}s\nTLS: %{time_appconnect}s\nFirstByte: %{time_starttransfer}s\nTotal: %{time_total}s\n" \
  http://10.0.1.50:8080/api/health
```

### 防火墙排除

```bash
# 检查本机防火墙规则
iptables -L -n | grep 8080
# 或 nftables
nft list ruleset | grep 8080

# 检查 SELinux（CentOS/RHEL）
getenforce
# 如果是 Enforcing，可能阻止了网络访问

# 检查安全组（云环境）
# AWS: aws ec2 describe-security-groups
# 阿里云: aliyun ecs DescribeSecurityGroupAttribute

# 跟踪路由，看在哪一跳断了
traceroute -T -p 8080 10.0.1.50
# -T  使用 TCP（默认是 UDP/ICMP，可能被防火墙放行但 TCP 被拦）
```

---

## 二、连接拒绝 ECONNREFUSED

```
含义：目标机器收到了 SYN，但内核直接回了 RST（拒绝）
本质：目标端口没有任何进程在 listen
```

### 常见原因

```bash
# 1. 服务没启动
ss -tlnp | grep 8080
# 没输出 → 端口没有被监听

# 2. 服务绑定了错误的地址
ss -tlnp | grep 8080
# LISTEN  0  128  127.0.0.1:8080  *:*
# 只绑了 127.0.0.1，外部连不上
# 应该绑 0.0.0.0:8080

# 3. listen backlog 满了（特殊情况）
# 当全连接队列满了且内核参数 tcp_abort_on_overflow=1 时，
# 内核会发 RST 给客户端
cat /proc/sys/net/ipv4/tcp_abort_on_overflow
# 默认是 0（不发 RST，而是静默丢弃，客户端会重试）
```

---

## 三、半连接队列溢出

### TCP 两个队列

```
TCP 三次握手涉及两个内核队列：

Client           Server
  |                |
  |---- SYN ------>|  → SYN 包到达，放入半连接队列（SYN Queue）
  |<--- SYN-ACK ---|
  |---- ACK ------>|  → ACK 到达，从半连接队列移到全连接队列（Accept Queue）
  |                |  → 应用 accept() 从全连接队列取出

半连接队列（SYN Queue）：存放收到 SYN 但还没完成三次握手的连接
全连接队列（Accept Queue）：存放已完成三次握手但应用还没 accept 的连接
```

### 排查方法

```bash
# 查看队列状态
ss -tnl
# State   Recv-Q  Send-Q  Local Address:Port
# LISTEN  0       128     0.0.0.0:8080
#         ↑       ↑
#         │       └── 全连接队列大小（backlog）
#         └────────── 当前全连接队列中的连接数

# 如果 Recv-Q 接近 Send-Q → 全连接队列快满了

# 检查溢出统计
netstat -s | grep -i "listen"
# X times the listen queue of a socket overflowed  ← 全连接队列溢出次数
# Y SYNs to LISTEN sockets dropped                  ← 半连接队列溢出次数

# 持续监控溢出增长
watch -n 1 'netstat -s | grep -i "listen\|overflow"'
```

### 调优参数

```bash
# 半连接队列大小
sysctl net.ipv4.tcp_max_syn_backlog
# 默认 128 或 256，高并发建议调大
sudo sysctl -w net.ipv4.tcp_max_syn_backlog=4096

# 全连接队列大小（取 min(somaxconn, backlog)）
sysctl net.core.somaxconn
# 默认 128，高并发建议调大
sudo sysctl -w net.core.somaxconn=4096

# 应用层也需要配合调大 backlog
# Go: net.Listen("tcp", ":8080") 默认 backlog = somaxconn
# Java: new ServerSocket(8080, 4096)  第二个参数是 backlog
# Nginx: listen 8080 backlog=4096;

# 开启 SYN Cookie（防 SYN Flood 攻击）
sysctl net.ipv4.tcp_syncookies
# 默认 1（开启），在半连接队列满时用 cookie 验证而非直接丢弃
```

---

## 四、TIME_WAIT 堆积

### 什么是 TIME_WAIT

```
TCP 四次挥手后，主动关闭方进入 TIME_WAIT 状态，持续 2MSL（通常 60 秒）。

为什么需要 TIME_WAIT：
1. 确保最后一个 ACK 到达对端（如果丢了，对端会重发 FIN）
2. 确保旧连接的残留包在网络中消亡，不会干扰新连接
```

### 排查

```bash
# 统计各状态连接数
ss -s
# TCP:   1254 (estab 200, closed 50, orphaned 10, timewait 950)
#                                                  ↑
#                                             950 个 TIME_WAIT

# 按目标 IP 统计 TIME_WAIT
ss -tan state time-wait | awk '{print $4}' | sort | uniq -c | sort -rn | head
# 450 10.0.1.50:3306     ← 大量到 MySQL 的 TIME_WAIT
# 300 10.0.1.60:6379     ← 大量到 Redis 的 TIME_WAIT
```

### 解决方案

```bash
# 方案 1（正确方案）：使用连接池
# 不要每次请求都建新连接再关闭
# 连接池复用连接，根本不会产生大量 TIME_WAIT

# 方案 2：开启 tcp_tw_reuse（安全）
sudo sysctl -w net.ipv4.tcp_tw_reuse=1
# 允许在安全的情况下复用 TIME_WAIT 状态的连接（作为客户端发起连接时）
# 需要同时开启 tcp_timestamps
sudo sysctl -w net.ipv4.tcp_timestamps=1

# 方案 3：tcp_tw_recycle（危险，已在 Linux 4.12 移除）
# 不要使用！在 NAT 环境下会导致严重问题
# 同一 NAT 后的不同客户端的 timestamp 不同，会导致连接被丢弃

# 方案 4：减小 TIME_WAIT 持续时间（不推荐修改）
# Linux 的 TIME_WAIT 固定 60 秒，无法通过 sysctl 修改
# 有些文章说可以改 tcp_fin_timeout，这是错误的
# tcp_fin_timeout 控制的是 FIN_WAIT_2 状态的超时，不是 TIME_WAIT
```

**根本原因**：大量 TIME_WAIT 几乎总是因为**没有使用连接池**。解决方案是用连接池，而不是去调内核参数。调内核参数是治标不治本。

---

## 五、端口耗尽

### 问题描述

```
客户端发起大量连接时：
- 每个连接的源端口是动态分配的
- 端口范围默认 32768-60999（约 28000 个端口）
- 如果目标 IP:Port 相同，可用端口用完就连不上了
- TIME_WAIT 的连接也占用端口
```

### 排查与调优

```bash
# 查看可用端口范围
sysctl net.ipv4.ip_local_port_range
# 32768  60999

# 扩大端口范围
sudo sysctl -w net.ipv4.ip_local_port_range="1024 65535"
# 现在有约 64000 个端口可用

# 查看当前端口使用情况
ss -tan | awk '{print $4}' | grep -oP ':\K\d+$' | sort -n | wc -l

# 开启 SO_REUSEADDR（应用层设置）
# Go:
# listener, _ := net.Listen("tcp", ":8080")
# Go 默认已设置 SO_REUSEADDR

# Java:
# serverSocket.setReuseAddress(true);

# SO_REUSEADDR 允许绑定处于 TIME_WAIT 状态的地址
# 主要用于服务端重启时快速重新绑定端口
```

---

## 六、Keepalive 配置

### TCP Keepalive vs HTTP Keepalive

这是两个完全不同的东西，经常被混淆：

```
TCP Keepalive：
  - 传输层机制
  - 用于检测对端是否还活着（死连接检测）
  - 发送空的探测包
  - 由内核控制

HTTP Keep-Alive：
  - 应用层机制
  - 用于复用 TCP 连接（不用每个请求都三次握手）
  - 通过 Connection: keep-alive 头控制
  - 由 HTTP 服务器/客户端控制
```

### TCP Keepalive 参数

```bash
# 三个关键参数
sysctl net.ipv4.tcp_keepalive_time    # 连接空闲多久后开始探测（默认 7200 秒 = 2 小时）
sysctl net.ipv4.tcp_keepalive_intvl   # 探测间隔（默认 75 秒）
sysctl net.ipv4.tcp_keepalive_probes  # 探测次数，超过则认为连接死亡（默认 9 次）

# 默认行为：空闲 2 小时后，每 75 秒发一次探测，连续 9 次无响应则关闭
# 总共需要 2h + 75s × 9 ≈ 2h11m 才能检测到死连接

# 对后端服务来说，2 小时太长了
# 生产建议：
sudo sysctl -w net.ipv4.tcp_keepalive_time=60     # 空闲 60 秒后开始探测
sudo sysctl -w net.ipv4.tcp_keepalive_intvl=10    # 每 10 秒探测一次
sudo sysctl -w net.ipv4.tcp_keepalive_probes=6    # 6 次无响应则关闭
# 总共 60 + 10 × 6 = 120 秒检测到死连接
```

### 应用层 Keepalive 配置

```go
// Go HTTP 客户端连接池配置
transport := &http.Transport{
    MaxIdleConns:        100,              // 最大空闲连接数
    MaxIdleConnsPerHost: 10,               // 每个 host 最大空闲连接
    IdleConnTimeout:     90 * time.Second, // 空闲连接超时
    // TCP Keepalive
    DialContext: (&net.Dialer{
        KeepAlive: 30 * time.Second,       // TCP Keepalive 间隔
        Timeout:   10 * time.Second,       // 连接超时
    }).DialContext,
}
client := &http.Client{Transport: transport}
```

```java
// Java OkHttp 连接池
OkHttpClient client = new OkHttpClient.Builder()
    .connectionPool(new ConnectionPool(
        20,                        // 最大空闲连接
        5, TimeUnit.MINUTES        // 空闲连接保活时间
    ))
    .connectTimeout(10, TimeUnit.SECONDS)
    .readTimeout(30, TimeUnit.SECONDS)
    .build();
```

```nginx
# Nginx 上游 keepalive
upstream backend {
    server 10.0.1.50:8080;
    server 10.0.1.51:8080;
    keepalive 32;           # 每个 worker 到上游保持 32 个空闲连接
    keepalive_timeout 60s;  # 空闲连接超时
    keepalive_requests 1000; # 每个连接最多处理 1000 个请求后关闭
}
```

---

## 七、排查流程图

```
连接失败
  │
  ├── "Connection refused"
  │    └── ss -tlnp 检查端口是否监听
  │         ├── 没监听 → 服务没启动 / 绑错地址
  │         └── 在监听 → 全连接队列满 + tcp_abort_on_overflow=1
  │
  ├── "Connection timed out"
  │    └── telnet/nc 测试
  │         ├── 也超时 → 防火墙/安全组/路由问题
  │         └── 能通 → 应用层超时设置太短 / 间歇性网络问题
  │
  ├── "Cannot assign requested address"
  │    └── 端口耗尽
  │         ├── ss -s 看 TIME_WAIT 数量
  │         └── 扩大端口范围 / 使用连接池
  │
  └── "Connection reset by peer"
       └── 对端发了 RST
            ├── 对端服务崩溃
            ├── 对端防火墙规则
            ├── 负载均衡器超时断开
            └── 对端连接数限制
```

---

## 总结

连接问题排查的核心逻辑：

1. **先确定症状**：是 refused、timeout 还是 reset？不同症状对应不同根因。
2. **分层排查**：网络层（能不能通）→ 传输层（TCP 队列是否溢出）→ 应用层（服务是否正常）。
3. **用连接池**：绝大多数连接相关问题（TIME_WAIT 堆积、端口耗尽、频繁握手开销）都可以通过连接池解决。
4. **调内核参数要谨慎**：先理解参数的含义和副作用，不要盲目从网上抄配置。
