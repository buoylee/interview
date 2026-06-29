# OS-Fundamentals Primer 引子 + 回链 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给 `performance-tuning-roadmap/00-os-fundamentals/` 整章每篇加「原语地图」头部框 + 在掉进术语的小节加「你视角」30 秒引子和回链,并把「软中断≠硬件中断」补进两个 primer,让薄文档不再假设你已懂底层原语。

**Architecture:** 纯 Markdown 编辑,零新代码、零实跑。每篇 = 1 个头部框(组件 A)+ 若干你视角引子(组件 B,blockquote)+ 章末 1–2 条 `→` 回链。深度内容**不重写**——只引子 + 接线,指向已有的 `linux/` primer 与 `metrics-decoder`。

**Tech Stack:** Markdown;校验用 `test -e`(链接目标存在)+ `grep`(标记已插入)。

## Global Constraints

- **不重写已有深度内容**:本章只加引子 + 回链;`linux/`、`metrics-decoder`、`os-for-architects` 仅做 Task 7 的两句基线补充。
- **语言**:`00-os-fundamentals/*` 正文是简体,引子与回链用**简体**;`metrics-decoder/01-cpu.md` 是繁体,Task 7 在它里面插入的句子用**繁体**;回链里出现的 `原語 B` 是它的原标题,照抄不改。
- **相对路径基准**:章内文件在 `performance-tuning-roadmap/00-os-fundamentals/`;到仓库根用 `../../`(已验证 `../../linux/...`、`../../metrics-decoder/...`、`../../os-for-architects/...`、`../../linux-handson/...` 均可解析);同章互链用 `./04b-...md`。
- **引子格式**:用 `>` blockquote;固定标记词 `**你视角(30 秒):**`、`**一句破误解:**`、回链行 `**→ 深挖黑盒** / **→ 这些指标怎么读** / **→ 架构视角**`,保持全章一致。
- **不造假**:引子是概念桥,不得含伪造的命令输出。
- **git**:当前在 `main`;执行前先 `git switch -c docs/os-fundamentals-primer-bridge`。每个 Task 的 stage+commit 在**同一次 shell 调用**内用**显式文件路径**完成(本仓库常有并发 `git add -A`,绝不用 `-A`)。commit message 末尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

---

## Task 0: 建分支

- [ ] **Step 1: 从 main 切出工作分支**

```bash
cd /Users/buoy/Development/gitrepo/interview
git switch -c docs/os-fundamentals-primer-bridge
git rev-parse --abbrev-ref HEAD   # 期望输出: docs/os-fundamentals-primer-bridge
```

---

## Task 1: `01-cpu-architecture-scheduling.md`(含 §5 中断主角)

**Files:**
- Modify: `performance-tuning-roadmap/00-os-fundamentals/01-cpu-architecture-scheduling.md`

- [ ] **Step 1: 加头部框**

在第一个 `---`(开篇引言下方)与 `## 1. 多核 CPU 架构与缓存层级` 之间插入:

```markdown
> **🧱 本篇用到的底层原语,没把握先补:** 用户/内核态切换 · syscall · 中断 · 上下文切换 → [`linux/02-执行原语`](../../linux/02-execution-primitives/);`us/sy/ni/hi/si` 这些 CPU 指标怎么读 → [`metrics-decoder/01-cpu`](../../metrics-decoder/01-cpu.md)

---
```

- [ ] **Step 2: §3 用户态 vs 内核态 引子**

在标题 `## 3. 用户态 vs 内核态` 行正下方插入:

```markdown

> **你视角(30 秒):** 你在 Java 里调 `socket.read()`、Go 里 `os.Open()`,这些「碰硬件/碰内核资源」的活,你的代码自己**没权限**干。CPU 有两种身份:跑你代码时是「用户态(Ring 3)」,权限受限;要读网卡/磁盘必须切到「内核态(Ring 0)」。`syscall` 指令就是「切身份」的那一下——切过去由内核代劳,干完切回来。下面说的「系统调用代价」,代价就花在这一来一回的身份切换上。
```

在 §3 结尾(`## 4.` 之前的 `---` 之前)插入回链:

```markdown
**→ 深挖黑盒**(syscall 指令怎么切特权级、为什么不走中断向量表):[`linux/02-执行原语`](../../linux/02-execution-primitives/)
```

- [ ] **Step 3: §4 上下文切换 引子**

在标题 `## 4. 上下文切换` 行正下方插入:

```markdown

> **你视角(30 秒):** 你开了 200 个线程,CPU 只有 8 核——其余线程在哪?CPU 在它们之间「轮流坐庄」:跑一会 A,把 A 的现场(寄存器、栈指针)**存档**,把 B 的现场**读档**,接着跑 B。这一存一读就是「上下文切换」,纯属管理开销(没干你的活)。线程开太多,CPU 大量时间花在存档读档上,这就是「上下文切换太多拖慢系统」的由来。
```

在 §4 结尾(`## 5.` 之前的 `---` 之前)插入回链:

```markdown
**→ 这个指标怎么读**(`vmstat` 的 `cs`、自愿/非自愿切换):[`metrics-decoder/01-cpu`](../../metrics-decoder/01-cpu.md) · **→ 深挖黑盒**(切换时内核到底存了什么):[`linux/02-执行原语`](../../linux/02-execution-primitives/)
```

- [ ] **Step 4: §5 中断主角引子(含破误解)**

在标题 `## 5. 中断与软中断` 行正下方、`### 硬中断` 之前插入:

```markdown

> **你视角(30 秒):** 你的 Java/Go 代码一条条顺序执行,它**不会**主动去看「网卡收到包了没」。CPU 怎么知道?两条路:① **轮询**——自己每隔一会问「好了没」,大多时候答案是「没」,纯浪费;② **中断**——平时不管,**硬件有事拉一根信号线主动打断 CPU**。系统几乎全用中断。所以「中断」= 硬件强行打断 CPU、处理完再回原处,跟你熟的 event callback 很像,不是 busy-wait。
>
> **一句破误解:** 下面的「软中断」**不是硬件触发的中断**,是内核自己的一条**高优先级待办队列**(NET_RX/TIMER…)。名字里的「中断」是历史包袱——读成「内核的延后处理任务」就通了。
```

在 §5 结尾(`## 6.` 之前的 `---` 之前)插入回链:

```markdown
**→ 深挖黑盒**(中断上下文为何不能睡眠、top/bottom half、IRQ vs syscall 本质):[`linux/02-执行原语` 原语三](../../linux/02-execution-primitives/)
**→ 这俩指标怎么读**(`top` 的 `hi`/`si`、si 为何打满、RSS/RPS):[`metrics-decoder/01-cpu` 原語 B](../../metrics-decoder/01-cpu.md)
```

- [ ] **Step 5: 校验链接 + 标记**

```bash
cd /Users/buoy/Development/gitrepo/interview/performance-tuning-roadmap/00-os-fundamentals
grep -c "你视角(30 秒)" 01-cpu-architecture-scheduling.md   # 期望: 3
grep -c "一句破误解" 01-cpu-architecture-scheduling.md       # 期望: 1
for t in ../../linux/02-execution-primitives ../../metrics-decoder/01-cpu.md; do test -e "$t" && echo "OK $t" || echo "MISS $t"; done
```
Expected: `3`, `1`, 两行 `OK`。

- [ ] **Step 6: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add performance-tuning-roadmap/00-os-fundamentals/01-cpu-architecture-scheduling.md && \
git commit -m "docs(perf-os): 01-cpu 加原语地图头部框 + 用户内核态/上下文切换/中断你视角引子

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: `02-memory-management.md`

**Files:**
- Modify: `performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md`

- [ ] **Step 1: 加头部框**

在开篇 `---` 与 `## 1. 虚拟内存：为什么需要` 之间插入:

```markdown
> **🧱 本篇用到的底层原语,没把握先补:** 虚拟地址 · 页表 · 缺页(page fault) · brk/mmap → [`linux/01-内存原语`](../../linux/01-memory-primitives/);`RSS/VIRT/Swap/缺页率/OOM` 这些内存指标怎么读 → [`metrics-decoder/02-memory`](../../metrics-decoder/02-memory.md)

---
```

- [ ] **Step 2: §1–3 合一个引子(虚拟内存→页表→缺页链)**

在标题 `## 1. 虚拟内存：为什么需要` 行正下方插入:

```markdown

> **你视角(30 秒):** 你 `new` / `make` 出来的对象地址(打印出个 `0x7f3c...`)是个**假地址**——虚拟地址。每个进程都以为自己独占整条地址空间、互不打架,这就是「虚拟内存」给的隔离。但 CPU 真访问内存得用物理地址,中间靠**页表**把虚拟翻译成物理(按 4KB 一页翻),表太大就分多级、还在 CPU 里加个缓存叫 **TLB**。如果你访问的那一页**还没在物理内存里**,CPU 就触发一次**缺页(Page Fault)**陷进内核补页——只动内存是 minor(快),要去磁盘读是 major(慢,毫秒级)。下面 §2/§3 讲的就是这条「虚拟→页表/TLB→缺页」链路。
```

在 §3 结尾(`## 4.` 之前的 `---` 之前)插入回链:

```markdown
**→ 深挖黑盒**(虚拟地址/页表/缺页在内核里怎么走、怎么亲眼看到):[`linux/01-内存原语`](../../linux/01-memory-primitives/)
**→ 这些指标怎么读**(`VmRSS/VmSize`、`min_flt/maj_flt`):[`metrics-decoder/02-memory`](../../metrics-decoder/02-memory.md)
```

- [ ] **Step 3: §5 OOM 引子**

在标题 `## 5. OOM Killer` 行正下方插入:

```markdown

> **你视角(30 秒):** 内存真不够时,Linux 不会优雅地「分配失败让你处理」——它早把内存**超额借**给了大家(每个进程都以为自己内存很多),等真兑现不出来,内核就派 **OOM Killer** 挑一个进程**直接杀掉**抢回内存。你的 Java 进程「莫名其妙消失、日志里没有异常栈」,十有八九就是被它杀了(`dmesg | grep -i oom` 能看到)。容器里更常见:cgroup 给的内存上限一到就在**容器内**触发 OOM,和宿主机整体满不满无关。
```

在 §5 结尾(`## 6.` 之前的 `---` 之前)插入回链:

```markdown
**→ 架构视角**(OOM / cgroup 内存上限如何影响容器资源规划):[`os-for-architects/05-隔离与 cgroups`](../../os-for-architects/05-isolation-and-cgroups/)
```

- [ ] **Step 4: 校验**

```bash
cd /Users/buoy/Development/gitrepo/interview/performance-tuning-roadmap/00-os-fundamentals
grep -c "你视角(30 秒)" 02-memory-management.md   # 期望: 2
for t in ../../linux/01-memory-primitives ../../metrics-decoder/02-memory.md ../../os-for-architects/05-isolation-and-cgroups; do test -e "$t" && echo "OK $t" || echo "MISS $t"; done
```
Expected: `2`,三行 `OK`。

- [ ] **Step 5: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md && \
git commit -m "docs(perf-os): 02-memory 加头部框 + 虚拟内存链/OOM 你视角引子

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `03-disk-io-filesystem.md`

**Files:**
- Modify: `performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md`

- [ ] **Step 1: 加头部框**

在开篇 `---` 与 `## 1. 块设备模型` 之间插入:

```markdown
> **🧱 本篇用到的底层原语,没把握先补:** fd · VFS/inode · write→page cache→回写路径 · 阻塞 I/O → [`linux/03-IO 原语`](../../linux/03-io-primitives/);`%util/await/iowait/r/s·w/s` 这些磁盘指标怎么读 → [`metrics-decoder/03-disk-io`](../../metrics-decoder/03-disk-io.md)

---
```

- [ ] **Step 2: §3 Page Cache 引子**

在标题 `## 3. Page Cache` 行正下方插入:

```markdown

> **你视角(30 秒):** 你以为 `write()` 把数据写进了磁盘?不——绝大多数情况它只写进了内存里的一层缓存叫 **Page Cache** 就立刻返回了(所以快),真正落盘是内核**稍后**后台批量做的。读也一样:第一次读穿到磁盘(慢),数据顺手留在 Page Cache,第二次直接从内存拿(快)。这解释了两件你常困惑的事:① `free` 里内存「几乎被吃光」很正常,大半是 Page Cache、随时可回收;② `write()` 返回 ≠ 数据安全,断电会丢——要安全得显式 `fsync`(见 §6)。
```

在 §3 结尾(`## 4.` 之前的 `---` 之前)插入回链:

```markdown
**→ 深挖黑盒**(write→page cache→脏页回写这条路径在内核里怎么走):[`linux/03-IO 原语`](../../linux/03-io-primitives/)
**→ 这些指标怎么读**(`free` 的 cache 行、脏页 `Dirty`):[`metrics-decoder/03-disk-io`](../../metrics-decoder/03-disk-io.md)
```

- [ ] **Step 3: §6 fsync 引子**

在标题 `## 6. fsync 与 fdatasync` 行正下方插入:

```markdown

> **你视角(30 秒):** 接着 §3——既然 `write()` 只到 Page Cache,那「写完了」其实不保证断电不丢。`fsync(fd)` 就是那句「现在,真的,给我落到磁盘介质上,落完再返回」,代价就是它**必须等磁盘**,慢。数据库的命根子(redo log / WAL)每次提交都得 `fsync` 一次,所以「每秒能 commit 多少」很大程度上就是「磁盘每秒能 fsync 多少」——这也是为什么 DB 对磁盘 fsync 延迟极度敏感。
```

- [ ] **Step 4: 校验**

```bash
cd /Users/buoy/Development/gitrepo/interview/performance-tuning-roadmap/00-os-fundamentals
grep -c "你视角(30 秒)" 03-disk-io-filesystem.md   # 期望: 2
for t in ../../linux/03-io-primitives ../../metrics-decoder/03-disk-io.md; do test -e "$t" && echo "OK $t" || echo "MISS $t"; done
```
Expected: `2`,两行 `OK`。

- [ ] **Step 5: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md && \
git commit -m "docs(perf-os): 03-disk-io 加头部框 + Page Cache/fsync 你视角引子

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: `04a-network-tcp-core.md`

**Files:**
- Modify: `performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md`

- [ ] **Step 1: 加头部框**

在开篇 `---` 与 `## 1. TCP/IP 四层模型` 之间插入:

```markdown
> **🧱 本篇用到的底层原语,没把握先补:** Socket · 内核收发包 · sk_buff → 同章 [`04b Socket 与内核网络`](./04b-network-socket-kernel.md);`ss` 看连接状态/队列 → [`metrics-decoder/04-network`](../../metrics-decoder/04-network.md)

---
```

- [ ] **Step 2: §2 两个队列 引子**

在标题 `## 2. 三次握手详解` 行正下方插入:

```markdown

> **你视角(30 秒):** 服务端 `listen()` 之后,内核替你维护了**两个排队队列**,握手的包先在这排队,你的 `accept()` 才从队尾取走连接:
> - **半连接队列(SYN Queue)**:收到 SYN、还没完成三次握手的连接放这。被 SYN Flood 打满 → 新连接握不上手。
> - **全连接队列(Accept Queue)**:三次握手已完成、等你 `accept()` 取走的连接放这。应用 `accept()` 太慢 → 这个队列溢出 → 连接被丢/被拒。
>
> 记住这俩队列,下面 `tcp_max_syn_backlog`、`somaxconn`、各种 `*Overflows` 指标才有归属。
```

在 §4 TIME_WAIT 结尾(`## 5.` 之前的 `---` 之前,即 `**最佳实践**` 那段之后)插入回链:

```markdown
**→ 这些状态/队列怎么看**(`ss -ant` 状态分布、Accept Queue 溢出):[`metrics-decoder/04-network`](../../metrics-decoder/04-network.md)
```

- [ ] **Step 3: 校验**

```bash
cd /Users/buoy/Development/gitrepo/interview/performance-tuning-roadmap/00-os-fundamentals
grep -c "你视角(30 秒)" 04a-network-tcp-core.md   # 期望: 1
for t in ./04b-network-socket-kernel.md ../../metrics-decoder/04-network.md; do test -e "$t" && echo "OK $t" || echo "MISS $t"; done
```
Expected: `1`,两行 `OK`。

- [ ] **Step 4: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md && \
git commit -m "docs(perf-os): 04a-tcp 加头部框 + SYN/Accept 两队列你视角引子

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: `04b-network-socket-kernel.md`

**Files:**
- Modify: `performance-tuning-roadmap/00-os-fundamentals/04b-network-socket-kernel.md`

- [ ] **Step 1: 加头部框**

在开篇 `---` 与 `## 1. Socket Buffer（sk_buff）` 之间插入:

```markdown
> **🧱 本篇用到的底层原语,没把握先补:** 中断(硬/软中断) · 上下文 → [`linux/02-执行原语`](../../linux/02-execution-primitives/);DMA/零拷贝靠的 fd 与内核缓冲 → [`linux/03-IO 原语`](../../linux/03-io-primitives/);`si` 软中断 + 网卡队列指标 → [`metrics-decoder/01-cpu` 原語 B](../../metrics-decoder/01-cpu.md) 与 [`metrics-decoder/04-network`](../../metrics-decoder/04-network.md)

---
```

- [ ] **Step 2: §1 Socket Buffer 引子**

在标题 `## 1. Socket Buffer（sk_buff）` 行正下方插入:

```markdown

> **你视角(30 秒):** 你 `recv()` 还没读到数据时,数据在哪?在内核替这条连接准备的**接收缓冲区(rmem)**里躺着;你 `send()` 的数据也不是立刻上网线,先进**发送缓冲区(wmem)**,由协议栈慢慢发。这俩缓冲区就是「应用」和「网卡」之间的蓄水池:太小会直接限制吞吐(TCP 窗口 ≤ 缓冲区),太大则吃内存——下面 `tcp_rmem/tcp_wmem` 调的就是这两个池子。
```

- [ ] **Step 3: §2 内核收包流程 引子**

在标题 `## 2. 内核收包完整流程` 行正下方插入:

```markdown

> **你视角(30 秒):** 这张图就是「一个包从网线到你 `recv()`」的全程,里面的**硬中断/软中断**正是你之前看不懂的那对:网卡 DMA 把包丢进 Ring Buffer 后,**拉硬中断**喊一嗓子「有货」(②③,极短),真正解析协议栈的重活交给 **NET_RX 软中断 / NAPI**(④⑤)慢慢干,最后放进 §1 的接收缓冲区等你来取(⑦⑧)。一句话:§1 的缓冲区是「货架」,这一节是「上货流水线」。
```

在 §2 结尾(`## 3.` 之前的 `---` 之前)插入回链:

```markdown
**→ 中断这对原语没吃透**(轮询 vs 中断、为何拆 top/bottom half):[`linux/02-执行原语` 原语三](../../linux/02-execution-primitives/) + [`metrics-decoder/01-cpu` 原語 B](../../metrics-decoder/01-cpu.md)
```

- [ ] **Step 4: §4 RSS/RPS 引子**

在标题 `## 4. 网卡多队列与 RSS` 行正下方插入:

```markdown

> **你视角(30 秒):** 接 §2——默认下,**哪个 CPU 接了网卡硬中断,后续那坨软中断(协议栈重活)就压在同一个核上**。流量一大,这一个核的 `si`(软中断)先打到 100%、其他核还闲着,这就是「单核 si 瓶颈」。**RSS** 是网卡硬件层面把不同连接的包分到多个队列→多个核;**RPS/RFS** 是没有多队列网卡时用软件把这活分散到多核。本质都是「别让一个核扛下所有收包」。
```

- [ ] **Step 5: 校验**

```bash
cd /Users/buoy/Development/gitrepo/interview/performance-tuning-roadmap/00-os-fundamentals
grep -c "你视角(30 秒)" 04b-network-socket-kernel.md   # 期望: 3
for t in ../../linux/02-execution-primitives ../../linux/03-io-primitives ../../metrics-decoder/01-cpu.md ../../metrics-decoder/04-network.md; do test -e "$t" && echo "OK $t" || echo "MISS $t"; done
```
Expected: `3`,四行 `OK`。

- [ ] **Step 6: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add performance-tuning-roadmap/00-os-fundamentals/04b-network-socket-kernel.md && \
git commit -m "docs(perf-os): 04b-socket 加头部框 + Socket Buffer/收包流程/RSS 你视角引子

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: `05-process-thread-coroutine.md`

**Files:**
- Modify: `performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md`

- [ ] **Step 1: 加头部框**

在开篇 `---` 与 `## 1. 进程 vs 线程 vs 协程` 之间插入:

```markdown
> **🧱 本篇用到的底层原语,没把握先补:** 进程/线程的内核表示(task_struct) · 上下文切换 · 信号 · fd · epoll → [`linux/02-执行原语`](../../linux/02-execution-primitives/) + [`linux/03-IO 原语`](../../linux/03-io-primitives/);动手观察进程/线程状态 → [`linux-handson/03-进程模型`](../../linux-handson/03-process-model/)

---
```

- [ ] **Step 2: §1 进程/线程/协程 引子**

在标题 `## 1. 进程 vs 线程 vs 协程` 行正下方插入:

```markdown

> **你视角(30 秒):** 三个词其实是「被调度的单位有多重」在变:**进程**=独立地址空间+独立 fd 表,最重,隔离最强(一个崩了不连累别人);**线程**=共享同一进程的地址空间和 fd,只独立栈和寄存器,切换比进程轻(不用换页表);**协程**=连内核都不知道它存在,由你语言的 runtime(Go scheduler、Python asyncio)在用户态自己调度,切换最轻(一次函数跳转级别)。所以表里「切换代价 进程 > 线程 > 协程」不是玄学,是「每次切换内核要存/换多少东西」决定的。
```

- [ ] **Step 3: §3 信号 引子**

在标题 `## 3. 信号机制` 行正下方插入:

```markdown

> **你视角(30 秒):** 信号就是**内核(或别的进程)塞给你进程的一个「软件中断」**——和硬件中断一个味道:打断你正常的控制流,逼你跳去执行一段处理函数。你 `kill -15` 发的 SIGTERM、Ctrl+C 的 SIGINT、段错误的 SIGSEGV,全是信号。关键性质:`SIGKILL(9)` 和 `SIGSTOP(19)` **不可捕获**(你拦不住,这就是 `kill -9` 一定生效的原因);其他信号可以注册 handler 优雅处理(比如收到 SIGTERM 先把连接 drain 完再退)。
```

在 §3 结尾(`## 4.` 之前的 `---` 之前)插入回链:

```markdown
**→ 深挖黑盒**(信号怎么异步投递、为何只在「内核态返回用户态」那一刻才处理):[`linux/04-并发原语`](../../linux/04-concurrency-primitives/)
```

- [ ] **Step 4: §5 epoll 引子**

在标题 `## 5. I/O 多路复用演进` 行正下方插入:

```markdown

> **你视角(30 秒):** 一个线程怎么同时盯着上万条连接、谁来数据就处理谁?这就是 I/O 多路复用要解决的。你用的几乎一切高并发框架(Java NIO/Netty、Redis、Nginx、Go runtime、Python asyncio)底层都是 **epoll**。一句话抓住演进:`select/poll` 每次都得把「要盯的 fd 全集」整个交给内核、内核再整个扫一遍找就绪的(O(n),连接越多越慢);**epoll** 把「盯哪些 fd」一次性注册进内核的红黑树,谁就绪内核回调把它丢进一条「就绪链表」,`epoll_wait` 直接取这条短链表(O(就绪数))——这就是它能扛百万连接的根。
```

在 §5 结尾(`## 6. 实用诊断命令` 之前的 `---` 之前)插入回链:

```markdown
**→ 深挖黑盒**(epoll 红黑树+就绪链表、fd 在内核里怎么表示):[`linux/03-IO 原语`](../../linux/03-io-primitives/)
```

- [ ] **Step 5: 校验**

```bash
cd /Users/buoy/Development/gitrepo/interview/performance-tuning-roadmap/00-os-fundamentals
grep -c "你视角(30 秒)" 05-process-thread-coroutine.md   # 期望: 3
for t in ../../linux/02-execution-primitives ../../linux/03-io-primitives ../../linux/04-concurrency-primitives ../../linux-handson/03-process-model; do test -e "$t" && echo "OK $t" || echo "MISS $t"; done
```
Expected: `3`,四行 `OK`。

- [ ] **Step 6: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md && \
git commit -m "docs(perf-os): 05-proc 加头部框 + 进程线程协程/信号/epoll 你视角引子

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: 基线补句 — 把「软中断≠硬件中断」补进两个 primer

**Files:**
- Modify: `linux/02-execution-primitives/README.md`
- Modify: `metrics-decoder/01-cpu.md`

**Interfaces:**
- Consumes: Task 1 §5 与 Task 5 §2 的回链都指向这两处,本任务让目标内容真的把这句话写明。

- [ ] **Step 1: linux/02(简体)**

定位到「原语三:中断 IRQ」里 bottom-half 的类比那一行——以 `类比：网卡中断到来 → Top half` 开头、`走协议栈（可以睡眠等锁）。` 结尾的整行。在该行正下方插入:

```markdown

> **一句破误解:** 这里的「软中断(softirq)」**不是硬件触发的中断**,而是内核自己一套**固定几类的高优先级待办队列**(`NET_RX`/`NET_TX`/`TIMER`…)。硬中断的 top half 只是去队列上「打个标记:有活」,内核在硬中断返回时、或在专门的 `ksoftirqd` 内核线程里把这些待办跑掉。名字里的「中断」是历史包袱——读成「内核的延后处理任务」就不会和硬件中断混了。
```

- [ ] **Step 2: metrics-decoder/01(繁体)**

定位到「原語 B:中斷(`hi` / `si`)」里以 `- **軟中斷(softirq` 开头、`網路收包大量走 \`NAPI\` 這套軟中斷。` 结尾的那一行(`si` 的解释项)。在该行正下方插入:

```markdown

> **一句破誤解:** 這裡的「軟中斷(softirq)」**不是硬體觸發的中斷**,而是內核自己一套**固定幾類的高優先級待辦佇列**(`NET_RX`/`TIMER`…)。硬中斷的上半部只是去佇列「打個標記:有活」,內核稍後(硬中斷返回時、或 `ksoftirqd` 執行緒裡)把待辦跑掉。名字裡的「中斷」是歷史包袱——讀成「內核的延後處理任務」就不會和硬中斷混了。
```

- [ ] **Step 3: 校验**

```bash
cd /Users/buoy/Development/gitrepo/interview
grep -c "一句破误解" linux/02-execution-primitives/README.md   # 期望: 1
grep -c "一句破誤解" metrics-decoder/01-cpu.md                  # 期望: 1
```
Expected: 两个 `1`。

- [ ] **Step 4: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add linux/02-execution-primitives/README.md metrics-decoder/01-cpu.md && \
git commit -m "docs(primer): 点明软中断不是硬件中断、是内核待办队列(linux/02 + metrics-decoder/01)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: 全章终检

- [ ] **Step 1: 统计与链接总校验**

```bash
cd /Users/buoy/Development/gitrepo/interview/performance-tuning-roadmap/00-os-fundamentals
echo "你视角引子总数(期望 14):"
grep -rc "你视角(30 秒)" 0*.md | awk -F: '{s+=$2} END{print s}'
echo "头部框总数(期望 6):"
grep -lc "本篇用到的底层原语" 0*.md | wc -l
echo "破误解(章内 1 + 两 primer 各 1 = 3):"
grep -rl "一句破误解\|一句破誤解" ../../performance-tuning-roadmap/00-os-fundamentals/0*.md ../../linux/02-execution-primitives/README.md ../../metrics-decoder/01-cpu.md | wc -l
```
Expected: `14`、`6`、`3`。

- [ ] **Step 2: 抽查所有新增相对链接可解析**

```bash
cd /Users/buoy/Development/gitrepo/interview/performance-tuning-roadmap/00-os-fundamentals
grep -rhoE "\]\(\.\.?/[^)]+\)" 0*.md | sed -E 's/^\]\(//; s/\)$//' | sort -u | while read p; do
  test -e "$p" && echo "OK   $p" || echo "MISS $p"
done
```
Expected: 全部 `OK`,无 `MISS`。

---

## Self-Review(plan vs spec)

- **覆盖**:spec §5 触点地图 6 行 → Task 1–6 一一对应;基线两处 → Task 7;§4 模板(组件 A/B + 回链)→ 每个 Task 的 Step 落地。无遗漏。
- **占位符**:全部引子均为成稿,无 TBD/“类似上文”。每个 Edit 给了锚点 + 完整插入文本。
- **类型/命名一致**:全章统一标记词 `你视角(30 秒)` / `一句破误解`(章内简体)/`一句破誤解`(metrics-decoder 繁体);链接路径前缀统一 `../../`(章内)、`./`(同章)。终检脚本里 `你视角(30 秒)` 计数与各 Task 校验的期望值相加 = 3+2+2+1+3+3 = 14,自洽。
- **不碰清单**:无 Task 触及 01 §1/§2、各篇速查/总结、README.md——符合 spec §7。
