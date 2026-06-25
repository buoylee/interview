# `os-for-architects/` Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 写一个薄镜头文档 track `os-for-architects/`，把"OS 原语 → 架构决策"这个资深→架构师的思维跃迁做成索引式 spine，指进现有深矿而不重写。

**Architecture:** 7 章 + 面试卡，每章一个子目录含 `README.md`，对镜 `linux-handson/` 03–06 结构。坐在 `linux-handson`（机制）之上，横向指向 `concurrency-capacity`/`performance-tuning-roadmap`/`system-design`（深决策）。纯阅读，无代码、无 lab。

**Tech Stack:** Markdown（简体中文）。验证用 shell（`test -e` 查指针、`grep` 查模板段、`wc -l` 查篇幅）。

## Global Constraints

- **语言**：简体中文（对镜 `linux-handson`）。
- **薄·防重复硬契约**：不重教 OS 机制、不重推容量数学、不建新 lab。凡涉及"完整推导/机制细节/可跑实验"，一律改为一句反射 + 指针。
- **篇幅**：每个资源章（01–05）`README.md` 控制在 ~200–350 行；00/06/99 可更短（~120–250 行）。
- **指针准确**：所有指向深矿的链接用**相对路径**（从 `os-for-architects/NN-xxx/README.md` 出发即 `../../<target>`），且目标文件必须真实存在。
- **每个资源章必须有"面试转化"段**：把决策能力翻译成"能答→能设计"两层面试答法。
- **新目录**：`os-for-architects/`，与 `concurrency-capacity` 正交。
- **提交**：用显式路径 `git add <path>`（仓库有并发 agent 跑 `git add -A` 的陷阱），stage+commit 同一调用原子完成，提交到 `main`。每个 commit 末尾加 `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`。

**路径缩写**（在文档里写成 `../../` 相对路径；下表给的是仓库根相对路径，供验证用）：
- `lh` = `linux-handson`（03-process-model / 04-memory-model / 05-io-and-files / 06-networking / 07-troubleshooting-playbook / 09-containers-from-linux）
- `os-fund` = `performance-tuning-roadmap/00-os-fundamentals`（01-cpu-architecture-scheduling.md / 02-memory-management.md / 03-disk-io-filesystem.md / 04a-network-tcp-core.md / 04b-network-socket-kernel.md / 05-process-thread-coroutine.md）
- `cc` = `concurrency-capacity`（01-littles-law / 02-concurrency-models / 04-sizing-one-node / 05-pools / 06-isolation / 07-overload-backpressure）
- `perf-11` = `performance-tuning-roadmap/11-architecture`（01-caching-strategy.md / 02-connection-pooling.md / 03-async-reactive.md / 04-database-architecture.md）
- `perf-12` = `performance-tuning-roadmap/12-container`（01-cgroup-resource.md / 02-k8s-performance.md）
- `sd` = `system-design`（04-服務化與通信範式.md / 06-存儲選型.md / 07-數據規模化-分庫分表與讀寫分離.md / 08-可用性與容災-RPO-RTO.md）
- `sds` = `system-design-scenarios`

**目录与文件结构（决策已锁定）：**

```
os-for-architects/
  README.md                         # master 索引：定位/差异化/对镜地图/怎么用
  00-the-lens/README.md             # 镜头：资深(能答)→架构师(能设计) + 统一反射模板
  01-cpu-and-scheduling/README.md   # 调度/CPU → 并发模型与容量
  02-memory-and-paging/README.md    # 虚存/内存 → 内存预算与缓存层
  03-storage-io/README.md           # 存储 IO → 持久化与引擎选型
  04-network-and-connections/README.md  # 网络/连接 → 连接模型与容量
  05-isolation-and-cgroups/README.md    # 隔离/cgroup → 多租户与隔离设计
  06-capstone-design/README.md      # 综合：一道设计题串五条资源决策线
  99-interview-cards/README.md      # 面试卡："OS→设计"高频题（能答→能设计）
```

**资源章统一 6 段模板**（01–05 每章必须含这 6 个 `##` 段，标题用于验证 grep）：
1. `## 一、盲点` —— 这资源上你现在只会"事后解释"，架构师在"事前设计"，一句点破。
2. `## 二、原语 → 决策映射表` —— 三列表：`OS 原语 | 资深·能答(反应式) | 架构师·能设计(预判式)`。全章主体。
3. `## 三、定量锚点` —— 1–2 个"用数字定参数"反射：反射式公式 + 一例；完整推导指 cc/perf。
4. `## 四、决策清单 & 反模式` —— 设计这资源该问自己几个问题 + 经典错误决策。
5. `## 五、指针` —— 下指机制（lh / os-fund）、横指深矿（cc / perf / sd），相对路径。
6. `## 六、面试转化` —— 这资源在架构面试怎么被问，怎么从"能答"答出"能设计"。

---

### Task 1: 脚手架 + master README 索引

建目录骨架并写 `README.md`（front door，定义全 track 的定位/防重复契约/对镜地图/怎么用）。这是其它章引用的"接口"，必须先做。

**Files:**
- Create: `os-for-architects/README.md`

**Interfaces:**
- Produces: 全 track 的定位框架、差异化契约、对镜地图、章节清单 —— 后续每章的"怎么用/指针约定"都引用本文。

- [ ] **Step 1: 写 `os-for-architects/README.md`**

必须包含这些块：
- **一句话定位**："把『看到 OS 原语 → 反射出架构决策』这个资深→架构师的思维跃迁，做成一张薄地图；每个决策点不展开，指进深矿。"
- **课程拓扑图**（坐 `linux-handson` 之上、横指深矿），用代码块画：
  ```
  os-for-architects   ← 本 track：机制→设计决策（薄·全资源·横切）
        ▲ 坐在其上
  linux-handson       ← 机制·能答·能排查（含 lab）
        ▲
  00-os-fundamentals  ← 资深性能机制深度
  ```
- **与 `concurrency-capacity` 的差异化表**（防重复硬契约），逐字含这 4 行对比：形状（一根轴挖到底 vs 五种资源各挖一铲）、轴（容量/并发单轴 vs 全资源）、深度（完整 Little 数学+lab vs 只教反射+指针、容量指向 cc）、海拔（深而窄 vs 薄而广）。
- **章节地图表**：00–06 + 99，每行列出"章 / 对镜 lh / 横指深矿"。
- **怎么用本课**：下配 `linux-handson`（先打机制地基，指 `../linux-handson/`），横配 cc/perf/sd（钻深决策）；并提示"看不懂字段先回 `linux-handson/03→07`"。
- **薄契约声明**：本 track 不重教机制/不重推数学/不建 lab。

- [ ] **Step 2: 创建其余章节占位目录**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview
mkdir -p os-for-architects/{00-the-lens,01-cpu-and-scheduling,02-memory-and-paging,03-storage-io,04-network-and-connections,05-isolation-and-cgroups,06-capstone-design,99-interview-cards}
ls -d os-for-architects/*/
```
Expected: 列出 8 个子目录。

- [ ] **Step 3: 验证 README 里的相对指针解析**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects
for p in ../linux-handson ../concurrency-capacity ../performance-tuning-roadmap/00-os-fundamentals; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 4: 验证篇幅**

Run: `wc -l os-for-architects/README.md`
Expected: 50–150 行。

- [ ] **Step 5: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/README.md && git commit -m "docs(os-for-architects): master README — 定位/防重复契约/对镜地图

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: 00 镜头（the lens）

写"资深→架构师"思维跃迁本身 + 统一反射模板。这是后续 5 个资源章共享的"读法"。

**Files:**
- Create: `os-for-architects/00-the-lens/README.md`

**Interfaces:**
- Consumes: Task 1 的定位框架。
- Produces: "统一反射模板"（任何 OS 原语都问『它在设计期逼出什么决策』）—— 01–05 章的第二段映射表都是它的实例化。

- [ ] **Step 1: 写 `00-the-lens/README.md`**

必须含：
- **资深 vs 架构师 对照**：能答/反应式（出问题能解释、能排查）vs 能设计/预判式（写代码/定架构前用 OS 约束反推决策）。给一张并排对照。
- **统一反射模板**：拿到任一 OS 原语 → 问三件事：①它在运行期表现成什么指标（反应式，linux-handson 教）②它在设计期约束了什么（预判式）③这约束逼出哪个具体决策 + 怎么定量。
- **五资源 + 隔离 总览地图**：CPU/调度、虚存/内存、存储 IO、网络/连接、隔离/cgroup，每个一行"原语→典型决策"。
- **怎么配套**：下打地基 `../../linux-handson/`，深挖容量去 `../../concurrency-capacity/`。

- [ ] **Step 2: 验证指针解析**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects/00-the-lens
for p in ../../linux-handson ../../concurrency-capacity; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 3: 验证篇幅**

Run: `wc -l os-for-architects/00-the-lens/README.md`
Expected: 120–250 行。

- [ ] **Step 4: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/00-the-lens/README.md && git commit -m "docs(os-for-architects/00): 镜头 — 资深(能答)→架构师(能设计)统一反射模板

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: 01 调度/CPU → 并发模型与容量

**Files:**
- Create: `os-for-architects/01-cpu-and-scheduling/README.md`

**Interfaces:**
- Consumes: Task 2 的反射模板（6 段）。

- [ ] **Step 1: 写章节，按 6 段模板。具体必含内容：**

**二、原语→决策映射表**（至少这 4 行）：

| OS 原语 | 资深·能答（反应式） | 架构师·能设计（预判式） |
|---|---|---|
| 上下文切换有成本 | "cs 高 → 线程开太多" | 用核数 + Little 反推线程池/worker 上限，定容量而非拍脑袋 |
| CPU 密集 vs IO 密集 | "us 高 / wa 高" | 据此选并发模型（线程/协程/多进程）与运行时 |
| CFS quota 限流 | "被 throttle 了" | 容器 CPU limit 的 throttling 陷阱（拉爆 P99）→ 设 request/limit |
| NUMA 跨节点延迟 | "numastat 跨节点多" | 大内存进程绑核绑节点 |

**三、定量锚点**：线程数 ≈ 核数 ÷ (1 − 阻塞占比)（CPU 密集→≈核数）；并发 = 吞吐 × 延迟（Little）—— 完整推导指 `../../concurrency-capacity/01-littles-law/` 与 `04-sizing-one-node/`。

**四、决策清单 & 反模式**：反模式至少 3 条 —— 拍脑袋线程池 200；容器只设 limit 不设 request；忽略 CFS throttling 对延迟的影响。

**五、指针**：下指 `../../linux-handson/03-process-model/`、`../../performance-tuning-roadmap/00-os-fundamentals/01-cpu-architecture-scheduling.md`；横指 `../../concurrency-capacity/01-littles-law/`、`02-concurrency-models/`、`04-sizing-one-node/`。

**六、面试转化**（至少 2 题，含"能答→能设计"两层）："你怎么定线程池大小？"、"为什么线程不是越多越好？"。

- [ ] **Step 2: 验证 6 段齐全**

Run:
```bash
grep -c "^## " os-for-architects/01-cpu-and-scheduling/README.md
```
Expected: ≥ 6。

- [ ] **Step 3: 验证指针目标存在**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects/01-cpu-and-scheduling
for p in ../../linux-handson/03-process-model ../../performance-tuning-roadmap/00-os-fundamentals/01-cpu-architecture-scheduling.md ../../concurrency-capacity/01-littles-law ../../concurrency-capacity/02-concurrency-models ../../concurrency-capacity/04-sizing-one-node; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 4: 验证篇幅**

Run: `wc -l os-for-architects/01-cpu-and-scheduling/README.md`
Expected: 200–350 行。

- [ ] **Step 5: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/01-cpu-and-scheduling/README.md && git commit -m "docs(os-for-architects/01): 调度/CPU → 并发模型与容量

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: 02 虚存/内存 → 内存预算与缓存层

**Files:**
- Create: `os-for-architects/02-memory-and-paging/README.md`

**Interfaces:**
- Consumes: Task 2 的反射模板。

- [ ] **Step 1: 写章节，按 6 段模板。具体必含内容：**

**二、映射表**（至少 4 行）：

| OS 原语 | 资深·能答 | 架构师·能设计 |
|---|---|---|
| swap / OOMKill | "swap 了 → 内存不够" | 容器 memory limit 留余量（堆外 + page cache）、避免 OOMKill 设计 |
| page cache 可回收 | "available 还够" | 把 page cache 当"免费缓存层"，读密集架构靠它 |
| GC ↔ page fault | "缺页多 / GC 久" | 大堆绑 NUMA、限堆别和 cache 抢内存 |
| RSS 只增 | "可能泄漏" | 设计期就定内存预算 + 监控基线 |

**三、定量锚点**：容器内存预算 = 堆 + 堆外 + 栈 × 线程数 + page cache 余量。

**四、反模式**（≥3）：limit = 堆大小（必 OOM）；忽略 page cache 被算进 cgroup RSS；关 swap 又不留余量。

**五、指针**：下指 `../../linux-handson/04-memory-model/`、`../../performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md`；横指 `../../performance-tuning-roadmap/11-architecture/01-caching-strategy.md`、`../../performance-tuning-roadmap/12-container/01-cgroup-resource.md`、`../../system-design/06-存儲選型.md`。

**六、面试转化**（≥2）："容器 memory limit 怎么设？"、"page cache 算不算你的内存？"

- [ ] **Step 2: 验证 6 段齐全**

Run: `grep -c "^## " os-for-architects/02-memory-and-paging/README.md`
Expected: ≥ 6。

- [ ] **Step 3: 验证指针目标存在**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects/02-memory-and-paging
for p in ../../linux-handson/04-memory-model ../../performance-tuning-roadmap/00-os-fundamentals/02-memory-management.md ../../performance-tuning-roadmap/11-architecture/01-caching-strategy.md ../../performance-tuning-roadmap/12-container/01-cgroup-resource.md ../../system-design/06-存儲選型.md; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 4: 验证篇幅**

Run: `wc -l os-for-architects/02-memory-and-paging/README.md`
Expected: 200–350 行。

- [ ] **Step 5: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/02-memory-and-paging/README.md && git commit -m "docs(os-for-architects/02): 虚存/内存 → 内存预算与缓存层

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: 03 存储 IO → 持久化与引擎选型

**Files:**
- Create: `os-for-architects/03-storage-io/README.md`

**Interfaces:**
- Consumes: Task 2 的反射模板。

- [ ] **Step 1: 写章节，按 6 段模板。具体必含内容：**

**二、映射表**（至少 4 行）：

| OS 原语 | 资深·能答 | 架构师·能设计 |
|---|---|---|
| 顺序 IO ≫ 随机 IO | "await 高 → 盘慢" | 顺序 vs 随机决定引擎选型（LSM vs B+树）与日志结构 |
| fsync/fdatasync 语义 | "fsync 阻塞" | 持久化 vs 吞吐权衡（DB/MQ 的 acks、组提交） |
| 顺序写最快 | —— | WAL：把随机写转顺序写的架构手法 |
| page cache 回写 | "脏页回刷" | page cache 命中率作为容量假设；direct IO 何时用 |

**三、定量锚点**：IOPS/带宽预算 vs 需求（含读写放大）。

**四、反模式**（≥3）：每次写都 fsync；用随机 IO 当顺序估容量；忽略写放大。

**五、指针**：下指 `../../linux-handson/05-io-and-files/`、`../../performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md`；横指 `../../system-design/06-存儲選型.md`、`../../system-design/07-數據規模化-分庫分表與讀寫分離.md`、`../../performance-tuning-roadmap/11-architecture/04-database-architecture.md`。

**六、面试转化**（≥2）："顺序写 vs 随机写怎么影响存储选型？"、"acks/fsync 怎么权衡？"

- [ ] **Step 2: 验证 6 段齐全**

Run: `grep -c "^## " os-for-architects/03-storage-io/README.md`
Expected: ≥ 6。

- [ ] **Step 3: 验证指针目标存在**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects/03-storage-io
for p in ../../linux-handson/05-io-and-files ../../performance-tuning-roadmap/00-os-fundamentals/03-disk-io-filesystem.md ../../system-design/06-存儲選型.md ../../system-design/07-數據規模化-分庫分表與讀寫分離.md ../../performance-tuning-roadmap/11-architecture/04-database-architecture.md; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 4: 验证篇幅**

Run: `wc -l os-for-architects/03-storage-io/README.md`
Expected: 200–350 行。

- [ ] **Step 5: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/03-storage-io/README.md && git commit -m "docs(os-for-architects/03): 存储 IO → 持久化与引擎选型

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: 04 网络/连接 → 连接模型与容量

**Files:**
- Create: `os-for-architects/04-network-and-connections/README.md`

**Interfaces:**
- Consumes: Task 2 的反射模板。

- [ ] **Step 1: 写章节，按 6 段模板。具体必含内容：**

**二、映射表**（至少 4 行）：

| OS 原语 | 资深·能答 | 架构师·能设计 |
|---|---|---|
| 连接 = fd + 内存 + 队列 | "CLOSE_WAIT/TIME_WAIT 多" | 连接池、长连 vs 短连、复用 |
| epoll/reactor | "C10K" | 事件循环/reactor vs 线程每连接的选型 |
| backlog/accept queue | "队列满丢连接" | 容量与限流/背压设计 |
| 端口/fd 上限 | "端口耗尽" | 客户端连接池、源端口规划、fd ulimit 规划 |

**三、定量锚点**：连接池大小 = Little（并发 = QPS × 延迟）—— 完整推导指 `../../concurrency-capacity/05-pools/`；每连接 1 fd → fd 上限规划。

**四、反模式**（≥3）：每请求新建连接；连接池拍脑袋；不设超时致连接堆积。

**五、指针**：下指 `../../linux-handson/06-networking/`、`../../performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md`、`04b-network-socket-kernel.md`；横指 `../../concurrency-capacity/05-pools/`、`07-overload-backpressure/`、`../../performance-tuning-roadmap/11-architecture/02-connection-pooling.md`、`03-async-reactive.md`、`../../system-design/04-服務化與通信範式.md`。

**六、面试转化**（≥2）："连接池大小怎么定？"、"为什么用长连接？TIME_WAIT 堆积怎么设计避免？"

- [ ] **Step 2: 验证 6 段齐全**

Run: `grep -c "^## " os-for-architects/04-network-and-connections/README.md`
Expected: ≥ 6。

- [ ] **Step 3: 验证指针目标存在**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects/04-network-and-connections
for p in ../../linux-handson/06-networking ../../performance-tuning-roadmap/00-os-fundamentals/04a-network-tcp-core.md ../../performance-tuning-roadmap/00-os-fundamentals/04b-network-socket-kernel.md ../../concurrency-capacity/05-pools ../../concurrency-capacity/07-overload-backpressure ../../performance-tuning-roadmap/11-architecture/02-connection-pooling.md ../../performance-tuning-roadmap/11-architecture/03-async-reactive.md ../../system-design/04-服務化與通信範式.md; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 4: 验证篇幅**

Run: `wc -l os-for-architects/04-network-and-connections/README.md`
Expected: 200–350 行。

- [ ] **Step 5: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/04-network-and-connections/README.md && git commit -m "docs(os-for-architects/04): 网络/连接 → 连接模型与容量

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: 05 隔离/cgroup → 多租户与隔离设计

**Files:**
- Create: `os-for-architects/05-isolation-and-cgroups/README.md`

**Interfaces:**
- Consumes: Task 2 的反射模板。

- [ ] **Step 1: 写章节，按 6 段模板。具体必含内容：**

**二、映射表**（至少 4 行）：

| OS 原语 | 资深·能答 | 架构师·能设计 |
|---|---|---|
| namespaces + cgroups = 容器 | "容器只是受限进程" | limit/request 设计、QoS 分级 |
| CFS throttling | "被 throttle" | 关键服务别只设 limit；据峰值/稳态定 request |
| noisy neighbor | "邻居吵" | 资源隔离、bulkhead 隔板、独占 vs 共享 |
| st（被偷的 CPU） | "宿主超卖" | 关键服务独占/绑核、避开超卖；故障传播边界设计 |

**三、定量锚点**：request = 稳态用量、limit = 峰值 + 余量。

**四、反模式**（≥3）：只设 limit 不设 request；关键服务和批处理混部；忽略 throttling。

**五、指针**：下指 `../../linux-handson/09-containers-from-linux/`；横指 `../../concurrency-capacity/06-isolation/`、`../../performance-tuning-roadmap/12-container/01-cgroup-resource.md`、`02-k8s-performance.md`、`../../system-design/08-可用性與容災-RPO-RTO.md`。

**六、面试转化**（≥2）："怎么避免 noisy neighbor？"、"limit/request 怎么设？容器为什么被 OOMKill？"

- [ ] **Step 2: 验证 6 段齐全**

Run: `grep -c "^## " os-for-architects/05-isolation-and-cgroups/README.md`
Expected: ≥ 6。

- [ ] **Step 3: 验证指针目标存在**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects/05-isolation-and-cgroups
for p in ../../linux-handson/09-containers-from-linux ../../concurrency-capacity/06-isolation ../../performance-tuning-roadmap/12-container/01-cgroup-resource.md ../../performance-tuning-roadmap/12-container/02-k8s-performance.md ../../system-design/08-可用性與容災-RPO-RTO.md; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 4: 验证篇幅**

Run: `wc -l os-for-architects/05-isolation-and-cgroups/README.md`
Expected: 200–350 行。

- [ ] **Step 5: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/05-isolation-and-cgroups/README.md && git commit -m "docs(os-for-architects/05): 隔离/cgroup → 多租户与隔离设计

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: 06 综合 capstone

**Files:**
- Create: `os-for-architects/06-capstone-design/README.md`

**Interfaces:**
- Consumes: Task 3–7 五个资源章的决策线。

- [ ] **Step 1: 写章节。不套 6 段模板，结构是一次设计推演：**

- 选一道设计题：**"设计一个支撑 5000 QPS、P99 < 100ms 的订单查询服务"**（题面固定，给出 QPS/延迟/数据量假设）。
- 按五条资源决策线逐步推：① CPU/调度 → 用 Little 定 worker/线程数；② 内存 → 定容器内存预算与 page cache 缓存策略；③ 存储 IO → 选引擎与索引、读写放大估算；④ 网络 → 定连接池大小、长连接、背压；⑤ 隔离 → request/limit 与部署拓扑。
- 每一步**回指对应资源章**（`../01-cpu-and-scheduling/` … `../05-isolation-and-cgroups/`）。
- 末尾指向 `../../system-design-scenarios/` 做更系统的场景训练。

- [ ] **Step 2: 验证指针目标存在**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects/06-capstone-design
for p in ../01-cpu-and-scheduling ../02-memory-and-paging ../03-storage-io ../04-network-and-connections ../05-isolation-and-cgroups ../../system-design-scenarios; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 3: 验证篇幅**

Run: `wc -l os-for-architects/06-capstone-design/README.md`
Expected: 150–300 行。

- [ ] **Step 4: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/06-capstone-design/README.md && git commit -m "docs(os-for-architects/06): capstone — 一道设计题串五条资源决策线

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: 99 面试卡

**Files:**
- Create: `os-for-architects/99-interview-cards/README.md`

**Interfaces:**
- Consumes: Task 3–7 的面试转化段。

- [ ] **Step 1: 写面试卡。每题给"能答 → 能设计"两层答法，覆盖五资源：**

至少含这些题（每题：一句能答 + 一句能设计 + 指针回对应章）：
- 你怎么定线程池/worker 大小？（→01）
- 容器 CPU limit/request 怎么设？为什么会被 throttle 拉爆 P99？（→01/05）
- 容器 memory limit 怎么设？page cache 算不算你的内存？为什么被 OOMKill？（→02/05）
- 顺序写 vs 随机写怎么影响存储引擎选型？acks/fsync 怎么权衡？（→03）
- 连接池大小怎么定？为什么用长连接？TIME_WAIT/端口耗尽怎么设计避免？（→04）
- 怎么避免 noisy neighbor？关键服务怎么隔离？（→05）

- [ ] **Step 2: 验证指针（回章）解析**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects/99-interview-cards
for p in ../01-cpu-and-scheduling ../02-memory-and-paging ../03-storage-io ../04-network-and-connections ../05-isolation-and-cgroups; do
  test -e "$p" && echo "OK $p" || echo "MISSING $p"
done
```
Expected: 全部 OK。

- [ ] **Step 3: 验证篇幅**

Run: `wc -l os-for-architects/99-interview-cards/README.md`
Expected: 120–250 行。

- [ ] **Step 4: Commit**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/99-interview-cards/README.md && git commit -m "docs(os-for-architects/99): 面试卡 — OS→设计 高频题(能答→能设计)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: 收口 —— 全 track 指针体检 + README 章节清单核对

**Files:**
- Modify: `os-for-architects/README.md`（如章节清单与实际不符则修正）

- [ ] **Step 1: 全 track 死链体检**

Run（扫所有 `../` 相对链接，逐一 `test -e`）:
```bash
cd /Users/buoy/Development/gitrepo/interview/os-for-architects
fail=0
while IFS=: read -r f link; do
  d=$(dirname "$f")
  target=$(cd "$d" 2>/dev/null && cd "$(dirname "$link")" 2>/dev/null && echo ok)
  if [ -e "$d/$link" ] || [ "$target" = ok ]; then :; else echo "DEAD $f -> $link"; fail=1; fi
done < <(grep -rno '\.\./[^) ]*' */README.md README.md | sed 's/:[0-9]*:/:/')
[ $fail -eq 0 ] && echo "ALL POINTERS OK"
```
Expected: `ALL POINTERS OK`（若有 DEAD，回对应章修正路径再提交）。

- [ ] **Step 2: 核对 README 章节清单与磁盘一致**

Run:
```bash
cd /Users/buoy/Development/gitrepo/interview
ls -d os-for-architects/*/ | sed 's#os-for-architects/##;s#/##'
```
Expected: 8 个目录名与 `README.md` 章节地图表逐一对应；不符则改 README。

- [ ] **Step 3: 防重复抽查（薄契约）**

人工抽 3 段（任选 3 个资源章的"映射表"以外段落），确认是"反射 + 指针"而非展开教机制/推数学。若发现展开，删减为一句 + 指针。

- [ ] **Step 4: Commit（若有修正）**

```bash
cd /Users/buoy/Development/gitrepo/interview
git add os-for-architects/README.md && git commit -m "docs(os-for-architects): 收口 — 指针体检 + 章节清单核对

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>" || echo "无需修正"
```

---

## Self-Review

**1. Spec coverage**（spec 各节 → 任务）：
- §2 定位与差异化契约 → Task 1（README 差异化表）✓
- §3 章节地图（00–06+99）→ Task 1 地图表 + Task 2–9 各章 ✓
- §4 每章 6 段模板 → Task 3–7 Step 1 + grep 验证 ✓
- §5 各章内容大纲 → Task 3–9 Step 1 逐章必含内容 ✓
- §6 放哪/名字/篇幅 → Task 1 目录结构 + 各 Task `wc -l` 验证 ✓
- §7 写作约束（不重教/不推数学/不建 lab）→ Global Constraints + Task 10 Step 3 抽查 ✓
- §8 DoD（指针有效、不重复）→ Task 10 全 track 体检 ✓
- §9 待确认小项（子目录 vs 单文件、capstone 题）→ 已锁定：每章子目录含 README；capstone = 订单查询服务（Task 8）✓

**2. Placeholder scan**：无 TBD/TODO；各章 Step 1 给了实际映射表行、锚点公式、反模式条目、精确指针路径、面试题面 —— 非占位。✓

**3. Type/路径一致性**：所有指针路径用 Global Constraints 缩写表的真实路径；目录名（`01-cpu-and-scheduling` 等）在结构图、各 Task Files、验证命令、capstone/面试卡回指中一致。✓
