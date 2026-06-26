# Linux/OS 底层原语 primer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 复活空壳目录 `linux/`,把它做成「所有 OS 课假设你懂、但没人教的底层原语」的 primer,每原语爬三层深度,当 `linux-handson` 的词汇底座。

**Architecture:** 5 个 Markdown 文件(`00-README` 索引 + `01内存`/`02执行`/`03IO`/`04并发` 四个原语章)。每原语走固定三层模板:① 你视角(Java/Go 桥)② 黑盒内部(资深·内核真相+取舍,必有)③ 砸实(命令+真实预期输出,透明证据,干净复现才放)。写作顺序 01→02→03→04→00。

**Tech Stack:** 纯 Markdown 文档。③ 层的命令在**抛弃式 Linux 容器**里实跑取真实输出(`docker run --rm`),因 host 是 macOS 跑不了 strace/`/proc`。

## Global Constraints

- **语言**:简体中文(对齐父课 `linux-handson/`)。
- **三层模板**:① 你视角(Java/Go 等价物,≤30 秒桥)· ② 黑盒内部(必有,讲内核/runtime 内部 + 架构取舍)· ③ 砸实(命令 **连同真实输出** 印在文档,非作业;只在有干净复现的原语放,不强求每原语都有)。
- **③ 输出禁造**:每条 ③ 命令必须在真 Linux 容器实跑、贴**真实**输出;跑不出干净结果就降级为「② 讲透,不放 ③」,绝不编造 console 输出。
- **回链**:每原语末尾回链到假设它的 handson 章(见各任务表的「主回链」)。
- **边界**:只讲「原语内部如何运作 + 为何这样设计」;「怎么排查现象」回链 `linux-handson`,「推什么架构决策」回链 `os-for-architects`,不在本 track 展开。
- **不教写 C**:③ 的代码片段 ≤5 行,只为亲眼看到原语行为。
- **不建 VM lab / 不出作业**:③ 是印在文档的透明证据,不要求读者跑了回报。
- **本次不写 `05` 链接装载**(留扩展位)。
- **commit 纪律**:每文件单独 commit,`git add` 用**显式路径**(本仓库有并发 agent 跑 `git add -A`),stage+commit 同一条 Bash 调用原子完成。commit message 结尾加 `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`。

---

## File Structure

| 文件 | 职责 |
|---|---|
| `linux/README.md`(改写现有重定向壳) | `00` 索引:track 是什么/怎么用 + 拓扑关系图 + 三层模板说明 + 扩展位说明 |
| `linux/01-memory-primitives/README.md`(新建) | 内存原语:指针/虚拟地址/页/page fault/brk vs mmap/malloc/VSZ·RSS 底层 |
| `linux/02-execution-primitives/README.md`(新建) | 执行原语:syscall/用户↔内核切换/中断/上下文切换/栈帧/进程 vs 线程 |
| `linux/03-io-primitives/README.md`(新建) | I/O 原语:fd/fd table/inode/阻塞 vs 非阻塞/内核缓冲/epoll/一切皆文件 |
| `linux/04-concurrency-primitives/README.md`(新建) | 并发原语:原子/CAS/futex/signal/条件变量·唤醒/内存屏障 |

> 现有 `linux/README.md` 是重定向壳,`linux/_archive/` 旧笔记**保留不动**。目录名用英文(对齐 `linux-handson` 的 `04-memory-model` 风格)。

## ③ 容器取证规约(所有任务共用)

跑 ③ 命令取真实输出,用抛弃式容器,一条 bash 脚本喂进去(zsh 不拆分变量,故用 `bash -c`;对标 memory `reference_handson_lab_bash`):

```bash
docker run --rm --cap-add=SYS_PTRACE ubuntu:24.04 bash -c '
  set -e
  apt-get update -qq && apt-get install -y -qq gcc strace >/dev/null 2>&1
  # … 各任务给具体编译+运行+strace 命令 …
'
```

- `--cap-add=SYS_PTRACE` 让 strace 在容器内可用。
- 把真实 stdout/stderr 原样(可截断+`# 注释`)贴进文档 ③ 段。
- 若某命令在容器里输出不稳定/不干净,该原语 ③ 降级跳过(见 Global Constraints)。

---

### Task 1: `01-memory-primitives`(优先首发)

**Files:**
- Create: `linux/01-memory-primitives/README.md`

**Interfaces:**
- Produces:本章是后续 02/03 的地基(虚拟地址/页/page fault 被反复引用);00 索引会回链本章。
- 主回链:`linux-handson/04-memory-model`、`linux-handson/07-troubleshooting-playbook`。

收录原语(每个走三层;② 必有,③ 见下):

| 原语 | ② 黑盒内部必须讲到 | ③ 砸实 |
|---|---|---|
| 指针 | 就是个存「虚拟地址」的整数;Java 引用/Go 指针的去糖版;解引用 = MMU 翻译那一步 | 无(概念,跳过 ③) |
| 虚拟地址空间 | 每进程独占一张地图;栈/堆/mmap/代码段布局;隔离+按需+超额承诺 | `cat /proc/self/maps` 看真实段布局 |
| 页 / page(4KB) | 内核管理内存的最小单位;页表 虚→物 映射;为什么 4KB | 无(概念) |
| page fault(缺页) | minor vs major;malloc 给地址不给物理页,首次写才触发内核分页 | 见 malloc ③(RSS 随触碰增长) |
| `brk` vs `mmap` | 堆顶抬升 vs 匿名映射;小块走 brk(不还内核)、大块走 mmap(munmap 还内核) | strace 区分:小块 brk、1MB 大块 mmap |
| `malloc`(arena) | glibc arena/不还内核 → free 后 RSS 不降;多线程锁竞争 → jemalloc/tcmalloc per-thread arena+收缩抗碎片(架构取舍) | strace brk/mmap;free 大块后 `/proc/self/status` VmRSS 真降、小块不降 |
| VSZ / RSS 底层 | VSZ=映射总和(虚)、RSS=驻留物理页(含共享库重复计入)→ 回链 lh/04 现象 | 一个 malloc 2G 只摸 200M 的程序看 VSZ/RSS |

- [ ] **Step 1: 跑 ③ 取真实输出(虚拟地址布局)**

```bash
docker run --rm ubuntu:24.04 bash -c 'cat /proc/self/maps | head -20'
```
预期:看到 `[heap]`/`[stack]`/`r-xp` 代码段等真实行。把真实输出留存待贴。

- [ ] **Step 2: 跑 ③ 取真实输出(brk vs mmap 分流 + RSS 行为)**

```bash
docker run --rm --cap-add=SYS_PTRACE ubuntu:24.04 bash -c '
set -e
apt-get update -qq && apt-get install -y -qq gcc strace >/dev/null 2>&1
cat > /tmp/m.c <<"EOF"
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
int main(){
  char *small = malloc(1024);          // 小块 → brk
  char *big   = malloc(1<<20);         // 1MB → mmap
  memset(big, 1, 1<<20);               // 触碰 → 缺页 → RSS 涨
  FILE *f=fopen("/proc/self/status","r"); char l[256];
  while(fgets(l,sizeof l,f)) if(strncmp(l,"VmRSS",5)==0) printf("after touch: %s",l);
  free(big);                           // 大块 munmap 还内核
  f=fopen("/proc/self/status","r");
  while(fgets(l,sizeof l,f)) if(strncmp(l,"VmRSS",5)==0) printf("after free big: %s",l);
  (void)small; return 0;
}
EOF
gcc -O0 /tmp/m.c -o /tmp/m
strace -e trace=brk,mmap,munmap /tmp/m 2>&1 | grep -E "brk|mmap|munmap|after" | head -30
'
```
预期:看到小块走 `brk`、`mmap(NULL, 1048576…`、`munmap(…1048576…)`,以及 `after touch` 的 VmRSS 高于 `after free big`。**贴真实输出,数字以实跑为准。**

- [ ] **Step 3: 写章节(三层模板,贴上 Step 1–2 的真实输出)**

按上表写 7 个原语;开头一段「这章解决什么 + 三层怎么读」;每原语末尾回链 lh/04。③ 段只贴 Step 1–2 实跑到的真实输出(可加 `#` 注释指明看点),严禁编造。

- [ ] **Step 4: 事实自查**

逐条核对:VSZ/RSS 定义与 lh/04 表述一致;brk/mmap 128KB 阈值表述为「glibc 默认 `M_MMAP_THRESHOLD` 约 128KB,可调」(别说死);③ 输出确为 Step 1–2 实跑所得。

- [ ] **Step 5: Commit**

```bash
git add linux/01-memory-primitives/README.md && git commit -m "$(printf 'docs(linux/01): 内存原语 primer(指针/虚存/page fault/brk·mmap/malloc/VSZ·RSS)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 2: `02-execution-primitives`

**Files:**
- Create: `linux/02-execution-primitives/README.md`

**Interfaces:**
- Consumes:Task 1 的虚拟地址/页/缺页概念(用户↔内核切换、缺页都踩它)。
- Produces:syscall 概念被 Task 3 的 fd 操作引用。
- 主回链:`linux-handson/03-process-model`。

收录原语:

| 原语 | ② 黑盒内部必须讲到 | ③ 砸实 |
|---|---|---|
| syscall | 用户态进内核的唯一合法门;`read`/`write`/`mmap` 都是;libc 是薄封装;软中断/`syscall` 指令切换 | strace 一个 `echo`/小程序看真实 syscall 序列 |
| 用户态↔内核态切换 | 为什么贵:寄存器保存、特权级切换、cache/TLB 影响 → 批处理/io_uring 的动机(架构取舍) | 无干净 5 行复现 → 跳过 ③,② 讲透 |
| 中断 IRQ | 硬件打断 CPU;中断上下文不能睡;top/bot half;与 syscall(软)的区别 | `cat /proc/interrupts` 看真实中断计数 |
| 上下文切换 | 进程/线程切换保存什么;主动 vs 抢占;切换成本与 cache 失效 → 回链调度 | `vmstat 1` 看 `cs` 列(真实切换数) |
| 栈帧 | 函数调用栈怎么长;局部变量/返回地址;为什么栈溢出;每线程一个栈 → 线程数×栈大小=内存 | 无(概念)或 `ulimit -s` 看默认栈大小 |
| 进程 vs 线程(内核视角) | Linux 都是 task_struct;`clone` 标志位决定共享什么(地址空间/fd 表);Go goroutine 是用户态之上 | `ps -eLf` 看一个多线程进程的 LWP |

- [ ] **Step 1: 跑 ③ 取真实输出(syscall 序列 + 中断 + 切换 + 栈大小 + LWP)**

```bash
docker run --rm --cap-add=SYS_PTRACE ubuntu:24.04 bash -c '
set -e
apt-get update -qq && apt-get install -y -qq strace procps >/dev/null 2>&1
echo "=== syscall 序列(write 是真 syscall)==="; strace -e trace=write echo hi 2>&1 | head -5
echo "=== 中断计数 ==="; head -5 /proc/interrupts
echo "=== 上下文切换 cs 列 ==="; vmstat 1 2 | tail -1
echo "=== 默认栈大小 ==="; bash -c "ulimit -s"
'
```
预期:`write(1, "hi\n", 3) = 3`、`/proc/interrupts` 前几行、vmstat 的 `cs` 数字、`ulimit -s`(通常 8192 KB)。**贴真实输出。**

- [ ] **Step 2: 写章节**

按上表写;②「用户↔内核切换为什么贵」讲透(明确标注本原语无 ③,符合「干净复现才放」)。每原语回链 lh/03。

- [ ] **Step 3: 事实自查**

核对:syscall vs 库函数区别表述准确;中断上下文「不能睡」表述准确;goroutine 是「用户态调度坐在 OS 线程之上」别说成内核线程;③ 为 Step 1 实跑所得。

- [ ] **Step 4: Commit**

```bash
git add linux/02-execution-primitives/README.md && git commit -m "$(printf 'docs(linux/02): 执行原语 primer(syscall/用户内核切换/中断/上下文切换/栈帧/进程vs线程)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 3: `03-io-primitives`

**Files:**
- Create: `linux/03-io-primitives/README.md`

**Interfaces:**
- Consumes:Task 2 的 syscall(fd 操作都是 syscall)、Task 1 的 mmap(文件映射)。
- 主回链:`linux-handson/05-io-and-files`、`linux-handson/06-networking`。

收录原语:

| 原语 | ② 黑盒内部必须讲到 | ③ 砸实 |
|---|---|---|
| 文件描述符 fd | 进程级小整数,索引进 fd 表;0/1/2 = stdin/out/err | `ls -l /proc/self/fd` 看真实 fd→目标 |
| fd table | 每进程一张;`clone` 可共享;fork 后子进程拷贝;ulimit -n 上限 → 「too many open files」根因 | `ulimit -n` 看上限 |
| inode | 文件元数据(非名字);硬链接=多名字共享 inode;`stat` 看;删除是减引用 | `stat` 一个文件看 inode 号 |
| 阻塞 vs 非阻塞 | 阻塞=线程睡在 syscall;非阻塞=立即返回 EAGAIN;O_NONBLOCK 标志 | 无干净 5 行 → 跳过或极简 |
| 内核缓冲 / page cache | write 先进内核缓冲再异步刷盘;read 命中 page cache;fsync 强刷 → 回链 lh/05 | 无(回链 lh/04 page cache)或跳过 |
| epoll 底层 | select/poll O(n) vs epoll O(1) 就绪通知;红黑树+就绪链表;边沿 vs 水平触发;事件循环根基 | 无干净复现 → ② 讲透,跳过 ③ |
| 「一切皆文件」 | 普通文件/socket/pipe/设备都用 fd + read/write 统一接口;为什么这设计强 | `ls -l /proc/self/fd` 看 socket/pipe 也是 fd |

- [ ] **Step 1: 跑 ③ 取真实输出(fd / ulimit / inode)**

```bash
docker run --rm ubuntu:24.04 bash -c '
set -e
apt-get update -qq && apt-get install -y -qq coreutils >/dev/null 2>&1
echo "=== 进程的 fd(0/1/2 + 额外)==="; ls -l /proc/self/fd
echo "=== fd 上限 ==="; bash -c "ulimit -n"
echo "=== inode(硬链接共享)==="; echo hi > /tmp/a; ln /tmp/a /tmp/b; stat -c "%n inode=%i links=%h" /tmp/a /tmp/b
'
```
预期:`/proc/self/fd` 列出 0/1/2 软链;`ulimit -n`(如 1024/1048576);`/tmp/a` 与 `/tmp/b` 同 inode、links=2。**贴真实输出。**

- [ ] **Step 2: 写章节**

按上表写;epoll/阻塞 ② 讲透并标注无 ③;每原语回链 lh/05 或 lh/06。

- [ ] **Step 3: 事实自查**

核对:epoll 边沿/水平触发表述准确;inode「存元数据不存名字、名字在目录项」表述准确;③ 为 Step 1 实跑所得。

- [ ] **Step 4: Commit**

```bash
git add linux/03-io-primitives/README.md && git commit -m "$(printf 'docs(linux/03): IO 原语 primer(fd/fd表/inode/阻塞·非阻塞/内核缓冲/epoll/一切皆文件)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 4: `04-concurrency-primitives`

**Files:**
- Create: `linux/04-concurrency-primitives/README.md`

**Interfaces:**
- Consumes:Task 2 的上下文切换/进程vs线程、Task 1 的内存(屏障关乎内存可见性)。
- 主回链:`linux-handson/03-process-model`。

收录原语(本章最抽象,压轴;多数无干净 5 行复现 → 以 ② 为主):

| 原语 | ② 黑盒内部必须讲到 | ③ 砸实 |
|---|---|---|
| 原子操作 / CAS | 硬件 `lock` 前缀/LL-SC;compare-and-swap 是无锁基石;ABA 问题 | 无(概念) |
| 锁底层(futex) | 用户态自旋无争用时不进内核,争用才 futex 进内核睡眠/唤醒;互斥锁=原子+futex 组合 | strace 看争用时 `futex` syscall |
| 信号 signal | 异步打断进程;信号处理器;可重入限制;`kill -SIGTERM`→优雅退出根基 → 回链零停机 | `kill -l` 看信号表 |
| 条件变量 / 唤醒 | wait/notify 底层=futex;为什么要 while 循环防虚假唤醒;惊群 | 无(概念) |
| 内存屏障 | 编译器/CPU 重排;happens-before;为什么 volatile/atomic 才保证可见性 → 桥到 Java volatile/Go sync | 无(概念) |

- [ ] **Step 1: 跑 ③ 取真实输出(futex + 信号表)**

```bash
docker run --rm --cap-add=SYS_PTRACE ubuntu:24.04 bash -c '
set -e
apt-get update -qq && apt-get install -y -qq gcc strace >/dev/null 2>&1
echo "=== 信号表 ==="; kill -l | tr " " "\n" | grep -n SIG | head -15 || kill -l
cat > /tmp/f.c <<"EOF"
#include <pthread.h>
pthread_mutex_t m = PTHREAD_MUTEX_INITIALIZER;
void* w(void* a){ for(int i=0;i<100000;i++){ pthread_mutex_lock(&m); pthread_mutex_unlock(&m);} return 0; }
int main(){ pthread_t t1,t2; pthread_create(&t1,0,w,0); pthread_create(&t2,0,w,0);
  pthread_join(t1,0); pthread_join(t2,0); return 0; }
EOF
gcc /tmp/f.c -o /tmp/f -lpthread
echo "=== futex(锁争用才进内核)==="; strace -f -e trace=futex /tmp/f 2>&1 | grep -c futex; echo "futex 调用次数 ↑(上面是计数)"
'
```
预期:`kill -l` 真实信号名;futex 调用计数为正整数(证明争用才进内核)。**贴真实输出;若 futex 计数为 0 说明没触发争用,改述为「无争用时不进内核」并跳过该 ③ 数字。**

- [ ] **Step 2: 写章节**

按上表写;多数原语 ② 讲透并明确标注无 ③(符合「干净复现才放」);内存屏障 ① 桥到 Java `volatile`/Go `sync/atomic`(读者背景)。每原语回链 lh/03。

- [ ] **Step 3: 事实自查**

核对:futex「无争用不进内核」表述准确;虚假唤醒/while 循环表述准确;happens-before 与 volatile 关系表述准确;③ 为 Step 1 实跑所得。

- [ ] **Step 4: Commit**

```bash
git add linux/04-concurrency-primitives/README.md && git commit -m "$(printf 'docs(linux/04): 并发原语 primer(原子·CAS/futex/signal/条件变量·唤醒/内存屏障)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

### Task 5: `00-README` 索引(收尾·串全网)

**Files:**
- Modify: `linux/README.md`(现为重定向壳,整体改写)

**Interfaces:**
- Consumes:Task 1–4 的四个章(索引链接到它们)。
- Produces:本 track 的入口。

内容必须含:

1. **一句话定位**:教「所有 OS 课假设你懂、没人教的底层原语」,当 `linux-handson` 的词汇底座。
2. **拓扑关系图**(ASCII):`linux/`(原语本身)← 坐其下 → `linux-handson`(机制·能答)← `os-for-architects`(原语→架构决策),说明三者边界(对镜 spec §2 的表)。
3. **三层模板说明**:① 你视角 / ② 黑盒内部(必有) / ③ 砸实(透明证据非作业,干净复现才放),给读者「怎么读这套文档」。
4. **章节目录**:01–04 各一行 + 装哪些原语 + 链接。
5. **扩展位说明**:`05 链接装载原语` 留位,撞到再加。
6. **旧笔记去向**:`_archive/` 保留(沿用现有 README 末段信息,别丢)。

- [ ] **Step 1: 改写 `linux/README.md`**

按上 6 点写。保留现有 README 里「旧笔记已移到 `_archive/`」那段信息;删除「已迁移到 linux-handson」的重定向语义(本目录不再是空壳)。链接核对四个新章路径真实存在。

- [ ] **Step 2: 事实自查 + 链接核对**

`grep -r "linux-handson"` 确认回链路径对;四个章文件确实存在;拓扑表与 spec §2 一致。

- [ ] **Step 3: Commit**

```bash
git add linux/README.md && git commit -m "$(printf 'docs(linux/00): 底层原语 primer 索引(拓扑关系图+三层模板说明+章节目录)\n\nCo-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>')"
```

---

## Self-Review

- **Spec 覆盖**:§3 范围(4 类原语,无链接装载)→ Task 1–4 + Task5 扩展位说明 ✓;§4 三层模板 → 每任务表 + Global Constraints ✓;§5 章节地图 5 文件 → Task 1–5 ✓;§6 顺序 01→…→00 → 任务序 ✓;§7 成功标准(01 能讲清 VSZ/RSS 三连 + 每条有②依据③命令)→ Task1 表 ✓;§8 非目标 → Global Constraints ✓。
- **占位扫描**:无 TBD;每 ③ 给了**具体可跑命令**而非「跑个 strace」;每章给了原语清单 + ② 必讲点,非「写相关内容」。
- **一致性**:目录名英文风格统一(`01-memory-primitives` 等);回链缩写 `lh`=`linux-handson` 全程一致;③ 输出「实跑禁造」契约在 Global Constraints + 每任务 Step 重申一致。
- **已知降级点(非缺陷,设计如此)**:用户↔内核切换、epoll、内存屏障等无干净 5 行复现的原语,明确以 ② 为主、跳过 ③——符合 spec「③ 干净复现才放,不强求每原语都有」。
