# 03 IO 原语

> **这章解决什么问题**
>
> 你在 `linux-handson/05-io-and-files` 里看到 fd、`open`/`read`/`write`、inode、`epoll`——现象都在那章，但「fd 到底是什么」「write 调用返回后数据去哪了」「epoll 为什么比 select 快」这些底层机制在这里。本章补齐七个 IO 原语的内部工作原理，让 lh/05 和 lh/06 的每一句结论都有根。

**依赖**：
- fd 操作（`open`/`read`/`write`）本质上都是 syscall，如果 syscall 概念还不熟，先看 [`linux/02-execution-primitives/`](../02-execution-primitives/README.md)。
- 内核缓冲 / page cache **由本章讲解**（原语五）；它依赖的物理页/虚拟内存地基见 [`linux/01-memory-primitives/`](../01-memory-primitives/README.md)。

**三层怎么读：**

- **① 你视角** — 先用你熟悉的 Java/Go 概念搭桥，≤ 30 秒落地。
- **② 黑盒内部** — 内核真正做了什么，架构取舍在哪。这层是本章核心，每个原语必有。
- **③ 砸实** — 在真实 Linux 容器里跑出来的命令 + 输出，印在文档里作透明证据。只在能跑出干净结果的原语放，不强求每个都有。

> 注：所有 ③ 命令在 `arm64v8/ubuntu:22.04` 容器实跑（host 为 macOS aarch64，`ubuntu:24.04` 不在本机缓存中，故替换；内核行为相同，arch 差异只在地址前缀等表面细节）。

---

## 原语一：文件描述符 fd（file descriptor）

### ① 你视角

Java 里 `FileInputStream` 打开一个文件，底层有个 native 整数句柄；Go 里 `os.File` 有个 `.Fd()` 方法返回 `uintptr`。这个整数就是 **fd（文件描述符）**。Linux 把所有 IO 资源（文件、socket、管道、设备）统一抽象成 fd，用同一套 `read`/`write`/`close` syscall 操作，这就是「一切皆文件」的接口层。

### ② 黑盒内部

**fd 是进程级别的小整数，是进程 fd 表的索引下标。**

每个进程在内核里维护一张 **fd 表**（`files_struct`），表里每个槽位指向一个 **open-file description**（内核对象，记录文件偏移量 `pos`、打开标志 `flags`、指向 inode 的指针等）。fd 就是那个槽位的下标：

```
进程 fd 表
┌───┬───────────────────────────────────┐
│ 0 │ → open-file desc (stdin)          │  ← fd 0 = stdin
│ 1 │ → open-file desc (stdout)         │  ← fd 1 = stdout
│ 2 │ → open-file desc (stderr)         │  ← fd 2 = stderr
│ 3 │ → open-file desc (/etc/foo)       │  ← open("/etc/foo") 返回的就是 3
│ 4 │ → open-file desc (socket)         │  ← accept() 新连接
│ … │ …                                 │
└───┴───────────────────────────────────┘
```

**三个固定约定**：fd 0/1/2 分别是 stdin/stdout/stderr，shell 启动进程时已预先连接好。调用 `open()` 时内核分配当前最小可用的 fd 编号（通常从 3 开始往上填）。`close(fd)` 把那个槽位清空，该编号随即可被下一次 `open` 复用。

**fd 只是整数，轻量**：所有 IO 状态（偏移、模式）保存在 open-file desc 里，不在 fd 整数本身。这意味着两个不同进程的不同 fd 编号可以指向同一个 open-file desc（`fork` 后父子共享就是这样），位置和标志共享。

### ③ 砸实

```bash
docker run --rm arm64v8/ubuntu:22.04 bash -c 'ls -l /proc/self/fd'
```

真实输出：

```
total 0
lrwx------ 1 root root 64 Jun 26 09:03 0 -> /dev/null      # stdin → /dev/null（非交互式容器）
l-wx------ 1 root root 64 Jun 26 09:03 1 -> pipe:[9497962]  # stdout → pipe（docker 输出管道）
l-wx------ 1 root root 64 Jun 26 09:03 2 -> pipe:[9497963]  # stderr → pipe
lr-x------ 1 root root 64 Jun 26 09:03 3 -> /proc/211/fd    # ls 自己读 /proc/self/fd 打开的 fd
```

**看点**：
- `/proc/self/fd/` 里每个 fd 是一个 **软链接**，指向真实资源（`/dev/null`、`pipe:[…]`）——这就是内核暴露进程 fd 表的方式。
- fd 1 和 fd 2 指向 `pipe:[]`，不是文件——后面「一切皆文件」原语会专门说这个设计。
- fd 3 是 `ls` 命令打开 `/proc/211/fd` 目录时获得的，目录读取也走 fd。

→ **回链**：`linux-handson/05-io-and-files` §fd 操作（open/dup/close 在这里展开）

---

## 原语二：fd 表（fd table）

### ① 你视角

Java NIO 的 `Selector` 同时管着几百个 `Channel`，每个 Channel 底层是一个 fd。为什么并发连接数不能无限多？为什么 Java 服务崩时日志里会出现 `java.io.IOException: Too many open files`？根因就在 fd 表的上限。

### ② 黑盒内部

**fd 表是每进程一张，有容量上限。**

内核层面，每个进程的 `task_struct` 指向 `files_struct`（fd 表）。表的容量由两个参数控制：

1. **软限制（ulimit -n）**：进程当前可用的 fd 上限，默认通常是 1024（传统 Linux）或 20480/65536（现代发行版）。可以在 shell 里用 `ulimit -n <数字>` 调大，但不超过硬限制。
2. **硬限制**：管理员设置的天花板，普通用户无法超越。`/etc/security/limits.conf` 或 systemd 的 `LimitNOFILE` 控制。

**与进程/线程的关系——这是面试高频考点：**

| 场景 | fd 表状态 |
|------|-----------|
| `fork()` 后子进程 | fd 表被**拷贝**——子进程有独立副本，但副本里的 open-file desc 指针和父进程指向同一批 desc（即文件偏移共享） |
| `clone(CLONE_FILES)` 创建线程 | fd 表被**共享**——同一进程的所有线程共用一张 fd 表，一个线程 `close(3)` 对所有线程都生效 |
| `exec()` 替换程序 | 默认保留 fd，除非 fd 打开时设置了 `O_CLOEXEC` 标志（推荐做法，防止 fd 泄漏到子进程） |

**「Too many open files」根因**：进程打开的 fd 数超过 `ulimit -n`，内核拒绝新的 `open()`/`accept()` 返回 `EMFILE`，Java 抛出 `IOException`。高并发服务标配操作：`ulimit -n 65536`（或更高），或在 systemd unit 里设 `LimitNOFILE=65536`。

### ③ 砸实

```bash
docker run --rm arm64v8/ubuntu:22.04 bash -c 'bash -c "ulimit -n"'
```

真实输出：

```
20480
```

**看点**：这个容器环境的软限制是 20480（Docker 设置；裸金属 Ubuntu 默认常见 1024，现代 systemd 发行版默认可到 524288）。超过这个数 `open()` 返回 `EMFILE`。

→ **回链**：`linux-handson/05-io-and-files` §fd 泄漏排查（`lsof -p <pid>` 数 fd 数）

---

## 原语三：inode

### ① 你视角

你在文件系统里删了一个文件，为什么有时候磁盘空间没释放？为什么 `ln`（硬链接）创建的「副本」和原文件改动是同步的？这些行为的根源都在 **inode**（索引节点）。

### ② 黑盒内部

**inode 存文件的元数据，不存文件名。文件名存在目录里。**

每个文件在磁盘上有一个 inode，inode 里存：
- 文件大小
- 权限（rwx for owner/group/other）
- 所有者 UID/GID
- 时间戳（atime/mtime/ctime）
- **硬链接计数**（link count）
- **数据块指针**（指向文件内容所在的磁盘块）

inode **不存文件名**。文件名存在**目录项（directory entry / dentry）**里，目录项是一张 `{ 文件名 → inode 编号 }` 的映射表。

**这设计的关键推论——硬链接：**

```
目录 /home/user/
├── a  → inode #10504668  (dentry: 名字="a", inode=10504668)
└── b  → inode #10504668  (dentry: 名字="b", inode=10504668)  ← 硬链接，同一 inode
```

`ln /tmp/a /tmp/b` 做的事：在目录里增加一条新的 dentry，让 `b` 这个名字也指向同一个 inode。inode 的 **link count 从 1 变成 2**。两个名字读写的是同一份数据，因为它们索引到同一个 inode，同一批数据块。

**`rm` 不是"删文件"，是"减引用"：**

`rm a` 做的事是把目录里 `a` 这条 dentry 删掉，然后 inode 的 link count 减 1。
- 如果 link count 变成 0 且没有进程持有 fd 指向这个 inode → 内核才真正释放数据块，磁盘空间才释放。
- 如果还有进程持有打开的 fd → link count 到 0 但文件数据照样活着，直到所有 fd 都 `close()`。

这就是为什么日志文件被 `rm` 了，但跑着的进程还能写（`lsof` 还能看到 `(deleted)` 的 fd）——磁盘空间不释放，直到进程也关了 fd。

**软链接（symlink）与硬链接的区别**：软链接是一个独立的文件，inode 不同，内容是「指向另一个路径的字符串」；硬链接直接共享 inode，只能在同一文件系统内跨目录，不能跨挂载点，也不能 link 目录（防循环）。

### ③ 砸实

```bash
docker run --rm arm64v8/ubuntu:22.04 bash -c '
echo hi > /tmp/a
ln /tmp/a /tmp/b
stat -c "%n inode=%i links=%h" /tmp/a /tmp/b
'
```

真实输出：

```
/tmp/a inode=10504668 links=2
/tmp/b inode=10504668 links=2
```

**看点**：两个文件名，同一个 inode 编号（`10504668`），`links=2`——这就是硬链接的物理证据。`rm /tmp/a` 后 links 降为 1，`rm /tmp/b` 后降为 0，内核才释放数据块。

→ **回链**：`linux-handson/05-io-and-files` §inode 与硬链接实验（`df -i` 看 inode 用量、`find -inum` 找同 inode 文件）

---

## 原语四：阻塞 vs 非阻塞 IO

> ② 讲透，无干净 5 行复现，跳过 ③。

### ① 你视角

Java 老式 `InputStream.read()` 会卡住线程等数据——这是**阻塞**。Go 的 `net.Conn.Read()` 看起来也会"等"，但 Go runtime 在背后用非阻塞 fd + goroutine 调度来模拟阻塞体验。理解阻塞与非阻塞的区别，是理解 Netty、Node.js、Go net poller 的底座。

### ② 黑盒内部

**阻塞 IO**：

调用 `read(fd, buf, n)` 时，如果内核缓冲区里暂时没有数据（比如网络包还没到），内核会把当前线程从运行队列移出，放到等待队列里**睡眠**，CPU 立刻去跑其他线程。数据到达后，内核唤醒这个线程，`read()` 才返回。

线程从用户角度来看是「卡在 `read()` 调用里」——实际上是在睡眠，不消耗 CPU。但代价是：一个线程只能等一个 fd，要同时管 1000 个连接就需要 1000 个线程，内存和上下文切换开销大。

**非阻塞 IO（O_NONBLOCK）**：

`open("/path/to/fifo", O_RDONLY | O_NONBLOCK)` 或 `fcntl(fd, F_SETFL, O_NONBLOCK)` 把 fd 设成非阻塞模式。之后对这个 fd 调用 `read()`：
- **有数据**：正常返回读取的字节数。
- **没数据**：**立即返回 -1**，并设 `errno = EAGAIN`（"再试一次"）或 `EWOULDBLOCK`（两者等价，BSD/Linux 均支持）。

线程不睡眠——调用方得到 `EAGAIN` 之后自己决定是忙等（自旋，浪费 CPU）还是注册到事件通知机制（epoll）里等内核告知就绪，然后去干别的。

**别把阻塞/非阻塞和同步/异步混淆**：
- 阻塞/非阻塞指的是**内核缓冲区没就绪时，调用是否挂起线程**。
- 同步/异步指的是**数据拷贝过程（内核→用户缓冲区）是否由调用方自己做**。
- `read()` 在非阻塞模式仍是同步的：一旦有数据，还是调用方自己在 `read()` 里把数据从内核缓冲区复制到用户缓冲区。

→ **回链**：`linux-handson/05-io-and-files` §阻塞 IO 与 O_NONBLOCK 实验

---

## 原语五：内核缓冲 / page cache

> ② 讲透，无干净 5 行复现（需要 `/proc/meminfo` 对比 + 磁盘延迟测量，环境依赖多），跳过 ③。page cache 机制由本节自己讲透；它建立在 `linux/01-memory-primitives/` 的物理页/缺页地基之上。

### ① 你视角

你写 Go 或 Java：`file.Write(data)` 返回了——数据真的已经存盘了吗？不一定。如果服务器在 `Write()` 返回后、数据落盘前崩了，数据会不会丢？这就是内核缓冲带来的取舍。

### ② 黑盒内部

**write() 不等于落盘，它只是把数据交给内核缓冲区。**

调用链：

```
你的代码 write(fd, buf, n)
    ↓
内核把 buf 数据复制到 page cache（内存中的脏页）
    ↓  ← write() 到这里就返回了
    ↓  后台 pdflush/writeback 线程异步把脏页写到磁盘
    ↓
磁盘
```

**page cache 是内核管理的文件数据缓存**：
- `write()` 写的是内核里的内存页（打脏标记），调用立即返回——速度等同内存写入（几十 ns），不等磁盘。
- `read()` 优先命中 page cache，命中则不碰磁盘，速度等同内存读取（100 ns 级）；未命中才触发真实磁盘 IO（HDD 毫秒级，SSD 微秒级）。

**脏页刷盘时机（三种）：**

| 触发 | 说明 |
|------|------|
| 后台定时 | `dirty_writeback_centisecs`（默认 500 cs = 5s），writeback 线程（旧称 pdflush，2.6.37 后为 per-BDI `kworker/*-flush`）周期扫描脏页写盘 |
| 内存压力 | page cache 占用太多物理内存，LRU 淘汰时强制写盘 |
| 显式调用 | `fsync(fd)`（把指定 fd 的脏页全刷到磁盘并等待确认）、`fdatasync`、`sync` |

**架构取舍——什么时候需要 `fsync`：**

- **数据库**（MySQL、PostgreSQL）在每次提交事务后都调 `fsync()`，保证崩溃不丢数据（ACID 的 Durability）。代价：每次 commit 都要等磁盘（IOPS 成为瓶颈）。
- **日志服务**（nginx access log、Kafka producer 默认）不 `fsync`，允许缓冲区里最多几秒的数据在崩溃时丢失，换取高吞吐。
- **Redis** 默认 `appendfsync everysec`——每秒 `fsync` 一次，在崩溃安全性和吞吐之间折中。

→ **回链**：`linux-handson/05-io-and-files` §page cache 与 fsync 实验（`/proc/meminfo` 的 `Cached` 字段、`vmstat -s` 看 page-in/out）

---

## 原语六：epoll 底层

> ② 讲透（select/poll/epoll 对比 + 红黑树 + 就绪链表 + 边沿/水平触发），无干净 5 行 C 复现（最短正确的 epoll 程序需要创建 server socket + accept + 注册 epoll + 事件循环，超出 ≤5 行硬约束），跳过 ③。

### ① 你视角

Netty 为什么比传统 BIO（一连接一线程）高效？Node.js/nginx 单线程怎么撑高并发？Go 的 net poller 怎么不阻塞 goroutine 做 IO？底层都靠操作系统提供的**就绪通知**机制，Linux 上就是 **epoll**。

### ② 黑盒内部

**从 select/poll 到 epoll：从 O(n) 到 O(1)。**

**select/poll 的问题（O(n)）：**

`select(maxfd, &readfds, ...)` 每次调用：
1. 用户把监听的 fd 集合（位图或数组）**复制进内核**。
2. 内核**遍历所有 fd**，逐一检查是否就绪。
3. 把就绪的 fd 标记在位图里，返回用户——用户再遍历一遍找出哪些就绪了。

每次 `select()`/`poll()` 调用的代价都是 O(n)（n = 监听 fd 数）。fd 数越多、大部分又没数据，内核就在做无谓的全量扫描。

**epoll 的设计（O(1) 拿就绪 fd）：**

epoll 把工作分成两步：

**步骤一：注册（一次性）**

```c
int epfd = epoll_create1(0);             // 创建 epoll 实例
epoll_ctl(epfd, EPOLL_CTL_ADD, fd, &ev); // 注册 fd
```

内核在 **红黑树**（balanced BST）里记录这个 fd 和它的事件。注册是 O(log n)，但只做一次。

**步骤二：等待（每次只返回就绪的）**

```c
int n = epoll_wait(epfd, events, max, timeout); // 阻塞，直到有就绪事件
```

内核不扫描所有 fd——当 fd 对应的驱动/socket 有数据就绪时，**回调函数自动把这个 fd 加入就绪链表**。`epoll_wait` 只需要从就绪链表里取数据，O(1) 返回 n 个就绪事件。

```
内核 epoll 内部结构
┌─────────────────────────────────────────────────┐
│  红黑树（监听集合）                              │
│  fd5 ─ fd12 ─ fd99 ─ fd200 …（注册过的全部 fd）  │
│                                                  │
│  就绪链表（ready list）                          │
│  fd12 ─ fd99  ← 有数据时驱动回调加入此链表       │
└─────────────────────────────────────────────────┘
epoll_wait 只取就绪链表 → 返回 [fd12, fd99]
```

**边沿触发（Edge-Triggered, ET）vs 水平触发（Level-Triggered, LT）：**

| | 水平触发（LT，默认） | 边沿触发（ET）|
|--|--|--|
| **触发时机** | fd 处于就绪状态时，每次 `epoll_wait` 都通知 | fd 从未就绪**变为**就绪那一刻只通知一次 |
| **漏读风险** | 没读完数据，下次 `epoll_wait` 还会通知 | 没读完就丢了通知；**必须循环读到 EAGAIN** |
| **用法场景** | 简单、安全；Netty（NIO 默认）用 LT | 高性能、低通知次数，需正确处理 EAGAIN；Nginx（`EPOLLET`）、Go net poller 默认用 ET |

**为什么 epoll 是事件循环的根基：**

Netty 的 `NioEventLoop`、Node.js 的 `libuv`、Go 的 `runtime/netpoll`、nginx 的 worker loop——核心都是同一个模式：

```
loop:
    就绪事件 = epoll_wait(epfd, …, -1)   // 无就绪事件时睡眠
    for 每个就绪事件:
        dispatch 到对应 handler
    goto loop
```

一个线程管几万个连接，不是靠线程多，而是靠 epoll 的 O(1) 就绪通知让线程永远只处理有事可做的 fd。

→ **回链**：`linux-handson/06-networking` §epoll 与 reactor 模式实验；`linux-handson/05-io-and-files` §select vs poll vs epoll 性能对比

---

## 原语七：「一切皆文件」

### ① 你视角

Java 里 `InputStream` 和 `Socket.getInputStream()` 的接口一模一样——不管你读的是本地文件还是网络连接，都是 `.read(byte[])`。Go 里 `io.Reader` 接口统一了 `os.File`、`net.Conn`、`bytes.Buffer`……这种设计不是框架的品味，而是直接来自 Linux 内核的「一切皆文件」哲学。

### ② 黑盒内部

**Linux 把普通文件、socket、管道、设备全都抽象成 fd，暴露统一的 `read(fd,…)`/`write(fd,…)`/`close(fd)` 接口。**

这不是「字面意思的万物皆文件」（不是所有内核概念都有 fd，比如进程关系、内存映射不能直接 `read()`），而是一个**接口统一层**：

| 资源类型 | fd 从哪来 | 背后对象 |
|----------|-----------|----------|
| 普通文件 | `open("/etc/foo")` | inode + page cache |
| 网络 socket | `socket()` + `accept()` | TCP/UDP 连接状态机 |
| 管道 pipe | `pipe(fd[2])` | 内核环形缓冲区 |
| 字符设备 | `open("/dev/tty")` | 设备驱动 |
| epoll 实例 | `epoll_create1()` | epoll 红黑树 + 就绪链表 |
| 定时器 | `timerfd_create()` | 内核定时器 |

**为什么这个设计强：**

1. **工具通用**：`cat`、`grep`、`wc` 原来只处理文件，通过管道 `|`（pipe fd）可以处理任何字节流。
2. **epoll 可以监听所有类型**：因为 socket、pipe、timerfd 都是 fd，epoll 统一管理，一个事件循环处理网络 + 定时器 + 进程间通信。
3. **语言层接口统一**：Go 的 `io.Reader`/`io.Writer`、Java 的 `InputStream` 正是在语言层面继承了这个内核设计。

**「一切皆文件」的限制**：不是字面上的一切——内存（`mmap` 返回指针，不是 fd）、进程信号（信号处理是回调，不是 fd……但 `signalfd` 可以把信号变成 fd）、锁（futex 是整数，不是 fd）不走这套接口。这套哲学的本质是：**IO 资源尽量暴露为 fd，让用户空间用统一接口**，而非真正的「万物皆 fd」。

### ③ 砸实

前面原语一已经跑出了真实的 `/proc/self/fd` 输出，直接复用：

```
lrwx------ 1 root root 64 Jun 26 09:03 0 -> /dev/null      # 字符设备
l-wx------ 1 root root 64 Jun 26 09:03 1 -> pipe:[9497962]  # 管道
l-wx------ 1 root root 64 Jun 26 09:03 2 -> pipe:[9497963]  # 管道
lr-x------ 1 root root 64 Jun 26 09:03 3 -> /proc/211/fd    # 目录（特殊文件）
```

**看点**：同一进程的 fd 表里混着设备（`/dev/null`）、管道（`pipe:[]`）、目录（`/proc/…`）——全都是 fd，全都能 `close()`，对 epoll 来说都能注册。这就是「一切皆文件」在进程级别的真实体现。

→ **回链**：`linux-handson/05-io-and-files`（fd 类型与 open 标志综合实验）；`linux-handson/06-networking` §socket fd 的生命周期

---

## 本章总结

| 原语 | 一句话 | 有 ③ |
|------|--------|-------|
| fd | 进程级小整数，索引 fd 表，0/1/2 固定是 stdin/out/err | ✅ |
| fd 表 | 每进程一张，fork 拷贝、clone 共享，ulimit -n 是上限 | ✅ |
| inode | 存元数据不存名字，名字在目录项，硬链接共享 inode，rm 是减引用 | ✅ |
| 阻塞 vs 非阻塞 | 阻塞=线程睡在 syscall，O_NONBLOCK=立即返回 EAGAIN | ②（无干净复现） |
| 内核缓冲 / page cache | write 先进内存缓冲再异步落盘，fsync 强刷 | ②（回链 lh/05） |
| epoll | 注册进红黑树，就绪时加链表，epoll_wait O(1)，ET vs LT | ②（超 5 行约束） |
| 一切皆文件 | fd 统一普通文件/socket/pipe/设备，工具和事件循环由此通用 | ✅（复用原语一）|
