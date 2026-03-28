# tcpdump 与 Wireshark

## 为什么需要抓包分析

当应用日志显示"请求超时"或"连接失败"时，应用层看到的只是结果。**真正的原因藏在网络包里**——是 TCP 握手没完成？是服务端 RST 了连接？是中间某个网络设备丢包？抓包分析是网络问题排查的终极手段。

---

## 一、tcpdump 过滤语法详解

tcpdump 使用 BPF（Berkeley Packet Filter）语法，掌握过滤语法是高效抓包的关键。

### 基本过滤

```bash
# 按主机过滤
tcpdump host 10.0.1.50           # 源或目标是这个 IP
tcpdump src host 10.0.1.50       # 只看源 IP
tcpdump dst host 10.0.1.50       # 只看目标 IP

# 按端口过滤
tcpdump port 8080                # 源或目标端口是 8080
tcpdump src port 8080            # 只看源端口
tcpdump dst port 8080            # 只看目标端口
tcpdump portrange 8000-9000      # 端口范围

# 按协议过滤
tcpdump tcp                      # 只看 TCP
tcpdump udp                      # 只看 UDP
tcpdump icmp                     # 只看 ICMP（ping）
```

### 组合过滤

```bash
# AND 组合
tcpdump host 10.0.1.50 and port 8080

# OR 组合
tcpdump port 80 or port 443

# NOT 排除
tcpdump not port 22              # 排除 SSH 流量（抓包时很有用）
tcpdump host 10.0.1.50 and not port 22

# 复杂组合（用括号，需要转义）
tcpdump 'host 10.0.1.50 and (port 80 or port 443)'
```

### TCP Flags 过滤

```bash
# 抓 SYN 包（新连接）
tcpdump 'tcp[tcpflags] & tcp-syn != 0'

# 抓 RST 包（连接被重置）
tcpdump 'tcp[tcpflags] & tcp-rst != 0'

# 抓 FIN 包（正常关闭）
tcpdump 'tcp[tcpflags] & tcp-fin != 0'

# 只抓 SYN（不含 SYN-ACK）
tcpdump 'tcp[tcpflags] == tcp-syn'

# 抓 SYN 和 RST（排查连接问题常用）
tcpdump 'tcp[tcpflags] & (tcp-syn|tcp-rst) != 0'
```

---

## 二、常用命令模板

### 日常排查模板

```bash
# 模板 1：抓特定服务的流量，写入文件
tcpdump -i eth0 -nn -s0 -w /tmp/capture.pcap \
  host 10.0.1.50 and port 8080

# 参数说明：
# -i eth0    指定网卡（用 -i any 抓所有网卡）
# -nn        不解析主机名和端口名（更快、输出更清晰）
# -s0        抓完整包（默认可能只抓前 N 字节）
# -w file    写入 pcap 文件（后续用 Wireshark 分析）

# 模板 2：实时查看 HTTP 请求（快速排查）
tcpdump -i eth0 -nn -A port 80 | grep -E 'GET|POST|HTTP/'

# -A  以 ASCII 打印包内容（适合 HTTP 明文）

# 模板 3：抓 SYN 包，排查连接建立问题
tcpdump -i eth0 -nn 'tcp[tcpflags] & tcp-syn != 0' and port 8080

# 模板 4：抓 RST 包，排查连接被异常关闭
tcpdump -i eth0 -nn 'tcp[tcpflags] & tcp-rst != 0'

# 模板 5：限制抓包数量（避免磁盘写满）
tcpdump -i eth0 -nn -c 1000 -w /tmp/capture.pcap port 8080
# -c 1000  抓 1000 个包后停止

# 模板 6：按文件大小轮转（长时间抓包）
tcpdump -i eth0 -nn -w /tmp/capture.pcap -C 100 -W 10 port 8080
# -C 100   每个文件 100MB
# -W 10    最多 10 个文件，循环覆盖
```

### 容器环境抓包

```bash
# Docker 容器
docker exec -it <container_id> tcpdump -i eth0 -nn port 8080

# 如果容器内没有 tcpdump，用 nsenter 从宿主机抓
PID=$(docker inspect -f '{{.State.Pid}}' <container_id>)
nsenter -t $PID -n tcpdump -i eth0 -nn port 8080

# Kubernetes Pod
kubectl exec -it <pod-name> -- tcpdump -i eth0 -nn port 8080

# 或使用 kubectl debug 注入临时容器
kubectl debug -it <pod-name> --image=nicolaka/netshoot -- tcpdump -i eth0 -nn port 8080
```

---

## 三、Wireshark 分析流程

Wireshark 是 GUI 的网络分析工具，适合深度分析 tcpdump 抓到的 pcap 文件。

### 标准分析流程

```
1. 打开 pcap 文件
   File → Open → 选择 capture.pcap

2. 设置过滤器快速定位
   显示过滤器（Display Filter）语法与 tcpdump 不同：
   - tcp.port == 8080
   - ip.addr == 10.0.1.50
   - http.request.method == "POST"
   - tcp.flags.reset == 1          # RST 包
   - tcp.analysis.retransmission   # 重传包
   - tcp.time_delta > 1            # 包间隔超过 1 秒

3. Follow TCP Stream
   右键某个包 → Follow → TCP Stream
   → 查看完整的一次 TCP 会话内容
   → 不同颜色区分客户端和服务端

4. IO Graph（流量分布）
   Statistics → IO Graph
   → 看流量随时间的变化
   → 可以叠加多个过滤条件对比

5. Expert Information（异常汇总）
   Analyze → Expert Information
   → 自动识别 TCP 异常：重传、乱序、窗口满等
   → 按严重程度分类：Error / Warning / Note
```

### TCP 时序图解读

```
Wireshark 生成时序图：
Statistics → Flow Graph → TCP Flows

典型的 TCP 三次握手：
Client                    Server
  |                         |
  |------- SYN ----------->|     # 客户端发起连接
  |                         |
  |<----- SYN-ACK ---------|     # 服务端确认
  |                         |
  |------- ACK ----------->|     # 客户端确认，连接建立
  |                         |
  |------- HTTP GET ------>|     # 开始传输数据
  |                         |
  |<----- HTTP 200 --------|     # 服务端响应
  |                         |
  |------- FIN ----------->|     # 客户端关闭
  |<----- FIN-ACK ---------|     # 服务端确认关闭
  |------- ACK ----------->|
```

---

## 四、常见模式识别

### 1. TCP 重传

```
Wireshark 标记：[TCP Retransmission] 或 [TCP Fast Retransmission]

正常流程：
Client --- Data(seq=1000) ---> Server
Client <-- ACK(ack=2000) ----- Server

重传流程：
Client --- Data(seq=1000) ---> Server   # 数据包丢了
           ... 等待超时 ...
Client --- Data(seq=1000) ---> Server   # [TCP Retransmission] 重传
Client <-- ACK(ack=2000) ----- Server

排查方向：
- 偶尔重传：正常，互联网本身有丢包
- 频繁重传：网络链路质量差、交换机/防火墙问题、网卡驱动问题
```

### 2. TCP 窗口问题

```
[TCP Window Update]：接收方调整窗口大小
[TCP ZeroWindow]：接收方窗口为 0，告诉发送方"我处理不过来了，先别发"
[TCP Window Full]：发送方填满了接收方的窗口

ZeroWindow 排查方向：
- 应用层处理太慢（没及时从 socket buffer 读数据）
- 接收缓冲区太小（调 net.core.rmem_max）
```

### 3. RST 包（连接强制关闭）

```
常见原因：
1. 连接目标端口没有服务监听 → 内核直接回 RST
2. 防火墙策略拒绝 → 发 RST
3. 应用崩溃 → 操作系统对未关闭的连接发 RST
4. 连接超时（半开连接检测） → 发 RST
5. 负载均衡器健康检查失败 → 向客户端发 RST

区分方法：
- 看 RST 是谁发的（src IP）
- 看 RST 之前的包交互
- 看 RST 包中有没有 ACK（RST vs RST-ACK）
```

### 4. Keepalive 探测

```
TCP Keepalive 包特征：
- 长度为 0 或 1 字节
- 序列号为上次 ACK 的序列号 - 1
- 间隔固定（默认 75 秒一次，由 tcp_keepalive_intvl 决定）

Wireshark 标记：[TCP Keep-Alive] 和 [TCP Keep-Alive ACK]

如果 Keep-Alive 没有得到 ACK → 连接可能已经断了
```

---

## 五、实操：抓一次完整的 HTTP 请求

### 步骤

```bash
# 终端 1：启动抓包
sudo tcpdump -i lo -nn -s0 -w /tmp/http-demo.pcap \
  port 8080 and host 127.0.0.1

# 终端 2：发一个 HTTP 请求
curl http://127.0.0.1:8080/api/users

# 终端 1：Ctrl+C 停止抓包
```

### 用 Wireshark 分析

打开 `/tmp/http-demo.pcap`，你应该看到以下包序列：

```
No.  Time     Source          Dest            Protocol  Info
1    0.000    127.0.0.1:54321 127.0.0.1:8080  TCP       SYN
2    0.000    127.0.0.1:8080  127.0.0.1:54321 TCP       SYN-ACK
3    0.000    127.0.0.1:54321 127.0.0.1:8080  TCP       ACK
4    0.000    127.0.0.1:54321 127.0.0.1:8080  HTTP      GET /api/users
5    0.005    127.0.0.1:8080  127.0.0.1:54321 TCP       ACK
6    0.010    127.0.0.1:8080  127.0.0.1:54321 HTTP      200 OK
7    0.010    127.0.0.1:54321 127.0.0.1:8080  TCP       ACK
8    0.010    127.0.0.1:54321 127.0.0.1:8080  TCP       FIN-ACK
9    0.010    127.0.0.1:8080  127.0.0.1:54321 TCP       FIN-ACK
10   0.010    127.0.0.1:54321 127.0.0.1:8080  TCP       ACK
```

```
解读：
包 1-3：TCP 三次握手（约 0ms，本地回环）
包 4：  HTTP GET 请求
包 5：  TCP 层确认收到请求
包 6：  HTTP 200 响应（服务端处理耗时 ≈ 10ms）
包 7：  TCP 层确认收到响应
包 8-10：TCP 四次挥手关闭连接（curl 默认不复用连接）
```

### 从抓包中能发现的问题

| 现象 | 可能原因 |
|------|---------|
| SYN 发出去没有 SYN-ACK | 服务没启动 / 防火墙 / 端口未监听 |
| 三次握手后长时间没有数据 | 应用层连接建立慢（如 TLS 握手、认证） |
| 数据发出后很久才收到 ACK | 网络延迟高 / 服务端处理慢 |
| 大量 [TCP Retransmission] | 网络丢包 |
| 突然收到 RST | 服务崩溃 / 超时断开 / 防火墙 |
| [TCP ZeroWindow] | 接收方处理不过来 |

---

## 总结

tcpdump + Wireshark 是网络排查的黄金组合：

1. **tcpdump 负责抓**：在服务器上用精确的过滤条件抓取目标流量
2. **Wireshark 负责分析**：在本地用 GUI 深度分析包交互

核心技能：
- 熟练使用 tcpdump 过滤语法，避免抓太多无关流量
- 能从 Wireshark 的 TCP 时序中识别重传、窗口问题、RST
- 理解 TCP 状态机，知道每个包的含义

**抓包是最底层的调试手段**——当所有上层日志、监控都无法解释问题时，包里有真相。
