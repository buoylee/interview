# 04 · 内存模型 ⭐核心

> 🧪 **环境**:VM shell(`multipass shell linux-lab`),部分实验需 `sudo`
> 进程要的第二种资源:内存。本章解决一堆「看着像问题其实不是、看着没事其实要爆」的内存迷惑,以及云原生头号大坑——容器 OOM。

---

## 一、开篇盲点

- `top` 里进程 `RES` 涨了,就是内存泄漏?**不一定**——可能只是还没归还、或共享库被算进来。
- `free` 显示内存快满了,要慌吗?**不用**——Linux 故意把空闲内存拿去当缓存,这是好事。
- 容器里 `free` 明明显示一堆内存,为什么还 `OOMKilled`?
- 一个进程 `VSZ` 显示 2G、`RSS` 只有 200M,这 1.8G 差在哪?

这些盲区的根子,是不理解**虚拟内存、按需分页、page cache 和 cgroup 限制**。本章讲透,并让你能在沙箱里亲手触发一次 OOM。

---

## 二、正文 · 原理

### 2.1 虚拟内存:每个进程都以为自己独占内存

每个进程看到的都是一整片连续的**虚拟地址空间**,它根本不知道物理内存长什么样、别的进程在哪。

```
进程看到的(虚拟)          内核 + MMU 翻译         物理内存(真实)
┌──────────────┐                                ┌──────────────┐
│  栈   ↓       │                                │   page A     │
│              │      页表(page table)           │   page B     │
│  ↑ 堆        │  虚拟页 ──映射──► 物理页          │   ...        │
│  mmap 区     │  (按 4KB 一页管理)               │  (大家共享)   │
│  代码/数据   │                                  └──────────────┘
└──────────────┘
```

好处:**隔离**(进程互不可见)、**按需分配**(用到才给物理页)、**超额承诺**(允许申请的总和 > 物理内存,见 2.6)。

### 2.2 VSZ vs RSS vs PSS(高频题)

| 指标 | 全称 | 含义 | 怎么理解 |
|------|------|------|----------|
| **VSZ** | Virtual Size | 进程**映射**的虚拟地址空间总和 | 「我申请/映射了多大」,含没真正用的、共享库、未触碰的 mmap。**虚的,别太当真** |
| **RSS** | Resident Set Size | 真正占用的**物理页** | 「我实际占了多少物理内存」,**含共享库的份额(会重复计入多个进程)** |
| **PSS** | Proportional Set Size | 共享部分按比例分摊后的 RSS | 更公平,`smem` 看;统计「真实总占用」时用它避免重复计算 |

**为什么 VSZ 远大于 RSS?** 因为**按需分页(demand paging)**:`malloc`/`mmap` 只给你虚拟地址,并不真分物理内存;等你**真去写**那块内存,触发**缺页异常(page fault)**,内核才分一个物理页。所以「申请了 2G 但只摸了 200M」→ VSZ=2G、RSS=200M,完全正常。

### 2.3 page cache:空闲内存被当缓存是好事

Linux 把读过的文件页缓存在内存里(page cache),下次读同一文件直接命中内存,不碰磁盘;写则先写**脏页**,再由内核异步刷盘(回顾/预告 `05`)。

> **关键认知**:Linux 的哲学是「空闲内存就是浪费」,所以它会主动用空闲内存做 cache。**当应用需要内存时,这些 cache 可以立刻回收**。所以 `free` 里 cache 占很多、free 很少,**不代表内存紧张**。

### 2.4 `free` 怎么读:只看 `available`

```console
$ free -h
               total        used        free      shared  buff/cache   available
Mem:           3.8Gi       600Mi       180Mi        12Mi       3.0Gi       3.0Gi
Swap:          1.0Gi          0B       1.0Gi
```

- `free`(180Mi):**完全没被用**的内存——看着吓人,但没意义。
- `buff/cache`(3.0Gi):被拿去当缓存,**可回收**。
- **`available`(3.0Gi):真正还能给应用用的量 = free + 可回收的 cache**。✅ **判断内存够不够,只看这一列。**

记忆点:**别看 free,看 available。**

### 2.5 swap:内存不够时的「磁盘续命」

物理内存不够时,内核把**不活跃的页**换出到磁盘上的 swap 区;需要时再换入。问题是磁盘比内存慢几个数量级——

- 偶尔 swap 没事;**频繁换入换出(thrashing)= 性能雪崩**,系统看着没死但慢到不可用。
- `vmstat 1` 看 `si`/`so`(swap in/out),持续非 0 就是在 thrash。
- `vm.swappiness`(0–100)控制内核多倾向用 swap,数据库等延迟敏感服务常调低或关 swap。

### 2.6 overcommit 与 OOM killer

Linux 默认**超额承诺**:允许所有进程申请的虚拟内存总和超过物理内存(反正按需分页,很多申请了不用)。但万一大家真用起来、超过物理内存 + swap——

内核触发 **OOM killer**:按每个进程的 `oom_score`(主要看占用内存多少 + `oom_score_adj` 调整)挑一个「最该死的」杀掉,腾内存救系统。

```console
$ dmesg | grep -i 'killed process'
[12345.678] Out of memory: Killed process 4242 (java) total-vm:..., anon-rss:1800000kB
```

被 OOM 杀的进程,退出状态对应信号 9(SIGKILL),容器层面就是 **exit code 137**(128+9)。

### 2.7 容器内存:`free` 骗你(云原生头号坑)

容器的内存上限由 **cgroup** 控制(比如限 512M)。但坑在于:

> **传统 `free` / `/proc/meminfo` 读的是宿主机的内存,不是容器的 cgroup 限制!**

所以你在一个限 512M 的容器里 `free -h`,看到的是宿主机的 16G——然后你的进程用到 600M,**没超宿主机却超了 cgroup**,被 **cgroup OOM** 杀掉(`OOMKilled`),而宿主机内存还剩一大半。

看容器**真实**的内存限制与用量(cgroup v2):

```console
$ cat /sys/fs/cgroup/memory.max       # 限制,如 536870912 (512M),max=不限
$ cat /sys/fs/cgroup/memory.current   # 当前用量
```

> 完整的容器机制(namespaces/cgroups)在 `09` 展开,这里先记住「容器里别信 `free`,要看 cgroup」。

---

## 三、怎么看(命令 + 真实输出怎么读)

### 全局内存:`free -h` / `vmstat`

```console
$ vmstat 1
 r  b   swpd   free   buff  cache   si   so   bi   bo ...
 1  0      0 184320  20480 3080000    0    0    0    8 ...
#                    ↑cache 很大正常   ↑si/so 持续>0 = 在 swap,危险
```

### 按 RSS 排序找内存大户:`ps`

```console
$ ps -eo pid,vsz,rss,comm --sort=-rss | head -5
  PID    VSZ    RSS COMMAND
 4242 9800000 1830000 java       # VSZ 9.8G 但 RSS 1.8G —— 按需分页
  812  72000   8400 sshd
```

### 单进程细节:`/proc/<pid>/status`

```console
$ grep -E 'VmSize|VmRSS|VmSwap' /proc/4242/status
VmSize:  9800000 kB        # = VSZ
VmRSS:   1830000 kB        # = RSS
VmSwap:        0 kB        # 被换出去多少
```

### 看 OOM 记录:`dmesg`

```console
$ sudo dmesg -T | grep -iE 'out of memory|killed process'
```

---

## 四、动手实验(沙箱)

> 🧪 全部在 `multipass shell linux-lab` 里跑;清缓存和看 dmesg 需要 `sudo`。

**实验 1:VSZ ≫ RSS(按需分页)**
```bash
# 申请大块虚拟内存,但只触碰一小部分
stress-ng --vm 1 --vm-bytes 1G --vm-keep --timeout 20s &
sleep 2
ps -eo pid,vsz,rss,comm | grep stress-ng    # 观察 vsz 大、rss 随触碰增长
wait
```

**实验 2:page cache 让第二次读飞快**
```bash
dd if=/dev/zero of=/tmp/bigfile bs=1M count=512   # 造 512M 文件
sync; echo 3 | sudo tee /proc/sys/vm/drop_caches   # 清空 page cache
echo "== 第一次读(走磁盘)=="; time cat /tmp/bigfile > /dev/null
echo "== 第二次读(命中 cache)=="; time cat /tmp/bigfile > /dev/null   # 快很多
rm /tmp/bigfile
```

**实验 3:`free` 的 available 比 free 靠谱**
```bash
free -h                          # 记下 free 和 available
cat /tmp/* > /dev/null 2>&1; dd if=/dev/zero of=/tmp/c bs=1M count=300
free -h                          # free/buff-cache 变了,但 available 才反映"还能用多少"
rm -f /tmp/c
```

**实验 4:亲手触发 OOM killer(VM 里安全)**
```bash
# 申请远超物理内存且真去写,逼出 OOM(VM 内存越小越快触发)
stress-ng --vm 4 --vm-bytes 90% --vm-keep --timeout 30s
# 另开一个 shell,或事后查:
sudo dmesg -T | grep -iE 'out of memory|killed process' | tail
```
> 看到 `Killed process ... (stress-ng)` 就对了。这就是生产里 `OOMKilled` 的本体。

---

## 五、生产踩坑框 ⚠️

> **「内存一直涨,是泄漏吗?」**:先分清 **RSS 真涨** 还是 **page cache 涨**(看 `free` 的 used vs buff/cache)。真泄漏的特征是 **RSS 持续单调上涨、回收不掉**。Java 还要分清是堆内(看 GC 日志/堆 dump)还是堆外/Native(RSS 涨但堆没涨,查 DirectByteBuffer、JNI、线程数)。

> **容器 `OOMKilled`(exit 137)但宿主机内存还很多**:cgroup 限制被打爆。**老版本 JVM/Node 读宿主机内存来设堆**,在容器里必然超限 → 必 OOM。修法:JVM 用 `-XX:MaxRAMPercentage=75`(感知 cgroup),Node 用 `--max-old-space-size`,Go 用 `GOMEMLIMIT`。

> **swap 开不开**:延迟敏感服务(数据库、缓存)常关 swap 避免抖动;K8s 历史上默认要求节点关 swap。开了 swap 看似「内存变多」,实则可能 thrash 到雪崩。

> **OOM killer 杀错了关键进程**:用 `oom_score_adj`(写 `/proc/<pid>/oom_score_adj`,-1000 ~ 1000)保护关键进程,让 OOM 优先杀别的。

---

## 六、本章面试速记

- **RSS / VSZ / PSS 区别?** VSZ=映射的虚拟空间(虚,含没用的);RSS=实际占的物理页(含共享库,会重复计);PSS=共享部分按比例分摊(统计真实总量用它)。
- **`free` 看哪一列判断内存够不够?** 看 `available`(=free + 可回收 cache),不是 `free`。
- **page cache 占满内存是问题吗?** 不是,空闲内存当缓存、应用要时可立即回收。
- **什么是 OOM killer、怎么选进程?** 内存真不够时内核按 `oom_score`(占用 + adj)挑一个杀掉救系统;被杀进程 exit 137。
- **容器 OOMKilled 但宿主机内存充足为什么?** cgroup 限制小于实际用量;传统工具/老运行时读宿主机内存,没感知 cgroup → 超限。
- **VSZ 2G 但 RSS 200M 正常吗?** 正常,按需分页:申请虚拟地址不等于占物理内存,写到才缺页分配。

---

## 七、小结 + 桥接 + 延伸

**一句话记忆点**:
> 内存是按页、按需分配的虚拟资源;`VSZ` 是申请、`RSS` 是真占;空闲内存被当 page cache 是好事,判断够不够看 `available`;内存真不够时 OOM killer 出手;容器里要看 cgroup 不是 `free`。

**四语言桥接**(都绕不开「RSS ≠ 堆/逻辑内存」):

| 运行时 | 逻辑内存 | 为什么 RSS 更大 | 容器要设 |
|--------|----------|----------------|----------|
| Java | 堆 `-Xmx` | + Metaspace + 线程栈 + 堆外(DirectBuffer)+ JIT 代码缓存 | `-XX:MaxRAMPercentage`(感知 cgroup) |
| Go | runtime 管理 | + 栈 + GC 未归还的页 | `GOMEMLIMIT`(1.19+) |
| Python | 对象 + refcount/gc | pymalloc arena 释放后不一定还给 OS | — |
| Node | V8 堆 | + C++ 层、Buffer | `--max-old-space-size`(默认约 1.5–2G) |

→ 这正是「容器里给 JVM 设了 `-Xmx512m` 还 OOM」的原因:RSS = 堆 + 一堆堆外开销,超过 cgroup 的 512M。

**延伸指针**:
- 内存管理机制(页表、TLB、大页、NUMA 内存分配)深入 → `performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md`
- NUMA 跨节点访问对 GC 的影响 → `performance-tuning-roadmap/00-os-fundamentals/01-cpu-architecture-scheduling.md`

➡️ 下一章:[`05 · I/O 与文件`](../05-io-and-files/)(进程要的第三种资源:I/O;page cache 的脏页刷盘在那里展开)
