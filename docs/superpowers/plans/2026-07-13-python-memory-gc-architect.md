# Python 内存/GC 架构师级补强 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `python/16-objects-memory-gc-gil.md` 从资深级补强到架构师级:新增内存模型/分配器层(pymalloc+RSS)、GC 生产调优、PEP 683、Java↔Python 深度收口地图,并同步面试卡与关联文档。

**Architecture:** 纯文档改动。先在 Docker 容器采集真机数据(数字进正文),再按节增量改 ch16(每节一个 commit),最后收尾同步 3 个关联文件并全文校验。

**Tech Stack:** Markdown(简体中文)、Docker `python:3.11` / `python:3.12`(实测数据)。

**Spec:** `docs/superpowers/specs/2026-07-13-python-memory-gc-architect-design.md`

## Global Constraints

- 机制进正文教学;章末面试卡只复习,不承载新知识。
- 简体中文,行文与 `python/` track 现有风格一致(叙事+一句话收口+代码带注释输出)。
- 所有新代码片段的输出数字必须来自本次容器实测,不得凭记忆写。**实测值与 spec/plan 里预填的数字冲突时,以实测为准并同步修正正文。**
- 采集脚本用 `bash script.sh` 跑(zsh 不拆分变量);`docker exec` 显式给 stdin。
- git 提交:stage+commit 在同一条 Bash 命令、用显式路径(仓库有并发 agent 跑 `git add -A` 的历史)。
- 不新建教程文件;不覆盖 obmalloc usedpools/bitmap 实现细节;不动 `python/01`。

---

### Task 1: 容器真机数据采集

**Files:**
- Create: `<scratchpad>/mem_facts.py`、`<scratchpad>/rss_demo.py`(临时,不进仓库)
- Output: `<scratchpad>/facts-3.11.txt`、`<scratchpad>/rss-3.11.txt`、`<scratchpad>/immortal-3.12.txt`

**Interfaces:**
- Produces: 三份实测输出,后续任务从中抄数字:pymalloc 小对象阈值/pool/arena 尺寸、RSS 前后对比值、3.12 `sys.getrefcount(None)` 值。

- [ ] **Step 1: 写事实采集脚本**

```python
# mem_facts.py — 采集 pymalloc 结构参数与 GC 阈值
import sys, gc

print("version:", sys.version)
print("thresholds:", gc.get_threshold())
print("getsizeof 0/[] :", sys.getsizeof(0), sys.getsizeof([]))
# _debugmallocstats 打到 stderr:含 pool size、arena size、size class 表
sys._debugmallocstats()
```

关键读法:stderr 里 `N arenas * M bytes/arena` 的 M 即 arena 尺寸(**注意:3.10 起 64 位平台 arena 可能已从 256KB 升到 1MB,以这里的实测为准,若与 spec 的 256KB 不符,正文写实测值**);`pool size` 行给 pool 尺寸;size class 表末行给小对象上限(应为 512 bytes)。

- [ ] **Step 2: 写 RSS 演示脚本**

```python
# rss_demo.py — 「del 了 RSS 为什么不降」演示(将嵌入 ch16 §五,数字以实测替换)
import gc

def rss_mb():
    with open("/proc/self/status") as f:          # Linux 容器里跑;ru_maxrss 是峰值不是当前值,不能用
        for line in f:
            if line.startswith("VmRSS"):
                return int(line.split()[1]) // 1024

print(f"基线            RSS = {rss_mb()} MB")

objs = [{"i": i} for i in range(2_000_000)]        # 200 万小 dict,全走 pymalloc
print(f"建 200 万小对象 RSS = {rss_mb()} MB")

del objs; gc.collect()
print(f"del + collect   RSS = {rss_mb()} MB")      # 关键观察:降不回基线

big = bytes(200 * 1024 * 1024)                     # 200MB 大块,>512B 直走 malloc/mmap
print(f"建 200MB 大对象 RSS = {rss_mb()} MB")

del big
print(f"del 大对象      RSS = {rss_mb()} MB")      # 关键观察:这个立刻还回去
```

注意:spec 写的 `resource.getrusage` 不可用——`ru_maxrss` 是高水位,永不下降,演示不了「降/不降」对比;改用 `/proc/self/status` 的 VmRSS,正文同样用这个。

- [ ] **Step 3: 容器里实跑三项采集**

```bash
cd <scratchpad>
docker run --rm -i python:3.11 python < mem_facts.py > facts-3.11.txt 2>&1
docker run --rm -i python:3.11 python < rss_demo.py  > rss-3.11.txt  2>&1
docker run --rm -i python:3.12 python -c "import sys; print(sys.version); print('refcount(None) =', sys.getrefcount(None))" > immortal-3.12.txt 2>&1
cat facts-3.11.txt rss-3.11.txt immortal-3.12.txt
```

Expected:
- `facts-3.11.txt`:thresholds `(700, 10, 10)`;stderr 统计里能读出 pool/arena 尺寸与 512B 上限。
- `rss-3.11.txt`:五行 RSS;「del + collect」明显高于基线;「del 大对象」明显回落。
- `immortal-3.12.txt`:`refcount(None)` 为一个巨大常量(immortal 哨兵值,预期 4294967295 量级;3.11 里同命令是几千的普通数,可顺手采一份对照)。

- [ ] **Step 4: 记录数字**

把三份输出里将进正文的数字(arena/pool/512B、五行 RSS、immortal 值)整理成注释块留在 scratchpad,后续任务直接抄。无 commit(scratchpad 不进仓库)。

---

### Task 2: ch16 §二尾加 PEP 683 immortal objects

**Files:**
- Modify: `python/16-objects-memory-gc-gil.md`(§二「引用计数」末尾,`> 对比:Java/Go…` 引用块之前)

**Interfaces:**
- Consumes: Task 1 的 `immortal-3.12.txt` 数值。
- Produces: 正文锚点「永生对象(immortal objects)」,Task 3/5 的 CoW 叙述与面试卡引用它。

- [ ] **Step 1: 插入小节**

在 §二的 Java/Go 对比引用块前插入(数字用实测替换):

```markdown
### 永生对象:连 None 的 refcount 都不再动了(PEP 683,3.12)

引用计数有个隐藏成本:**读也会写**。哪怕只是把 `None`、`True`、小整数传来传去,refcount 也在不停 +1/-1——这会把本可多进程共享的内存页写脏(CoW,§四会展开),也是 free-threading 要做原子操作的负担。3.12 起(PEP 683)这类从不该死的对象被标记为**永生(immortal)**:refcount 固定在一个哨兵值上,增减操作直接跳过:

​```python
# python:3.12 实测
sys.getrefcount(None)   # 4294967295 —— 哨兵值,不再真实计数(3.11 里是普通的几千)
​```

永生对象读多写零,fork 后的共享页不再被写脏,也为 §七 free-threading 铺了路。
```

(嵌入时代码围栏正常写,上面 `​```` 仅为本计划的转义。)

- [ ] **Step 2: 校验渲染与数字**

Run: `grep -n 'PEP 683' python/16-objects-memory-gc-gil.md`
Expected: 命中新小节;数字与 `immortal-3.12.txt` 一致。

- [ ] **Step 3: Commit**

```bash
git add python/16-objects-memory-gc-gil.md && git commit -m "docs(python): ch16 补 PEP 683 永生对象" -- python/16-objects-memory-gc-gil.md
```

---

### Task 3: ch16 §四扩「生产视角」+ 收口地图框

**Files:**
- Modify: `python/16-objects-memory-gc-gil.md`(§四末尾;替换现有 `gc` 模块干预那一段,原句并入新小节)

**Interfaces:**
- Consumes: Task 2 的「永生对象」锚点(CoW 叙述引用)。
- Produces: 小节标题「生产视角:GC 什么时候成延迟元凶」+ 收口地图引用框,Task 5 面试卡引用。

- [ ] **Step 1: 扩写生产视角小节**

把 §四现有末段(`gc` 模块还可手动干预:…)替换为:

```markdown
### 生产视角:GC 什么时候成延迟元凶

分代 GC 是**stop-the-world 且单线程**的:扫描时暂停所有 Python 代码。gen0 只扫新对象、微秒级;但 **gen2 是全堆扫描,成本 = O(存活对象数)**——常驻千万级对象的服务(大缓存、大模型元数据),一次 gen2 可到百毫秒级,表现为**周期性 P99 尖峰**:流量越大、分配越快、触发越频。三个真实手段:

- **调大阈值**:`gc.set_threshold(50_000, 20, 20)` 之类,让扫描更稀疏(代价:循环垃圾滞留更久、峰值内存更高)。先用 `gc.set_debug(gc.DEBUG_STATS)` 或 `gc.callbacks` 计时,确认尖峰真来自 GC 再调。
- **确定无环的批处理直接 `gc.disable()`**:引用计数照常工作,只是没了兜底;短生命周期进程(脚本、Celery 任务)风险很低。
- **fork 型服务上 `gc.freeze()`**:预加载(gunicorn `--preload`)本想靠 CoW 让 worker 共享父进程内存,但 refcount 一动、整个 4KB 页就被复制,GC 扫描更是全堆摸一遍——共享页大量写脏。fork 前 `gc.freeze()` 把当前所有存活对象移出 GC 追踪,worker 里不再扫它们;3.12 的永生对象(§二)进一步让 None/小整数连 refcount 都不写。

**Instagram 案例**(经典,可直接讲):他们发现 worker 里 CoW 共享内存持续流失,根因就是 GC 扫描写脏共享页;先粗暴 `gc.set_threshold(0)` 关掉分代 GC,整体容量提升约 10%;后把「fork 前冻结」贡献回 CPython,就是 3.7 的 `gc.freeze()`。

> **收口地图:Java 的 GC 深度在收集器,Python 的在别处。** JVM 面试聊 GC 是聊收集器动物园(CMS/G1/ZGC、并发标记、卡表、停顿目标);CPython 的循环 GC 只是一个不并发、不搬移、不压缩的朴素 mark-sweep,**浅是设计使然**——因为 refcount 已经收掉 99%。Python 这边的深水区搬了家:**①分配器层**(pymalloc、RSS 行为,§五)、**②refcount 的涟漪效应**(GIL 的存在理由 §六、CoW 写脏页、永生对象 §二、free-threading 的 biased refcount §八)、**③生产调优**(本节)。被问「Python GC 和 JVM 比」照这张图答。
```

注:框内 §五/§六/§八 是 Task 4 顺延后的新节号,本任务先写好,Task 4 落地后自然对齐(Task 6 统一校验)。

- [ ] **Step 2: 校验**

Run: `grep -n 'gc.freeze\|Instagram\|收口地图' python/16-objects-memory-gc-gil.md`
Expected: 三者命中且原「gc 模块还可手动干预」旧段已并入、无重复。

- [ ] **Step 3: Commit**

```bash
git add python/16-objects-memory-gc-gil.md && git commit -m "docs(python): ch16 §四补 GC 生产调优与 Java↔Python 深度收口地图" -- python/16-objects-memory-gc-gil.md
```

---

### Task 4: ch16 新「§五 内存模型与分配:对象的一生」+ 节号顺延

**Files:**
- Modify: `python/16-objects-memory-gc-gil.md`(§四之后插入新节;原 五/六/七/八 → 六/七/八/九)

**Interfaces:**
- Consumes: Task 1 的 `facts-3.11.txt`(arena/pool/512B)与 `rss-3.11.txt`(五行 RSS)。
- Produces: 节标题「五、内存模型与分配:对象的一生」;顺延后节号:六 `__slots__`、七 GIL、八 free-threading、九 为什么慢。

- [ ] **Step 1: 插入新节**

结构(数字全部用实测替换;~70-80 行):

```markdown
## 五、内存模型与分配:对象的一生

refcount 归零「立即回收」——回收到哪儿?**不是还给操作系统。** CPython 与 OS 之间隔着自己的分配器,这一层是「del 了内存怎么不降」的全部答案。

### 分层图:内存从 OS 到名字

​```
OS 虚拟内存(mmap / brk)
 └─ CPython 私有堆
     ├─ pymalloc:arena(<实测>KB/MB,向 OS 整块要)→ pool(<实测>KB,按 size class 切)→ block(装对象)   ← ≤512B 小对象
     └─ 直接 malloc / mmap                                                                            ← >512B 大对象
         └─ 对象层:对象头(§一)+ 各类型 free list 复用
             └─ 名字层:引用绑定(第 01 章)
​```

### 一个对象的出生
`x = MyObj()` 的完整路径:类型的 `tp_alloc` 申请内存 → `PyObject_Malloc` 判断大小 → ≤512B 走 pymalloc(找对应 size class 的 pool,掰一个 block)/ >512B 直接 malloc → 装上对象头、refcount=1 → 名字 x 绑定。死亡是反向:refcount 归零 → block 还给 pool(或进类型 free list)→ **到此为止,通常不再往下还**。
顺带:对象**全部在堆上**,连函数调用的 frame 都是堆对象——Python 没有「栈上分配」这回事。

### 反 Java 直觉:三代不是三块内存
JVM 的分代是**物理分区**(eden/survivor/old),对象晋升要真搬家、GC 顺带压缩。CPython 的三代**只是三条追踪链表**:晋升 = 从 0 代链表摘下挂到 1 代,对象地址从生到死不变。**从不搬家 → 没有压缩 → 碎片只能靠运气消**,这正是下面 RSS 问题的根源。

### 「都 del 了,RSS 为什么不降?」(实测)
<rss_demo.py 代码 + 五行实测输出进正文>
三个根因,一层一个:
1. **arena 高水位**:pymalloc 只有当一个 arena 里**所有** pool 全空才把它还给 OS——一个 arena 里哪怕剩一个活对象,整个 arena(<实测尺寸>)都钉在进程里。对象从不搬家,活对象就没法归拢,典型「分配 200 万→只留 1%,RSS 几乎不动」。
2. **free list 不还**:float/list/dict 等类型自留复用池,回收的对象壳直接留着等下次分配。
3. **glibc malloc 自己也不还**:>512B 走 malloc 的部分,小块释放同样可能停在 glibc 的堆高水位下(大块 mmap 的除外——所以实测里 200MB 大对象 del 后立刻回落)。
结论:**RSS 是「历史峰值的滞留」而不是「当前活对象量」**。判断是真泄漏还是滞留/碎片:对照 RSS 与 tracemalloc 曲线(排查手册见 ../performance-tuning-roadmap/06a-python-profiling/02-python-memory-analysis.md);容量规划按峰值 RSS 留水位,别按「稳态该多小」想当然。
```

- [ ] **Step 2: 节号顺延 + 内部引用更新**

原 `## 五、__slots__…` → 六,`## 六、GIL…` → 七,`## 七、free-threading…` → 八,`## 八、为什么慢…` → 九。已知内部引用逐个改:

| 行(改前) | 现文 | 改为 |
|---|---|---|
| L32 | `__slots__` 见本章 §5 | §6 |
| L174(为什么慢#4) | 本章 §6 | §7 |
| L178(free-threading) | §7 | §8 |
| Task 3 收口地图框 | §五/§六/§八ok | 核对即可 |
| Q5-Q7 卡内如有节号 | 核对 | 同步 |

外部引用核查:`grep -rn '16-objects' python/ | grep '§'` → 目前只有 `python/02` 引 §1(不受影响),确认无其他。

- [ ] **Step 3: 校验**

Run: `grep -n '^## ' python/16-objects-memory-gc-gil.md`
Expected: 一~九连续;新 §五 在 §四之后。
Run: `grep -c 'RSS' python/16-objects-memory-gc-gil.md`
Expected: ≥5(实测输出进了正文)。

- [ ] **Step 4: Commit**

```bash
git add python/16-objects-memory-gc-gil.md && git commit -m "docs(python): ch16 新增 §五 内存模型与分配(pymalloc/RSS,真机实测)" -- python/16-objects-memory-gc-gil.md
```

---

### Task 5: 收尾同步(面试卡 / 99 / 06a 互指 / 心智句)

**Files:**
- Modify: `python/16-objects-memory-gc-gil.md`(开头「一句话心智」、Java/Go 对照框、章末卡)
- Modify: `python/99-interview-cards.md`(「并发/内部」节)
- Modify: `performance-tuning-roadmap/06a-python-profiling/03-cpython-gc.md`(头部)

**Interfaces:**
- Consumes: Task 2-4 的节号与锚点。

- [ ] **Step 1: ch16 章末卡 +3**

```markdown
**Q8. 对象都 del 了,进程 RSS 为什么不降?**
refcount 归零只把 block 还给 pymalloc 的 pool/free list,不还 OS。三根因:arena 高水位(一个活对象钉住整个 arena,且对象从不搬家、无压缩)、类型 free list 自留复用、glibc malloc 也有自己的高水位。RSS 反映历史峰值滞留而非当前活对象量;判泄漏还是滞留,对照 RSS 与 tracemalloc 曲线。

**Q9. 线上服务出现周期性 P99 尖峰,怀疑 GC,怎么确认、怎么治?**
CPython 分代 GC 是 STW 单线程,gen2 全堆扫描 O(存活对象数),大堆可达百毫秒。先 `gc.set_debug(gc.DEBUG_STATS)`/`gc.callbacks` 计时确认;治:调大阈值换峰值内存、确定无环批处理 `gc.disable()`、fork 型服务 `gc.freeze()` 防 CoW 写脏(Instagram:关分代 GC + freeze,容量 +10%)。

**Q10. 什么是永生对象(immortal objects)?解决什么问题?**
3.12(PEP 683)把 None/True/小整数等 refcount 冻结为哨兵值、增减跳过。解决「读也会写」:refcount 抖动把 CoW 共享页写脏、并在 free-threading 下要求原子操作。永生后共享页保持干净,为无 GIL 铺路。
```

- [ ] **Step 2: ch16 心智句与对照框微调**

- 「一句话心智」句尾追加:`;而回收只回到 CPython 自己的分配器(pymalloc),不等于还给 OS`。
- Java/Go 对照框加一行:`| 对象搬家/压缩 | 分代搬家+压缩 | 不搬(非分代) | 从不搬家,无压缩,靠 pymalloc 复用 |`。

- [ ] **Step 3: 99 速查 +2**

`python/99-interview-cards.md`「并发 / 内部(第 13、15 章)」节(改标题为「第 13、15、16 章」)追加:

```markdown
- **del 了 RSS 不降?** refcount 归零只还到 pymalloc/free list,不还 OS;arena 高水位+对象不搬家无压缩;判泄漏对照 tracemalloc。｜pymalloc/RSS
- **GC 造成 P99 尖峰?** gen2 全堆 STW 扫描 O(存活对象);调阈值/无环批处理 disable/fork 前 freeze 防 CoW。｜GC 调优
```

- [ ] **Step 4: ch16 ↔ 06a/03 互指分工声明**

ch16 开头引言(现 L5 段落)追加一句:

```markdown
本章讲**机制**;生产内存**排查工具链**(tracemalloc/objgraph/Memray)在 [`../performance-tuning-roadmap/06a-python-profiling/02`](../performance-tuning-roadmap/06a-python-profiling/02-python-memory-analysis.md),GC 的**排查视角与 PyPy 差异**在 [`同目录 03`](../performance-tuning-roadmap/06a-python-profiling/03-cpython-gc.md)。
```

`06a/03-cpython-gc.md` 概述后加:

```markdown
> 本文是**排查视角**的 GC 速查(工具操作、禁用场景、PyPy 差异);机制层的系统教学(对象头、pymalloc/RSS、GIL 与 free-threading)见 [`python/16`](../../python/16-objects-memory-gc-gil.md)。
```

- [ ] **Step 5: Commit(三文件一次)**

```bash
git add python/16-objects-memory-gc-gil.md python/99-interview-cards.md performance-tuning-roadmap/06a-python-profiling/03-cpython-gc.md && git commit -m "docs: ch16 面试卡+3、99 速查同步、ch16↔06a 分工互指" -- python/16-objects-memory-gc-gil.md python/99-interview-cards.md performance-tuning-roadmap/06a-python-profiling/03-cpython-gc.md
```

---

### Task 6: 全文校验

**Files:**
- Modify: 如发现问题,修上述文件

- [ ] **Step 1: 节号与内链**

```bash
grep -n '^## \|§[0-9一-九]' python/16-objects-memory-gc-gil.md
```
Expected: 节号一~九连续;正文 § 引用全部指向正确节(逐个人工核对,重点:收口地图框、为什么慢四根因、L32)。

- [ ] **Step 2: 相对链接存在性**

```bash
grep -oE '\]\([^)]+\.md[^)]*\)' python/16-objects-memory-gc-gil.md performance-tuning-roadmap/06a-python-profiling/03-cpython-gc.md | sed 's/.*(\(.*\))/\1/' | sed 's/#.*//' | sort -u
```
逐个确认文件存在(在各自目录相对路径下 `ls`)。

- [ ] **Step 3: 数字一致性**

正文中 arena/pool/512B/RSS 五行/immortal 值,逐个与 scratchpad 三份 txt 对照。凭记忆写的数字 = bug。

- [ ] **Step 4: 通读流畅度**

从 §一读到章末卡:新增三块(PEP 683、生产视角+收口地图、§五)与旧文衔接是否自然;「一句话心智」是否仍然成立;卡片 Q1-Q10 无与正文矛盾处。发现问题就地修。

- [ ] **Step 5: 如有修改,commit**

```bash
git add python/16-objects-memory-gc-gil.md python/99-interview-cards.md performance-tuning-roadmap/06a-python-profiling/03-cpython-gc.md && git commit -m "docs: ch16 内存/GC 补强校验修订" -- python/16-objects-memory-gc-gil.md python/99-interview-cards.md performance-tuning-roadmap/06a-python-profiling/03-cpython-gc.md
```
