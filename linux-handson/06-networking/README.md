# 06 · 网络模型 ⭐核心

> 🧪 **环境**:VM shell(`multipass shell linux-lab`)
> 进程要的第四种、也是最后一种资源:网络。**socket 也是 fd**(接 `05`)。本章讲透面试与排查的两大主角——**TIME_WAIT 与 CLOSE_WAIT**——以及「连不上一个服务」的分层定位。

---

## 一、开篇盲点

- 一台机器上一堆 `TIME_WAIT`,是不是出问题了?要不要改内核参数?
- 一堆 `CLOSE_WAIT` 又是什么?它和 `TIME_WAIT` 谁是你代码的锅?(`05` 埋的伏笔)
- `connection refused` 和 `connection timeout`,差在哪?分别说明什么?
- 连不上一个服务,怎么一层层定位是 DNS、网络、端口、还是服务没监听?

这些是**网络排查的日常**,根子在不熟 **TCP 状态机、端口/队列资源、DNS 路径**。

---

## 二、正文 · 原理

### 2.1 一条连接 = 四元组 + 一个 fd(接 05)

一条 TCP 连接由**四元组**唯一确定:`(本地IP:本地端口, 对端IP:对端端口)`。内核用一个 **socket fd** 表示它——所以连接数受 `RLIMIT_NOFILE` 限制(回顾 `05`「socket 也是 fd」)。

客户端每发起一条连接,占用:**一个本地(临时)端口 + 一个 fd**。这就是「端口耗尽」和「fd 耗尽」常常一起出现的原因。

### 2.2 TCP 状态机(聚焦实战的精简版)

```
建立:三次握手                         关闭:四次挥手
client        server                  主动关闭方         被动关闭方
  │── SYN ──────►│                       │── FIN ──────────►│
  │◄─ SYN+ACK ──│                        │◄─ ACK ──────────│  (被动方进 CLOSE_WAIT)
  │── ACK ──────►│                       │                  │  ← 等本端应用 close()
  ESTABLISHED  ESTABLISHED               │◄─ FIN ──────────│  (被动方 close 后发 FIN→LAST_ACK)
                                         │── ACK ──────────►│
                              (主动方进 TIME_WAIT, 等 2*MSL)  CLOSED
```

记住两个「停留态」:**主动关闭方 → `TIME_WAIT`**;**被动关闭方 → `CLOSE_WAIT`**。下面分别讲——这是本章的核心。

### 2.3 TIME_WAIT:正常的、出现在主动关闭方

主动关闭连接的一方,发完最后那个 ACK 后进入 **`TIME_WAIT`**,停留约 **2×MSL(Linux 默认约 60s)** 才彻底关闭。

**为什么要有这段等待:**
1. **保证最后的 ACK 送达**:万一对端没收到、重发了 FIN,本端还在 TIME_WAIT 能再回 ACK;若立刻关掉,对端会收到 RST。
2. **让旧连接的迷途包消散**:等足够久,网络里属于这条连接的延迟包都过期,避免污染之后**相同四元组**的新连接。

**大量 TIME_WAIT 要紧吗?** 通常**无害**——它出现在主动关闭方(如反向代理、短连接客户端),每个占一点内存和一个四元组,60s 后自动消失。**唯一真问题**:客户端用固定源 IP 对固定目标发起海量短连接时,**本地临时端口被 TIME_WAIT 占满 → 端口耗尽**,新连接建不出来。

**怎么处理(按优先级):**
1. **根治**:用**长连接 / 连接池**减少连接创建(HTTP keep-alive、DB 连接池)——这才是正道。
2. 客户端侧可开 `net.ipv4.tcp_tw_reuse=1`:允许新连接安全复用处于 TIME_WAIT 的端口。
3. ⚠️ **别用 `tcp_tw_recycle`**:在 NAT 环境会丢连接,新内核已移除,是经典踩坑。

### 2.4 CLOSE_WAIT:不正常的,几乎一定是你代码的 bug(接 05 伏笔)

被动关闭方收到对端 FIN 后,进入 **`CLOSE_WAIT`**,然后**等待本端应用调用 `close()`** 才会发出自己的 FIN(进 LAST_ACK)继续挥手。

所以——**大量 `CLOSE_WAIT` = 本端应用收到了对端的关闭,却迟迟没有 `close()` 这个 socket**。它不会自己消失(在等你 close),会一直占着 fd 和连接。

| | TIME_WAIT | CLOSE_WAIT |
|---|---|---|
| 出现在 | **主动**关闭方 | **被动**关闭方 |
| 成因 | 协议正常机制 | **应用没 close()** |
| 会自己消失吗 | 会(2×MSL 后) | **不会**(等你 close) |
| 大量堆积说明 | 短连接多(多半无害) | **代码 bug**:漏关连接/连接池没回收 |

> 记忆口诀:**TIME_WAIT 是协议在等(主动方,会自己走);CLOSE_WAIT 是你在欠(被动方,等你 close)。** 看到一堆 CLOSE_WAIT,先去查代码漏没漏 `close`。

### 2.5 端口:监听端口 vs 临时端口

- **监听端口**:服务 `bind` 的固定端口(如 80、3306)。
- **临时端口(ephemeral)**:客户端发起连接时内核自动分配,范围由 `net.ipv4.ip_local_port_range` 决定(默认约 `32768–60999`,约 2.8 万个)。

**本地端口耗尽**:单机客户端对**同一目标**发起海量短连接,临时端口 +(TIME_WAIT 占用)用尽 → `Cannot assign requested address`。解法:扩大 port range、用连接池、分散到多目标。

### 2.6 连接队列:半连接 与 全连接(backlog)

服务端 `listen` 时,内核维护两个队列:
- **半连接队列(SYN queue)**:收到 SYN、还没完成握手的连接。
- **全连接队列(accept queue)**:已完成三次握手、**等应用 `accept()` 取走**的连接;上限是 `min(backlog, somaxconn)`。

**全连接队列满**(应用 accept 太慢 / `backlog` 太小 / 瞬时高并发)→ 新完成的连接被丢弃或拒绝 → 客户端表现为**偶发连接超时或被重置**。`ss -lnt` 看监听 socket:`Recv-Q` = 当前全连接队列中的连接数,`Send-Q` = 队列上限。

### 2.7 DNS 解析路径

应用要连 `api.example.com`,解析顺序大致:
```
/etc/nsswitch.conf(hosts: 行决定顺序)
   → /etc/hosts(本地静态映射,先查)
   → /etc/resolv.conf 里的 nameserver(发 DNS 查询)
```
解析慢/失败的排查从这条链入手(容器里常是 `resolv.conf` 或 `ndots` 配置问题)。

### 2.8 「连不上服务」的分层排查(为 07 铺垫)

一层层往下定位,别一上来抓包:

```
① DNS 能解析吗?      dig / nslookup           → 解析不了:DNS 问题
② 能到对端主机吗?    ping(可能被禁 ICMP)      → 不通:路由/网络
③ 端口通吗?          nc -vz host port / curl  → refused / timeout(见下)
④ 服务在监听吗?      ss -lnt(在对端机器上)    → 没监听:服务没起/绑错地址
⑤ 看握手细节         tcpdump 抓 SYN           → 终极手段
```

**`refused` vs `timeout`(高频题):**
- **`Connection refused`**:包到了对端主机,但**那个端口没人监听**,对端回了 **RST**。→ 服务没起、或端口/地址绑错。
- **`Connection timed out`**:包发出去**没有任何回应**。→ 防火墙/安全组**丢包(DROP)**、路由不通、或主机不可达。

---

## 三、怎么看(命令 + 真实输出怎么读)

### 连接状态总览与统计:`ss`

```console
$ ss -s                          # 一眼看各状态总数
Total: 230
TCP:   180 (estab 40, closed 100, timewait 95, ...)

$ ss -tan | awk 'NR>1{print $1}' | sort | uniq -c   # 按状态计数
     40 ESTAB
     95 TIME-WAIT
     12 CLOSE-WAIT          # ← 这个多了就该查代码
```

### 看监听端口 + 全连接队列:`ss -lnt`

```console
$ ss -lnt
State   Recv-Q  Send-Q  Local Address:Port
LISTEN  0       128     0.0.0.0:8000       # Send-Q=128 是 backlog 上限
LISTEN  5       128     0.0.0.0:3306       # Recv-Q=5 当前积压(持续接近128=队列要满)
```

### 带进程看是谁在连:`ss -tanp`(需权限看别人的)

```console
$ sudo ss -tanp state close-wait
ESTAB ... users:(("java",pid=4242,fd=87))   # 直接定位到漏 close 的进程和 fd
```

### DNS / 连通性 / 抓包

```console
$ dig api.example.com +short          # 解析结果
$ nc -vz 127.0.0.1 8000               # 探端口:succeeded / refused / timed out
$ curl -v http://127.0.0.1:8000/      # 看完整请求与 TCP 建连
$ sudo tcpdump -i any -nn 'tcp port 8000'   # 抓该端口的包看握手
$ cat /proc/sys/net/ipv4/ip_local_port_range   # 临时端口范围
```

---

## 四、动手实验(沙箱)

> 🧪 在 `multipass shell linux-lab` 里跑;Ubuntu 自带 `python3`,用来起测试服务。

**实验 1:看连接状态、建一条连接**
```bash
ss -s
python3 -m http.server 8000 >/dev/null 2>&1 & SRV=$!
curl -s http://127.0.0.1:8000/ >/dev/null
ss -tan '( sport = :8000 or dport = :8000 )'
kill $SRV
```

**实验 2:制造一堆 TIME_WAIT**
```bash
python3 -m http.server 8000 >/dev/null 2>&1 & SRV=$!
for i in $(seq 1 100); do curl -s http://127.0.0.1:8000/ >/dev/null; done
echo "== TIME-WAIT 数量 =="; ss -tan state time-wait | grep -c 8000
kill $SRV
```

**实验 3:制造 CLOSE_WAIT(复现代码 bug 场景)**
```bash
# 起一个"收了连接但永远不 close"的服务
python3 -c '
import socket,time
s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
s.bind(("127.0.0.1",9999)); s.listen()
c,_=s.accept()          # 接受后什么都不做、不 close
time.sleep(300)
' & SRV=$!
sleep 1
exec 7<>/dev/tcp/127.0.0.1/9999   # bash 建一条 TCP 连接(client)
exec 7>&-                          # client 主动关闭 → 发 FIN
sleep 1
echo "== server 侧应在 CLOSE-WAIT(收到FIN但没close),client 侧 FIN-WAIT-2 =="
ss -tan '( sport = :9999 or dport = :9999 )'
kill $SRV
```

**实验 4:`refused` vs `timeout`**
```bash
echo "== 没人监听的端口 → refused(对端回 RST)=="
nc -vz 127.0.0.1 65000 2>&1 | tail -1
echo "== 不可达地址 → timeout(包石沉大海)=="
nc -vz -w 3 10.255.255.1 80 2>&1 | tail -1
```

**实验 5:tcpdump 抓三次握手**
```bash
python3 -m http.server 8000 >/dev/null 2>&1 & SRV=$!
sudo timeout 5 tcpdump -i lo -nn 'tcp port 8000' & sleep 1
curl -s http://127.0.0.1:8000/ >/dev/null
sleep 1; kill $SRV
# tcpdump 输出里看 [S] / [S.] / [.] 即 SYN / SYN-ACK / ACK
```

---

## 五、生产踩坑框 ⚠️

> **看到一堆 `TIME_WAIT` 先别调内核**:确认是不是短连接太多。根治是上长连接/连接池;客户端侧端口紧张才考虑 `tcp_tw_reuse=1`。**永远别开 `tcp_tw_recycle`**(NAT 下丢连接,新内核已删)。

> **一堆 `CLOSE_WAIT` = 你的 bug**:应用收到对端关闭却没 `close()`。`sudo ss -tanp state close-wait` 直接定位到进程;查代码:HTTP response body 没关、DB 连接没归还连接池、`defer Close()` 漏写。既泄漏 fd 又泄漏连接(接 `05`)。

> **偶发连接超时、压测上不去**:看 `ss -lnt` 的 `Recv-Q` 是否持续接近 `Send-Q`(全连接队列满)→ 调 `net.core.somaxconn` + 应用 `backlog`,并加快 accept/处理。

> **容器里 DNS 解析慢**:常因 `/etc/resolv.conf` 的 `ndots:5`(K8s 默认),非 FQDN 域名会被拼接 search 域多次查询;用 FQDN(带末尾 `.`)或调 `ndots` 缓解。

> **客户端 `Cannot assign requested address`**:本地临时端口耗尽(单机狂连同一目标)。扩 `ip_local_port_range`、用连接池、分散目标。

---

## 六、本章面试速记

- **大量 `TIME_WAIT` 在哪一方、要紧吗、怎么办?** 主动关闭方;通常无害(60s 自消),除非客户端端口被占满;根治用长连接/连接池,客户端可 `tcp_tw_reuse`,别用 `tcp_tw_recycle`。
- **大量 `CLOSE_WAIT` 说明什么、怎么修?** 被动关闭方的应用没 `close()` socket;是代码 bug,`ss -tanp` 定位进程后修漏关的连接。
- **TIME_WAIT 与 CLOSE_WAIT 区别?** TIME_WAIT 在主动方、协议正常机制、会自消;CLOSE_WAIT 在被动方、因应用没 close、不会自消。
- **`refused` 和 `timeout` 区别?** refused=端口没监听对端回 RST(服务没起/绑错);timeout=包没回应(防火墙 DROP/路由不通)。
- **全连接队列满会怎样、怎么看?** 新连接被丢/拒,客户端偶发超时;`ss -lnt` 看 `Recv-Q`/`Send-Q`,调 `somaxconn` + backlog。
- **连不上服务怎么排查?** DNS(dig)→ 主机(ping)→ 端口(nc/curl)→ 监听(ss -lnt)→ 抓包(tcpdump)。

---

## 七、小结 + 桥接 + 延伸

**一句话记忆点**:
> 连接是四元组 + 一个 socket fd;主动关闭进 `TIME_WAIT`(协议正常、会自消),被动关闭进 `CLOSE_WAIT`(你没 close、不会自消);排查连通性按 DNS→主机→端口→监听→抓包分层,`refused` 是没监听、`timeout` 是没回应。

**四语言桥接**(核心都是「用连接池/长连接避免反复建连」):

| 关注点 | Java | Go | Python | Node/JS |
|------|------|-----|--------|---------|
| 连接池(防 TIME_WAIT) | HikariCP / HttpClient keep-alive | `database/sql` 池 / `http.Transport` | `requests.Session` / DBAPI 池 | `http.Agent({keepAlive})` / pool |
| 漏 close → CLOSE_WAIT/fd 泄漏 | 没关 `Connection`/`InputStream` | 漏 `defer resp.Body.Close()` | 没 `with`/没 close | 没消费/关闭 response |
| 优雅关闭(停止 accept) | Spring shutdown | `server.Shutdown(ctx)` | asyncio server close | `server.close()` |

→ 优雅关闭接 [`03 信号/SIGTERM`](../03-process-model/);epoll 多路复用接 [`05`](../05-io-and-files/) 与你的并发笔记。应用层协议(HTTP/WebSocket/SSE)细节见仓库已有的 [`network/`](../../network/)(`http.md`、`websocket.md` 等)。

**延伸指针**:
- TCP 核心机制(滑动窗口、拥塞控制、重传)→ `performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md`
- socket 内核路径 → `performance-tuning-roadmap/00-os-fundamentals/04b-network-socket-kernel.md`
- 连接问题 / 丢包延迟 / 抓包实战 → `performance-tuning-roadmap/08-network-io/`(`02-connection-issues.md`、`03-packet-loss-latency.md`、`01-tcpdump-wireshark.md`)

➡️ 至此「内核四大资源」(进程/内存/IO/网络)全部打通。下一章:[`07 · 排查方法论与工具箱`](../07-troubleshooting-playbook/),把 03–06 串成一套系统化排查流程。
