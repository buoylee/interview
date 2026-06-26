# 01 内存原语

> **这章解决什么问题**
>
> 你在 `linux-handson/04-memory-model` 里看到 `VSZ`/`RSS` 的差距、`malloc` 不还内存、`free` 后 RSS 不降——现象都在那章，但「为什么会这样」的底层机制在这里。本章补齐七个内存原语的内部工作原理，让 lh/04 的每一句结论都有根。

**三层怎么读：**

- **① 你视角** — 先用你熟悉的 Java/Go 概念搭桥，≤ 30 秒落地。
- **② 黑盒内部** — 内核/分配器真正做了什么，架构取舍在哪。这层是本章核心，每个原语必有。
- **③ 砸实** — 在真实 Linux 容器里跑出来的命令 + 输出，印在文档里作透明证据。只在能跑出干净结果的原语放，不强求每个都有。

---

## 原语一：指针（pointer）

### ① 你视角

Java 的 `Object obj` 是个引用，Go 的 `*int` 是个指针。两者本质上都是**存了一个地址的整数**——只是语言替你包了一层糖（GC 追踪、nil 检查等）。C 的指针是去掉糖之后的原始形态。

### ② 黑盒内部

指针就是一个整数，存的是**虚拟地址**（后面原语二会讲）。大小等于 CPU 字长：64 位机器上是 8 字节。

「解引用」(`*p`) 发生时，CPU 把这个整数交给 **MMU（内存管理单元）**，MMU 查页表把虚拟地址翻译成物理地址，再去物理内存取值。这个翻译步骤对程序员完全透明，但它是缺页异常（原语四）、内存保护（段错误）的发生场所。

Java 引用 / Go 指针的去糖版就是这个：一个整数 + MMU 翻译。Java 的 GC 能移动对象是因为它持有引用表，能在移动后更新所有引用里的整数；C 程序直接持有原始整数，对象移动后指针就失效了（野指针）。

> 没有 ③（概念层，无干净 5 行复现）

→ **回链**：`linux-handson/04-memory-model` §2（虚拟地址空间模型，指针如何落到段里）

---

## 原语二：虚拟地址空间

### ① 你视角

在 Java 里你从来不用担心「我和另一个进程会不会踩内存」——其实是操作系统给每个进程都发了一张「私人地图」，你看到的 `0x...` 地址是你进程专属的虚拟地址，不是真实物理内存的位置。

### ② 黑盒内部

Linux 每个进程都有一张**独立的虚拟地址空间**，64 位下理论可用 128TB（用户态部分）。这张地图的布局从低到高大致是：

```
低地址
├─ 代码段（text）    — 可执行机器码，r-xp（只读+可执行）
├─ 只读数据段        — 字符串常量等
├─ 数据段 / BSS      — 已初始化/未初始化全局变量
├─ 堆（heap）        — malloc 从这里分配，向上增长
│    …… 空洞 ……
├─ mmap 区域         — 共享库、匿名映射，从高往低增长
│    …… 空洞 ……
└─ 栈（stack）       — 函数调用帧，向下增长
高地址
```

**三个核心设计动机：**

1. **隔离**：进程 A 的 `0x1000` 和进程 B 的 `0x1000` 映射到不同物理页，互不干扰。进程崩溃不影响其他进程。
2. **按需分配（demand paging）**：映射一段地址不立即分配物理内存，真正读写时才通过缺页异常（原语四）分配物理页。这让 `malloc(2GB)` 几乎是瞬时的。
3. **超额承诺（overcommit）**：所有进程的 VSZ 加总可以远超物理内存，因为大部分映射从未被触碰。内核赌大多数程序不会同时用完。

### ③ 砸实

在抛弃式容器里看 `bash` 进程的真实段布局：

```
$ docker run --rm arm64v8/ubuntu:22.04 bash -c 'cat /proc/self/maps | head -25'
```

真实输出（arm64，aarch64 地址以 `aaaa`/`ffff` 开头，x86-64 则以 `7f` 开头，段结构相同）：

```
aaaab6950000-aaaab6956000 r-xp 00000000 00:4e 836901                     /usr/bin/cat
aaaab6965000-aaaab6966000 r--p 00005000 00:4e 836901                     /usr/bin/cat
aaaab6966000-aaaab6967000 rw-p 00006000 00:4e 836901                     /usr/bin/cat
aaaada7a3000-aaaada7c4000 rw-p 00000000 00:00 0                          [heap]
ffffa1cbe000-ffffa1ce0000 rw-p 00000000 00:00 0
ffffa1ce0000-ffffa1e6e000 r-xp 00000000 00:4e 837466                     /usr/lib/aarch64-linux-gnu/libc.so.6
ffffa1e6e000-ffffa1e7d000 ---p 0018e000 00:4e 837466                     /usr/lib/aarch64-linux-gnu/libc.so.6
ffffa1e7d000-ffffa1e81000 r--p 0018d000 00:4e 837466                     /usr/lib/aarch64-linux-gnu/libc.so.6
ffffa1e81000-ffffa1e83000 rw-p 00191000 00:4e 837466                     /usr/lib/aarch64-linux-gnu/libc.so.6
ffffa1e83000-ffffa1e8f000 rw-p 00000000 00:00 0
ffffa1e9d000-ffffa1ec8000 r-xp 00000000 00:4e 837448                     /usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1
ffffa1ecf000-ffffa1ed1000 rw-p 00000000 00:00 0
ffffa1ed1000-ffffa1ed5000 r--p 00000000 00:00 0                          [vvar]
ffffa1ed5000-ffffa1ed7000 r-xp 00000000 00:00 0                          [vdso]
ffffa1ed7000-ffffa1ed9000 r--p 0002a000 00:4e 837448                     /usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1
ffffa1ed9000-ffffa1edb000 rw-p 0002c000 00:4e 837448                     /usr/lib/aarch64-linux-gnu/ld-linux-aarch64.so.1
fffff140c000-fffff142d000 rw-p 00000000 00:00 0                          [stack]
```

**怎么看：**

| 列 | 含义 |
|---|---|
| `aaaab6950000-aaaab6956000` | 虚拟地址范围 |
| `r-xp` | 权限：r=可读，x=可执行，p=私有（copy-on-write） |
| `/usr/bin/cat` | 映射来源（共享库/可执行文件路径，或匿名） |
| `[heap]` | 进程堆区（由 `brk` 系统调用扩展） |
| `[stack]` | 主线程栈 |

`r-xp` 第一行是代码段（只读+可执行），`rw-p` 是可读写的堆/数据段，`libc.so.6` 是 glibc 动态库——每个进程都映射了它，但物理页是共享的（节省内存）。

→ **回链**：`linux-handson/04-memory-model` §2（VSZ/RSS 的「VSZ=映射总和」就来自这张地图的所有行加总）

---

## 原语三：页 / page（4 KB）

### ① 你视角

你在 Java/Go 里申请内存时（`new Object()`、`make([]byte, n)`），运行时内部最终还是要向操作系统要内存——但 OS 不会给你「1 字节」，最小给你「1 页」。就像磁盘不按字节读取而按扇区，OS 不按字节管内存而按页。

### ② 黑盒内部

**页**是内核管理物理内存的最小单位，x86-64 默认 **4 KB**（4096 字节）。虚拟地址空间和物理内存都按页对齐，两者之间由**页表（page table）** 维护映射关系：

```
虚拟地址 → [MMU + 页表] → 物理页帧地址
```

一条页表项（PTE）记录：
- 该虚拟页映射到哪个物理页帧
- 是否存在（present bit）——为 0 时访问触发缺页
- 权限位（读/写/执行）
- 是否 dirty（写过）

**为什么是 4 KB？**

这是 1970–80 年代确定的历史折中：
- **太小**（如 512 B）→ 页表条目过多，内存开销大，TLB 命中率低
- **太大**（如 1 MB）→ 内部碎片严重（申请 1 字节浪费 999 KB）

4 KB 在当时是「管理开销 vs 碎片」的甜点。现代内核也支持 2 MB / 1 GB 的**大页（Huge Pages）**，数据库/JVM 堆常用它来降低 TLB miss 频率。

**TLB（Translation Lookaside Buffer）**：MMU 内部的页表缓存，保存最近用过的虚拟→物理映射。命中时翻译几乎零开销；miss 时要走多级页表（x86-64 是 4 级），约 10–100 个时钟周期。上下文切换（进程切换）时 TLB 一般被 flush，这是切换成本的一部分。

> 没有 ③（概念层，无简单 5 行复现来展示页表本身）

→ **回链**：`linux-handson/04-memory-model` §2（「按需分页」原理，malloc 后 RSS 不立即涨就是这里说的 present bit=0）

---

## 原语四：page fault（缺页异常）

### ① 你视角

你在 Java 里 `new byte[1 << 20]`（分配 1 MB 数组），JVM 向 OS 申请内存——这一步几乎是瞬时的。但你真正第一次往每个字节写数据时，速度可能会有一个短暂的抖动。这就是缺页异常在发生。

### ② 黑盒内部

**缺页异常（page fault）** 是一个 CPU 异常，在访问一个虚拟地址时、该地址对应的页表项 present bit=0 时触发。内核的缺页处理器介入，分配物理页、更新页表项，然后让 CPU 重新执行那条指令——程序对此无感知。

**两种缺页：**

| 类型 | 场景 | 代价 |
|---|---|---|
| **minor fault（软缺页）** | 页表项不存在，但无需磁盘 I/O（两种情况：① 数据已在物理内存里，如共享库已被其他进程加载；② 匿名页首次访问，内核直接分配空白物理页） | 低（微秒级） |
| **major fault（硬缺页）** | 数据不在物理内存，需要从磁盘（swap/文件）读入 | 高（毫秒级，I/O） |

**malloc 的关键行为**：`malloc` 调用 `brk` 或 `mmap`（见原语五），只是**注册了虚拟地址范围**，此时 present bit=0，没有物理内存。等你第一次**写**（读有时会 lazy 分配，写必须分配）那块内存，触发 minor fault，内核才分配物理页——这就是为什么 `malloc(2GB)` 是瞬时的但实际占用物理内存（RSS）很少。

`memset` 会触碰每一页，所以 `memset` 之后 RSS 会明显上升——后面 ③ 会看到这个现象。

> ③ 见下方原语六 malloc 的 `③ 砸实`（RSS 随触碰增长就是缺页触发的证据）

→ **回链**：`linux-handson/04-memory-model` §2（「VSZ 2G 但 RSS 200M 正常吗？」答案就是按需分页+缺页机制）

---

## 原语五：`brk` vs `mmap`

### ① 你视角

Java 的 `new`、Go 的 `make` 最终都走到 C 的 `malloc`。`malloc` 向操作系统要内存有两条路：一条叫 `brk`，一条叫 `mmap`。用哪条、什么时候用，决定了「free 后内存还不还给 OS」这个行为。

### ② 黑盒内部

**`brk`（抬堆顶）**：

堆区有个堆顶指针（program break）。`brk(addr)` 把堆顶移到新地址，相当于「把堆区扩大/缩小」。这段虚拟内存属于进程，即使 `free` 掉里面的小块，glibc 通常**不会立即调 `brk` 把堆顶缩回来**——因为缩回后下次 malloc 又要涨，频繁 brk 有开销。结果就是：小块 free 后 RSS **不降**（内核看来那段内存还是你的）。

**`mmap`（匿名映射）**：

`mmap(NULL, size, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0)` 在 mmap 区创建一个新的独立映射，和堆区不相邻。`free` 时 glibc 调 `munmap`，把那段映射归还内核，RSS **立即降**。

**glibc 的分流策略**：

glibc 默认用 **`M_MMAP_THRESHOLD`**（约 128 KB，可调）作为分水岭：

- 申请 `< M_MMAP_THRESHOLD`（约 128 KB）：走 `brk`，在堆上分配
- 申请 `≥ M_MMAP_THRESHOLD`：走 `mmap`，独立映射

> 这个阈值不是硬法律，可以用 `mallopt(M_MMAP_THRESHOLD, n)` 调整，也会随实际分配动态变化。

### ③ 砸实

用 strace 看真实系统调用，验证小块走 `brk`、大块（1 MB）走 `mmap`：

```
$ docker run --rm --cap-add=SYS_PTRACE arm64v8/ubuntu:22.04 bash -c '...'
```

真实 strace 输出（节选，含 glibc 初始化 + malloc 调用）：

```
brk(NULL)                               = 0xaaab0a9df000          # 查当前堆顶
mmap(NULL, 8192, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0xffff93c09000
mmap(NULL, 8592, PROT_READ, MAP_PRIVATE, 3, 0) = 0xffff93c06000
mmap(NULL, 1830504, PROT_NONE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0xffff93a18000
mmap(0xffff93a20000, 1764968, PROT_READ|PROT_EXEC, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3, 0) = 0xffff93a20000
munmap(0xffff93a18000, 32768)           = 0
munmap(0xffff93bcf000, 32360)           = 0
mmap(0xffff93bbd000, 24576, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_DENYWRITE, 3, 0x18d000) = 0xffff93bbd000
mmap(0xffff93bc3000, 48744, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_FIXED|MAP_ANONYMOUS, -1, 0) = 0xffff93bc3000
munmap(0xffff93c06000, 8592)            = 0
brk(NULL)                               = 0xaaab0a9df000          # glibc arena 初始化查堆顶
brk(0xaaab0aa00000)                     = 0xaaab0aa00000          # 小块 malloc(1024) → 抬堆顶（扩堆 ~132 KB arena）
mmap(NULL, 1052672, PROT_READ|PROT_WRITE, MAP_PRIVATE|MAP_ANONYMOUS, -1, 0) = 0xffff9391f000
                                                                   # 大块 malloc(1<<20=1MB) → mmap（1048576+4096 对齐）
munmap(0xffff9391f000, 1052672)         = 0                        # free(big) → munmap 归还内核
after touch: VmRSS:	    2080 kB                                    # memset 触碰后 RSS 实测值
after free big: VmRSS:	    1196 kB                                # munmap 后 RSS 降回（差值 ≈ 884 kB ≈ 1MB 大块）
```

**关键点：**

- `brk(0xaaab0aa00000)` — 堆顶从 `0xaaab0a9df000` 抬到 `0xaaab0aa00000`，差值 0x21000 ≈ 132 KB，是 glibc 为小块 malloc 扩展的 arena（glibc 一次多申请一些，减少 brk 次数）
- `mmap(NULL, 1052672, ...)` — 1052672 = 1048576（1 MB） + 4096（页对齐开销），这是大块 malloc(1<<20) 走 mmap
- `munmap(…, 1052672)` — `free(big)` 立即归还，RSS 从 2080 kB → 1196 kB（差值 ≈ 884 kB，剩余因 libc 等共享页占用）

→ **回链**：`linux-handson/04-memory-model` §3（「free 后 RSS 不降」的根因：小块走 brk，brk 区不还内核）

---

## 原语六：`malloc` 与 arena

### ① 你视角

Go 的内存分配器（mcache/mcentral/mheap）、Java 的 G1/ZGC——每个运行时都有自己的分配器层在 OS 之上。C 的 `malloc` 是其中最原始的一个，理解它的结构能帮你看懂「为什么 free 后内存不降」「为什么多线程分配会竞争」。

### ② 黑盒内部

**glibc malloc 的 arena 机制：**

glibc 在 `brk` 扩来的堆上维护一个**分配器 arena**（内部管理结构），记录哪些块已用、哪些已 free。`free` 时小块回到 arena 的空闲链表，等待下次 `malloc` 复用——不会立即还给内核，所以 RSS 不降。

**为什么不还内核？**

还内核（`brk` 下降）有成本：下次分配又要 `brk` 上升，还要触发缺页重新建页表。glibc 宁愿持有内存当「内存池」，加快后续 malloc 速度。代价是「free 后进程 RSS 看起来不降」，对监控有误导。

**多线程问题：**

只有一个 arena 时，多线程并发 malloc 都要竞争同一把锁。glibc 的解法是**多 arena**（Per-thread arena pool），但依然有上限（通常 8×核数），超出后线程仍然竞争。这是为什么高并发场景要换 **jemalloc** 或 **tcmalloc** 的根本原因：

| 分配器 | 策略 | 优势场景 |
|---|---|---|
| glibc malloc | 有限多 arena | 通用，单线程/低并发 |
| **jemalloc** | per-thread tcache + size-class slab | 高并发/碎片敏感（Firefox、FreeBSD） |
| **tcmalloc** | per-thread 缓存 + 中央堆 + 主动还内核 | 高并发 + RSS 可控（Chrome、Go 早期参考） |

**③ 砸实（含 page fault 现象）**

同上方原语五的 ③ 输出——注意两行 RSS 读数：

```
after touch: VmRSS:	    2080 kB    # memset(big, 1, 1MB) 触碰每一页 → page fault → RSS 涨
after free big: VmRSS:	    1196 kB  # free(big) 走 munmap → 物理页还内核 → RSS 降
```

**小块对比**：代码里的 `malloc(1024)`（小块）的 free 没写（`(void)small` 保留到程序退出），进程退出时堆区才统一回收——说明小块 free 后 RSS 不会单独降，需要 arena 收缩或进程退出才释放。

→ **回链**：`linux-handson/04-memory-model` §3（「free 后 RSS 不降的根因」+ 「内存一直涨是泄漏吗」判断方法）

---

## 原语七：VSZ / RSS 底层

### ① 你视角

你在 `ps` / `top` 里看到 Java 进程 VSZ=9.8G、RSS=1.8G，心里一惊——「是不是内存泄漏？」其实不是，这两个数字分别对应完全不同的东西。

### ② 黑盒内部

| 指标 | 全称 | 定义 | 什么时候涨 |
|---|---|---|---|
| **VSZ** | Virtual Size | 进程**虚拟地址空间映射总和**：把 `/proc/self/maps` 每行地址范围相加 | `mmap`/`malloc`/加载库时（注册了虚拟地址范围，不管有没有物理页） |
| **RSS** | Resident Set Size | **驻留在物理内存的页数 × 页大小**：只统计 present bit=1 的页 | 真正访问过（读/写触发缺页）才涨 |

**两个容易踩的坑：**

1. **RSS 含共享库，会重复计入**：libc.so 被 100 个进程共享，每个进程的 RSS 都把 libc 那几 MB 算进去，但物理内存里只有一份。所以所有进程 RSS 之和 > 真实物理内存占用。（更准确的是 PSS，见 lh/04 §2.2）

2. **VSZ ≫ RSS 是正常的**：因为「按需分页」。`malloc(2GB)` 后 VSZ 立刻涨 2 GB，RSS 几乎不变；等你 `memset` 触碰物理页后 RSS 才涨。这正是 lh/04 里「VSZ 2G 但 RSS 200M 正常吗？正常」的底层根据。

**用代码演示这个差距**（同 Step 2 实验程序，若 `malloc` 2 GB 但只 memset 200 MB，则 VSZ 涨 2 GB、RSS 只涨 200 MB 级别）：

这个现象在 Step 2 实验里已有缩影：`malloc(1<<20)` 分配 1 MB（VSZ 涨），但在 `memset` 之前 RSS 不涨；`memset` 完成后才看到 `after touch: VmRSS: 2080 kB`。

> ③ 见原语五的 ③（`after touch` vs `after free big` 的 RSS 差值已验证物理页的实际分配和归还）

→ **回链**：`linux-handson/04-memory-model` §2.2（VSZ/RSS/PSS 三指标完整对比表）、`linux-handson/07-troubleshooting-playbook`（RSS 持续上涨的排查流程）

---

## 速查：七个原语关系

```
malloc(n)
  ├─ n < ~128KB  → brk()     → 扩堆顶，free 后不还内核（RSS 不降）
  └─ n ≥ ~128KB  → mmap()    → 匿名映射，free 后 munmap 还内核（RSS 降）

两条路都只给「虚拟地址」：
  指针 = 虚拟地址整数
  虚拟地址 → [MMU + 页表] → 物理页帧
  首次访问（present=0）→ page fault → 内核分配物理页

VSZ = 所有 mmap/brk 区间之和（虚）
RSS = 已分配物理页之和（含共享库，实）
```

---

*本章是后续章节的地基：[02 执行原语](../02-execution-primitives/README.md)（syscall/上下文切换）和 [03 IO 原语](../03-io-primitives/README.md)（fd/page cache）都假设你已经懂虚拟地址和 page fault。*
