# Linux 动手课 · 资深全栈「够用且能答」

> **定位**：你有 7 年全栈经验(Java/Go/Python/JS),但 Linux 接触少、能跑命令却缺系统性原理。这门课从应用开发者视角打通 Linux,目标是**理解原理 + 能动手排查 + 面试讲得清**,不钻内核源码。

> **设计 spec**：[`docs/superpowers/specs/2026-05-31-linux-learning-path-design.md`](../docs/superpowers/specs/2026-05-31-linux-learning-path-design.md)

---

## 一根主线：内核是资源管理者

学这门课,始终抓住一句话:

> **Linux 内核是一个资源管理者;每种资源管一章。**
> 一切皆文件 → 进程是资源的使用者 → 内核把 **CPU / 内存 / I/O / 网络** 分给进程 → 出问题时,顺着这四种资源排查。

学完你会从「命令靠现搜」升级成「我知道这条命令在向内核要什么、卡在哪」。

---

## 模块地图

| # | 章节 | 解决的盲点 | 层级 |
|---|------|-----------|------|
| [00](./00-lab/) | **lab 沙箱** | 在 Mac 上起一个能反复折腾的真 Linux VM | 前置 |
| [01](./01-mental-model-and-shell/) | **世界观 + shell 原理** | 命令怎么被执行、管道/重定向/fd 0·1·2 的本质 | on-ramp |
| [02](./02-filesystem-and-permissions/) | **文件系统 + 权限** | FHS、inode/软硬链接、rwx/suid/umask、`/proc` `/sys` | on-ramp |
| [03](./03-process-model/) | **进程模型** ⭐ | fork/exec、状态 R/S/D/Z、信号、僵尸/孤儿、会话与控制终端 | 核心 |
| [04](./04-memory-model/) | **内存模型** ⭐ | 虚拟内存/page cache、RSS vs VSZ、OOM killer、swap | 核心 |
| [05](./05-io-and-files/) | **I/O 与文件** ⭐ | fd、缓冲/直接 I/O、fsync、iostat 指标、**fd 耗尽** | 核心 |
| [06](./06-networking/) | **网络模型** ⭐ | socket、TCP 状态机、端口耗尽、DNS、tcpdump 入门 | 核心 |
| [07](./07-troubleshooting-playbook/) | **排查方法论与工具箱** ⭐⭐ | 把 03–06 串起来:负载→CPU→内存→IO→网络 系统化排查 | 高潮 |
| [08](./08-systemd-and-services/) | **systemd 与服务管理** | unit/service、systemctl/journalctl、开机自启、资源限制 | 工程化 |
| [09](./09-containers-from-linux/) | **容器底层(Linux 视角)** | namespaces/cgroups/overlayfs:「容器只是受限的进程」 | 工程化 |
| [10](./10-shell-scripting/) | **Shell 脚本 + 文本三件套** | 够用的 bash、grep/sed/awk、一键排查脚本 | 工具 |
| [11](./11-fault-injection-lab/) | **故障注入实验室(道场)** ⭐⭐ | 按需造真故障、走完整事故流程,补「大厂真实经验」 | 演练 |
| [99](./99-interview-cards/) | **面试卡** | 速答表 + 场景化深题卡 | 面试 |

**学习节奏**:`03–07` 是核心必学(也是面试重灾区);`01–02` 是 on-ramp;`08–10` 工程化拓展;[`11`](./11-fault-injection-lab/) 是配合 `03–07` 的演练道场,学完核心随时回来刷。建议**核心先打通,拓展后补**。

---

## 每章长什么样(七段式)

顺序刻意为「先懂原理、再动手、最后应试」:

1. **开篇盲点** —— 点破你现在大概率的误解,给动机。
2. **正文 · 叙事式原理** —— 图 + 类比 + 四语言桥接,从现象推到机制。
3. **怎么看 · 命令边讲边给** —— 每个概念配命令 + 真实输出 + 逐栏怎么读。
4. **动手实验(沙箱)** —— 制造现象 → 观察 → 排查 → 验证。
5. **生产踩坑框** —— app-dev 视角的真实坑。
6. **本章面试速记** —— 2–3 条「这题一句话怎么答」。
7. **小结 + 一句话记忆点 + 延伸指针**。

---

## 四语言桥接

每个核心概念,用你四种运行时的对应物搭桥,把新知识挂在旧知识上:

| Linux 机制 | Java | Go | Python | Node/JS |
|---|---|---|---|---|
| 线程 = OS 调度单位 | JVM 线程 ≈ 1:1 | goroutine M:N | GIL 下多线程不真并行 | 单线程事件循环 + worker_threads |
| 阻塞 I/O vs epoll | Netty epoll | Go netpoller | asyncio | libuv |
| 进程内存 RSS | JVM 堆 vs RSS | Go runtime + GC | refcount + gc | V8 堆 |
| SIGTERM 优雅关闭 | Spring graceful shutdown | signal.Notify + context | signal + asyncio | process.on('SIGTERM') |

讲到并发/IO 时,会指回你仓库里已有的笔记:[`python-concurrency/`](../python-concurrency/)(GIL、asyncio)、[`golang/concurrency`](../golang/concurrency/)(netpoller)。

---

## 与 `performance-tuning-roadmap` 的分工

这门课是**入门到够用**的应用开发者视角(理解 + 日常排查 + 面试)。当你想再深入**性能拐点 / 火焰图 / eBPF / SRE 闭环**时,各章末尾会用指针引向 [`performance-tuning-roadmap/`](../performance-tuning-roadmap/) 的深章,不在本课重复展开。

---

## 开始

先做 [**00-lab**](./00-lab/) 把沙箱搭起来,然后从 [**01**](./01-mental-model-and-shell/) 开始。每章的动手实验都在这个沙箱里跑。
