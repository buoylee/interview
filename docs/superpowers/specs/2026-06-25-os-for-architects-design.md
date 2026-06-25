# `os-for-architects/` — OS 原语 → 架构决策（薄镜头·指进深矿）

> **设计日期**：2026-06-25
> **状态**：已批准，待写实现计划
> **语言**：简体中文（与直接父课 `linux-handson/` 及主要被指向的 `concurrency-capacity/` 一致；如需改繁体在实现前提出）

---

## 1. 背景与动机

学习者从 `fastapi-ops/02`（系统指标速查手册）入门时撞墙：`us/sy/wa` 这类字段读不懂，感觉术语多、要背。诊断结论：**不是内容缺口，是入口/顺序问题** —— 仓库里已有为他量身定做的 OS 课 `linux-handson/`（机制·能答·能排查），以及 `performance-tuning-roadmap/00-os-fundamentals`（资深性能深度）。`fastapi-ops/02` 的入口已接回 `linux-handson`（本次已修）。

剩下唯一真实的内容缺口：现有两套 OS 内容教的是**资深 = 能答 = 反应式**（出问题能解释、能排查）；缺一层**架构师 = 能设计 = 预判式**（写代码/定架构之前，用 OS 约束反推设计决策）。这层的"砖"散落在 `concurrency-capacity/`、`perf-roadmap/11-architecture`、`12-container`、`system-design/` 里，**没有统一在"OS 原语"镜头下**。

本 track 补这层镜头。**核心约束：薄。它不重教机制、不重推容量数学、不建新 lab，只教"反射"并指进深矿。** 这是防止与现有深内容重复的硬契约。

## 2. 定位与差异化（防重复硬契约）

**一句话定位**：把"看到 OS 原语 → 反射出架构决策"这个资深→架构师的思维跃迁，做成一张薄地图；每个决策点不展开，用指针指进深矿。

它在课程拓扑里的位置：

```
              os-for-architects   ← 本 track：机制 → 设计决策（薄·全资源·横切）
                    ▲ 坐在其上
              linux-handson       ← 机制·能答·能排查（含 lab）
                    ▲
        00-os-fundamentals        ← 资深性能机制深度
```

与最容易混淆的 `concurrency-capacity` 的边界（必须守住）：

| | `concurrency-capacity` | **`os-for-architects`（本 track）** |
|---|---|---|
| 形状 | 一根轴挖到底 | 五种资源各挖一铲 |
| 轴 | 容量/并发（单轴） | CPU/内存/存储/网络/隔离（全资源） |
| 深度 | 完整 Little 数学 + lab | 只教"反射"+指针；容量推导**指向 cc** |
| 海拔 | 深而窄 | 薄而广 |

**重复检测规则**：写每一章时，凡涉及"完整推导/机制细节/可跑实验"，一律改为一句反射 + 指针，不在本 track 展开。Review 时按此规则逐段检查。

## 3. 章节地图（对镜 linux-handson，7 章 + 面试卡）

| # | 章 | 对镜 lh | 下指（机制层） | 横指（深决策矿） |
|---|---|---|---|---|
| 00 | **镜头**：资深(能答)→架构师(能设计) + 统一反射模板 + 全资源总览 | — | — | — |
| 01 | 调度/CPU → **并发模型与容量** | 03 进程 | lh/03 · os-fund/01 | cc/01·02·04 |
| 02 | 虚存/内存 → **内存预算与缓存层** | 04 内存 | lh/04 · os-fund/02 | perf-11/01 · perf-12/01 · sd/06 |
| 03 | 存储 IO → **持久化与引擎选型** | 05 IO | lh/05 · os-fund/03 | sd/06·07 · perf-11/04 |
| 04 | 网络/连接 → **连接模型与容量** | 06 网络 | lh/06 · os-fund/04a·04b | cc/05·07 · perf-11/02·03 · sd/04 |
| 05 | 隔离/cgroup → **多租户与隔离设计** | 09 容器 | lh/09 | cc/06 · perf-12 · sd/08 |
| 06 | **综合 capstone**：一道设计题串起五条资源决策线 | — | — | 指 system-design-scenarios |
| 99 | **面试卡**："OS→设计"高频题速答（能答→能设计两层） | — | — | — |

路径缩写：`lh`=`linux-handson`，`os-fund`=`performance-tuning-roadmap/00-os-fundamentals`，`cc`=`concurrency-capacity`，`perf-11`=`performance-tuning-roadmap/11-architecture`，`perf-12`=`.../12-container`，`sd`=`system-design`。所有路径在本设计阶段已核实存在。

## 4. 每章模板（薄·反射单元，6 小段）

每个资源章（01–05）统一用这 6 段，其中第 2 段是核心：

1. **盲点** —— 这资源上，你现在只会"事后解释"，架构师在"事前设计"，一句点破，给动机。
2. **原语 → 决策映射表（核心）** —— 三列：`OS 原语（你在 lh 学的机制） | 资深·能答（反应式） | 架构师·能设计（预判式决策）`。这是全章主体。
3. **定量锚点（1–2 个）** —— 这资源最该有的"用数字定参数"反射：给反射式公式 + 一个例子；**完整推导指向 cc/perf**，本章不展开。
4. **决策清单 & 反模式** —— 设计这资源时该问自己的几个问题 + 经典错误决策（拍脑袋值、容器配错等）。
5. **指针** —— 下指机制（lh / os-fund）、横指深矿（cc / perf / sd），用相对路径。
6. **面试转化** —— 这资源在架构/系统设计面试怎么被问，怎么从"能答"答出"能设计"。

00（镜头）与 06（capstone）、99（面试卡）不套此模板，见下。

## 5. 各章内容大纲（实现时的填充指引）

### 00 镜头
- 资深(能答/反应式) vs 架构师(能设计/预判式) 的根本差别（一张对照）。
- 统一反射模板：对任何 OS 原语都问"它在设计期逼出什么决策"。
- 五资源 + 隔离 总览地图。
- 怎么用这门课：下配 `linux-handson`（先打机制地基），横配 cc/perf/sd（钻深决策）。

### 01 调度/CPU → 并发模型与容量
- 原语：上下文切换成本、CFS 公平/throttling、核数、用户态 vs 内核态。
- 映射样例：`cs 高→线程开太多` ⟶ 用核数+Little 反推线程池/worker 上限；`CPU 密集 vs IO 密集` ⟶ 选并发模型（线程/协程/多进程）与运行时；`CFS quota` ⟶ 容器 CPU limit 的 throttling 陷阱（P99）；`NUMA` ⟶ 大进程绑核绑节点。
- 定量锚点：线程数 ≈ 核数 ÷ (1−阻塞占比) 类反射；并发=吞吐×延迟（Little）→ 指 cc/01。
- 反模式：拍脑袋线程池 200；容器只设 limit 不设 request；忽略 throttling。

### 02 虚存/内存 → 内存预算与缓存层
- 原语：虚存/RSS/VSZ、page cache、缺页、swap、OOMKill、cgroup memory。
- 映射样例：`swap 了→内存不够` ⟶ 容器 memory limit 留余量（堆外+page cache）、避免 OOMKill 设计；`page cache` ⟶ 当"免费缓存层"用，读密集架构靠它；`GC↔page fault` ⟶ 大堆绑 NUMA、限堆别和 cache 抢；`RSS 只增` ⟶ 设计期内存预算与监控。
- 定量锚点：容器内存预算 = 堆 + 堆外 + 栈×线程数 + page cache 余量。
- 反模式：limit=堆大小（必 OOM）；忽略 page cache 被算进 RSS/cgroup；关 swap 不留余量。

### 03 存储 IO → 持久化与引擎选型
- 原语：顺序 vs 随机、fsync/fdatasync、page cache 回写、IO 调度、D 状态阻塞。
- 映射样例：`await 高→盘慢` ⟶ 顺序 vs 随机决定引擎（LSM vs B+树）与日志结构；`fsync 语义` ⟶ 持久化 vs 吞吐权衡（DB/MQ 的 acks、组提交）；`WAL/顺序写` ⟶ 把随机写转顺序写的架构手法；`page cache 命中` ⟶ 容量假设、direct IO 何时用。
- 定量锚点：IOPS/带宽预算 vs 需求（含读写放大）。
- 反模式：每次写都 fsync；用随机 IO 当顺序估容量；忽略写放大。

### 04 网络/连接 → 连接模型与容量
- 原语：连接=fd+内存+队列、TCP 状态机、TIME_WAIT/端口耗尽、epoll/reactor、backlog/syn queue、零拷贝。
- 映射样例：`CLOSE_WAIT/TIME_WAIT` ⟶ 连接池、长连 vs 短连、复用；`C10K` ⟶ epoll/reactor vs 线程每连接；`backlog/accept queue` ⟶ 容量与限流/背压设计；`端口耗尽` ⟶ 客户端连接池、源端口规划；`零拷贝/sendfile` ⟶ 高吞吐传输架构。
- 定量锚点：连接池大小=Little（并发=QPS×延迟）→ 指 cc/05；fd 上限规划。
- 反模式：每请求新建连接；池子拍脑袋；不设超时致连接堆积。

### 05 隔离/cgroup → 多租户与隔离设计
- 原语：namespaces（隔离视图）+ cgroups（限资源）= 容器本质、limit/request、QoS、CFS throttling、st（超卖）。
- 映射样例：`被 throttle` ⟶ limit/request 设计、QoS 分级；`noisy neighbor` ⟶ 资源隔离、bulkhead 隔板、独占 vs 共享；`st 高` ⟶ 超卖认知、关键服务独占/绑核；`故障传播` ⟶ 隔离边界设计（线程池隔离、连接隔离）。
- 定量锚点：request=稳态、limit=峰值的余量反射。
- 反模式：只设 limit 不设 request；关键和批处理混部；忽略 throttling。

### 06 综合 capstone
- 一道设计题（如"设计一个支撑 X QPS 的订单查询服务"），走五条资源决策线：CPU 定并发 → 内存定预算 → 存储定引擎 → 网络定连接池 → 隔离定部署。
- 把前五章的反射串成一次完整设计推演；末尾指向 `system-design-scenarios` 的整机装配线做更系统的场景训练。

### 99 面试卡
- "OS→设计"高频题，每题给"能答 → 能设计"两层答法。示例题：你怎么定线程池/连接池大小？容器 limit/request 怎么设？为什么用长连接？顺序写 vs 随机写对存储选型的影响？怎么避免 noisy neighbor？容器为什么会被 OOMKill？

## 6. 放哪 / 名字 / 篇幅

- **新顶层目录 `os-for-architects/`**（坐 `linux-handson` 之上，与 `concurrency-capacity` 正交）。含 `README.md`（master 索引，讲清定位/差异化/对镜关系/怎么用）+ 7 章 + `99-interview-cards/`。
- **篇幅·薄**：每个资源章 ~200–350 行，主体是映射表 + 指针 + 面试转化；00/06/99 可更短。
- 总 **~7 章 + 面试卡**。

## 7. 写作约束（YAGNI / 不做什么）

- **不重教机制**：OS 机制细节是 `linux-handson`/`os-fund` 的活，本 track 只引用 + 指针。
- **不重推数学**：Little 定律等完整推导指 `cc`，本 track 只给反射式公式 + 一例。
- **不建新 lab**：动手实验指 `linux-handson` 的 lab 与 `cc/lab`，本 track 是纯阅读薄 spine。
- **指针必须准**：用相对路径指向实际存在的章节文件。
- **面试导向**：每个资源章必须有"面试转化"段，把决策能力翻译成面试答法。

## 8. 成功标准（DoD）

- 读完能对任意一个 OS 原语反射出"它在设计期逼出什么架构决策"。
- 五个资源各能在架构/系统设计面试里，从"能答"答出"能设计"。
- 每个决策点都能顺指针找到对应深矿（路径有效）。
- 全 track 不与 `linux-handson`（机制）/ `cc`（容量数学）/ `perf` / `sd` 重复展开，只做镜头 + 索引：随机抽 3 段检查，均应是"反射 + 指针"而非"展开教学"。

## 9. 待实现时确认的小项

- 00/06 是否需要各自的子目录还是单文件（倾向：每章一个子目录含 `README.md`，对镜 `linux-handson` 结构）。
- capstone 06 的设计题选型（订单查询服务 vs 其他），实现时定一个即可。
