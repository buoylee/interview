# Performance Roadmap Interview Tracks Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the performance tuning roadmap into a senior-interview-ready training system with one shared core loop, three interview tracks, an explicit lab maturity contract, and seniority rubrics.

**Architecture:** Add four focused navigation/standards documents under `performance-tuning-roadmap/`, then make small linking and wording updates to the top-level roadmap, learning guide, and capstone README. Existing technical articles remain the source of detailed implementation knowledge; new documents organize them by interview readiness and runnable lab maturity.

**Tech Stack:** Markdown documentation, existing repository structure, shell verification with `rg`, `sed`, and `git diff`.

---

## File Structure

- Create: `performance-tuning-roadmap/LAB-CONTRACT.md`
  - Owns P0/P1/P2 lab maturity definitions and exercise status labels.
- Create: `performance-tuning-roadmap/SENIOR-RUBRIC.md`
  - Owns junior/mid/senior/Staff performance answer standards.
- Create: `performance-tuning-roadmap/TRACKS.md`
  - Owns Backend Senior, SRE / Platform, and Staff / Tech Lead learning paths.
- Create: `performance-tuning-roadmap/INTERVIEW-MATRIX.md`
  - Owns scenario-to-skill mapping for senior performance interviews.
- Modify: `performance-tuning-roadmap.md`
  - Add interview-oriented entry links and correct P0/P1/P2 positioning.
- Modify: `performance-tuning-roadmap/LEARNING-GUIDE.md`
  - Add interview-goal learning guidance and checkpoint artifact expectations.
- Modify: `performance-tuning-roadmap/14-capstone/README.md`
  - Add track-specific graduation standards.

---

### Task 1: Add Lab Contract

**Files:**
- Create: `performance-tuning-roadmap/LAB-CONTRACT.md`

- [ ] **Step 1: Create the lab contract document**

Use `apply_patch` to add `performance-tuning-roadmap/LAB-CONTRACT.md` with this structure and content:

~~~markdown
# PerfShop 实验契约

> 目标：明确哪些实验当前可以直接运行，哪些需要手工补环境，哪些属于目标态示例，避免学习者把路线图中的完整 PerfShop 设想误解为当前仓库已经全部实现。

## 1. 为什么需要实验契约

这套路线上有两类内容：

- 当前仓库已经提供的最小可运行实验。
- 用来说明目标能力的完整生产级场景。

两者都重要，但用途不同。学习者应该先用当前可运行的 P0 完成闭环，再逐步扩展到 P1 和 P2。

## 2. 实验成熟度

| 层级 | 状态 | 目标 | 当前说明 |
|------|------|------|----------|
| P0 | 当前可运行 | 单服务、MySQL、Prometheus、Grafana、wrk/Locust、3 类故障注入 | 已在 `labs/perfshop-p0/` 提供 |
| P1 | 后续扩展 | Redis、Kafka、Tracing、日志聚合、更多故障注入 | 文档可先描述目标，练习需标注环境要求 |
| P2 | 目标态 | Java / Go / Python 三语言同构 PerfShop，多服务链路和完整 runtime 对比 | 用于路线终局设计，不应写成当前 P 阶段必需 |

## 3. 练习状态标签

后续新增或修订练习时，建议在练习标题或说明中标注：

| 标签 | 含义 | 学习者动作 |
|------|------|------------|
| `Runnable now` | 当前仓库可直接运行 | 按文档命令执行并记录结果 |
| `Runnable with manual setup` | 需要学习者先安装工具、改配置或准备服务 | 先完成前置条件，再执行练习 |
| `Target-state example` | 用于展示完整生产场景或未来 PerfShop 形态 | 重点学习排查思路，不假设当前仓库可直接运行 |

## 4. 当前 P0 能力

当前 `labs/perfshop-p0/` 提供：

- Python 标准库 HTTP 服务。
- MySQL 商品表和可制造慢查询的数据。
- Prometheus 指标暴露。
- Grafana datasource provisioning。
- wrk 和 Locust 压测脚本。
- 慢 SQL、CPU 热点、下游等待三类故障开关。

P0 的完成标准是学习者能走完：

```text
压测 -> 观测 -> 假设 -> 证据 -> 定位 -> 修复或关闭故障 -> 复测 -> 记录
```

## 5. P1 扩展目标

P1 应优先补齐会显著提高排查训练价值的组件：

- Redis 慢命令和大 Key。
- OpenTelemetry Trace 和 Jaeger。
- 日志聚合或至少结构化日志关联 TraceID。
- 连接池耗尽。
- 下游超时和重试风暴。
- Kafka consumer lag 或等价消息积压场景。

P1 的完成标准是学习者可以证明单点问题如何放大成跨组件延迟或错误率上升。

## 6. P2 扩展目标

P2 才承担完整三语言 PerfShop：

- Java 服务覆盖 JVM、GC、线程、连接池、Netty 或 Web 框架调优。
- Go 服务覆盖 pprof、goroutine、runtime、net/http 或 gRPC 调优。
- Python 服务覆盖 GIL、asyncio、FastAPI/Django、py-spy、tracemalloc。
- 三语言提供同构业务接口，便于同一问题在不同 runtime 下对比。

P2 的完成标准是学习者能解释同一性能问题在不同语言 runtime 下的诊断差异。

## 7. 写作规则

- 不把 P2 目标态写成阶段 P 的硬性前置。
- 所有新练习都要说明运行状态标签。
- 目标态示例可以保留，但要明确它训练的是思路、机制和面试表达。
- 当前可运行命令必须指向仓库真实存在的目录或文件。
~~~

- [ ] **Step 2: Verify the file exists and has the required labels**

Run:

```bash
rg -n "Runnable now|Runnable with manual setup|Target-state example|P0|P1|P2" performance-tuning-roadmap/LAB-CONTRACT.md
```

Expected: output includes all three labels and all three maturity levels.

- [ ] **Step 3: Commit**

Run:

```bash
git add performance-tuning-roadmap/LAB-CONTRACT.md
git commit -m "docs: add performance lab contract"
```

Expected: commit succeeds with one new file.

---

### Task 2: Add Senior Rubric

**Files:**
- Create: `performance-tuning-roadmap/SENIOR-RUBRIC.md`

- [ ] **Step 1: Create the seniority rubric document**

Use `apply_patch` to add `performance-tuning-roadmap/SENIOR-RUBRIC.md` with this structure and content:

~~~markdown
# 资深性能面试评分标准

> 目标：帮助学习者判断自己的回答是否达到资深工程师水平，而不是只停留在会背工具名或会跑命令。

## 1. 四档能力定义

| 档位 | 典型表现 | 面试风险 |
|------|----------|----------|
| 初级 | 知道工具名和部分概念 | 容易把排查说成命令清单 |
| 中级 | 能按 checklist 逐步排查 | 能定位常见问题，但解释机制和验证较弱 |
| 资深 | 能提出可证伪假设、拿证据、解释机制、排除替代原因、量化验证 | 面试中需要把过程讲清楚 |
| Staff | 能设计长期治理、容量模型、风险控制、发布策略和组织改进 | 如果只讲单点修复，会显得不像 Staff |

## 2. 通用评分维度

| 维度 | 初级 | 中级 | 资深 | Staff |
|------|------|------|------|-------|
| 现象识别 | 复述“接口慢” | 能区分错误率、吞吐、延迟 | 能识别 P50/P95/P99、基线和影响面 | 能把现象映射到业务风险和 SLO |
| 假设构建 | 直接猜根因 | 列出几个可能方向 | 每个假设都说明因果机制和证据需求 | 能设计分层排查策略和优先级 |
| 工具选择 | 说出工具名 | 能选择常见工具 | 能说明为什么用这个工具、能排除什么 | 能推动工具链和平台化能力建设 |
| 机制解释 | 解释片段概念 | 能讲清单个组件机制 | 能串起 OS/runtime/框架/业务链路 | 能解释架构级 trade-off 和长期演进 |
| 修复方案 | 提出单个改动 | 能给出直接修复 | 能区分缓解、修复、回滚和副作用 | 能给出 rollout、容量、治理和 owner 机制 |
| 验证复盘 | 说“再测一下” | 能复测核心指标 | 能量化前后对比并说明成功标准 | 能沉淀 guardrail、runbook、告警和流程 |

## 3. 资深回答必须包含的 6 个元素

一个资深回答至少要包含：

1. 明确现象和影响面。
2. 给出按层次推进的排查路径。
3. 为主要假设列出证据。
4. 解释根因发生机制。
5. 区分缓解、修复和长期预防。
6. 给出验证指标和复盘动作。

## 4. 示例：P99 延迟突然升高

### 初级回答

“看一下日志，再用 top 看 CPU，如果数据库慢就加索引。”

问题：没有基线、没有分位数分析、没有假设验证，也没有说明为什么是数据库。

### 中级回答

“先看 Grafana 的 QPS、错误率、P99，再看 CPU、内存、数据库慢查询。如果慢查询增加，用 EXPLAIN 分析索引。”

优点：有基本路径。缺口：没有说明如何排除 GC、网络、连接池、下游依赖，也没有验证策略。

### 资深回答

“我会先确认 P99 升高是否伴随 QPS 或错误率变化，并和最近发布、流量变化对齐时间线。然后从 RED 看服务入口，从 USE 看主机资源。如果入口 QPS 没变但 P99 抖动，我会同时检查 GC pause、连接池 pending、慢查询、下游 span 和网络重传。每个假设都有对应证据：GC 看 pause 时间和慢请求时间相关性，连接池看 active/pending/timeout，数据库看 slow log 和 EXPLAIN，分布式调用看 Trace 的慢 span。修复后用同样压测或生产窗口对比 P95/P99、错误率、资源饱和度，确认不是把瓶颈转移到下游。”

优点：有现象、假设、证据、机制、验证和风险意识。

### Staff 回答

“除了完成这次排查，我会把它沉淀成 SLO 触发后的 runbook，补齐 P99、连接池 pending、慢查询、GC pause、下游错误率的联合 dashboard。若根因是容量或架构问题，需要建立容量模型、压测基线、发布性能门禁和降级策略。复盘里明确 owner、预防动作和验收指标，避免同类问题只靠个人经验排查。”

优点：从单次排查上升到系统治理。

## 5. 使用方式

- 学完一个阶段后，用本 rubric 检查回答是否只有工具名。
- 做 capstone 时，用 6 个元素组织报告。
- 准备面试时，把每个高频场景都练到“资深回答”标准。
~~~

- [ ] **Step 2: Verify rubric levels and required elements**

Run:

```bash
rg -n "初级|中级|资深|Staff|6 个元素|P99" performance-tuning-roadmap/SENIOR-RUBRIC.md
```

Expected: output includes all four levels, required-elements section, and the P99 example.

- [ ] **Step 3: Commit**

Run:

```bash
git add performance-tuning-roadmap/SENIOR-RUBRIC.md
git commit -m "docs: add senior performance interview rubric"
```

Expected: commit succeeds with one new file.

---

### Task 3: Add Interview Tracks

**Files:**
- Create: `performance-tuning-roadmap/TRACKS.md`

- [ ] **Step 1: Create the tracks document**

Use `apply_patch` to add `performance-tuning-roadmap/TRACKS.md` with this structure and content:

~~~markdown
# 性能调优面试 Track

> 目标：在共享核心闭环之上，为 Backend Senior、SRE / Platform、Staff / Tech Lead 三类面试目标提供不同学习路径。

## 1. 共同起点

所有 track 都先完成最小闭环：

```text
P -> 1 -> 2 核心工具 -> 3 Prometheus/Grafana -> 3.5 -> 主语言 profiling -> 7 -> 9a -> 10 -> 14 一个场景
```

最小产物：

- 一份 P0 压测记录。
- 一张 RED dashboard 或 Prometheus 查询证据。
- 一份 profile、慢查询或 trace 证据。
- 一份性能排查记录。

## 2. Backend Senior Track

### 适合人群

- 目标是资深后端工程师。
- 日常负责 Java、Go 或 Python 服务。
- 面试重点是线上排查、runtime、数据库、缓存、分布式调用。

### 必学

| 模块 | 原因 |
|------|------|
| 0 OS 基础 | 解释 CPU、内存、I/O、网络现象 |
| 1 方法论 | 建立假设和证据链 |
| 2 Linux 工具 | 做第一轮主机定位 |
| 3 可观测性 | 从 RED 和 Trace 进入问题 |
| 主语言 4a/4b 或 5a/5b 或 6a/6b | runtime 和代码级瓶颈 |
| 7 压测 | 证明优化效果 |
| 8 网络与 I/O | 处理连接、丢包、TLS、超时 |
| 9a 数据库 | 慢 SQL、索引、事务、连接池 |
| 9b 中间件 | Redis、MQ 高频问题 |
| 10 分布式 | 超时、重试、降级、链路瓶颈 |
| 14 综合实战 | 面试叙事训练 |

### 可暂缓

- 12 容器与云原生性能：如果目标公司不是 K8s 强相关，可以先学 cgroup 和 OOMKilled。
- 13 SRE：先掌握 SLI/SLO、事故复盘和容量规划基础。

### 4 周版本

```text
P0 -> 1 -> 2 -> 3.5 -> 主语言 profiling -> 7 -> 9a -> 10 -> 14
```

### 8 周版本

```text
P0 -> 0 -> 1 -> 2 -> 3 -> 3.5 -> 主语言完整路径 -> 7 -> 8 -> 9a -> 9b -> 10 -> 14
```

### 12 周版本

```text
8 周版本 + 11 架构级优化 + 12 容器基础 + 13 SLO/容量/复盘
```

### Capstone 产物

- 一份完整排查报告。
- 至少一份 runtime 证据。
- 至少一份数据库或分布式链路证据。
- 一段能在面试中 5 分钟讲完的排查故事。

## 3. SRE / Platform Track

### 适合人群

- 目标是 SRE、平台工程、基础设施或稳定性岗位。
- 面试重点是观测体系、容量、告警、K8s、事故响应。

### 必学

| 模块 | 原因 |
|------|------|
| P0 | 建立可复现实验入口 |
| 0 OS 基础 | 理解资源瓶颈 |
| 1 方法论 | 统一排查语言 |
| 2 Linux 工具 | 主机和容器节点定位 |
| 3 可观测性 | Prometheus、Grafana、Trace、告警 |
| 7 压测 | 容量和回归验证 |
| 8 网络与 I/O | 处理网络、TLS、丢包 |
| 10 分布式 | 处理级联故障和降级 |
| 12 容器与云原生 | cgroup、K8s、Service Mesh 开销 |
| 13 SRE | SLI/SLO、容量规划、事故和复盘 |
| 14 综合实战 | 告警到复盘的闭环 |

### 可暂缓

- 三门语言 runtime 全量学习：先掌握主语言 profiling 入口和 runtime 指标。
- 11 架构：按容量规划和降级需要选学。

### 4 周版本

```text
P0 -> 1 -> 2 -> 3 -> 3.5 -> 7 -> 10 -> 13/01 -> 13/04 -> 14
```

### 8 周版本

```text
P0 -> 0 -> 1 -> 2 -> 3 -> 7 -> 8 -> 10 -> 12 -> 13 -> 14
```

### 12 周版本

```text
8 周版本 + 9a/9b 高频数据组件 + 11 容量相关架构 + chaos 演练
```

### Capstone 产物

- 一份 SLO breach 调查报告。
- 一份告警规则或 dashboard 说明。
- 一份容量估算。
- 一份事故响应和复盘记录。

## 4. Staff / Tech Lead Track

### 适合人群

- 目标是 Staff Engineer、Tech Lead 或架构负责人。
- 面试重点是系统性、权衡、治理、容量、风险控制和跨团队推动。

### 必学

| 模块 | 原因 |
|------|------|
| 1 方法论 | 建立组织统一排查语言 |
| 3 可观测性 | 建立可观测性标准 |
| 7 压测 | 建立容量和性能基线 |
| 9a/9b | 数据层和中间件风险治理 |
| 10 分布式 | 超时、重试、降级体系 |
| 11 架构级性能优化 | 设计级性能权衡 |
| 12 容器与云原生 | 平台资源模型和成本 |
| 13 SRE | SLO、容量、事故、复盘 |
| 14 综合实战 | 系统治理方案表达 |

### 可暂缓

- 单语言所有工具细节：至少精通主语言，其他语言掌握风险模型和诊断入口。
- 单个命令的使用细节：面试重点是如何建立机制和验证系统性改进。

### 4 周版本

```text
1 -> 3 -> 7 -> 10 -> 11 -> 13 -> 14 Staff 场景
```

### 8 周版本

```text
P0 -> 1 -> 2 核心工具 -> 3 -> 7 -> 9a/9b -> 10 -> 11 -> 12 核心 -> 13 -> 14
```

### 12 周版本

```text
8 周版本 + 主语言 runtime 深入 + 多组件 capstone + 性能治理设计文档
```

### Capstone 产物

- 一份性能治理 proposal。
- 一份容量模型。
- 一份分阶段 rollout 和回滚策略。
- 一份 SLO、告警、压测门禁和复盘机制说明。

## 5. 如何选择

| 你的目标 | 首选 track |
|----------|------------|
| 面试资深业务后端 | Backend Senior |
| 面试 SRE、平台、基础设施 | SRE / Platform |
| 面试 Staff、TL、架构负责人 | Staff / Tech Lead |
| 不确定 | 先走 Backend Senior 的 4 周版本，再补 SRE 的 3/7/13 |
~~~

- [ ] **Step 2: Verify all tracks and time boxes exist**

Run:

```bash
rg -n "Backend Senior|SRE / Platform|Staff / Tech Lead|4 周版本|8 周版本|12 周版本|Capstone" performance-tuning-roadmap/TRACKS.md
```

Expected: output includes all three tracks, all three time boxes, and capstone sections.

- [ ] **Step 3: Commit**

Run:

```bash
git add performance-tuning-roadmap/TRACKS.md
git commit -m "docs: add performance interview tracks"
```

Expected: commit succeeds with one new file.

---

### Task 4: Add Interview Matrix

**Files:**
- Create: `performance-tuning-roadmap/INTERVIEW-MATRIX.md`

- [ ] **Step 1: Create the interview matrix document**

Use `apply_patch` to add `performance-tuning-roadmap/INTERVIEW-MATRIX.md` with this structure and content:

~~~markdown
# 性能面试能力矩阵

> 目标：把路线中的章节映射到真实面试场景，帮助学习者从“我学了哪些章节”转换成“我能处理哪些性能问题”。

## 1. 使用方法

每个场景按同一结构训练：

- 先识别现象。
- 再给出第一轮排查路径。
- 然后说明证据和工具。
- 最后讲清机制、修复、验证和相关章节。

面试中不要只报工具名。好的回答要说明为什么这个工具能验证或推翻某个假设。

## 2. 场景矩阵

| 场景 | 先看什么 | 核心证据 | 需要解释的机制 | 相关章节 |
|------|----------|----------|----------------|----------|
| 接口慢 / P99 抖动 | RED、发布和流量时间线 | P95/P99、Trace、GC pause、连接池 pending | 平均值掩盖长尾、排队放大、下游等待 | 1、3、7、10、14 |
| CPU 高 | load、CPU user/system、热点线程 | `top -H`、`mpstat`、`pidstat`、profile | 用户态计算、系统调用、软中断、调度等待 | 0、2、4/5/6 |
| 内存泄漏 / OOM | RSS、heap、off-heap、容器限制 | heap dump、NMT、pprof heap、tracemalloc、dmesg | heap 与 RSS 区别、GC 可达性、cgroup OOM | 0、4a/4b、5a/5b、6a/6b、12 |
| GC / runtime pause | 延迟尖刺和 pause 时间相关性 | GC log、JFR、runtime metrics | STW、对象晋升、分配速率、collector trade-off | 4a、5a、6a |
| 慢 SQL | DB 耗时和慢查询占比 | slow log、EXPLAIN、rows examined、buffer pool | 索引选择、回表、锁等待、执行计划 | 9a |
| 锁等待 / 死锁 | 线程堆积和事务等待 | InnoDB status、performance_schema、thread dump | 隔离级别、行锁、间隙锁、等待图 | 9a、4b |
| Redis 慢命令 / 大 Key | Redis latency、命中率、内存 | SLOWLOG、`--bigkeys`、INFO MEMORY | 单线程事件循环、数据结构复杂度、内存碎片 | 9b、11 |
| Kafka consumer lag | lag 增长和消费吞吐 | consumer group lag、rebalance、partition skew | 分区、批量、offset、rebalance 风暴 | 9b、10 |
| 连接池耗尽 | pending、timeout、active=max | HikariCP metrics、DB connections、thread dump | 池大小、下游容量、请求排队、泄漏 | 9a、11 |
| 下游超时 / 重试风暴 | Trace 和下游错误率 | retry count、QPS 放大、timeout config | 超时预算、指数退避、抖动、幂等 | 10、13 |
| 网络丢包 / TLS | 重传、握手耗时、连接错误 | tcpdump、Wireshark、ss、mtr | TCP 重传、拥塞控制、TLS 握手和会话复用 | 8、0 |
| K8s throttling / OOMKilled | container CPU/memory 和事件 | cgroup 指标、kubectl describe、cadvisor | CFS quota、request/limit、QoS、OOM killer | 12 |
| 容量规划 / SLO | 当前基线和目标流量 | 压测曲线、error budget、QPS/P99 拐点 | Little 定律、排队论、SLO 与成本权衡 | 1、7、13 |

## 3. 场景训练模板

```text
场景：
现象：
影响面：
第一假设：
需要证据：
使用工具：
排除项：
根因机制：
缓解动作：
长期修复：
验证指标：
相关章节：
```

## 4. 示例：连接池耗尽

### 现象

接口 P99 从 100ms 上升到 3s，错误率开始出现少量 5xx，数据库 CPU 不高。

### 排查路径

1. 先看入口 RED，确认 P99 和错误率变化。
2. 看应用线程和连接池指标：active、idle、pending、timeout。
3. 看数据库连接数是否接近上限。
4. 用 thread dump 确认是否大量线程卡在获取连接。
5. 检查是否存在连接泄漏或下游 SQL 变慢导致连接持有时间变长。

### 证据

- `hikaricp.connections.active` 持续等于 max。
- `hikaricp.connections.pending` 大于 0。
- `hikaricp.connections.timeout` 增长。
- thread dump 中大量线程等待 `getConnection`。

### 机制

连接池耗尽不一定表示池太小。更常见的是查询变慢、事务过长或连接泄漏导致连接持有时间增长。连接持有时间增长会让请求排队，排队会放大 P99。

### 修复和验证

- 短期：降低超时时间，限流或降级非核心请求。
- 中期：修复慢 SQL、连接泄漏或事务边界。
- 长期：给连接池 pending、timeout、active/max 建告警。
- 验证：P99、错误率、pending、timeout 回到基线。

## 5. 面试使用建议

- 每个场景准备一个 3 分钟回答和一个 8 分钟深挖版本。
- 3 分钟版本强调路径和证据。
- 8 分钟版本补机制、权衡、验证、复盘。
~~~

- [ ] **Step 2: Verify scenario coverage**

Run:

```bash
rg -n "接口慢|CPU 高|OOM|GC|慢 SQL|Redis|Kafka|连接池|重试风暴|K8s|容量规划" performance-tuning-roadmap/INTERVIEW-MATRIX.md
```

Expected: output includes all listed interview scenarios.

- [ ] **Step 3: Commit**

Run:

```bash
git add performance-tuning-roadmap/INTERVIEW-MATRIX.md
git commit -m "docs: add performance interview matrix"
```

Expected: commit succeeds with one new file.

---

### Task 5: Update Top-Level Roadmap Entry Points

**Files:**
- Modify: `performance-tuning-roadmap.md`

- [ ] **Step 1: Add interview positioning after the opening quote block**

Find the first quote block near the top of `performance-tuning-roadmap.md`. Add this section after the existing positioning and principle paragraphs:

```markdown
> **面试目标**：这套路线上可以服务三类目标：资深后端工程师、SRE / 平台工程师、Staff / Tech Lead。所有学习者先完成同一个性能排查核心闭环，再按目标岗位进入不同 track。

### 面试导向入口

| 文件 | 解决的问题 |
|------|------------|
| [TRACKS.md](./performance-tuning-roadmap/TRACKS.md) | Backend Senior / SRE / Staff 三条学习路径怎么选 |
| [INTERVIEW-MATRIX.md](./performance-tuning-roadmap/INTERVIEW-MATRIX.md) | 高频性能面试场景需要哪些能力和证据 |
| [LAB-CONTRACT.md](./performance-tuning-roadmap/LAB-CONTRACT.md) | 哪些实验当前可运行，哪些属于目标态示例 |
| [SENIOR-RUBRIC.md](./performance-tuning-roadmap/SENIOR-RUBRIC.md) | 什么样的回答算资深或 Staff 水平 |
```

- [ ] **Step 2: Correct stage P wording in the route diagram and navigation**

Replace wording that says stage P requires a complete three-language demo with P0-first wording.

Use `rg` first:

```bash
rg -n "三语言 Demo|三语言版本都跑起来|三语言 Demo 服务|全部跑通" performance-tuning-roadmap.md
```

Then update the affected lines so the meaning is:

```markdown
阶段P 实践环境搭建（P0 最小可运行闭环；P2 再扩展为三语言 PerfShop）
```

and:

```markdown
| P | 搭建 P0 最小环境，先跑通一个可观测服务 |
```

and:

```markdown
| **P** | [实践环境搭建](./performance-tuning-roadmap/P-lab-setup/) | 2 | Docker Compose 监控栈 / P0 最小 PerfShop 闭环 |
```

- [ ] **Step 3: Update the detailed stage P description**

In `阶段 P：实践环境搭建`, replace the sentence that says all three language services must run with:

```markdown
**学完能做什么**：一条命令拉起最小实验环境，至少跑通一个 HTTP 服务、Prometheus 指标和 Grafana 观测入口。完整 Java / Go / Python 三语言 PerfShop 属于 P2 目标态，不是阶段 P 的完成前置。
```

Update the file table entry for `02-perfshop-demo.md` to:

```markdown
| 02-perfshop-demo.md | PerfShop 作为贯穿项目的目标架构 / P0 单服务闭环 / P1 多组件扩展 / P2 Java + Go + Python 三语言同构目标 |
```

Update the exercise list so it starts with one service:

```markdown
1. `docker compose up -d` 启动 P0 环境，确认 Grafana 或 Prometheus 有数据
2. 用 curl 请求一个 PerfShop 商品查询接口，确认返回正常
3. 在后续 P1/P2 阶段再补 Trace、Redis、Kafka 和三语言同构服务
```

- [ ] **Step 4: Verify links and removed ambiguity**

Run:

```bash
rg -n "TRACKS.md|INTERVIEW-MATRIX.md|LAB-CONTRACT.md|SENIOR-RUBRIC.md|P0|P1|P2" performance-tuning-roadmap.md
rg -n "三语言 Demo 服务全部跑通|三语言版本都跑起来" performance-tuning-roadmap.md
```

Expected: first command finds new links and P0/P1/P2 wording. Second command prints no output.

- [ ] **Step 5: Commit**

Run:

```bash
git add performance-tuning-roadmap.md
git commit -m "docs: align performance roadmap with interview tracks"
```

Expected: commit succeeds with only `performance-tuning-roadmap.md` modified.

---

### Task 6: Update Learning Guide For Interview Goals

**Files:**
- Modify: `performance-tuning-roadmap/LEARNING-GUIDE.md`

- [ ] **Step 1: Add interview-goal route guidance after Section 2**

After `## 2. 三层学习路线`, add:

```markdown
## 2.4 按面试目标选择路线

所有学习者先完成 P0 最小闭环，然后按目标选择 track：

| 面试目标 | 推荐入口 | 学习重点 |
|----------|----------|----------|
| 资深后端工程师 | [TRACKS.md](./TRACKS.md) 的 Backend Senior Track | runtime、数据库、缓存、连接池、分布式调用 |
| SRE / 平台工程师 | [TRACKS.md](./TRACKS.md) 的 SRE / Platform Track | 可观测性、容量、K8s、告警、事故响应 |
| Staff / Tech Lead | [TRACKS.md](./TRACKS.md) 的 Staff / Tech Lead Track | 架构权衡、性能治理、容量模型、跨团队落地 |

如果目标不确定，先走 Backend Senior 的 4 周版本，因为它最贴近日常服务排查；之后补 SRE 的可观测性、容量和事故复盘能力。
```

- [ ] **Step 2: Add interview artifact expectations after checkpoint section**

After `## 4. 阶段检查点`, add:

```markdown
## 4.6 面试化产物要求

每个 checkpoint 的产物都要能转化成面试表达：

| Checkpoint | 面试化产物 | 面试中要讲清楚 |
|------------|------------|----------------|
| 方法论成型 | 一份 USE/RED 排查记录 | 如何从现象提出假设，而不是直接猜根因 |
| 观测闭环 | 一张 dashboard 或 PromQL 证据 | 哪个指标异常，为什么它支持某个假设 |
| 主语言排查 | 一份 profile、火焰图或 runtime 证据 | 热点、等待或 GC 的机制是什么 |
| 生产场景排查 | 一份数据库、中间件或 Trace 分析 | 根因、诱因、放大器分别是什么 |
| 完整闭环 | 一份报告或复盘 | 如何修复、验证、回滚和预防复发 |

回答是否达到资深水平，使用 [SENIOR-RUBRIC.md](./SENIOR-RUBRIC.md) 自检。
```

- [ ] **Step 3: Verify guide links and artifact section**

Run:

```bash
rg -n "按面试目标选择路线|面试化产物要求|TRACKS.md|SENIOR-RUBRIC.md" performance-tuning-roadmap/LEARNING-GUIDE.md
```

Expected: output includes the new section titles and links.

- [ ] **Step 4: Commit**

Run:

```bash
git add performance-tuning-roadmap/LEARNING-GUIDE.md
git commit -m "docs: add interview learning guidance"
```

Expected: commit succeeds with only `LEARNING-GUIDE.md` modified.

---

### Task 7: Add Track-Specific Capstone Standards

**Files:**
- Modify: `performance-tuning-roadmap/14-capstone/README.md`

- [ ] **Step 1: Add graduation standards after the main stage purpose**

After the opening paragraph in `performance-tuning-roadmap/14-capstone/README.md`, add:

```markdown
## 面试 Track 毕业标准

同一个 capstone 可以按不同面试目标产出不同材料：

| Track | 必须证明的能力 | 最低产物 |
|-------|----------------|----------|
| Backend Senior | 能从服务现象定位到 runtime、数据库或分布式根因，并量化修复效果 | 完整排查报告、profile/slow query/trace 证据、优化前后对比 |
| SRE / Platform | 能从 SLO 或告警出发完成响应、缓解、容量判断和复盘 | SLO breach 分析、告警或 dashboard 证据、容量估算、复盘记录 |
| Staff / Tech Lead | 能把单次性能问题上升为系统治理方案 | 性能治理 proposal、容量模型、rollout/rollback 方案、长期 guardrail |

如果只做第 0 轮最小闭环，至少完成 Backend Senior 的最低产物；如果准备 SRE 或 Staff 面试，需要把同一问题扩展到 SLO、容量、发布风险和组织改进。
```

- [ ] **Step 2: Add rubric link near self-assessment section**

In the section that mentions self-assessment, add:

```markdown
自测题完成后，用 [../SENIOR-RUBRIC.md](../SENIOR-RUBRIC.md) 判断回答是否达到资深或 Staff 标准。
```

- [ ] **Step 3: Verify capstone track standards**

Run:

```bash
rg -n "面试 Track 毕业标准|Backend Senior|SRE / Platform|Staff / Tech Lead|SENIOR-RUBRIC.md" performance-tuning-roadmap/14-capstone/README.md
```

Expected: output includes all track names and the rubric link.

- [ ] **Step 4: Commit**

Run:

```bash
git add performance-tuning-roadmap/14-capstone/README.md
git commit -m "docs: add capstone interview standards"
```

Expected: commit succeeds with only `14-capstone/README.md` modified.

---

### Task 8: Final Documentation Verification

**Files:**
- Read: all files changed in Tasks 1-7.

- [ ] **Step 1: Verify all new documents are linked from the roadmap**

Run:

```bash
rg -n "TRACKS.md|INTERVIEW-MATRIX.md|LAB-CONTRACT.md|SENIOR-RUBRIC.md" performance-tuning-roadmap.md performance-tuning-roadmap/LEARNING-GUIDE.md performance-tuning-roadmap/14-capstone/README.md
```

Expected: top-level roadmap links all four documents; learning guide links tracks and rubric; capstone links rubric.

- [ ] **Step 2: Verify no old P-stage ambiguity remains in the top-level roadmap**

Run:

```bash
rg -n "三语言 Demo 服务全部跑通|三语言版本都跑起来|三语言 Demo 服务" performance-tuning-roadmap.md
```

Expected: no output. If output remains, update that line to P0/P1/P2 phased wording.

- [ ] **Step 3: Verify exercise-status labels are defined once**

Run:

```bash
rg -n "Runnable now|Runnable with manual setup|Target-state example" performance-tuning-roadmap
```

Expected: at minimum, labels appear in `LAB-CONTRACT.md`.

- [ ] **Step 4: Review final diff**

Run:

```bash
git diff --stat HEAD~7..HEAD
git log --oneline -7
```

Expected: seven documentation commits exist, covering four new docs and three existing-doc updates.

- [ ] **Step 5: Final read-through**

Run:

```bash
sed -n '1,220p' performance-tuning-roadmap/TRACKS.md
sed -n '1,220p' performance-tuning-roadmap/INTERVIEW-MATRIX.md
sed -n '1,220p' performance-tuning-roadmap/LAB-CONTRACT.md
sed -n '1,220p' performance-tuning-roadmap/SENIOR-RUBRIC.md
```

Expected: each file has one clear responsibility, no contradictory claims about current lab readiness, and no duplicated long technical tutorials.

---

## Self-Review Checklist

- Spec coverage:
  - `TRACKS.md` covers the three interview tracks.
  - `INTERVIEW-MATRIX.md` covers scenario-to-skill mapping.
  - `LAB-CONTRACT.md` covers P0/P1/P2 and runnable labels.
  - `SENIOR-RUBRIC.md` covers junior/mid/senior/Staff answer standards.
  - Existing docs link to the new navigation layer.
- Placeholder scan:
  - The implementation should not introduce unfinished markers or vague future-work wording.
- Scope control:
  - Do not add new technical tutorial chapters.
  - Do not implement Java/Go/Python PerfShop.
  - Do not rewrite existing 45K+ lines of content.
