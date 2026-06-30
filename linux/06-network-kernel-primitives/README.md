# 06 网络内核原语

> **这章解决什么问题**
>
> 你已经知道应用层有 socket、连接池、`epoll`、HTTP/gRPC，但线上真正出问题时经常会落到这些问题：`listen backlog` 到底堵在哪里？`accept` 慢为什么会丢连接？`Recv-Q` / `Send-Q` 是什么？网卡中断、软中断、NAPI、`sk_buff` 和 socket buffer 是什么关系？本章补齐「网络包从网卡到进程」这条内核路径。

**依赖**：

- syscall、中断、软中断、调度 → [`linux/02-execution-primitives`](../02-execution-primitives/README.md)
- fd、阻塞/非阻塞、epoll → [`linux/03-io-primitives`](../03-io-primitives/README.md)
- futex、线程等待/唤醒 → [`linux/04-concurrency-primitives`](../04-concurrency-primitives/README.md)
- 网络指标解码 → [`metrics-decoder/04-network`](../../metrics-decoder/04-network.md)

**三层怎么读：**

- **① 你视角** — 先从服务端 `ServerSocket` / Go `net.Listen` / Python `socket` 的行为理解。
- **② 黑盒内部** — 看 kernel socket object、队列、buffer、协议栈、软中断如何协作。
- **③ 砸实** — 用 `ss`、`/proc/net/softnet_stat`、`/proc/softirqs`、`ethtool` 看证据。

---

## 原语一：socket 不是普通变量，而是 fd 背后的内核对象

### ① 你视角

Java 里一个 `Socket`，Go 里一个 `net.Conn`，Python 里一个 `socket.socket()`，表面上都是语言对象。真正执行 `read` / `write` 时，它们最终都落到一个 Linux 文件描述符。

所以 socket 首先是一个 **fd**：可以 `read`、`write`、`poll`、`epoll`、`close`。

### ② 黑盒内部

用户态看到的是整数 fd，内核里大致是这条引用链：

```text
process fd table
  fd number
    → struct file
      → struct socket
        → struct sock
          → TCP/UDP protocol state
          → receive queue / send queue
          → local addr / remote addr / state
```

普通文件的 fd 背后接的是 inode/page cache；socket fd 背后接的是协议栈状态和网络队列。因此：

- `read(socket_fd)` 不是从磁盘读，而是从 socket receive queue 取数据。
- `write(socket_fd)` 不是写文件，而是把数据放进 send buffer，再由 TCP/IP 协议栈发出去。
- `epoll` 监听 socket，本质是监听这些队列/状态是否满足「可读」「可写」「出错」。

### ③ 砸实

```bash
ls -l /proc/$$/fd
ss -tanp
```

看点：

- `/proc/<pid>/fd/<n>` 里 socket 会显示成 `socket:[inode]`。
- `ss -tanp` 能把 TCP 状态、队列和进程关联起来。

---

## 原语二：connect / listen / accept 创建的是不同角色的 socket

### ① 你视角

服务端写：

```text
bind → listen → accept
```

客户端写：

```text
connect
```

这些 API 不是简单地「打开网络」，而是在内核里创建不同角色的 socket 状态。

### ② 黑盒内部

服务端 `listen` 后有一个 **listening socket**，它只负责接收新连接请求，不直接承载某个客户端连接的数据流。

当三次握手完成后，内核为这个客户端创建一个新的 **connected socket**，再由 `accept` 把这个新 socket 交给应用。

```text
server socket:
  socket()
  bind(0.0.0.0:8080)
  listen()
    → listening socket

client:
  connect(server:8080)
    → SYN / SYN-ACK / ACK

server kernel:
  handshake complete
    → create connected socket
    → put into accept queue

server app:
  accept()
    → returns new fd for connected socket
```

所以服务端至少有两类 fd：

| fd | 角色 |
|---|---|
| listening fd | 监听端口，只负责接新连接 |
| accepted fd | 某个客户端连接的数据通道 |

### ③ 砸实

```bash
ss -ltn
ss -tan state established
```

看点：

- `LISTEN` 状态的是 listening socket。
- `ESTAB` 状态的是已经建立的连接。

---

## 原语三：SYN queue 和 accept queue 是两段不同的排队

### ① 你视角

服务端压测时可能看到：

- 客户端连接超时。
- `connect` 很慢。
- 服务端 CPU 不高，但新连接进不来。
- 调大线程池没用，调 `backlog` 或 `somaxconn` 才有变化。

这通常和连接建立阶段的两个队列有关。

### ② 黑盒内部

TCP 服务端连接建立至少涉及两段队列：

```text
client SYN
  → SYN queue / half-open queue
    等待三次握手完成
  → accept queue / completed queue
    握手完成，等待应用 accept()
  → application accept()
```

| 队列 | 放什么 | 堵住时的现象 |
|---|---|---|
| SYN queue | 收到 SYN，但握手还没完成的半连接 | SYN flood、网络抖动、握手失败、重传 |
| accept queue | 握手完成，但应用还没 `accept` 的连接 | 新连接看起来卡住，应用 accept 太慢 |

`listen(fd, backlog)` 主要影响完成握手后等待 `accept` 的队列长度，但最终上限还受系统参数影响，例如 `net.core.somaxconn`。SYN 队列还会受 `net.ipv4.tcp_max_syn_backlog` 等参数影响。

### ③ 砸实

```bash
ss -ltn
sysctl net.core.somaxconn
sysctl net.ipv4.tcp_max_syn_backlog
```

`ss -ltn` 的常见看法：

```text
State   Recv-Q Send-Q Local Address:Port
LISTEN  0      4096   0.0.0.0:8080
```

对 `LISTEN` socket：

- `Recv-Q` 常用于观察当前等待 `accept` 的完成连接数。
- `Send-Q` 常显示该监听 socket 的 backlog 上限。

不要只看一个瞬时值。连接风暴通常是尖峰问题，需要结合压测时间线、应用 `accept` 线程、系统参数和 TCP 重传指标一起看。

---

## 原语四：socket buffer 是应用和协议栈之间的缓冲层

### ① 你视角

你调用 `write(socket, bytes)` 后，不代表对端应用已经读到。你调用 `read(socket)` 阻塞，也不代表网卡没收到包。中间隔着内核 socket buffer。

### ② 黑盒内部

每个 TCP socket 都有接收和发送方向的缓冲：

```text
receive path:
  NIC / protocol stack
    → socket receive buffer
      → application read()

send path:
  application write()
    → socket send buffer
      → TCP/IP stack
        → NIC
```

这些 buffer 决定了很多应用层现象：

| 现象 | 内核语义 |
|---|---|
| `read` 阻塞 | receive buffer 没有满足条件的数据 |
| fd 可读 | receive buffer 有数据，或连接关闭/出错 |
| `write` 阻塞 | send buffer 没空间，或 TCP 窗口/拥塞限制 |
| fd 可写 | send buffer 有空间，不代表对端已经处理 |
| 非阻塞写返回 `EAGAIN` | 现在没有足够 buffer 空间，稍后再试 |

TCP 还有流控和拥塞控制。即使本机应用写得很快，数据也不一定立刻离开机器；它可能先堆在 send buffer，等待对端窗口、拥塞窗口、网卡队列等条件。

### ③ 砸实

```bash
ss -tin
sysctl net.ipv4.tcp_rmem
sysctl net.ipv4.tcp_wmem
```

看点：

- `ss -tin` 可以看到单连接更细的 TCP 信息，如 RTT、拥塞窗口、发送/接收队列等。
- `tcp_rmem` / `tcp_wmem` 是 TCP 自动调节 buffer 的范围，不是每条连接固定占用这么多。

---

## 原语五：sk_buff 是内核网络包的载体

### ① 你视角

应用层看到的是字节流，尤其 TCP 没有消息边界。但内核协议栈处理网络时，需要在不同层之间传递「一个包」及其元信息。

这个载体就是 `sk_buff`，常简称 `skb`。

### ② 黑盒内部

`sk_buff` 不只是包内容，它还带着协议栈处理需要的元数据：

```text
struct sk_buff
  packet data pointer
  headroom / tailroom
  protocol headers offset
  device info
  checksum info
  routing / qdisc metadata
  list pointers
```

网络包在内核里大致这样走：

```text
RX:
  NIC DMA buffer
    → skb
      → L2/L3/L4 protocol stack
        → socket receive queue

TX:
  socket send buffer
    → skb
      → qdisc
        → driver
          → NIC DMA
```

TCP 对应用暴露的是流，但底层仍然会按 MSS、拥塞窗口、网卡能力等拆分/合并成多个 skb。理解这一点可以避免把「一次 write」误认为「一个网络包」。

### ③ 砸实

`sk_buff` 本身不是日常直接看的对象。通常通过这些现象间接观察：

```bash
ss -tin
ip -s link
ethtool -S eth0
```

看点：

- `ip -s link` 看接口级收发包/错误/丢弃。
- `ethtool -S` 看网卡驱动统计，字段因驱动而异。
- 更深入要用 tracepoint / eBPF 跟踪 skb 生命周期，见 [`linux/10-observability-kernel-primitives`](../10-observability-kernel-primitives/README.md)。

---

## 原语六：网卡到进程的接收路径

### ① 你视角

你看到 Java/Go 线程从 socket `read` 到数据，好像数据是「网络直接送到线程」。实际路径更长：网卡先把包放到内存，内核在中断和软中断上下文里处理，最后才把数据挂到 socket receive queue。

### ② 黑盒内部

典型 RX 路径：

```text
packet arrives at NIC
  → NIC DMA writes packet into RX ring buffer
  → NIC raises hardware interrupt
  → driver interrupt handler schedules NAPI poll
  → NET_RX softirq runs protocol stack
  → IP/TCP processing
  → data appended to socket receive queue
  → waiting task / epoll waiters are woken
  → application read()
```

为什么要有 NAPI？

如果每个包都触发一次硬中断，高流量下 CPU 会被中断打爆。NAPI 的思路是：有包来时先用中断唤醒，随后切到 poll 模式在软中断里批量收包，减少中断风暴。

这也是为什么网络高负载时你可能看到：

- `si` 软中断 CPU 时间升高。
- `/proc/softirqs` 里 `NET_RX` 增长很快。
- `/proc/net/softnet_stat` 出现 backlog/drop 相关增长。

### ③ 砸实

```bash
cat /proc/softirqs
cat /proc/net/softnet_stat
mpstat -P ALL 1
```

看点：

- `NET_RX` / `NET_TX` 是网络收发软中断。
- 某几个 CPU 的 `NET_RX` 特别高，可能和 RSS/RPS/XPS、网卡队列绑定有关。
- `softnet_stat` 字段需要按内核版本解释，常用于观察每 CPU 网络 backlog 和 drop 趋势；不要脱离版本直接死背列号。

---

## 原语七：epoll 监听的是 socket 状态，不是业务消息

### ① 你视角

很多服务端框架说「epoll 收到事件」，容易让人误以为事件就是一条完整请求。实际上 epoll 只告诉你 fd 的内核状态变了：可读、可写、挂断、错误。

### ② 黑盒内部

对 socket 来说：

```text
可读:
  receive buffer 有数据
  或对端关闭
  或 socket 出错

可写:
  send buffer 有空间
  不代表对端应用已经读到

挂断/错误:
  TCP state / error queue 改变
```

这带来几个重要结论：

- TCP 是字节流，一次 `epoll` 可读不等于一个完整 HTTP 请求。
- 一次 `read` 可能读到半个请求，也可能读到多个请求。
- 边缘触发 `EPOLLET` 下必须读到 `EAGAIN`，否则缓冲区剩余数据可能不会再次触发事件。
- `EPOLLOUT` 常常一直为真；只有在 send buffer 曾经写满后，等待可写才有意义。

### ③ 砸实

```bash
strace -e trace=epoll_wait,accept4,read,write -p <pid>
ss -tinp
```

看点：

- `epoll_wait` 返回后，应用通常还要循环 `accept` / `read` / `write`。
- `ss -tinp` 的队列状态能解释「epoll 有事件但业务慢」和「业务想写但内核发不动」的差异。

---

## 本章速查

| 问题 | 先看哪里 |
|---|---|
| 新连接建立慢/超时 | `ss -ltn`、accept 线程、`somaxconn`、`tcp_max_syn_backlog` |
| 连接很多但请求处理慢 | `ss -tanp`、应用线程池、socket receive/send queue |
| `si` 高 | `/proc/softirqs`、`NET_RX` / `NET_TX`、网卡队列、包量 |
| 丢包 | `ip -s link`、`ethtool -S`、`/proc/net/softnet_stat`、协议层重传 |
| epoll 事件理解混乱 | 回到「ready 是 fd 状态，不是业务消息」 |

**最小心智模型**：

```text
fd
  → socket object
    → TCP state
    → receive/send buffer
    → sk_buff
    → protocol stack
    → NIC queue
```

下一章：[`07 容器与 cgroup 原语`](../07-container-cgroup-primitives/README.md)
