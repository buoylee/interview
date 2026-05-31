# Linux 系统学习 / 面试路径 — 设计 Spec

> 日期:2026-05-31
> 目标读者:本人(7 年全栈,Java/Go/Python/JS;Linux 接触少,能跑命令但缺系统性原理)
> 语言约定:课程正文用简体中文,与仓库已有 `performance-tuning-roadmap`、`mysql-handson` 等保持一致。

---

## 1. 目标与定位(已对齐)

| 维度 | 结论 |
|------|------|
| **目标定位** | 资深全栈/后端「够用且能答」——应用开发者视角打通 Linux,理解原理 + 能动手排查 + 面试讲得清。**不**钻内核源码。 |
| **当前起点** | 能 SSH 上去、会基础命令,但权限、进程/资源排查、复杂命令组合靠现搜。需要扎实的 CLI + 文件系统/权限 on-ramp,再进系统模型。 |
| **文档形态** | 读练结合:每章正文讲原理 + 沙箱动手实验 + 99 面试卡。对标本人熟悉的 `mysql-handson` 风格。 |
| **结构方案** | 方案 A:新建独立目录,自洽线性可读;在需要深入处用一行指针指向 `performance-tuning-roadmap` 深章,不复制。 |
| **沙箱** | 路线①:真实轻量 VM(multipass/Lima)为主 + Docker 辅(用于 09-容器章)。 |

**核心主线(系统性的那根线):**
> Linux 内核是一个**资源管理者**;每种资源管一章。一切皆文件 → 进程是资源使用者 → 内核把 CPU/内存/I/O/网络分给进程 → 出问题时顺着这四种资源排查。

**成功标准:** 学完后,面对一台真实 Linux 机器的常见问题(CPU 100%、内存涨/OOM、磁盘满、fd 耗尽、连接数爆、僵尸进程、服务起不来),能独立用工具定位到资源与进程,并在面试中讲清原理与排查链路。

---

## 2. 目录结构与命名

新目录:**`linux-handson/`**(对齐 `mysql-handson` 命名惯例)。

```
linux-handson/
├── README.md                      # 课程总览 + 学习弧线 + 节奏建议 + 与 perf-roadmap 的分工
├── 00-lab/                        # 沙箱搭建(VM + provision 脚本)
├── 01-mental-model-and-shell/     # 世界观 + shell 工作原理
├── 02-filesystem-and-permissions/ # 文件系统 + 权限
├── 03-process-model/              # 进程模型 ⭐核心
├── 04-memory-model/               # 内存模型 ⭐核心
├── 05-io-and-files/               # I/O 与文件 ⭐核心
├── 06-networking/                 # 网络模型 ⭐核心
├── 07-troubleshooting-playbook/   # 排查方法论与工具箱 ⭐⭐高潮(串起 03–06)
├── 08-systemd-and-services/       # systemd 与服务管理
├── 09-containers-from-linux/      # 容器底层(Linux 视角)
├── 10-shell-scripting/            # Shell 脚本 + 文本三件套
├── 99-interview-cards/            # 速答表 + 深题卡
└── templates/                     # 章节模板、lab 模板、卡片模板
```

**层级标注:** 03–07 核心必学(面试重灾区);01–02 on-ramp;08–10 工程化拓展。可核心先打通,拓展后补。

**旧 `linux/` 处理:**
- 有用笔记并入新章:`好用命令.md` → 各章「怎么看」段 + 一张速查;`memory.md` → 04;`basic.md` → 01/02。
- 3 个空档(`CPU.md` / `io.md` / `network.md`)删除(被新章取代)。
- `linux/` 留一个 `README.md` 重定向到 `linux-handson/`;旧笔记归档到 `linux/_archive/`(沿用 `mysql/_archive` 习惯,不丢东西)。

---

## 3. 模块地图(内容大纲)

| # | 章节 | 解决的盲点(要点) | 层级 |
|---|------|------|------|
| 00 | lab 沙箱 | 在 Mac 上起一个能反复折腾的真 Ubuntu VM;约定每章动手都在此跑 | 前置 |
| 01 | 世界观 + shell 原理 | 内核 vs 用户态、一切皆文件;命令如何被执行(fork+exec 预告)、PATH、内建 vs 外部;管道/重定向/fd 0·1·2 本质(`2>&1` 为何顺序重要) | on-ramp |
| 02 | 文件系统 + 权限 | 目录树/FHS、inode/硬链接/软链接;rwx/ugo、suid/sgid/sticky、umask;用户/组、sudo;`/proc` `/sys` 作为内核窗口 | on-ramp |
| 03 | 进程模型 ⭐ | fork/exec/wait、PID/PPID、进程状态 R/S/D/Z/T;僵尸 & 孤儿、init/systemd 收养;信号(SIGTERM/SIGKILL/SIGCHLD)、kill、trap;会话/进程组/控制终端(关 SSH 为何进程死)、nohup/disown | 核心 |
| 04 | 内存模型 ⭐ | 虚拟内存/地址空间/页、page cache;RSS vs VSZ vs PSS、共享内存;OOM killer、swap;`free`/`/proc/meminfo` 怎么读;容器里 `free` 为何是宿主机、cgroup 内存限制 | 核心 |
| 05 | I/O 与文件 ⭐ | fd、打开文件表、阻塞/非阻塞;缓冲 I/O vs 直接 I/O、fsync、脏页回写;磁盘 I/O 指标(util/await);ulimit / **fd 耗尽** | 核心 |
| 06 | 网络模型 ⭐ | socket、TCP 状态机(TIME_WAIT/CLOSE_WAIT 实战意义);端口/本地端口耗尽、`ss`;DNS 解析路径、`/etc/hosts` `/etc/resolv.conf`;tcpdump 入门、curl/nc/telnet 排查连通性 | 核心 |
| 07 | 排查方法论与工具箱 ⭐⭐ | USE 方法(指针 perf-roadmap/01);「一台机器慢/挂了」系统化排查路径:负载→CPU→内存→IO→网络→进程;工具地图(top/htop, vmstat, iostat, pidstat, ss, strace, lsof, dmesg, journalctl);strace/lsof 实战;经典案例集 | 高潮 |
| 08 | systemd 与服务管理 | unit/service/target;systemctl/journalctl 日常、开机自启、依赖、资源限制(对接 cgroup);journald vs 文件日志、logrotate | 工程化 |
| 09 | 容器底层(Linux 视角) | namespaces(pid/net/mnt…)、cgroups v2、overlayfs;「容器只是受限的进程」;对接日常 Docker/K8s 经验 | 工程化 |
| 10 | Shell 脚本 + 文本三件套 | 够用的 bash(变量/条件/循环/函数、`set -euo pipefail`);grep/sed/awk;一键排查脚本、日志分析 one-liner | 工具 |
| 99 | 面试卡 | 速答表 + 场景化深题卡 | 面试 |

---

## 4. 每章内部结构(`01`–`10` 通用七段式)

顺序刻意为「先懂原理、再动手、最后应试」。**讲清原理之前不丢预测题。**

1. **开篇盲点** — 「你现在大概这样理解,但其实…」点破常见误解,给动机。
2. **正文 · 叙事式原理** — 图 + 类比 + 四语言桥接,从现象推到机制。先把「公式」讲透。
3. **怎么看 · 命令边讲边给** — 每个概念配命令 + **真实输出示例 + 逐栏怎么读**(不是裸列命令)。
4. **动手实验(沙箱)** — 制造现象 → 观察 → 排查 → 验证。可复制、可重跑;开头标注所需环境(VM shell / `docker run --cap-add=...`)。
5. **生产踩坑框** — app-dev 视角的真实坑(仿 perf-roadmap 的「生产经验」框)。
6. **本章面试速记** — 2–3 条「这题一句话怎么答」,与 99 卡呼应。
7. **小结 + 一句话记忆点 + 延伸指针**(→ `perf-roadmap/XX`)。

### 质感基准(节录自 03 的「D 状态」)
> 盲点:以为 `kill -9` 万能。原理:`D`(不可中断睡眠)在等内核 I/O 完成,不响应信号。怎么看:`ps -eo pid,stat,wchan,cmd`,`wchan` 看卡在哪个内核函数。动手:沙箱里对慢速挂载 `dd`,观察进程进入 `D`,`kill -9` 无效。桥接:Java 服务「假死」、线程 dump 看不出问题,可能卡在 `D`,问题在磁盘不在 JVM。

---

## 5. 四语言桥接策略(提升流畅度的关键)

每个核心概念,用四种运行时的对应物搭桥,并在合适处指回**本仓库已有的笔记**:

| Linux 机制 | Java | Go | Python | Node/JS |
|---|---|---|---|---|
| 线程 = OS 调度单位 | JVM 线程 ≈ 1:1 | goroutine M:N | GIL 下多线程不真并行 | 单线程事件循环 + worker_threads/cluster |
| 阻塞 I/O vs epoll | Netty epoll | **Go netpoller** | **asyncio** | libuv |
| 进程内存 RSS | JVM 堆 vs RSS、MaxRAMPercentage | Go runtime + GC | refcount + gc | V8 堆、--max-old-space-size |
| SIGTERM 优雅关闭 | Spring graceful shutdown | signal.Notify + context | signal + asyncio 收尾 | process.on('SIGTERM') |

**内部指针:** 讲到并发/IO 时指回 `python-concurrency/04-asyncio-core`、`python-concurrency/01-foundations-gil`、`golang/concurrency`(netpoller),把已有的并发笔记用「OS 线程/epoll」这条 Linux 主线重新串成网。

---

## 6. 99 面试卡设计

**① 速答表** — 一行一题、一句话答,按资源分组(进程/内存/IO/网络/容器/systemd),快速自测。

**② 深题卡** — 每张固定结构:
```
题目  →  30 秒口头答(先给结论)
      →  展开(原理 + 图/数据)
      →  追问预案(面试官接着会问什么,怎么接)   ← 体现资深差距的关键栏
      →  踩坑/数据点
```
核心主题各 3–5 张(示例:TIME_WAIT 堆积怎么办、内存涨了怎么定位是否泄漏、机器 load 高怎么查、容器 OOM 但宿主机内存还多)。卡片用相对链接回对应章节。

---

## 7. 沙箱方案(`00-lab`)

**路线①:真实 VM 为主 + Docker 辅**
- 用 `multipass`(默认,装起来最简单;可改 Lima/Colima)起一个真 Ubuntu LTS VM。
- 配 `provision.sh` 一键装齐工具箱:`procps sysstat strace ltrace lsof iproute2 net-tools tcpdump stress-ng htop dstat` 等。
- 弄坏了 `multipass delete && launch` 重来。
- **诚实度:** systemd 真跑、`sysctl`/cgroup/namespace 真改、OOM/swap/`D` 状态能真实复现。
- **09-容器章**单独用 Docker,演示「容器只是受限进程」(`free` 为何看到宿主机、限额 OOM)——此时容器的「不真」本身就是教学点。
- 每章 lab 开头标注所需环境与权限(如 strace 需 `SYS_PTRACE`、tcpdump 需 `NET_RAW`)。

---

## 8. 交付节奏(增量,不一次倒)

1. **垂直切片先行:** 先写 `00-lab` + `01`(世界观+shell)+ 这两章的几张 99 卡,验证七段式 + 四语言桥接 + lab 手感。
2. **确认质感后**,一章一章往下推,核心 03–07 优先;每章 review → 反馈 → 下一章。99 卡随章增长。

---

## 9. 验收口径(每章「学到什么程度算完成」)

- 能用自己的话讲清该资源的内核模型 + 一个 Java/Go/Python/JS 桥接。
- 能在沙箱独立跑完该章 lab,并解释每个命令输出的关键栏。
- 能默答该章对应的 99 速答表条目,并完整讲一张深题卡(含追问预案)。

---

## 10. 暂不纳入(YAGNI)

- 内核源码级剖析、驱动开发、编译内核。
- 发行版差异大全(以 Ubuntu/Debian 为主,RHEL 差异仅在必要处点注)。
- 深度性能调优 / eBPF / SRE 闭环 —— 用指针引向 `performance-tuning-roadmap`,不在本课展开。
