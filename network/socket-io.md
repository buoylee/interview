# Socket 编程与 IO 模型

更新时间：2026-04-17

**上下文**：
- **上游**（读本文前建议先懂）：[`basic.md`](./basic.md) —— TCP/UDP 协议与状态机
- **下游**（读完可以接着看）：[`http.md`](./http.md) §6（连接管理）、[`websocket.md`](./websocket.md)（WebSocket 服务端实现基础）
- **索引**：[`README.md`](./README.md)

目标：读完你应该能——

- 说出 `socket → bind → listen → accept → read/write` 每一步**内核在干什么**
- 解释 `listen` 的 backlog **到底控制的是哪个队列**
- 从根因上理解**为什么 TCP 会粘包**、应用层怎么分帧
- 画出 **5 种 IO 模型**并定位它们在"**等数据 + 拷数据**"两阶段上的差异
- 讲清楚 `select / poll / epoll` **每一代解决了上一代的什么问题**
- 选得出 Reactor 模式的单线程 / 多线程 / 主从版本
- 看到 `too many open files` / `EAGAIN` / `Address already in use` 能分诊

---

## 0. 导读

这篇文档把你从"TCP 协议本身"（`basic.md`）带到"**怎么用 TCP 写出能扛百万并发的服务**"。三个主题：

1. **Socket API**：和内核怎么打交道
2. **字节流与分帧**：TCP 给你的是流，你要自己切消息
3. **IO 模型与并发**：一个线程能盯多少连接

三者密不可分。讲 `listen` 的 backlog 离不开并发模型；讲粘包的"长度前缀"方案离不开 `read` 的行为；讲 epoll 的优势离不开"一个 socket 是一个 fd"这个前提。**线性读下去，别跳**。

---

## 1. Socket 是什么

### 1.1 一句话定义

**Socket = 文件描述符（fd）+ 协议族抽象**。

Unix 哲学里"一切皆文件"，网络连接也不例外。一个 socket 在用户态就是一个整数（fd），对它 `read/write` 就等于收发数据。内核在 fd 背后挂一整套 TCP/UDP 协议栈。

```
用户态：  fd = 5
          │
          ▼
内核态：  [文件表项] ──► [socket 对象] ──► [协议栈] ──► [网卡]
                        类型: TCP/UDP        ↑
                        状态: ESTABLISHED  拥塞控制 / 重传 / 缓冲区
                        本地: 1.2.3.4:8080
                        对端: 5.6.7.8:54321
```

### 1.2 协议族参数

创建 socket 时三个参数决定协议族：

```c
socket(domain, type, protocol)
```

| 参数 | 常见值 | 含义 |
|---|---|---|
| domain | `AF_INET` / `AF_INET6` / `AF_UNIX` | IPv4 / IPv6 / 本机进程间 |
| type | `SOCK_STREAM` / `SOCK_DGRAM` / `SOCK_RAW` | 字节流（TCP） / 数据报（UDP） / 原始 |
| protocol | 0（让内核按 type 选）| 一般写 0 |

### 1.3 Unix Domain Socket：被忽略的"本机最快 IPC"

`AF_UNIX`+ `SOCK_STREAM` 是**本机进程间**的 socket，API 和 TCP 一样，但**不走 TCP/IP 栈**——内核直接拷。比 loopback（127.0.0.1）还快，没端口概念，用文件路径作地址。

常见用户：Docker Daemon (`/var/run/docker.sock`)、MySQL（本地连接可走 unix socket）、Postgres 同理。

---

## 2. 服务端 / 客户端 API 流水

### 2.1 服务端模板

```
    socket()        ← 创建 fd
       │
    bind()          ← 绑定到某个 IP:Port
       │
    listen()        ← 标记为被动，内核开始接受握手
       │
       ▼
    ┌─► accept()    ← 阻塞等已完成握手的连接
    │      │
    │   返回新的 fd  ← 这个 fd 才是"和具体客户端的通道"
    │      │
    │   read/write  ← 传数据
    │      │
    │   close()     ← 关这个连接
    │      │
    └──────┘        ← 回到 accept() 等下一个

   （服务端的"监听 fd"自己是另一个 fd，不用关）
```

**关键直觉**：**`listen` 的 fd 和 `accept` 返回的 fd 不是同一个**。前者是"大门口的接待"，后者是"给每个客人的专属走廊"。

### 2.2 客户端模板

```
    socket()
       │
    connect()     ← 发起三次握手
       │
    read/write
       │
    close()
```

客户端可以跳过 `bind`（内核自动分配本地端口）；服务端也能跳过 `bind`（但那就没法被连了，所以实际不会跳）。

### 2.3 每一步内核做什么

| API | 内核做的事 |
|---|---|
| `socket()` | 分配 socket 对象，挂到进程 fd 表 |
| `bind()` | 把 IP:Port 绑定到这个 socket（检查是否被占） |
| `listen(fd, backlog)` | 标记为被动 socket，创建半/全连接队列 |
| `accept()` | 从全连接队列取一条，返回新 fd |
| `connect()` | 发 SYN，等握手，建立后返回 |
| `read()` | 从接收缓冲区读（缓冲区空 → 阻塞 or 返回 EAGAIN） |
| `write()` | 写到发送缓冲区（缓冲区满 → 阻塞 or 返回 EAGAIN） |
| `close()` | 减引用计数，到 0 则发 FIN 并回收 |

---

## 3. listen 的 backlog 到底是啥

`listen(fd, backlog)` 的 `backlog` 历史上含义变过，现代 Linux 上它**只控制全连接队列**。

### 3.1 两个队列再次出现

（回顾 `basic.md §4.4`）

```
SYN 到 ──► [半连接队列] ──握手完成──► [全连接队列] ──► accept() 取走
           SYN_RECV                    ESTABLISHED
           大小: tcp_max_syn_backlog   大小: min(backlog, somaxconn)
```

- **半连接队列**：内核参数 `net.ipv4.tcp_max_syn_backlog`，**和 listen 的 backlog 无关**
- **全连接队列**：应用 `listen(fd, backlog)` 的 backlog 和系统 `net.core.somaxconn` 的较小值

### 3.2 队列溢出会怎样

**全连接队列满**（应用 `accept()` 太慢）：
- 默认行为：**丢掉握手第 3 次的 ACK**，客户端重传，还满就放弃
- 可改 `net.ipv4.tcp_abort_on_overflow=1` 变成发 RST（快速失败）
- **观察**：`ss -lnt` 显示的 `Recv-Q` 就是当前全连接队列长度

**半连接队列满**：
- 默认：丢弃 SYN
- `net.ipv4.tcp_syncookies=1` → 启用 SYN Cookie 绕过队列（抗 SYN flood）

### 3.3 为什么应用配 backlog=1024 没用

**两处短板效应**：
- `listen(fd, 1024)`，但 `net.core.somaxconn` 默认 128 → 实际是 128
- 先改 `sysctl -w net.core.somaxconn=65535` 才能放开

Go / Java / nginx 等默认 backlog 往往很大（Go 默认 `somaxconn` 的值），**瓶颈一般在内核参数**。

---

## 4. TCP 是字节流：粘包的根因

### 4.1 流 vs 报文

- **UDP**：发一次 sendto 就是一个独立数据报，收端 recvfrom 拿到的是**完整一个报文**，要么一整个，要么没有
- **TCP**：**没有"消息"这个概念**。你 `write(fd, "hello", 5)` 两次，对方 `read` 可能一次性拿到 `"hellohello"`，也可能第一次拿到 `"he"` 第二次 `"llohello"`

**根因**：TCP 的抽象是**字节流**，就像文件。"消息边界"是**应用层的概念**，TCP 不管。

### 4.2 为什么 TCP 不保持消息边界

工程上的权衡：

- **Nagle 算法**：为减少小包，发送方把短时间内的小 write 合并成一个段。消息边界在发送方就被抹平
- **MSS 切分**：一个大 write 被切成多个段分别发
- **接收方缓冲区合并**：连续到达的段内容被直接拼在缓冲区里

**三种翻车**（站在接收方视角）：

| 术语 | 现象 | 成因 |
|---|---|---|
| **粘包** | 多条消息被一次 read 全部收到 | 发送方 Nagle 合并 / 接收方 read 慢 |
| **半包** | 一条消息被拆成多次 read | 大消息超 MSS / 接收方 read 缓冲区小 |
| **错位** | 上一条没读完，下一条已经开始 | 上面两种的组合 |

### 4.3 Nagle 算法与 TCP_NODELAY

**Nagle**：如果前一个发出的小段还没被 Ack，新的小 write 就先攒着，直到**要么凑够 MSS、要么前段被 Ack**。目的：减少小包充斥网络（比如每个键盘敲击都发一个包）。

**禁用**：`setsockopt(fd, IPPROTO_TCP, TCP_NODELAY, 1)` 让小包立即发送。

**什么时候要禁**：
- 低延迟要求（游戏、交易、RPC）
- 应用已经自己做了批量合并
- 交互式协议（telnet、SSH 曾经默认禁）

HTTP/1.1 长连接 + 流水线（pipelining）时代，Nagle 和延迟 Ack 共同导致"400ms 卡顿"——很多 HTTP 客户端都默认开 `TCP_NODELAY`。

### 4.4 HTTP 为什么不需要担心粘包

因为 HTTP **已经在应用层做了分帧**：

- `Content-Length: N` → 读完 N 字节就是一条响应
- `Transfer-Encoding: chunked` → 按 chunk 协议读（见 [`http.md §2.4`](./http.md)）

所以你用 HTTP 库收请求时从没遇到"粘包"，是因为 HTTP **设计了消息边界**，库替你处理了。

---

## 5. 应用层分帧的三种方案

### 5.1 方案对比

| 方案 | 做法 | 优点 | 缺点 |
|---|---|---|---|
| **定长** | 每条消息固定字节数 | 最简单 | 浪费（短消息补零）或不够（长消息放不下） |
| **分隔符** | 特定字符/序列作结束 | 简单、可读 | 消息里不能含该字符（要转义） |
| **长度前缀** | 先发 4 字节长度 N，再发 N 字节体 | 最通用、最高效 | 需要处理"连长度还没收齐"的情况 |

### 5.2 长度前缀为什么是工业主流

几乎所有现代二进制协议都用长度前缀：

- Redis RESP 协议：`*3\r\n$3\r\nSET\r\n...`（混用分隔符和长度）
- gRPC（HTTP/2 帧）：每帧头里有 `Length` 字段
- WebSocket（见 [`websocket.md`](./websocket.md)）：帧头里有 payload length
- Kafka 消息、Protobuf 在 wire 上一般也配长度前缀

**为什么好**：
- 不依赖内容（二进制安全）
- 不需要扫描找分隔符，读固定字节就行
- 收到长度就知道还需要读多少，精确控制 `read` 次数

### 5.3 Netty 的 LengthFieldBasedFrameDecoder

Java 生态里最常见的粘包处理器。核心参数：

- `lengthFieldOffset` — 长度字段在帧里的偏移
- `lengthFieldLength` — 长度字段占几字节
- `lengthAdjustment` — 长度字段表示的是"还差多少字节"还是"总长度"
- `initialBytesToStrip` — 解析完丢掉前面几个字节

有这一个 decoder，绝大多数自定义二进制协议都不用自己写状态机。

### 5.4 正确的分帧伪代码

用长度前缀演示：

```python
buf = bytearray()
while True:
    chunk = sock.recv(4096)
    if not chunk:
        break
    buf += chunk
    while len(buf) >= 4:
        msg_len = int.from_bytes(buf[:4], 'big')
        if len(buf) < 4 + msg_len:
            break   # 长度读够了但体还没到齐
        msg = buf[4:4+msg_len]
        handle(msg)
        buf = buf[4+msg_len:]
```

**关键点**：
- **一次 recv 可能读到 0 条或多条完整消息**
- **循环解析直到数据不够一条**
- **剩下的字节留在 buf 里等下次 recv**

新手常见错误：`if len(buf) >= 4 + msg_len: ...` 只解一条就 continue，有粘包时前两条一起到，第二条要等下一次 recv 才会被处理——延迟叠加。

---

## 6. 阻塞 vs 非阻塞

### 6.1 阻塞 IO 的默认行为

```python
fd = socket(...)
sock.connect(...)
data = sock.recv(4096)   # 如果没数据，这里卡住
```

`recv` 没数据就 block 线程。一个线程一次只能处理一个连接的 IO。想处理 10000 个连接 → 10000 个线程 → 内存爆。

### 6.2 非阻塞的 API 差异

把 fd 设为非阻塞：`fcntl(fd, F_SETFL, O_NONBLOCK)`。之后：

| 调用 | 有数据 | 没数据 / 缓冲区满 |
|---|---|---|
| `read` | 正常返回字节数 | 立即返回 -1 + `errno = EAGAIN` |
| `write` | 正常返回写入字节数 | 立即返回 -1 + `errno = EAGAIN` |
| `connect` | 若握手完即返回 0 | 返回 -1 + `errno = EINPROGRESS` |
| `accept` | 返回新 fd | 立即返回 -1 + `errno = EAGAIN` |

**`EAGAIN` 不是错误，是"现在没 IO，你等会再来"**。新手看到 EAGAIN 就 `retry` 死循环——CPU 100%。正确做法：**把这个 fd 交给 IO 多路复用器（select/epoll）监听，等它告诉你"可以读/写了"再来**。

### 6.3 非阻塞 + 多路复用 = 现代高性能服务器的基石

单线程非阻塞：

```python
epoll 监听一堆 fd
while True:
    ready_fds = epoll.wait()        # 阻塞等任何 fd 就绪
    for fd in ready_fds:
        if fd.can_read:
            data = fd.read()        # 保证有数据，不会 block
            process(data)
        if fd.can_write:
            fd.write(...)
```

一个线程就能撑上万连接——这就是 Redis / nginx / Node.js 的模型。

---

## 7. IO 两阶段模型：理解 5 种 IO 的钥匙

### 7.1 一次 read 实际发生了什么

```
阶段 1: 等数据到达（数据从网卡进内核缓冲区）
  ↓
阶段 2: 把数据从内核缓冲区拷到用户缓冲区
```

**5 种 IO 模型的差异就在于这两阶段谁阻塞、谁异步**。

### 7.2 5 种 IO 对齐到两阶段

| 模型 | 阶段 1（等数据） | 阶段 2（拷数据） |
|---|---|---|
| 阻塞 IO (BIO) | **阻塞** | 阻塞 |
| 非阻塞 IO (NIO) | **轮询**（EAGAIN 忙等） | 阻塞 |
| IO 多路复用 | **阻塞在 select/epoll** | 阻塞 |
| 信号驱动 IO | 不阻塞（等信号） | 阻塞 |
| **异步 IO (AIO)** | **不阻塞** | **不阻塞**（内核完成后通知） |

**关键认识**：

- 前 4 种都叫**同步 IO**——虽然阶段 1 处理方式不同，但**阶段 2 都是用户态同步等拷贝**
- 只有 AIO 是**真异步**——发起请求后用户态完全不管，内核拷完再通知

### 7.3 为什么阶段 2 通常不是瓶颈

阶段 2 是**内存拷贝**，一般微秒级，只要数据量不夸张，阻塞可以忽略。真正费时间的是阶段 1——等对方发数据或等缓冲区腾出空间。这是为什么多路复用（优化阶段 1）就足够大多数场景了。

**特殊场景**：大文件传输（几百 MB 响应），阶段 2 的拷贝开销可见 → 用 `sendfile` / `splice` 做**零拷贝**（内核态直接从文件 fd 挪到 socket fd，不过用户态）。

---

## 8. 五种 IO 模型详解

### 8.1 BIO（阻塞 IO）

```
while True:
    conn = accept()          # 阻塞
    thread = spawn(handle, conn)

def handle(conn):
    data = conn.read()       # 阻塞
    conn.write(response)     # 阻塞
```

**每个连接一个线程**。代码直白，但：
- 线程栈默认 1–8MB，1 万连接吃 10GB+ 内存
- 上下文切换开销随线程数线性上升
- **上限约几千连接**

**适用**：连接数 < 1000 的内部服务、学习代码、不在意性能的工具。

### 8.2 NIO（非阻塞 IO）

把 fd 都设为非阻塞，单线程轮询：

```python
while True:
    for fd in all_fds:
        data = fd.read()
        if data is EAGAIN:
            continue
        process(data)
```

**问题**：没数据时 CPU 空转 100%。仅在 fd 极少 + 有数据概率极高时勉强能用。**生产上几乎不单独用，只作为多路复用的底层**。

### 8.3 IO 多路复用

**"一个线程同时监听很多 fd，哪个就绪处理哪个"**。

```python
epoll.register(all_fds)
while True:
    ready = epoll.wait()    # 阻塞在这里
    for fd in ready:
        handle(fd)
```

这是**现代服务器的标配**。细节见 §9（select/poll/epoll 对比）。

### 8.4 信号驱动 IO（SIGIO）

注册一个信号处理器，让内核在数据到达时发 SIGIO 信号。

**用得很少**。理由：
- 信号异步，处理复杂且容易丢
- 信号携带信息有限
- 多路复用已经够用

知道有这东西就行。

### 8.5 异步 IO（AIO）

**用户发起请求就走**。内核读好数据、**拷到用户给的缓冲区**、完成后通过信号/回调/事件通知用户。

```python
aio_read(fd, buf, len, callback)
# 立即返回，之后 buf 里直接就是数据，callback 被调用
```

**Linux 上的两套 AIO**：

1. **Linux AIO (io_submit)**：1998 年加入，长期只对磁盘 IO 有用、对网络 socket 支持不完善 → **没普及**
2. **io_uring**（2019 年 Linux 5.1 加入）：Jens Axboe 重新设计的真·AIO。双环形队列（提交 + 完成）避免系统调用开销，对网络和磁盘都支持得好。**未来方向**，但目前生态还在追赶。

**Windows IOCP**：Windows 上的 AIO 实现，比 Linux 早且完善——这是为什么早期用 Windows 做高并发服务器（比如游戏）有优势。

---

## 9. select → poll → epoll 的演进

### 9.1 select（1983）

```c
fd_set readfds;
FD_ZERO(&readfds);
FD_SET(fd1, &readfds);
FD_SET(fd2, &readfds);
...
select(max_fd+1, &readfds, NULL, NULL, &timeout);
// 返回后要遍历所有 fd 看谁置位了
```

**三大瓶颈**：

1. **fd 数量有硬上限**（`FD_SETSIZE` 默认 1024）
2. **每次调用都要把整个 fd_set 从用户态拷到内核态**（O(n)）
3. **返回后要遍历全部 fd 找谁就绪**（O(n)）

典型用法在 1 万 fd 的场景下**每秒几万次 select**，每次都拷 1 万个 fd 的位图——CPU 跑不动。

### 9.2 poll（1986）

```c
struct pollfd fds[] = { {fd1, POLLIN, 0}, {fd2, POLLIN, 0}, ... };
poll(fds, n, timeout);
```

解决了第 1 个瓶颈（**没有 1024 上限**，数组能开多大就多大）。

**其它两个瓶颈依然存在**：
- 每次调用都拷整个数组到内核
- 返回后要遍历找就绪的

**poll 只是加大号的 select**。

### 9.3 epoll（2002，Linux 2.5.44）

**设计哲学变了**：不再"每次提交一堆 fd"，而是"**先告诉内核我关心哪些 fd，内核自己维护这张表，就绪时只把就绪的 fd 告诉我**"。

三个 API：

```c
int epfd = epoll_create1(0);                    // 创建 epoll 实例

struct epoll_event ev = { .events = EPOLLIN, .data.fd = sock };
epoll_ctl(epfd, EPOLL_CTL_ADD, sock, &ev);      // 注册

struct epoll_event events[1024];
int n = epoll_wait(epfd, events, 1024, -1);     // 等就绪
```

**解决了哪些瓶颈**：

1. **没有 fd 数量上限**（受内存限制）
2. **注册一次就行，内核维护 fd 集合，调用 `epoll_wait` 不再拷整个集合**
3. **`epoll_wait` 只返回就绪的 fd**（O(就绪数)，不是 O(总数)）

**性能直觉**：10 万个连接但只有 100 个活跃 → select/poll 每次扫 10 万，epoll 每次只返回 100。差几千倍。

### 9.4 LT vs ET 两种触发模式

**LT（Level Triggered，水平触发，默认）**：只要 fd 有数据可读，`epoll_wait` 就会一直通知你。**和 select/poll 语义一致**。

**ET（Edge Triggered，边缘触发）**：只在 fd 状态**变化时**通知一次。即使这次没读完剩余数据，下次 `epoll_wait` 不会再通知你直到又有新数据到。

**ET 的编程约束**：
- **必须配非阻塞 fd**
- **读/写时要循环读直到 `EAGAIN`**，否则会丢事件

**为什么还要 ET**：减少 `epoll_wait` 返回次数，性能略好。但编程复杂，Netty / nginx 默认用 LT。Redis 用的是 LT。

### 9.5 各语言/运行时怎么用

| 运行时 | 底层 |
|---|---|
| **Linux epoll** | — |
| **macOS / BSD kqueue** | 类似 epoll，API 不同 |
| **Windows IOCP** | 真正的 AIO |
| Go runtime | **epoll (LT) + goroutine**，写起来像 BIO |
| Java NIO / Netty | epoll（默认 NioEventLoop 用 epoll） |
| Node.js | libuv → epoll |
| Python asyncio | selectors → epoll |
| Redis | 直接用 epoll + 单线程 |
| nginx | epoll + 多 worker |

Go 的 **"写同步代码跑异步"** 非常讨巧——goroutine 阻塞时 runtime 把它从 M 解绑，转去跑别的 goroutine；fd 就绪后把 goroutine 重新挂回去。本质还是 epoll + 调度器。

---

## 10. Reactor 模式

**Reactor = 事件驱动的设计模式**。围绕"`epoll_wait` 返回就绪事件 → 派发到对应 handler"这个循环。

### 10.1 单 Reactor 单线程（Redis 模型）

```
┌─────────────────────────────────┐
│   一个线程                        │
│   │                             │
│   ├── epoll_wait                │
│   │                             │
│   ├── 若就绪的是 listen fd       │
│   │   → accept 新连接            │
│   │   → 注册进 epoll             │
│   │                             │
│   └── 若就绪的是 conn fd         │
│       → read → 业务逻辑 → write   │
└─────────────────────────────────┘
```

**优点**：无锁、简单、上下文切换零
**缺点**：**业务逻辑不能阻塞**，否则全连接卡死
**代表**：Redis（利用了业务逻辑都是内存操作，足够快）

### 10.2 单 Reactor 多线程（加个线程池跑业务）

```
      Reactor 线程
      │
      ├── epoll_wait
      ├── 网络 IO（accept / read / write）
      │
      └── 业务逻辑 → 丢给 Worker 线程池
                       │
                     [处理完写回结果]
                       │
                     回到 Reactor 做 write
```

**优点**：业务逻辑不阻塞 IO 线程
**缺点**：单 Reactor 线程仍是瓶颈（accept 也在这里）
**代表**：较少见了，不如主从 Reactor 好

### 10.3 主从 Reactor（Netty 默认、nginx 模型）

```
  Main Reactor                Sub Reactors
  │                           (N 个，通常 = CPU 核数)
  │                             │
  └── 只监听 listen fd           │
      accept 到新连接            │
      │                          │
      └──► 按策略分给某个 Sub ──► 注册进该 Sub 的 epoll
                                  │
                                  └── 读写 + 业务（或把业务再丢线程池）
```

**优点**：accept 和读写解耦，多核利用充分
**代表**：Netty（`bossGroup` + `workerGroup`）、nginx（`master` + `worker`）

### 10.4 为什么名字叫 Reactor

**Reactor = "反应"**。主循环反应于事件（"fd 可读了" → 触发 handler），是被动的。对应的是 **Proactor（主动者）**——用户发起 AIO 请求，内核主动完成并通知。**Reactor 处理"就绪"，Proactor 处理"完成"**。

Linux 上的 AIO 生态不成熟，Reactor 是事实标准。io_uring 成熟后 Proactor 会抬头。

---

## 11. 惊群问题

### 11.1 经典惊群

多个进程/线程都 `epoll_wait` 同一个 fd（比如 listen socket），连接到来时内核**把所有等待者都唤醒**——但只有一个能真正 accept 成功，其它白醒。

### 11.2 解决方案的演进

- **Linux 2.6**：`accept` 已修复惊群（只唤醒一个）
- **Linux 3.9**：`SO_REUSEPORT` 允许多个进程 bind 同一个端口，**内核按四元组哈希分发连接**——彻底消除惊群，且自带负载均衡
- **Linux 4.5**：`EPOLLEXCLUSIVE` 标志，多个 epoll 监听同一 fd 时只唤醒一个

**现代做法**：nginx 开 `reuseport on`、每个 worker 独立 listen + epoll，没有惊群。

### 11.3 `accept_mutex`（nginx 老方案）

历史上 nginx 用文件锁让 worker 轮流 accept——本质是用锁回避惊群。现在 `reuseport` 替代，这个选项渐废。

---

## 12. 从连接到并发模型的选择图谱

| 并发规模 | 模型 | 代表 |
|---|---|---|
| < 100 连接 | BIO + 每连接一线程 | 早期 Tomcat BIO connector |
| 100 – 10K | IO 多路复用单线程 | Redis |
| 10K – 100K | 主从 Reactor + Worker Pool | Netty、Node.js |
| 100K+ | 多进程 + `SO_REUSEPORT` + 多路复用 | nginx、Envoy |
| 特殊高吞吐 | io_uring + 用户态协议栈（DPDK） | 少数极端场景 |

**选择时别光看数字**：你的业务逻辑**同步 or 异步**、**有没有阻塞操作（DB、文件）**，往往比 IO 模型选择更影响性能。

---

## 13. 关键 socket 选项（setsockopt）

| 选项 | 作用 | 何时用 |
|---|---|---|
| `SO_REUSEADDR` | bind 处于 TIME_WAIT 的端口不报错 | 服务端重启快速绑定 |
| `SO_REUSEPORT` | 多进程 bind 同端口 | nginx 多 worker、消除惊群 |
| `SO_KEEPALIVE` | 开启 TCP keepalive | 长连接探测对方存活（见 `basic.md §7.5`） |
| `SO_LINGER` | close 时缓冲区里还有数据怎么办 | 默认"尽力发完"，设 0 立即 RST |
| `TCP_NODELAY` | 关闭 Nagle | 低延迟、交互协议 |
| `TCP_CORK` | 和 Nagle 相反，主动聚包 | 批量发送（如 sendfile） |
| `SO_RCVBUF` / `SO_SNDBUF` | 接收/发送缓冲区大小 | 特殊调优场景（一般让内核自动） |

### 13.1 `SO_REUSEADDR` vs `SO_REUSEPORT`

常被搞混：

- **`SO_REUSEADDR`**：允许 bind 到**处于 TIME_WAIT** 状态的地址（重启服务能立刻 bind，不用等 60 秒）
- **`SO_REUSEPORT`**：允许**多个进程 / 线程**同时 bind 同一个 IP:Port（Linux 3.9+），内核自动分发连接

**实操**：
- 服务端几乎一定要开 `SO_REUSEADDR`（否则重启会报 `Address already in use`）
- 多进程服务器应该开 `SO_REUSEPORT`（替代 `accept_mutex`）

---

## 14. 排障锚点

### 14.1 `Address already in use`（EADDRINUSE）

**原因**：
1. 上一次进程还活着占着端口（`lsof -i :PORT` 确认）
2. 上一次的 socket 在 TIME_WAIT 没释放 → 开 `SO_REUSEADDR`
3. 某个别的进程在用这端口（端口冲突）

### 14.2 `Too many open files`（EMFILE）

**原因**：fd 用完了。每个 socket 一个 fd，每个打开的文件一个 fd，accept 一个新连接要一个 fd。

**查**：
```
ulimit -n              # 进程级限制（默认 1024，改 /etc/security/limits.conf）
cat /proc/sys/fs/file-max   # 系统级上限
ls /proc/$PID/fd | wc -l     # 进程当前打开多少
```

**改**：
- `ulimit -n 1000000`（当前 shell）
- systemd 里 `LimitNOFILE=1000000`
- 高并发服务务必要改（默认 1024 很快爆）

### 14.3 `EAGAIN / EWOULDBLOCK`

**不是错误**，是非阻塞 IO 的正常信号："现在没数据 / 缓冲区满，待会再来"。

新手错误：当成错误重试导致 CPU 100%。正确做法：交给 epoll 监听该 fd 的可读 / 可写事件。

### 14.4 `Connection refused` / `Connection reset` / `Connection timeout`

见 [`basic.md §13`](./basic.md)。socket 层这些错误本质是 TCP 层的现象。

### 14.5 `EPIPE` / `SIGPIPE`

对方已关的连接你还在写 → EPIPE（或默认收到 SIGPIPE 直接杀进程）。

**防御**：
- `signal(SIGPIPE, SIG_IGN)` 忽略这个信号
- `write` 带 `MSG_NOSIGNAL` flag
- 检查 write 返回值和 errno

### 14.6 连接数上不去但 CPU 也不高

**嫌疑**：
1. `ulimit -n` 太低（最常见）
2. `net.core.somaxconn` 太低（全连接队列满，客户端在重试）
3. `net.ipv4.ip_local_port_range` 客户端端口不够（大量主动出连接时）
4. `net.ipv4.tcp_max_syn_backlog` 半连接队列不够
5. 应用没用多路复用，还在用 BIO

**查**：
```
ss -s                              # socket 总览
ss -lnt                            # 看 listen 状态
ss -ant | awk '{print $1}' | sort | uniq -c   # 按状态统计
cat /proc/net/sockstat             # 系统 socket 用量
```

### 14.7 `Nagle + 延迟 Ack` 导致的 40ms 卡顿

症状：某些请求/响应卡 40ms 后才完成，CPU / 网络都不忙。

**原理**：
- 客户端发了一个小包，Nagle 等前一个包被 Ack
- 服务端收到后用**延迟 Ack**（攒一下再发 Ack，减少 Ack 包数）
- 双方都在等对方 → 锁死 40–200ms

**解法**：开 `TCP_NODELAY`。HTTP/1.1 长连接主流实现默认开。

---

## 15. 延伸阅读

- [《怎样理解 socket 的实现机制》](https://zhuanlan.zhihu.com/p/6955291)
- [Draveness《为什么 TCP 协议有粘包问题》](https://draveness.me/whys-the-design-tcp-message-frame/)
- 《UNIX 网络编程 卷 1》（Stevens）—— 圣经，啃得动就啃
- [Marek's blog《epoll is fundamentally broken》](https://idea.popcount.org/2017-02-20-epoll-is-fundamentally-broken-12/) —— epoll 边界条件讨论
- [Jens Axboe《Efficient IO with io_uring》](https://kernel.dk/io_uring.pdf) —— io_uring 作者论文
- `man 7 epoll` / `man 7 socket` —— 最权威的一手资料

---

**本文到此结束。接下来的路线**：
- 想看 TCP/UDP 协议本身 → [`basic.md`](./basic.md)
- 想看用户态怎么在 TCP 上封装应用协议 → [`http.md`](./http.md)
- 想看 Netty / Redis 之类高性能服务怎么建立在这些概念上 → 去看它们的源码或官方文档
