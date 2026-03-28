# 进程、线程与协程

> 并发模型的选择直接决定了系统的资源效率和可扩展性。本文从操作系统视角对比进程/线程/协程，并深入 I/O 多路复用的演进。

---

## 1. 进程 vs 线程 vs 协程

```
┌────────────────────────────────────────────────────────────┐
│                         进程                                │
│  独立地址空间 │ 独立文件描述符表 │ 独立信号处理               │
│                                                            │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                     线程 1                            │  │
│  │  独立栈 + 寄存器                                      │  │
│  │  ┌─────────────┐  ┌─────────────┐                    │  │
│  │  │  协程 A      │  │  协程 B      │   用户态调度       │  │
│  │  │  独立栈(KB级) │  │  独立栈(KB级) │                   │  │
│  │  └─────────────┘  └─────────────┘                    │  │
│  └──────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │                     线程 2                            │  │
│  │  独立栈 + 寄存器                                      │  │
│  │  共享：堆内存、全局变量、文件描述符                       │  │
│  └──────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────┘
```

### 全面对比

| 维度 | 进程 | 线程 | 协程 |
|------|------|------|------|
| 地址空间 | 独立 | 共享（同一进程内） | 共享（同一线程内） |
| 栈大小 | 独立（通常 8MB） | 独立（通常 1-8MB） | 独立（通常 2-8 KB） |
| 创建代价 | 高（~ms，需复制页表等） | 中（~10us） | 低（~1us） |
| 切换代价 | 高（3-5us，需切换页表、刷 TLB） | 中（1-3us） | 极低（100-200ns，用户态） |
| 调度 | 内核调度 | 内核调度 | 用户态调度器（runtime） |
| 通信方式 | 管道、Socket、共享内存、信号 | 共享内存 + 互斥锁/条件变量 | Channel（Go）、async/await |
| 故障隔离 | 强（一个崩溃不影响其他） | 弱（一个段错误整个进程崩溃） | 弱（同线程） |
| 最大数量 | 百级 | 千级 | 百万级 |

### 各语言的并发模型

| 语言 | 主要模型 | 说明 |
|------|---------|------|
| Java | 线程（1:1 映射内核线程） | Thread / ThreadPool，虚拟线程（JDK 21+）引入协程 |
| Go | 协程（goroutine，M:N 调度） | 运行时自动将 goroutine 调度到 OS 线程上 |
| Python | 协程（asyncio）+ 多进程 | GIL 限制了多线程 CPU 并行，CPU 密集用多进程 |

---

## 2. fork 与 COW（Copy-On-Write）

`fork()` 创建子进程时不会立即复制父进程的全部内存，而是共享同一份物理页面，只有写入时才复制：

```
fork() 之前:
父进程页表 ──→ 物理页面 A (可读写)
                物理页面 B (可读写)

fork() 之后:
父进程页表 ──→ 物理页面 A (只读)  ◄── 子进程页表
                物理页面 B (只读)  ◄──

写入时（COW 触发）:
父进程写页面 A:
  1. Page Fault（因为页面被标记为只读）
  2. 内核分配新物理页面 A'，拷贝 A 的内容
  3. 父进程页表指向 A'（可读写），子进程仍指向 A（可读写）
```

**COW 对性能的影响**：
- `fork()` 本身很快（只复制页表，不复制数据）
- 但如果父子进程都频繁写入，会触发大量 Page Fault 和页面复制
- **Redis 持久化（RDB/AOF rewrite）**使用 `fork()` 创建子进程做数据快照，如果此时有大量写入，COW 导致内存使用翻倍

```bash
# 监控 COW 导致的额外内存使用
# Redis INFO 中的 latest_fork_usec 显示上次 fork 耗时
redis-cli INFO | grep fork

# 查看进程的 COW 页面数
cat /proc/<pid>/smaps | grep -i "shared\|private"
```

---

## 3. 信号机制

信号是进程间通信的最古老方式之一，也是运维中最常用的进程控制手段。

### 常见信号

| 信号 | 编号 | 默认行为 | 用途 |
|------|------|----------|------|
| SIGHUP | 1 | 终止 | 终端断开；很多守护进程用它重新加载配置 |
| SIGINT | 2 | 终止 | Ctrl+C |
| SIGQUIT | 3 | 终止+CoreDump | Ctrl+\，Java 中触发线程堆栈打印 |
| SIGKILL | 9 | 终止 | 强制杀死，**不可捕获** |
| SIGSEGV | 11 | 终止+CoreDump | 段错误（访问非法内存） |
| SIGPIPE | 13 | 终止 | 写入已关闭的管道/Socket |
| SIGTERM | 15 | 终止 | 优雅终止（默认的 kill 信号） |
| SIGSTOP | 19 | 暂停 | 暂停进程，**不可捕获** |
| SIGCONT | 18 | 继续 | 恢复暂停的进程 |
| SIGUSR1/2 | 10/12 | 终止 | 自定义用途（如 JVM dump、Nginx 重载） |

### 优雅关闭的标准做法

```bash
# 1. 先发 SIGTERM（允许应用清理资源）
kill -TERM <pid>
# 或
kill -15 <pid>

# 2. 等待一段时间
sleep 30

# 3. 如果进程还在，发 SIGKILL（强制杀死）
kill -9 <pid>
```

**性能相关**：
- `SIGPIPE` 未处理会导致进程意外终止。Go 默认忽略 SIGPIPE，Java 和 Python 需要显式处理。
- 发送 `SIGQUIT` 给 Java 进程会触发 Thread Dump（打印所有线程栈），这是排查死锁和性能问题的常用手段，不会终止 JVM。

---

## 4. 文件描述符

文件描述符（fd）是进程访问文件、Socket、管道等资源的"句柄"。每个进程有一个 fd 表。

```
进程 fd 表:
fd 0 → stdin
fd 1 → stdout
fd 2 → stderr
fd 3 → /var/log/app.log（打开的日志文件）
fd 4 → TCP Socket（连接到 MySQL）
fd 5 → TCP Socket（连接到 Redis）
fd 6 → TCP Socket（客户端连接1）
fd 7 → TCP Socket（客户端连接2）
...
```

### fd 上限配置

```bash
# 查看系统级别最大 fd 数
cat /proc/sys/fs/file-max
# 通常是几十万到几百万

# 查看当前系统已使用的 fd 数
cat /proc/sys/fs/file-nr
# 已分配  未使用  最大值

# 查看当前用户的进程级 fd 上限
ulimit -n
# 默认 1024（太小！）

# 临时修改
ulimit -n 65535

# 永久修改 (/etc/security/limits.conf)
# * soft nofile 65535
# * hard nofile 65535
# root soft nofile 65535
# root hard nofile 65535

# systemd 管理的服务需要在 service 文件中配置
# [Service]
# LimitNOFILE=65535

# 查看进程已打开的 fd 数
ls -la /proc/<pid>/fd | wc -l

# 查看进程的 fd 上限
cat /proc/<pid>/limits | grep "open files"
```

**常见问题**：`Too many open files` 错误。原因通常是：
1. fd 上限太低（默认 1024）
2. 连接泄漏（建立连接后未关闭）
3. 文件句柄泄漏（打开文件后未 close）

---

## 5. I/O 多路复用演进

### 问题背景

一个服务器需要同时处理数千个 Socket 连接。如果每个连接一个线程，线程太多（内存开销、上下文切换）。I/O 多路复用让一个线程可以监控多个 fd。

### select（1983，BSD）

```c
int select(int nfds, fd_set *readfds, fd_set *writefds, fd_set *exceptfds, struct timeval *timeout);
```

| 特性 | 说明 |
|------|------|
| fd 数量限制 | 1024（FD_SETSIZE 宏定义，编译期确定） |
| 触发方式 | 水平触发（LT） |
| 每次调用 | 需要把 fd_set 从用户态拷贝到内核态 |
| 返回后 | 需要遍历所有 fd 找出就绪的 |
| 时间复杂度 | O(n)，n 是监控的 fd 总数 |

**缺点**：1024 fd 上限、每次调用线性扫描、频繁拷贝。

### poll（1986，System V）

```c
int poll(struct pollfd *fds, nfds_t nfds, int timeout);
```

| 特性 | 说明 |
|------|------|
| fd 数量限制 | 无固定上限（用链表替代 bitmap） |
| 触发方式 | 水平触发（LT） |
| 每次调用 | 仍需拷贝 pollfd 数组到内核 |
| 返回后 | 仍需遍历所有 fd |
| 时间复杂度 | O(n) |

**改进**：去掉了 1024 限制，但性能问题没解决。

### epoll（2002，Linux 2.5.44）

```c
int epoll_create(int size);
int epoll_ctl(int epfd, int op, int fd, struct epoll_event *event);
int epoll_wait(int epfd, struct epoll_event *events, int maxevents, int timeout);
```

```
epoll 工作原理：

① epoll_create: 创建 epoll 实例（内核中的红黑树 + 就绪链表）
② epoll_ctl:    向红黑树中添加/修改/删除 fd（O(logN)）
③ 当 fd 就绪时: 内核通过回调函数将就绪 fd 加入就绪链表
④ epoll_wait:   直接返回就绪链表中的 fd（O(1)，不需要遍历所有 fd）

┌──────────────────────────────────┐
│          epoll 内核结构            │
│                                  │
│  红黑树（所有监控的 fd）            │
│      ┌───┐                       │
│     ┌┤30 ├┐                      │
│     │└───┘│                      │
│   ┌─┴─┐┌─┴─┐                    │
│   │15 ││45 │                     │
│   └───┘└───┘                     │
│                                  │
│  就绪链表（有事件的 fd）            │
│  [fd=30] → [fd=45] → NULL        │
│                                  │
│  epoll_wait 直接返回就绪链表       │
└──────────────────────────────────┘
```

| 特性 | 说明 |
|------|------|
| fd 数量限制 | 系统 fd 上限 |
| 触发方式 | 支持水平触发（LT）和边缘触发（ET） |
| 注册 fd | 只在 epoll_ctl 时传一次，不需要每次 wait 都传 |
| 返回 | 只返回就绪的 fd，不需要遍历 |
| 时间复杂度 | epoll_wait: O(就绪fd数)，epoll_ctl: O(logN) |

### 水平触发（LT）vs 边缘触发（ET）

```
水平触发 (Level Triggered, 默认):
- 只要 fd 上有数据可读，每次 epoll_wait 都会通知
- 不需要一次读完所有数据
- 编程简单，不容易出 bug
- 可能产生不必要的 epoll_wait 返回

边缘触发 (Edge Triggered):
- 只在 fd 状态变化时通知一次（从不可读变为可读）
- 必须一次性读完所有数据（读到 EAGAIN）
- 必须使用非阻塞 I/O
- 性能更好（减少 epoll_wait 调用次数），但编程复杂

场景选择:
- LT: 大多数业务应用，安全简单
- ET: 高性能中间件（Nginx 使用 ET）
```

**各主流框架的选择**：
- Nginx: epoll ET
- Redis: epoll LT
- Java NIO (Selector): epoll LT
- Go runtime: epoll LT (非阻塞 + runtime 调度)
- Python asyncio: epoll LT

### io_uring（2019，Linux 5.1）

io_uring 是 Linux I/O 多路复用的最新演进：

```
传统模型（epoll）:
  每次 I/O 至少需要 2 次系统调用：
  1. epoll_wait() → 获取就绪 fd
  2. read()/write() → 执行 I/O

io_uring:
  通过共享内存的环形队列（Ring Buffer）通信
  SQ (Submission Queue): 用户态写入 I/O 请求
  CQ (Completion Queue): 内核写入完成事件

  ┌─────────────┐              ┌─────────────┐
  │ 用户态       │   共享内存    │ 内核态       │
  │             │              │             │
  │ SQ Ring ────┼──────────────┼──► 处理请求   │
  │             │              │    │         │
  │ CQ Ring ◄───┼──────────────┼────┘ 完成通知 │
  └─────────────┘              └─────────────┘

  优势:
  - 减少甚至消除系统调用（SQPOLL 模式下内核主动轮询 SQ）
  - 支持批量提交和完成
  - 统一文件 I/O 和网络 I/O 的接口
```

### 四种方案对比总结

| 特性 | select | poll | epoll | io_uring |
|------|--------|------|-------|----------|
| fd 上限 | 1024 | 无 | 无 | 无 |
| 事件通知 | 遍历 O(n) | 遍历 O(n) | 回调 O(1) | 共享内存 O(1) |
| fd 传递 | 每次全量 | 每次全量 | 增量 | 增量 |
| 触发模式 | LT | LT | LT/ET | 无（异步） |
| 系统调用 | 每次 select | 每次 poll | 每次 wait | 可为 0 |
| 适用规模 | < 1024 | 几千 | 百万级 | 百万级 |
| 平台 | 跨平台 | 跨平台 | Linux only | Linux >= 5.1 |

---

## 6. 实用诊断命令

```bash
# 查看进程的线程数
ps -eLf | grep <process_name> | wc -l
# 或
cat /proc/<pid>/status | grep Threads

# 查看系统线程总数
cat /proc/sys/kernel/threads-max

# 查看 Go 程序的 goroutine 数
curl http://localhost:8082/debug/pprof/goroutine?debug=1 | head -5

# 查看 Java 线程栈（排查死锁）
kill -3 <java_pid>
# 或
jstack <java_pid>

# 查看进程使用的 epoll fd
ls -la /proc/<pid>/fd | grep eventpoll

# strace 观察 epoll 调用
strace -e trace=epoll_wait,epoll_ctl -p <pid>
```

---

## 要点总结

1. **进程隔离强但代价高**——适合需要故障隔离的场景（如 Nginx worker 进程），不适合高并发连接处理。
2. **线程共享内存但有锁开销**——Java 传统模型，线程数通常控制在 CPU 核心数的 2-4 倍。过多线程导致上下文切换开销压过业务逻辑。
3. **协程是高并发的最优解**——Go goroutine 可以轻松创建百万级，但注意 goroutine 泄漏问题。
4. **COW 让 fork 很快但有代价**——Redis fork 持久化时如果写入量大，会导致内存使用翻倍。
5. **fd 上限默认 1024 远远不够**——生产环境至少调到 65535。
6. **epoll 是当前主流**——理解 LT/ET 的区别即可，大多数场景用 LT。io_uring 是未来方向，但目前生态还在成熟中。
