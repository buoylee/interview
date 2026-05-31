# 99 · Linux 面试卡

> 两层:**① 速答表**(一行一题、快速自测)+ **② 深题卡**(场景化、含「追问预案」)。卡片随各章增长。

---

## ① 速答表

> 用法:盖住右栏自测,卡壳的去对应章节复习。

### 世界观 / shell(`01`)

| 问题 | 一句话答 |
|------|----------|
| 用户态进程怎么碰硬件? | 不能直接碰,只能发**系统调用(syscall)**请内核代劳 |
| 「一切皆文件」指什么? | 文件/目录/设备/管道/socket/`/proc` 都用 `open/read/write/close` 操作,内核用 **fd** 做句柄 |
| fd 0/1/2 分别是? | stdin / stdout / stderr,默认都指向终端 |
| 命令怎么被执行? | shell `fork()` 出子进程 → `execve()` 换脑成目标程序 → 父 `wait()` 回收 |
| `cd` 为什么是内建命令? | 要改 shell **自身**的工作目录,外部程序在子进程里改完就退出、对父无效 |
| `>` 重定向的内核动作? | `open` 文件拿到 fd → `dup2(fd, 1)` 把 fd1 改指向它 |
| `a \| b` 两端几个进程? | 两个,内核 `pipe()` 把 a 的 fd1 接到 b 的 fd0 |
| `2>&1` 为什么要放 `>file` 后面? | 它复制 fd1 **当下**的指向;先让 fd1 指文件,fd2 再跟上才都进文件 |

### 进程模型(`03`)

| 问题 | 一句话答 |
|------|----------|
| `D` 状态是什么、为什么 `kill -9` 没用? | 等内核 I/O 的不可中断睡眠;信号要回用户态处理,`D` 卡在内核态没机会处理 |
| `Z`(僵尸)是什么、怎么清? | 子进程退出但父没 `wait`;让父去 wait 或杀父(转 1 号回收),杀僵尸本身没用 |
| 孤儿进程可怕吗? | 不可怕,被 1 号(systemd)收养并回收;僵尸才麻烦 |
| `kill -15` vs `kill -9`? | 15(TERM)可捕获、做优雅收尾;9(KILL)不可捕获、内核硬杀、无清理机会 |
| SSH 断了后台进程为何死? | 终端关闭→会话收到 `SIGHUP`→默认终止;用 `nohup`/`disown`/`setsid`/`tmux` 避免 |
| Linux 线程和进程区别? | 都是 `task`(`clone` 创建);线程共享地址空间+fd 表,进程不共享 |
| 怎么看进程卡在哪? | `ps -eo pid,stat,wchan,comm`,`wchan` 是它睡的内核函数 |

### 内存模型(`04`)

| 问题 | 一句话答 |
|------|----------|
| VSZ / RSS / PSS 区别? | VSZ=映射的虚拟空间(虚);RSS=实占物理页(含共享库重复计);PSS=共享按比例分摊 |
| `free` 看哪列判断内存够不够? | 看 `available`(=free + 可回收 cache),不是 `free` |
| page cache 占满内存是问题吗? | 不是,空闲内存当缓存、应用要时可立即回收 |
| OOM killer 怎么选进程? | 按 `oom_score`(占用 + `oom_score_adj`)挑一个杀;被杀 exit 137 |
| 容器 OOMKilled 但宿主机内存充足? | cgroup 限制小于实际用量;传统工具/老运行时读宿主机内存没感知 cgroup |
| VSZ 2G、RSS 200M 正常吗? | 正常,按需分页:申请虚拟地址≠占物理内存,写到才缺页分配 |
| swap 频繁意味着什么? | thrashing,性能雪崩;`vmstat` 看 `si`/`so` 持续>0 |

### I/O 与文件(`05`)

| 问题 | 一句话答 |
|------|----------|
| fd 耗尽什么表现、怎么查? | `Too many open files`、建不了新连接;`ulimit -n` + `ls /proc/<pid>/fd \| wc -l` + `lsof` |
| socket 算 fd 吗? | 算,连接数和打开文件数共用 `RLIMIT_NOFILE` 配额 |
| `write` 返回了就落盘了吗? | 没,默认只到 page cache 脏页;`fsync`/`fdatasync` 才落盘 |
| `rm` 大文件空间没释放? | 进程还持有它的 fd,链接数 0 但未释放;`lsof +L1` 找,`truncate`/`: >` 清空 |
| `%util` 100% 一定瓶颈吗? | 单队列 HDD 接近饱和;SSD/NVMe 不一定,看 `await`/`aqu-sz` |
| 有空间却报 No space left? | inode 耗尽,`df -i` 看(海量小文件) |
| 缓冲 IO vs 直接 IO? | 缓冲走 page cache 快不保证落盘;`O_DIRECT` 绕过 cache(DB 自管缓存) |

### 网络模型(`06`)

| 问题 | 一句话答 |
|------|----------|
| 一条 TCP 连接由什么唯一确定? | 四元组(本地IP:端口, 对端IP:端口);内核用一个 socket fd 表示 |
| 大量 TIME_WAIT 要紧吗? | 出现在主动关闭方,通常无害(60s 自消),除非客户端端口耗尽 |
| 大量 CLOSE_WAIT 说明什么? | 被动关闭方应用没 `close()`,代码 bug;不会自消 |
| TIME_WAIT vs CLOSE_WAIT? | 前者主动方/协议正常/会自消;后者被动方/没close/不自消 |
| refused vs timeout? | refused=端口没监听回RST;timeout=包没回应(防火墙DROP/不可达) |
| 全连接队列满怎么看? | `ss -lnt` 的 Recv-Q 接近 Send-Q;调 `somaxconn`+backlog |
| 连不上服务怎么排查? | DNS(dig)→主机(ping)→端口(nc/curl)→监听(ss -lnt)→抓包(tcpdump) |
| 临时端口范围在哪看? | `net.ipv4.ip_local_port_range`(默认约 32768–60999) |

*(02、07–10 章的速答条目随章补充)*

---

## ② 深题卡

> 卡片结构:**30 秒口头答(先结论)→ 展开 → 追问预案 → 踩坑/数据点**。
> 追问预案 = 模拟面试官接着会问什么,提前备好——这是拉开资深差距的地方。

---

### 卡 01-A:`cmd > out 2>&1` 和 `cmd 2>&1 > out` 有什么区别?

**30 秒口头答**
> 第一个会把标准输出和标准错误都写进文件;第二个只把标准输出写进文件,标准错误仍打到屏幕。因为重定向是从左到右处理的,而 `2>&1` 的含义是「让 fd2 指向 fd1 **此刻**所指的地方」,是复制当下指向,不是绑定后续变化。

**展开**
- `cmd > out 2>&1`:① `>out` 让 fd1→文件;② `2>&1` 让 fd2→fd1 此刻指的(文件)。两者都进文件。
- `cmd 2>&1 > out`:① `2>&1` 让 fd2→fd1 此刻指的(**屏幕**);② `>out` 让 fd1→文件,但 fd2 已经定格在屏幕。错误没进文件。

**追问预案**
- *Q:底层是哪个系统调用?* → `dup2(1, 2)`(把 fd2 复制成 fd1 的指向);`>out` 是 `open`+`dup2(fd,1)`。可以现场 `strace -e dup2,openat` 验证。
- *Q:那 `&>out` 是什么?* → bash 的简写,等价 `>out 2>&1`,一次把两条都收进文件。
- *Q:只想丢弃错误怎么写?* → `cmd 2>/dev/null`。

**踩坑/数据点**
> 生产里「报错日志神秘丢失」十有八九是 `app 2>&1 > app.log`(顺序错)或漏了 `2>&1`。后台服务标准写法:`nohup ./app > app.log 2>&1 &`。

---

### 卡 01-B:你敲一条 `ls -l` 回车,到进程结束,系统发生了什么?

**30 秒口头答**
> shell 解析命令行,判断 `ls` 不是内建命令,在 `PATH` 里找到 `/usr/bin/ls`;然后 `fork()` 出一个子进程(复制了 shell,包括 fd 0/1/2),子进程 `execve("/usr/bin/ls")` 把自己换成 ls 程序;父 shell `wait()` 阻塞等子进程结束并回收它,然后打印新提示符。

**展开**
- `fork` 复制出的子进程,继承父 shell 的三个标准 fd,所以 `ls` 的输出默认就打到你的终端。
- 如果命令行里有 `> out`,shell 会在 `fork` 之后、`execve` 之前改写子进程的 fd1。
- `execve` 成功后,原来的 shell 代码被 ls 代码整个替换,但 PID 和已打开的 fd 不变。

**追问预案**
- *Q:fork 出来要复制整个内存吗,不是很慢?* → 现代内核用 **写时复制(COW)**,父子共享物理页,谁写谁才真正复制那一页。(详见 `04` 内存章)
- *Q:子进程没被 wait 会怎样?* → 变成**僵尸进程(Z)**,占着 PID 表项直到父进程回收。(详见 `03`)
- *Q:为什么 `cd` 不走这个流程?* → `cd` 是内建命令,要改 shell 自身状态,不能 fork 出去。

**踩坑/数据点**
> 一台机器上僵尸进程堆积,通常是父进程没正确 `wait()` 子进程(典型:自己 fork 子进程却没处理 `SIGCHLD`)。

---

### 卡 03-A:进程状态 `D` 和 `Z` 有什么区别?各自的危害?

**30 秒口头答**
> `D` 是不可中断睡眠,进程在等内核 I/O 完成(磁盘、NFS),此时连 `kill -9` 都杀不掉,只能等 I/O 或重启;大量 `D` 说明存储出了问题。`Z` 是僵尸,进程已经退出但父进程没 `wait` 回收它,占着 PID 但不占 CPU/内存;大量堆积会耗尽 PID 导致 `fork` 失败。

**展开**
- `D`:卡在内核态,信号无法投递(信号要回用户态处理)。用 `ps -eo pid,stat,wchan` 看 `wchan` 知道卡在哪个内核函数。
- `Z`:根因永远在父进程没尽责 `wait`。杀僵尸无效(它已死),要让父去 wait 或杀掉父进程。

**追问预案**
- *Q:怎么定位是哪块盘导致大量 D?* → `iostat -x 1` 看 `%util`/`await`(详见 `05`),结合 `wchan`。
- *Q:容器里僵尸特别多为什么?* → PID 1 是你的 app 而非 init,app 不回收子进程就堆积;用 `--init`/`tini`。
- *Q:PID 耗尽了会怎样?* → 新 `fork`/`pthread_create` 报 `EAGAIN`,起不了新进程/线程;看 `/proc/sys/kernel/pid_max`。

**踩坑/数据点**
> 服务「假死」、线程 dump 看不出问题,先 `ps` 看有没有 `D`——很可能是慢盘/NFS,问题不在你的代码。

---

### 卡 03-B:`kill -9` 和 `kill -15` 区别?为什么不建议一上来就 `-9`?

**30 秒口头答**
> `-15`(SIGTERM)是礼貌请求退出,进程可以捕获它做收尾——flush 缓冲、关连接、删 pid 文件、从注册中心反注册——然后干净退出;`-9`(SIGKILL)不可被捕获或忽略,内核直接回收进程,进程没有任何清理机会。所以正确做法是先 `-15` 给几秒,不退再 `-9`。

**展开**
- `SIGKILL`/`SIGSTOP` 是仅有的两个不可捕获/忽略的信号,由内核直接处理。
- 一上来 `-9` 的风险:数据没落盘、文件锁/共享内存没释放、pid 文件残留导致下次起不来、连接没优雅关闭导致对端报错。

**追问预案**
- *Q:K8s 是怎么关 Pod 的?* → 先 `SIGTERM`,等 `terminationGracePeriodSeconds`(默认 30s),超时再 `SIGKILL`。所以 app 要捕获 SIGTERM。
- *Q:发了 `-15` 进程不退怎么办?* → 它可能没注册 handler、或卡在 `D`(`-9` 也没用)、或 handler 里死循环;先确认状态再决定。
- *Q:各语言怎么捕获 SIGTERM?* → Java `addShutdownHook`、Go `signal.Notify`+context、Python `signal.signal`、Node `process.on('SIGTERM')`。

**踩坑/数据点**
> 优雅关闭没做好的典型现象:滚动发布时偶发 502/连接 reset——就是老实例被 SIGTERM 后没停止接新请求、或没处理完存量就被 SIGKILL。

---

### 卡 03-C:SSH 一断,我后台跑的进程就没了,为什么?怎么让它活着?

**30 秒口头答**
> SSH 断开会关闭控制终端,内核给这个会话发 `SIGHUP`,而 `SIGHUP` 的默认动作是终止,所以你后台的进程被一起杀掉。让它活下来:`nohup cmd &`(忽略 HUP + 重定向输出)、`disown`(从作业表摘除)、`setsid`(脱离会话)、或用 `tmux`/`screen` 托管会话。

**追问预案**
- *Q:`nohup` 和 `&` 各自管什么?* → `&` 只是丢后台,不防 HUP;`nohup` 才是忽略 SIGHUP。两者要一起用。
- *Q:`disown` 和 `nohup` 区别?* → `nohup` 启动时就忽略 HUP;`disown` 用于「已经在后台、忘了加 nohup」的补救,把作业从 shell 摘掉。
- *Q:生产上长任务怎么跑?* → 别靠终端,交给 systemd service(见 `08`)或调度系统,这才是正经做法。

**踩坑/数据点**
> 临时跑长任务忘了 `nohup`,又不想断——先 `Ctrl-Z` 暂停,`bg` 转后台,再 `disown -h %1`,然后安全断开。

---

### 卡 04-A:容器被 `OOMKilled`(exit 137),但宿主机内存还很充足,为什么?

**30 秒口头答**
> 容器的内存上限由 cgroup 控制,和宿主机总内存是两回事。被杀是因为进程用量超过了 cgroup 的限制,触发 cgroup 级 OOM——这时宿主机可能还剩很多内存。最常见的诱因是运行时没感知 cgroup:老版本 JVM/Node 读宿主机的总内存来决定堆大小,在容器里就会把堆设得远超 cgroup 限制,必然 OOM。

**展开**
- exit 137 = 128 + 9(SIGKILL),是被 OOM killer 强杀的标志。
- 容器里 `free`/`/proc/meminfo` 读的是宿主机,会误导;要看 `/sys/fs/cgroup/memory.max` 和 `memory.current`。
- RSS = 逻辑内存(堆)+ 一堆额外开销,所以「设了 `-Xmx512m` 还 OOM」很常见。

**追问预案**
- *Q:JVM 怎么修?* → `-XX:MaxRAMPercentage=75`(JDK 10+ 默认已感知 cgroup),别再用读宿主机的老参数。Node 用 `--max-old-space-size`,Go 用 `GOMEMLIMIT`。
- *Q:`-Xmx512m` 了为什么还超?* → 堆只是一部分,RSS 还含 Metaspace、线程栈(线程多很可观)、堆外 DirectBuffer、JIT 缓存。
- *Q:怎么确认是 cgroup OOM 还是宿主机 OOM?* → `dmesg` 看 OOM 记录里有没有 `memory cgroup out of memory`;看容器 `memory.events` 的 `oom_kill` 计数。

**踩坑/数据点**
> 排查顺序:`kubectl describe pod` 看 `Reason: OOMKilled` + exit 137 → 看运行时堆参数是否感知 cgroup → 看是否堆外内存(RSS 涨但堆没涨)。

---

### 卡 04-B:`free` 显示可用内存只剩几百 M 了,要紧吗?怎么判断内存是否真的紧张?

**30 秒口头答**
> 大概率不要紧。Linux 会主动把空闲内存拿去做 page cache,所以 `free` 那一列(完全没用的)很小是常态。判断内存够不够要看 `available` 那一列——它等于 free 加上可回收的 cache,才是真正还能给应用用的量。再配合 `vmstat` 看 `si`/`so` 有没有在 swap。

**追问预案**
- *Q:cache 和应用抢内存时谁让步?* → cache 可回收,应用要内存时内核会回收干净页(脏页先刷盘),所以 cache 不算「占用」。
- *Q:那什么时候才算真紧张?* → `available` 持续很低 + `si`/`so` 持续非 0(在 swap)+ 出现 OOM 记录。
- *Q:buff 和 cache 区别?* → buffers 偏块设备元数据缓冲,cached 偏文件页缓存;现在合并显示为 buff/cache,日常不必细分。

**踩坑/数据点**
> 监控告警别用「free 内存低于阈值」,会一直误报;要用 `MemAvailable`(`/proc/meminfo`)做指标。

---

### 卡 05-A:服务报 `Too many open files`,怎么排查和解决?

**30 秒口头答**
> 这是进程打开的 fd 数到达了 `RLIMIT_NOFILE` 上限。注意 socket 也是 fd,所以连接数和文件数共用这个配额。排查三步:先 `ulimit -n` 和 `/proc/<pid>/limits` 看限制,再 `ls /proc/<pid>/fd | wc -l` 看实际开了多少、`lsof -p <pid>` 看开的是什么——十有八九是没关闭的 socket(连接池泄漏)。治标是调大限制,治本是修代码漏 close。

**展开**
- 限制分软/硬:`ulimit -Sn` / `-Hn`;systemd 服务用 `LimitNOFILE=` 设(见 `08`),容器在 compose/k8s 里设。
- fd 数只增不减 = 泄漏;典型是 HTTP/DB 连接没复用或没归还连接池。

**追问预案**
- *Q:调大 ulimit 就行了吗?* → 只是争取时间,泄漏不修迟早再爆;而且盲目调大掩盖问题。
- *Q:全局还有限制吗?* → 有,`fs.file-max`(系统级)、`fs.nr_open`(单进程硬上限天花板)。
- *Q:怎么快速定位是哪种 fd 泄漏?* → `lsof -p <pid>` 按类型统计,大量 `TCP`/`CLOSE_WAIT` 指向连接没关(接 `06`)。

**踩坑/数据点**
> 大量 `CLOSE_WAIT` + fd 飙升,几乎可以断定是「对端关了连接但本端代码没 close」,既泄漏 fd 又泄漏连接。

---

### 卡 05-B:磁盘报满,`rm` 删了大日志,`df` 显示空间却没释放,为什么?

**30 秒口头答**
> 因为 `rm` 只是 `unlink`——删目录项、把 inode 的硬链接计数减一。只有当链接数为 0 **且没有任何进程还打开着它**时,数据块才真正释放。日志文件通常还被进程(nginx、你的 app)开着 fd,所以删了空间不降。用 `lsof +L1` 能看到这些「已删除但被持有」的文件。

**展开**
- 正确做法:别 `rm`,用 `truncate -s 0 file` 或 `: > file` 原地清空(inode 还在,进程继续写没问题)。
- 或重启/重载持有进程让它放掉 fd;日志滚动交给 logrotate 的 `copytruncate`(见 `08`)。

**追问预案**
- *Q:`df` 和 `du` 对不上是不是这个原因?* → 是常见原因之一:`du` 按目录项算(已删的不算),`df` 按块算(被持有的仍占),两者差额就是被持有的已删文件。
- *Q:为什么不直接重启进程?* → 生产服务重启有代价;能 `truncate` 就别重启。
- *Q:`: > file` 和 `truncate` 区别?* → 效果类似(清空),`: > file` 是 shell 重定向清空,`truncate -s 0` 更直观且能设任意大小。

**踩坑/数据点**
> 磁盘告警时先 `df -i` 排除 inode 满,再 `lsof +L1` 找被持有的已删大文件——这两步能解决一大半「莫名其妙磁盘满」。

---

### 卡 06-A:机器上一堆 `TIME_WAIT`,有问题吗?要怎么处理?

**30 秒口头答**
> 大概率没问题。TIME_WAIT 出现在主动关闭连接的一方,是协议保证「最后的 ACK 送达 + 旧包消散」的正常机制,持续约 60 秒后自动消失。只有一种情况要管:客户端用固定源 IP 对固定目标发起海量短连接,本地临时端口被 TIME_WAIT 占满导致端口耗尽。处理上,根治是用长连接/连接池减少建连;客户端侧端口紧张可以开 `tcp_tw_reuse`,但绝不要用 `tcp_tw_recycle`(NAT 下会丢连接,新内核已移除)。

**追问预案**
- *Q:为什么要等 2×MSL?* → 一是确保对端没收到最后 ACK 时能重发 FIN 被响应,二是让旧连接迷途包消散,避免污染相同四元组的新连接。
- *Q:TIME_WAIT 在服务端还是客户端?* → 在主动关闭方。HTTP/1.0 或服务端主动断时在服务端;短连接客户端主动断时在客户端。
- *Q:`tcp_tw_reuse` 为什么安全而 `recycle` 不安全?* → reuse 仅用于本端**发起**新连接时复用,有时间戳保护;recycle 对所有连接按源 IP 记时间戳,NAT 后多客户端共享 IP 会被误丢。

**踩坑/数据点**
> 监控里 TIME_WAIT 几万个常被误报为故障;真正该盯的是「客户端是否报 `Cannot assign requested address`」(端口耗尽)。

---

### 卡 06-B:一堆 `CLOSE_WAIT` 怎么回事?和 TIME_WAIT 有什么区别?

**30 秒口头答**
> CLOSE_WAIT 出现在被动关闭方:对端已经发来 FIN、本端内核也 ACK 了,但**本端应用迟迟没有调用 `close()`**,连接就卡在 CLOSE_WAIT,不会自己消失。所以大量 CLOSE_WAIT 基本可以断定是代码 bug——漏关连接、连接池没回收。它和 TIME_WAIT 正好相反:TIME_WAIT 在主动方、是协议正常机制会自消;CLOSE_WAIT 在被动方、是应用没尽责不会自消。

**展开**
- 危害:每个 CLOSE_WAIT 占一个 fd 和一条连接,堆积会同时引发 `Too many open files`(接 `05`)。
- 定位:`sudo ss -tanp state close-wait` 直接看到是哪个进程、哪个 fd。

**追问预案**
- *Q:常见代码原因?* → HTTP client 没消费/关闭 response body、DB 连接没归还池、Go 漏 `defer resp.Body.Close()`、Java 没关 `Connection`/`Stream`。
- *Q:为什么 CLOSE_WAIT 不会自动超时?* → 它在等应用 `close()`,内核无法替应用决定何时关;只能靠改代码或重启进程。
- *Q:和 fd 耗尽的关系?* → CLOSE_WAIT 是 fd 泄漏的一种典型来源,两个现象常同时出现。

**踩坑/数据点**
> 口诀:**TIME_WAIT 是协议在等,CLOSE_WAIT 是你在欠。** 看到一堆 CLOSE_WAIT,先翻代码找漏 `close` 的地方,而不是调内核参数。

---

*(07 起每章续补:机器 load 高怎么系统排查、容器视角 …)*
