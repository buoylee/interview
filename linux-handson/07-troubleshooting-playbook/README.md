# 07 · 排查方法论与工具箱 ⭐⭐核心高潮

> 🧪 **环境**:VM shell(`multipass shell linux-lab`),部分命令需 `sudo`
> 前面 03–06 是四种资源的「知识」;这一章把它们拧成一套**可复用的排查路径**。资深和初级的差距,往往不在记得多少命令,而在**有没有方法论**——面对一台「变慢/变卡」的机器,知道先看什么、再看什么、怎么证伪。

---

## 一、开篇盲点

- 出问题时你是不是习惯「凭感觉猜 + 重启大法」?没有系统方法,运气好蒙对,运气差越查越乱、还把现场弄没了。
- 「`load` 高」到底是 CPU 忙、还是在等 I/O、还是进程太多?——多数人以为 load 高就是 CPU 高,**错**。
- 同事三分钟定位的问题你查半天,差距不在工具数量,而在**有没有一条自顶向下的排查主线**。

这一章给你那条主线,以及把它落地的工具地图和经典案例。

---

## 二、正文 · 方法论

### 2.1 一条闭环主线

任何性能/故障排查都走这条线(别跳步):

```
现象 → 指标 → 假设 → 工具 → 定位 → 修复 → 验证 → 复盘
```

- **现象**:用户说慢?监控告警?——先量化(慢多少、什么时候开始)。
- **假设 → 工具 → 定位**:形成可证伪的假设,用工具验证,**一次只动一个变量**。
- **复盘**:留证据、写记录,把这次变成下次的基线。

### 2.2 USE 方法:对每种资源系统体检

对 CPU / 内存 / 磁盘 / 网络,逐一检查三项(Brendan Gregg 的 USE):

- **U**tilization 使用率:忙到什么程度(如 CPU 80%)。
- **S**aturation 饱和度:有没有排队等不及(如运行队列、I/O 队列、swap)。
- **E**rrors 错误:有没有报错(丢包、重传、OOM、I/O error)。

> 方法论细节(USE / RED / 性能定律)见 `performance-tuning-roadmap/01-methodology/`。本章重在落地到 Linux 命令。

### 2.3 自顶向下的分层排查路径(背下来)

```
① 先看全局负载:  uptime / top         → load 高不高?方向在哪?
        │
        ├─ CPU 饱和?   top 看 %us/%sy 高、id 低     → 03 进程 + CPU 工具
        ├─ 在等 I/O?   top 看 %wa 高、有 D 状态进程  → 05 I/O
        ├─ 内存不够?   free 看 available 低、si/so>0 → 04 内存
        ├─ 网络?       ss -s、重传/队列              → 06 网络
        └─ 进程异常?   大量 D/Z、线程数暴涨          → 03 进程
```

先定方向(哪类资源),再深入那一类的工具,**别一上来就抓包/拉火焰图**。

### 2.4 读懂 `load average`(纠正最常见的误解)

```console
$ uptime
 15:04:01 up 3 days,  load average: 8.21, 5.10, 2.30
#                                   1分钟  5分钟  15分钟
```

**关键**:Linux 的 load 是「**处于 R(运行/可运行)+ D(不可中断睡眠,通常等 I/O)状态的任务数**」的平均值——**不只是 CPU**。所以:

- load 高 + `%us` 高 → **CPU 真的忙**(计算密集 / 死循环 / 频繁 GC)。
- load 高 + `%us` 低 + `%wa` 高 + 一堆 `D` 进程 → **在等 I/O**(慢盘 / NFS),CPU 其实闲着。

> 判断 load 高不高,粗略基准是和 **CPU 核数**比:`load ≈ 核数` 算满载,`load ≫ 核数` 是过载。但**先分清是 CPU 型还是 I/O 型过载**——这是本章案例 1 vs 案例 2 的分水岭。

### 2.5 「第一分钟」体检清单

登上一台有问题的机器,先跑这一串(各看一眼,快速定方向):

| 命令 | 看什么 |
|------|--------|
| `uptime` | load 三个值,是不是在涨 |
| `dmesg -T \| tail` | 最近的内核报错:OOM、I/O error、网卡 |
| `vmstat 1 5` | `r`(运行队列)`b`(阻塞)、`si/so`(swap)、`wa`(等IO)、`us/sy` |
| `mpstat -P ALL 1` | 是不是单核打满(其它核闲 → 单线程瓶颈) |
| `pidstat -u 1` | 哪个进程在吃 CPU |
| `iostat -xz 1` | 磁盘 `await`/`%util`/`aqu-sz` |
| `free -m` | `available` 够不够、swap 用没用 |
| `ss -s` | 连接数、TIME-WAIT/CLOSE-WAIT 总量 |
| `top` | 综合,按 CPU/内存排序、看 `D`/`Z` 状态 |

### 2.6 `strace`:看进程在哪个系统调用卡住/出错(接 01)

回顾 `01`:进程干的实事都是 syscall。进程「卡住」「慢」「报权限错」,`strace` 直接告诉你它停在/失败在哪个 syscall:

```bash
sudo strace -p <pid>              # 挂上一个活进程,看它正在做什么 syscall
sudo strace -f -p <pid>           # -f 跟踪所有线程/子进程
sudo strace -p <pid> -e trace=network   # 只看网络相关 syscall
sudo strace -c -p <pid>           # 统计:每种 syscall 的次数和耗时(找热点)
sudo strace -T -p <pid>           # 每个 syscall 实际耗时(揪慢调用)
```

典型用法:进程假死 → `strace -p` 看到它停在 `read(8, ...)` 一直不返回 → 8 号 fd 是什么?用 `lsof` 一查是某个网络连接 → 对端不回包。链路就清晰了。

> ⚠️ `strace` 会显著拖慢目标进程(每个 syscall 都被拦截),生产上对关键进程慎用、短时用。

### 2.7 `lsof`:看进程打开的一切(接 05/06)

```bash
sudo lsof -p <pid>                # 该进程打开的所有文件 + socket
sudo lsof -i :8080                # 谁在用 8080 端口
sudo lsof -i TCP:ESTABLISHED      # 所有已建立的 TCP 连接
sudo lsof +L1                     # 已删除但仍被持有的文件(接 05,磁盘不释放)
```

`strace`(看动作)+ `lsof`(看 fd 指向)是排查「进程卡在某个 fd」的黄金搭档。

---

## 三、工具地图(按资源)

把前面各章的工具按「全局 / 每进程 / 深入」归一张表,排查时照着这张表走:

| 资源 | 全局看 | 每进程看 | 深入 | 章节 |
|------|--------|----------|------|------|
| **CPU** | `uptime` `top` `mpstat -P ALL` `vmstat` | `pidstat -u` `top -H`(线程) | `perf` `strace -c` | 03 |
| **内存** | `free -m` `vmstat`(si/so) | `pidstat -r` `ps --sort=-rss` | `/proc/<pid>/smaps` | 04 |
| **磁盘 I/O** | `iostat -xz` `vmstat`(b,wa) | `pidstat -d` `iotop` | `lsof` `strace` | 05 |
| **网络** | `ss -s` `sar -n DEV` | `ss -tanp` | `tcpdump` | 06 |
| **进程** | `uptime`(load) `top` | `ps -eo …,stat,wchan` `pstree` | `strace` `lsof` | 03 |

---

## 四、动手实验 · 案例集(制造现象 → 用方法论定位)

> 🧪 在 `multipass shell linux-lab` 里跑。这一章的「动手」就是**复现经典故障并按分层路径排查**。

**案例 1:CPU 100%(CPU 型过载)**
```bash
stress-ng --cpu 2 --timeout 40s &
uptime                       # ① load 上升
top -bn1 | head -8           # ② %Cpu us 高、id 低、wa 低 → CPU 型
pidstat -u 1 3               # ③ 锁定 stress-ng 在吃 CPU
top -H -bn1 -p $(pgrep -d, stress-ng) | head   # ④ 定位到具体线程(TID)
```
> 在真实 Java 服务里:`top -H` 拿到吃 CPU 的线程 TID → `printf '%x\n' <TID>` 转十六进制 → 在 `jstack` 输出里按 `nid=0x...` 找到对应线程栈,就知道是哪段代码在烧 CPU。

**案例 2:load 高但 CPU 不高(I/O 型过载——破除「load=CPU」误解)**
```bash
stress-ng --hdd 2 --timeout 40s &
uptime                       # ① load 同样高
top -bn1 | head -8           # ② 但 %us 低、%wa 高,能看到 D 状态进程!
vmstat 1 3                   # ③ b 列(阻塞)>0、wa 高
iostat -xz 1 3               # ④ %util/await 飙升 → 确认 I/O 瓶颈(接 05)
```
对比案例 1:load 都高,但案例 2 的 CPU 是闲的,瓶颈在磁盘。**这就是为什么不能只看 load 就喊「CPU 不够,加机器」。**

**案例 3:进程「卡住」,用 strace 看它停在哪**
```bash
mkfifo /tmp/p
cat /tmp/p & P=$!            # cat 阻塞在 read,等管道数据
sudo strace -p $P 2>&1 | head -3    # 看到 read(3,  ← 卡在这个 syscall
sudo lsof -p $P | grep /tmp/p       # 3 号 fd 指向 /tmp/p,真相大白
echo "data" > /tmp/p                # 喂数据,cat 读到后退出
rm -f /tmp/p
```

**案例 4:跑一遍「第一分钟」体检**
```bash
uptime; echo ---; sudo dmesg -T | tail -5; echo ---
vmstat 1 3; echo ---; free -m; echo ---; ss -s
```
> 内存 OOM、fd 耗尽(`Too many open files`)、CLOSE_WAIT 堆积的复现实验,已分别在 [`04`](../04-memory-model/)、[`05`](../05-io-and-files/)、[`06`](../06-networking/) 做过,这里直接套用本章方法论去定位即可,不重复造轮子。

---

## 五、排查心法(生产铁律)⚠️

> **先留证据,再重启**:重启能止血但会毁现场。重启前先抓:`top`/`top -H` 快照、`jstack`/线程 dump、堆 dump、`ss -tanp`、`dmesg`、相关日志。否则事后复盘无据,问题必复发。

> **一次只动一个变量**:同时改内核参数 + 改代码 + 扩容,好了也不知道是谁的功劳,坏了更乱。每次验证一个假设。

> **区分「现象」和「原因」**:CPU 高可能只是结果(频繁 Full GC 导致),内存涨可能是 page cache(不是泄漏)。顺着资源链往上找根因,别停在第一个异常指标。

> **没有基线就没有「异常」**:平时就该有监控基线(正常 load/CPU/内存/连接数是多少),否则你根本不知道当前算不算异常。监控先行(接 `08` journald、`performance-tuning-roadmap/03-observability`)。

---

## 六、本章面试速记

- **`load average` 是什么?load 高一定是 CPU 高吗?** 是 R + D 状态任务数的平均,不只是 CPU;load 高 + `%wa` 高 + 一堆 D = 在等 I/O,CPU 可能闲着。
- **一台机器变慢/CPU 100%,你的排查步骤?** uptime 看 load → top 看是 CPU(us/sy)还是等 IO(wa) → pidstat 锁定进程 → top -H 锁定线程 → 对 Java 用 nid 映射到 jstack → 定位代码。
- **进程卡住了怎么查?** `ps` 看状态(D? `wchan`?)→ `strace -p` 看停在哪个 syscall → `lsof -p` 看相关 fd 指向什么。
- **USE 方法是什么?** 对每种资源查 Utilization(使用率)、Saturation(饱和/排队)、Errors(错误)。
- **「第一分钟」会敲哪些命令?** uptime、dmesg、vmstat、mpstat、pidstat、iostat、free、ss、top。

---

## 七、小结 + 桥接 + 延伸

**一句话记忆点**:
> 排查走「现象→指标→假设→工具→定位→修复→验证→复盘」;自顶向下先用 `uptime`/`top` 定方向(CPU?IO?内存?网络?),`load` 是 R+D 不是纯 CPU;`strace` 看进程卡在哪个 syscall、`lsof` 看 fd 指向什么;重启前先留证据。

**四语言桥接**(OS 层定位到进程/线程后,进语言层 profiler 定位代码):

| 运行时 | 找热点线程/代码 | 与 OS 层衔接 |
|--------|----------------|--------------|
| Java | `jstack` / async-profiler | `top -H` 的 TID → 十六进制 = jstack 的 `nid` |
| Go | `pprof`(CPU/heap/block) | OS 看进程整体,pprof 看 goroutine/函数 |
| Python | `py-spy`(免侵入采样) | `py-spy dump --pid` 直接看卡在哪 |
| Node | `--prof` / `clinic` / `0x` | 火焰图定位事件循环阻塞 |

→ 这正是「OS 定位资源/进程 → 语言 profiler 定位代码」的标准接力。各语言 profiling 实操见 `performance-tuning-roadmap/04a/05a/06a-*-profiling`。

**延伸指针**:
- 把本章方法论拿去**反复演练**(按需造真故障、走完整事故流程)→ [`11 · 故障注入实验室`](../11-fault-injection-lab/)
- 方法论(USE / RED / 性能定律)→ `performance-tuning-roadmap/01-methodology/`
- 各类 Linux 工具系统教程 → `performance-tuning-roadmap/02-linux-tools/`(含 `05-tracing-profiling`、`06-ebpf-bcc-bpftrace`)
- 压测建基线、找拐点 → `performance-tuning-roadmap/07-load-testing/`

➡️ 核心闭环(03–07)完成。后续工程化拓展:[`08 · systemd 与服务管理`](../08-systemd-and-services/) → `09 容器` → `10 shell 脚本`;on-ramp 回补 [`02 文件系统+权限`](../02-filesystem-and-permissions/)。
