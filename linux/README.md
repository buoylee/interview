# Linux 底层原语 Primer

> **一句话定位**:教「所有 OS 课假设你懂、但没人认真讲过」的底层原语——指针/虚拟地址/syscall/fd/futex 这一层——作为 `linux-handson/` 的词汇底座。

---

## 三层拓扑关系

```
   os-for-architects/          ← 原语 → 架构决策(薄镜头:为什么这样选型、这样设计)
         ▲ 坐其上
   linux-handson/              ← 机制·能答·能排查(动手课:假设原语已懂,教怎么用/怎么排查)
         ▲ 坐其上
   linux/  (本 track)          ← 底层原语本身:它是什么、黑盒里发生什么、怎么亲眼看到
```

**三者边界**

| track | 问的问题 | 深度 |
|-------|----------|------|
| `linux/`(本 track) | 原语本身是什么?黑盒里发生什么?怎么证明? | C/OS 内核视角,补齐空白层 |
| `linux-handson/` | 怎么用?命令是什么?面试怎么答?怎么排查? | 动手 + 七段式 + VM 沙箱 |
| `os-for-architects/` | 原语如何影响架构决策? | 原语 → 设计取舍(薄镜头,不重讲原语) |

读法建议:先读本 track 补概念底座 → 再去 `linux-handson/` 对应章动手 → 最后 `os-for-architects/` 拉到架构层。

---

## 怎么读本 track 的每个原语

每个原语遵循**三层模板**:

**① 你视角(Java/Go 桥)**
你在 Java/Go/Python 里已经隐式用了这个原语的上层封装,先把桥接点说清楚。

**② 黑盒内部(必有)**
内核/CPU 层面真正发生什么:数据结构、状态转换、谁拷贝了什么、谁唤醒了谁。这一层**每个原语都有**——没有 ② 的原语讲解是不完整的。

**③ 砸实(透明证据,非作业)**
能干净复现的原语给出**真实可跑命令**及预期输出(strace / /proc / perf 等);无法 5 行内干净复现的原语以 ② 为主,不强行造题。实跑结果从真机采集,禁止伪造。

---

## 已完成章节

| 章 | 主题 | 核心原语 |
|----|------|----------|
| [01 内存原语](./01-memory-primitives/) | 指针·虚拟地址·页·page fault·brk/mmap·malloc·VSZ/RSS | 虚拟地址空间、MMU/TLB、匿名映射(`MAP_ANONYMOUS`)、缺页异常、堆扩张与归还、内存计量 |
| [02 执行原语](./02-execution-primitives/) | syscall·用户↔内核切换·中断·上下文切换·栈帧·进程vs线程 | syscall 指令、特权级切换、硬件中断 vs 软件陷入(syscall)、调度器上下文切换、内核栈/用户栈、task_struct |
| [03 IO 原语](./03-io-primitives/) | fd·fd表·inode·阻塞/非阻塞·内核缓冲·epoll·一切皆文件 | 文件描述符表、VFS/inode、write→page cache→writeback 路径、epoll 红黑树+就绪链表 |
| [04 并发原语](./04-concurrency-primitives/) | 原子/CAS·futex·signal·条件变量·内存屏障 | CAS 与 Lock 前缀、futex 内核等待队列、信号异步交付、条件变量语义、store/load 屏障 |
| [05 链接装载原语](./05-link-load-primitives/) | ELF·静态/动态链接·`.so` 装载·符号解析 | ELF section/segment、目标文件/符号表/重定位、`ld-linux`、库搜索路径、`LD_PRELOAD`、`dlopen` |
| [06 网络内核原语](./06-network-kernel-primitives/) | socket 内核对象·listen/accept/connect·SYN/accept queue·socket buffer·`sk_buff`·NAPI 到协议栈 | socket fd、backlog、receive/send buffer、`sk_buff`、软中断、NAPI、epoll ready 语义 |
| [07 容器与 cgroup 原语](./07-container-cgroup-primitives/) | namespace·cgroup·CPU quota·memory limit·OOMKill·容器内 `/proc` 视角 | 容器进程模型、PID/mount/net/user namespace、cgroup v2、CPU throttling、memory OOM、overlayfs |
| [08 权限与安全原语](./08-permission-security-primitives/) | UID/GID·effective UID·文件权限·setuid·capabilities·seccomp/AppArmor/SELinux | real/effective UID、目录权限、umask、setuid/sticky bit、capability、user namespace、seccomp、LSM |
| [09 时间与定时器原语](./09-time-timer-primitives/) | wall clock vs monotonic·NTP 调时·timer/sleep/timeout | `CLOCK_REALTIME`、`CLOCK_MONOTONIC`、vDSO、sleep/wakeup、timerfd、deadline、分布式时钟偏差 |
| [10 观测与内核 tracing 原语](./10-observability-kernel-primitives/) | `/proc`/`/sys`·tracepoint·kprobe/uprobe·perf event·eBPF·call stack 采样 | procfs/sysfs、ptrace/strace、perf event、tracepoint、kprobe/uprobe、eBPF、观测成本 |

---

## 推荐阅读顺序

1. **先读 01-04**：补齐内存、执行、IO、并发这四类所有 Linux 问题都会反复用到的基础原语。
2. **再读 05-06**：理解程序如何被装载、网络请求如何从网卡进入应用线程。
3. **接着读 07-08**：把容器资源限制和权限安全边界补上。
4. **最后读 09-10**：理解 timeout/clock 语义,以及 perf/eBPF/trace 工具到底在看什么。

---

## 旧笔记去向

原来的 `basic.md`、`memory.md`、`好用命令.md` 已移到 [`_archive/`](./_archive/) 保留。
它们的内容(`top`/`free`/`VIRT`/`VSZ`/`RES`/`RSS` 等)已被新课更完整地覆盖:

| 旧笔记 | 现在看 |
|--------|--------|
| `basic.md`(top、VIRT/VSZ、文件映射) | [`linux-handson/04-memory-model`](../linux-handson/04-memory-model/) + [`07-troubleshooting-playbook`](../linux-handson/07-troubleshooting-playbook/) |
| `memory.md`(free、RES/RSS、查内存大户) | [`linux-handson/04-memory-model`](../linux-handson/04-memory-model/) |
| `好用命令.md`(个人命令片段) | 保留在 `_archive/`(非课程内容) |
