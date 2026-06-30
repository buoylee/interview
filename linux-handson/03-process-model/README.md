# 03 · 进程模型 ⭐核心

> 🧪 **环境**:VM shell(`multipass shell linux-lab`),部分实验需 `sudo`
> 这是「内核作为资源管理者」的第一个使用者——**进程**。本章是面试重灾区:进程状态、信号、僵尸、优雅关闭,几乎每场都问。

---

## 一、开篇盲点

- 你以为 `kill -9` 万能?进程卡在 **`D` 状态**时,`kill -9` 也杀不掉。
- 你以为进程退出就消失了?它可能变成**僵尸(Z)**,占着 PID 不走。
- 你以为 SSH 断开后台进程还在跑?默认情况下它会**被信号杀掉**。
- 你以为 Linux 里线程和进程是两种东西?在内核眼里**它们都是 `task`**,区别只在共享了什么。

这些都指向同一个盲区:**不了解进程的生命周期和信号机制**。本章讲透进程状态机、信号、僵尸/孤儿、会话与控制终端,上面四个问题学完都能秒答,而且能动手复现。

---

## 二、正文 · 原理

### 2.1 进程是什么:资源边界 + 执行流

回顾 `01`:`fork` 复制出进程,`execve` 给它换脑。一个进程(内核里叫 `task_struct`)本质是:

```
进程 = 身份(PID/PPID/UID) + 地址空间(它的内存) + 打开的 fd 表 + 至少一个执行流(线程)
```

面试先这样答:

> 进程是程序的一次运行实例,也是操作系统分配和隔离资源的基本单位。它拥有独立的虚拟地址空间、文件描述符表、权限身份等资源;进程里至少有一个线程,真正被 CPU 调度执行的是线程。进程解决的是资源隔离和管理,线程解决的是并发执行。

拆开看有三层:

- **程序 vs 进程**:程序是磁盘上的静态文件,比如 `/usr/bin/nginx`、一个 Java jar、一个 Go binary;进程是它跑起来之后的一次实例。同一个程序可以启动多个进程。
- **进程是资源容器**:内核用进程挂住一组资源,包括虚拟地址空间、fd 表、环境变量、当前工作目录、uid/gid、信号处理方式等。排查时你看 `/proc/<pid>/maps`、`/proc/<pid>/fd`、`/proc/<pid>/status`,本质就是在看这个容器里的资源状态。
- **进程是隔离边界**:进程 A 不能直接读写进程 B 的内存。它想读文件、发网络包、创建子进程、给别的进程发信号,都要通过 syscall 请内核代劳。

- **PID**:进程号;**PPID**:父进程号。每个进程都有父亲(除了 1 号)。
- **线程**:在 Linux 里线程就是「共享地址空间和 fd 表的 task」。进程和线程用同一个 `clone()` 创建,只是共享的东西不同。所以 `top` 里你看到的也可以是线程。

> 一句话压缩:进程偏「资源边界」,线程偏「执行流」。Linux 内核里两者底层都是 `task_struct`,区别主要看 `clone()` 时共享了哪些资源。

### 2.2 进程家谱:1 号进程是始祖

```console
PID 1 (systemd / init)       ← 内核启动的第一个用户态进程,所有进程的祖先
 ├─ sshd
 │   └─ bash (你的 shell)
 │       └─ ps               ← 你刚 fork 出来的
 └─ nginx
     ├─ nginx worker
     └─ nginx worker
```

`fork` 出的子进程挂在父进程下面。当父进程先死,子进程会被 **1 号进程收养**(见 2.4 孤儿)。

### 2.3 进程状态机(面试必背)

进程不是「要么跑要么停」,它在几个状态间转换。`ps` 的 `STAT` 列就是它:

```
            ┌──────────────────────────────────────────┐
            │                                          ▼
  创建 ──► R (Running/Runnable) ──等I/O或事件──► S (可中断睡眠)
  fork      在CPU跑 / 运行队列里等   ◄──事件到/信号──┘
            │  │                                     
            │  └──等内核I/O(磁盘/NFS)──► D (不可中断睡眠)
            │                              不响应任何信号,kill -9 也不行
            │                              I/O完成才回到 R
            │
            ├──收到SIGSTOP/Ctrl-Z──► T (停止)  ──SIGCONT──► R
            │
            └──exit()──► Z (僵尸)  ──父进程wait()回收──► 消失
```

| STAT | 状态 | 含义 | 关键点 |
|------|------|------|--------|
| `R` | Running/Runnable | 正在 CPU 上跑,或在运行队列排队 | load 高时一堆 R |
| `S` | 可中断睡眠 | 等事件(收包、定时器、锁),**能被信号唤醒** | 最常见,绝大多数空闲进程 |
| `D` | **不可中断睡眠** | 等内核 I/O 完成,**不响应信号** | `kill -9` 都没用,只能等 I/O 或重启 |
| `T` | 停止 | 被 `SIGSTOP`/`Ctrl-Z` 暂停 | `fg`/`SIGCONT` 恢复 |
| `Z` | **僵尸** | 已退出,等父进程回收 | 占 PID,不占 CPU/内存 |

`STAT` 还有后缀:`s`=会话首进程、`+`=前台进程组、`l`=多线程、`<`=高优先级、`N`=低优先级。例如 `Ssl` = 可中断睡眠 + 会话首 + 多线程。

### 2.4 僵尸与孤儿:别搞反了谁可怕

进程退出时不会立刻消失——它要把「退出码」留着,等父进程来收。这中间的状态就是僵尸。

- **僵尸(Zombie, Z)**:子进程已 `exit`,但父进程没调用 `wait()` 取走它的退出码。残留一个 PID 表项。
  - 不占 CPU、不占内存,**但占 PID**。大量堆积会耗尽 PID(`/proc/sys/kernel/pid_max`,默认约 4 万),导致 `fork` 失败、新进程起不来。
  - **根因永远在父进程**:是父进程没 `wait`。杀僵尸没用(它已经死了),要么让父进程去 `wait`,要么杀掉父进程——父死后僵尸被 1 号收养并立即回收。

- **孤儿(Orphan)**:父进程先死,子进程还活着。子进程被 **1 号进程(systemd)收养**,1 号会负责 `wait` 它。
  - **孤儿不可怕**——systemd 是尽职的养父,会回收它们。可怕的是僵尸(父亲还在却不尽责)。

> 一句话:**孤儿有人管(被 init 收养),僵尸没人收(父亲失职)。**

### 2.5 信号:内核给进程的「软件中断」

信号是内核或其他进程发给某进程的异步通知。常见的:

| 信号 | 编号 | 默认动作 | 能否被捕获/忽略 | 场景 |
|------|------|----------|------------------|------|
| `SIGHUP` | 1 | 终止 | 可 | 终端挂断(SSH 断开) |
| `SIGINT` | 2 | 终止 | 可 | `Ctrl-C` |
| `SIGKILL` | 9 | **强杀** | **不可** | 最后手段,内核直接干掉 |
| `SIGTERM` | 15 | 终止 | 可 | **优雅关闭的标准信号** |
| `SIGSTOP` | 19 | 停止 | **不可** | 暂停进程 |
| `SIGCONT` | 18 | 继续 | 可 | 恢复被停的进程 |
| `SIGCHLD` | 17 | 忽略 | 可 | 子进程状态变化时通知父进程 |
| `SIGSEGV` | 11 | 终止+core | 可 | 段错误 |

**`SIGTERM`(15)vs `SIGKILL`(9)——这是高频题:**
- `SIGTERM`:**礼貌请求退出**。进程能捕获它,做收尾(flush 缓冲、关连接、删 pid 文件、反注册服务发现),然后自己退出。`kill <pid>` 默认就是发 TERM。
- `SIGKILL`:**强制处决**。不能被捕获/忽略,内核直接回收进程,进程**没有任何清理机会**。
- 所以**不要一上来就 `kill -9`**:可能导致数据没落盘、锁没释放、pid 文件残留。正确顺序:先 `SIGTERM`,给几秒;不退再 `SIGKILL`。

**为什么 `D` 状态连 `kill -9` 都没用?** 信号要让进程「回到用户态去处理」,而 `D` 卡在内核态等 I/O,根本没机会处理信号。只能等 I/O 完成或重启机器。

### 2.6 会话 / 进程组 / 控制终端:回答「SSH 断了进程为啥死」

这套机制是「作业控制」的基础,也是 `nohup` 存在的原因:

```
SSH 登录 → 内核分配一个【控制终端】(/dev/pts/N)
         → 启动一个【会话(session)】,你的 bash 是会话首进程
            ├─ 前台进程组:Ctrl-C 发 SIGINT、Ctrl-Z 发 SIGTSTP 给它
            └─ 后台进程组(你 & 丢后台的)
```

**SSH 断开发生了什么:** 控制终端关闭 → 内核给这个会话发 **`SIGHUP`** → 默认动作是终止 → 你后台的进程一起被杀。

让进程不被杀的几种办法:
- **`nohup cmd &`**:让进程忽略 `SIGHUP`,且把输出重定向到 `nohup.out`(回顾 `01` 的标准写法)。
- **`disown`**:把已经在后台的作业从 shell 的作业表里摘掉,shell 退出时不再给它发 HUP。
- **`setsid cmd`**:让进程脱离当前会话,自成新会话首,彻底没有控制终端。
- **`tmux`/`screen`**:把会话整个托管在后台,断开重连还在(运维常用)。

> 这就是 `01` 那行 `nohup ./app > app.log 2>&1 &` 的完整解释:`nohup` 挡 SIGHUP,重定向收日志,`&` 丢后台。

---

## 三、怎么看(命令 + 真实输出怎么读)

### 看进程 + 状态 + 卡在哪:`ps`

```console
$ ps -eo pid,ppid,stat,wchan:20,comm
  PID  PPID STAT WCHAN                COMMAND
    1     0 Ss   ep_poll              systemd
  812     1 Ssl  do_epoll_wait        sshd
  945   812 Ss   do_wait              bash
 1031   945 R+   -                    ps
```
- `STAT` 看状态(`Ss`=睡眠+会话首,`R+`=运行+前台)。
- `WCHAN` 是**它睡在哪个内核函数上**——排查 `D` 状态卡顿的关键(`-` 表示没睡,正在跑)。

### 看进程树:`pstree`

```console
$ pstree -p 945
bash(945)───ps(1031)        # 父子关系一目了然
```

### 列信号 / 发信号:`kill`

```console
$ kill -l | head -2          # 列出所有信号
 1) SIGHUP   2) SIGINT   3) SIGQUIT  4) SIGILL   5) SIGTRAP
 6) SIGABRT  7) SIGBUS   8) SIGFPE   9) SIGKILL 10) SIGUSR1

$ kill -TERM 1234            # 等价 kill 1234,礼貌退出
$ kill -9 1234               # 强杀(最后手段)
$ pkill -TERM nginx          # 按名字发信号
```

### 揪僵尸:

```console
$ ps -eo pid,ppid,stat,comm | awk '$3 ~ /Z/'
  PID  PPID STAT COMMAND
 2100  2099 Z+   <defunct>      # <defunct> 就是僵尸,看 PPID 找它失职的爹
```

### 看单个进程细节:`/proc/<pid>/status`

```console
$ grep -E 'State|Threads|PPid' /proc/945/status
State:  S (sleeping)
PPid:   812
Threads:        1
```

---

## 四、动手实验(沙箱)

> 🧪 全部在 `multipass shell linux-lab` 里跑。

**实验 1:看进程树与状态**
```bash
pstree -p $$                 # 从当前 shell 往下看
ps -eo pid,ppid,stat,wchan:20,comm | head
```

**实验 2:亲手造一个僵尸,再看它被回收**
```bash
# 父进程 fork 子进程后,故意 sleep 不去 wait → 子进程退出后变僵尸
bash -c 'sleep 0 & sleep 30' &
PARENT=$!
sleep 1
echo "== 此时子进程应是僵尸 Z =="
ps -eo pid,ppid,stat,comm | awk '$3 ~ /Z/'
echo "== 杀掉父进程,僵尸被 1 号收养并回收 =="
kill "$PARENT"; sleep 1
ps -eo pid,ppid,stat,comm | awk '$3 ~ /Z/'   # 没了
```

**实验 3:`SIGTERM` 可捕获、`SIGKILL` 不可(优雅关闭原理)**
```bash
# 写一个捕获 SIGTERM 的脚本
cat > /tmp/graceful.sh <<'EOF'
#!/bin/bash
trap 'echo "收到 SIGTERM,正在收尾..."; sleep 1; echo "干净退出"; exit 0' TERM
echo "运行中,PID=$$"
while true; do sleep 1; done
EOF
chmod +x /tmp/graceful.sh
/tmp/graceful.sh & PID=$!
sleep 1
kill -TERM $PID              # 看到"收到 SIGTERM...干净退出" —— 被捕获了
sleep 2
/tmp/graceful.sh & PID=$!
sleep 1
kill -9 $PID                 # 直接没,没有任何收尾输出 —— 不可捕获
```

**实验 4:观察 `D` 状态(不可中断睡眠)**
```bash
# 制造重 I/O,另开循环抓 D 状态(D 是瞬态,多抓几次)
stress-ng --hdd 2 --timeout 15s &
for i in $(seq 1 15); do
  ps -eo pid,stat,wchan:20,comm | awk '$2 ~ /D/' && echo "--- 第${i}次抓到D ---"
  sleep 1
done
```
> `D` 难长期复现(I/O 一完成就回 `R`),重点是**认识它 + 会用 `wchan` 看卡在哪个内核函数**。生产里一台机器大量 `D`,基本就是磁盘/网络存储出问题了。

**实验 5:`nohup` 对照(SIGHUP 杀不杀得动)**
```bash
sleep 1000 &  P1=$!
nohup sleep 1000 >/dev/null 2>&1 &  P2=$!
kill -HUP $P1                # 普通后台进程:被 HUP 杀掉
kill -HUP $P2                # nohup 的:忽略 HUP,活着
sleep 1
ps -o pid,stat,comm -p $P1 $P2 2>/dev/null   # 只剩 nohup 那个
kill $P2 2>/dev/null
```

---

## 五、生产踩坑框 ⚠️

> **K8s 优雅关闭的真相**:K8s 删 Pod 时先发 `SIGTERM`,等 `terminationGracePeriodSeconds`(默认 30s),还没退再 `SIGKILL`。所以你的 app **必须捕获 SIGTERM** 做收尾(停止接新请求、处理完存量、反注册),否则要么被强杀丢请求,要么白等 30s。

> **容器里的僵尸**:容器 PID 1 是你的 app 而不是 init。如果你的 app 会 fork 子进程(如调用脚本)却不回收,僵尸会堆积。解法:用 `tini`/`dumb-init` 当 PID 1,或 `docker run --init`。(连到 `09` 容器章)

> **服务「假死」线程 dump 看不出问题**:可能进程卡在 `D` 状态等 I/O(磁盘满/NFS 挂了/慢盘)。`ps` 看 `STAT=D` + `wchan`,问题在存储不在你的代码。

---

## 六、本章面试速记

- **什么是进程?** 程序的一次运行实例,也是 OS 分配/隔离资源的基本单位;进程拥有地址空间、fd 表、权限身份等资源,至少包含一个线程。进程偏资源边界,线程偏执行流。
- **进程状态 `D` 和 `Z` 的区别与危害?** `D`=等内核 I/O 的不可中断睡眠,连 `kill -9` 都杀不掉,大量出现说明存储有问题;`Z`=已退出待父回收的僵尸,占 PID 不占内存/CPU,堆积会耗尽 PID。
- **`kill -9` 和 `kill -15` 区别?为什么不要一上来 -9?** 15(TERM)可被捕获做优雅收尾;9(KILL)不可捕获,内核直接干掉,进程没机会清理 → 可能丢数据/留残锁。先 TERM 后 KILL。
- **僵尸怎么产生、怎么清?** 子进程退出而父没 `wait`。清理:让父去 wait 或杀掉父(僵尸转由 1 号收养回收);杀僵尸本身没用。
- **SSH 断了后台进程为什么死、怎么避免?** 终端关闭→会话收到 `SIGHUP`→默认终止。用 `nohup`/`disown`/`setsid`/`tmux` 避免。
- **Linux 线程和进程的区别?** 都是 `task`,用 `clone()` 创建;线程共享地址空间和 fd 表,进程不共享。

---

## 七、小结 + 桥接 + 延伸

**一句话记忆点**:
> 进程有生命周期(R/S/D/Z/T)和一个父亲;信号是控制它的遥控器,`TERM` 是礼貌、`KILL`/`STOP` 内核硬来;僵尸是父亲失职、孤儿被 init 收养;SSH 断进程死是因为会话收到了 `SIGHUP`。

**四语言桥接**:

| 概念 | Java | Go | Python | Node/JS |
|------|------|-----|--------|---------|
| 线程模型 | 线程 ≈ 1:1 OS 线程(`clone`) | goroutine **M:N** 复用 OS 线程 | GIL 下多线程不真并行,CPU 密集走多进程 | 单线程事件循环 + `worker_threads` |
| 捕获 SIGTERM 优雅关闭 | `Runtime.addShutdownHook` / Spring `@PreDestroy` | `signal.Notify(c, SIGTERM)` + `context` 取消 | `signal.signal(SIGTERM, handler)` | `process.on('SIGTERM', ...)` |
| 回收子进程 | `Process.waitFor()` | `cmd.Wait()` | `Popen.wait()` / `os.waitpid` | `child.on('exit')` |

→ 线程模型对比深入,见你已有的笔记:[`python-concurrency/01-foundations-gil`](../../python-concurrency/01-foundations-gil/)、[`golang/concurrency`](../../golang/concurrency/)。本章的「OS 线程 = 调度单位」正是它们的底座。

**延伸指针**:
- CPU 调度器(CFS、时间片、优先级、上下文切换)→ `performance-tuning-roadmap/00-os-fundamentals/01-cpu-architecture-scheduling.md`
- 进程/线程/协程三者对比 → `performance-tuning-roadmap/00-os-fundamentals/05-process-thread-coroutine.md`

➡️ 下一章:[`04 · 内存模型`](../04-memory-model/)(进程要的第二种资源:内存)
