# Elasticsearch Senior A/B Track Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add stage 12, a senior-level Elasticsearch A/B dual track covering senior backend production ownership and search-engineering/platform depth.

**Architecture:** Preserve stages 1-11 as the core backend-senior learning route. Add `elasticsearch/roadmap/12-senior-es-and-search-engineering/` as an additive stage with A-track production ownership, B-track search engineering depth, and synthesis case studies. Update existing chapters only with small senior-extension links so the current learning flow remains stable.

**Tech Stack:** Markdown documentation in this repository; verification with `rg`, `find`, `test`, `git diff --check`, and local link checks.

---

## File Structure

Create:

- `elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md`
  - Responsibility: stage 12 entry point, A/B track definitions, study orders, and document index.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/01-capacity-and-shard-sizing.md`
  - Responsibility: capacity models, shard sizing, rollover decisions, and interview answers.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md`
  - Responsibility: production topology, node roles, data tiers, and resource isolation.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md`
  - Responsibility: reliability design, SLOs, RPO/RTO, snapshot/restore, watermarks, and shard recovery.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/04-performance-diagnostics-playbook.md`
  - Responsibility: senior-level troubleshooting playbook for CPU, memory, rejections, breakers, hotspots, and queue backlogs.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/05-search-relevance-engineering.md`
  - Responsibility: B-track search quality, relevance tuning, query rewriting, and ranking evaluation.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md`
  - Responsibility: B-track Lucene execution mental models without requiring source-code study.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/07-hybrid-search-and-rerank.md`
  - Responsibility: BM25, vector retrieval, hybrid search, rerank pipeline, latency, and cost tradeoffs.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/08-search-platform-governance.md`
  - Responsibility: multi-tenant platform controls, query guardrails, relevance rollout, observability, and cost governance.
- `elasticsearch/roadmap/12-senior-es-and-search-engineering/09-senior-case-studies.md`
  - Responsibility: A+B interview case studies with requirements, constraints, design, risks, and narrative.

Modify:

- `elasticsearch/elasticsearch-roadmap.md`
  - Responsibility: add stage 12 to the overview, navigation table, learning flow, and stage list.
- `elasticsearch/roadmap/03-analysis/03-analysis.md`
  - Responsibility: add a small senior-extension link to relevance/synonym governance.
- `elasticsearch/roadmap/04-query-dsl/04-query-dsl.md`
  - Responsibility: add senior-extension links to relevance tuning and Lucene execution.
- `elasticsearch/roadmap/06-storage-internals/06-storage-internals.md`
  - Responsibility: add a senior-extension link to Lucene execution deep dive.
- `elasticsearch/roadmap/08-performance-tuning/08-performance-tuning.md`
  - Responsibility: add a senior-extension link to the diagnostics playbook.
- `elasticsearch/roadmap/10-production-advanced/10-production-advanced.md`
  - Responsibility: add senior-extension links to topology, data tiers, recovery, and SLO.
- `elasticsearch/roadmap/11-interview/01-internals-question-map.md`
  - Responsibility: add senior-extension links to stage 12 case studies and B-track follow-ups.

No automated tests are required because this is documentation-only work. Verification is file presence, required heading coverage, local-link sanity, no placeholder text, and `git diff --check`.

---

### Task 1: Stage 12 README

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md`

- [ ] **Step 1: Create the stage directory and README**

Create `elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md` with these sections and content:

```markdown
# 阶段 12：资深 ES 与搜索工程 A/B 双轨

> **目标**：把前 1-11 章的 ES 使用、原理、生产和面试能力提升到资深工程师层级。A 线面向 Java 后端资深工程师，强调生产治理；B 线面向搜索/ES 平台方向，强调搜索质量、Lucene 执行和平台治理。
>
> **前置依赖**：阶段 1-11。

## 为什么需要第 12 章

前 1-11 章解决的是“能系统学会 ES，并能讲清楚常见原理追问”。第 12 章解决的是“能以资深工程师视角负责 ES”：能做容量规划、能设计生产拓扑、能定义 SLO、能排查复杂故障、能解释架构取舍，也能继续深入搜索质量和搜索平台工程。

## A/B 双轨定义

| 轨道 | 面向目标 | ES 的角色 | 核心能力 |
| --- | --- | --- | --- |
| A 线：后端资深生产治理 | Java 后端资深工程师 | ES 是业务系统中的搜索视图和生产依赖 | 容量规划、shard sizing、ILM、故障恢复、SLO、数据同步、架构取舍 |
| B 线：搜索工程与平台深水区 | 搜索/推荐/ES 平台工程师 | 搜索本身是核心专业领域 | 搜索质量、相关性调优、Lucene 执行、hybrid search、rerank、多租户平台治理 |

## 推荐学习路径

### A only：Java 后端资深

```text
01 capacity and shard sizing
-> 02 production topology and data tiers
-> 03 failure recovery and SLO
-> 04 performance diagnostics playbook
-> 09 senior case studies 中的后端案例
```

### A + selected B：后端资深，同时补搜索工程加分项

```text
A only
-> 05 search relevance engineering
-> 07 hybrid search and rerank
-> 09 senior case studies 中的商品搜索和 hybrid search 案例
```

### Full A+B：搜索/ES 平台方向

```text
A only
-> 05 search relevance engineering
-> 06 Lucene query execution deep dive
-> 07 hybrid search and rerank
-> 08 search platform governance
-> 09 senior case studies 全量案例
```

## 文档导航

| 文件 | 轨道 | 解决的问题 |
| --- | --- | --- |
| [01-capacity-and-shard-sizing.md](./01-capacity-and-shard-sizing.md) | A core / B prerequisite | 数据、节点、shard、replica 如何一起规划 |
| [02-production-topology-and-data-tiers.md](./02-production-topology-and-data-tiers.md) | A core / B prerequisite | 生产集群如何拆角色、分层和隔离资源 |
| [03-failure-recovery-and-slo.md](./03-failure-recovery-and-slo.md) | A core / B prerequisite | ES 搜索能力如何定义可用性、恢复和告警 |
| [04-performance-diagnostics-playbook.md](./04-performance-diagnostics-playbook.md) | A core / B prerequisite | 高 CPU、高 heap、rejected、breaker、热点如何证据化排查 |
| [05-search-relevance-engineering.md](./05-search-relevance-engineering.md) | B core | 搜索质量、召回、排序、query rewrite、A/B test 如何设计 |
| [06-lucene-query-execution-deep-dive.md](./06-lucene-query-execution-deep-dive.md) | B core | Lucene 查询执行如何形成面试级心智模型 |
| [07-hybrid-search-and-rerank.md](./07-hybrid-search-and-rerank.md) | B core | BM25、向量、hybrid、rerank 如何组合 |
| [08-search-platform-governance.md](./08-search-platform-governance.md) | B core | 多租户搜索平台如何做 guardrail、隔离、观测和成本治理 |
| [09-senior-case-studies.md](./09-senior-case-studies.md) | A+B synthesis | 把资深能力转成系统设计和项目叙述 |

## 过关标准

学完 A 线后，你应该能：

- 解释一个业务搜索系统的容量模型和 shard 规划。
- 说明索引如何 rollover、如何进入不同数据层、如何恢复。
- 按证据排查查询慢、写入慢、heap 高、rejected、breaker、hot shard。
- 说明 ES 与 MySQL、Redis、Kafka、ClickHouse、对象存储的边界。

学完 B 线后，你还应该能：

- 设计搜索质量指标和相关性调优闭环。
- 解释 query rewrite、boost、function_score、rescore、rerank 的位置。
- 用面试级语言解释 Lucene 查询执行、Scorer、Collector、TopK、WAND 的直觉。
- 设计 BM25 + vector + rerank 的 hybrid search pipeline。
- 说明多租户搜索平台如何做限流、隔离、模板、观测和成本治理。
```

- [ ] **Step 2: Verify README**

Run:

```bash
test -f elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md
rg -n "^#|A 线|B 线|推荐学习路径|文档导航|过关标准" elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md
```

Expected: both commands succeed and print the stage 12 title, A/B track definitions, path sections, document navigation, and acceptance criteria.

- [ ] **Step 3: Commit Task 1**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md
git commit -m "Add Elasticsearch senior track README"
```

Expected: commit succeeds and includes only the README.

---

### Task 2: Capacity And Shard Sizing

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/01-capacity-and-shard-sizing.md`

- [ ] **Step 1: Create the capacity document**

Create `01-capacity-and-shard-sizing.md` with these exact top-level sections and required content:

```markdown
# 12.1 容量规划与 Shard Sizing

> **轨道**：A core / B prerequisite
>
> **目标**：能以资深工程师视角回答“这个 ES 集群要多少节点、多少 shard、多少 replica、什么时候 rollover、数据增长 10 倍怎么办”。

## 资深工程师先看什么

资深工程师不会先问“API 怎么写”，而是先问：

- 数据每天增长多少？
- 单条文档多大？
- 保留多久？
- 查询 QPS 和写入 TPS 分别是多少？
- 查询是按租户、时间、关键词、状态还是地理范围过滤？
- 是否需要聚合、排序、高亮、向量检索？
- 可接受的 P95/P99 延迟是多少？
- 故障时能丢多久数据，能停多久服务？

## 容量模型

必须包含这个计算框架：

```text
daily_raw_data = document_count_per_day * avg_document_size
indexed_data = daily_raw_data * index_expansion_factor
retention_data = indexed_data * retention_days
replicated_data = retention_data * (1 + replica_count)
disk_required = replicated_data / disk_watermark_target
node_count = disk_required / usable_disk_per_data_node
```

解释：

- `index_expansion_factor` 受 `_source`、倒排索引、Doc Values、stored fields、向量字段影响。
- `disk_watermark_target` 不能按 100% 算，要给 high watermark、merge、snapshot、恢复留下空间。
- heap 不是按数据总量线性扩大，shard 数、segment 数、mapping 数、查询并发和聚合更影响 heap 压力。

## Shard Sizing 原则

必须说明：

- shard 是 Lucene index，有固定管理成本。
- shard 太小会导致 oversharding、cluster state 变大、fan-out 变多。
- shard 太大会导致恢复慢、迁移慢、单 shard 查询压力大。
- 日志/时间序列索引用 rollover 控制 shard 大小。
- 商品/订单搜索要结合查询模式、租户隔离、更新频率和数据增长设计。

## Primary、Replica、Node 的关系

必须解释：

- primary 决定写入分布和基础并行度。
- replica 提供高可用和读扩展，但增加写入复制成本和磁盘成本。
- 节点数决定 shard 分布和故障域。
- 单节点承载过多 shard 会增加 heap、文件句柄、segment 元数据和恢复压力。

## Rollover 决策

必须覆盖：

- 按大小 rollover：控制 shard 尺寸。
- 按时间 rollover：便于生命周期和业务查询。
- 按文档数 rollover：适合文档大小稳定的场景。
- 真实生产往往组合多个条件，先满足者触发。

## 四个典型场景

### 日志检索

说明按时间写入、data stream、ILM、rollover、hot/warm/cold 和保留期。

### 商品搜索

说明固定主索引、alias/reindex、更新频率、相关性和排序字段。

### 订单搜索

说明正确性优先、MySQL 主库、ES 搜索视图、按时间/租户过滤、强一致回源。

### 多租户搜索

说明 shared index + routing、index per tenant、大租户隔离索引三种策略的取舍。

## 面试回答模板

### Q：你会怎么规划一个 ES 集群的 shard？

回答必须包含：

1. 先问数据量、增长、保留期、QPS/TPS、查询模式和 SLO。
2. 估算总存储和 replica 后的磁盘占用。
3. 根据目标 shard 大小反推 primary shard 数。
4. 根据节点数、故障域和 replica 规划分布。
5. 用 rollover/ILM 让长期增长可控。
6. 上线后用监控校正，而不是一次性拍脑袋。

### Q：数据增长 10 倍怎么办？

回答必须包含：

- 短期：扩 data node、调整 replica、控制写入和查询压力。
- 中期：rollover、reindex、冷热分层、拆分索引或租户隔离。
- 长期：重新设计容量模型、生命周期策略和查询边界。

## 常见反模式

| 反模式 | 后果 | 改法 |
| --- | --- | --- |
| 每天每租户一个索引 | shard 爆炸 | shared index + routing 或大租户单独索引 |
| primary shard 先随便设 | 后续扩容困难 | 建模时估算增长和 rollover |
| 只按磁盘估算节点 | heap、CPU、fan-out 被忽略 | 同时估算查询、聚合、shard 数 |
| replica 越多越好 | 写入成本和磁盘成本上升 | 按读 QPS 和 HA 需求设置 |
```

- [ ] **Step 2: Verify capacity document**

Run:

```bash
rg -n "容量模型|Shard Sizing|Primary、Replica、Node|Rollover|日志检索|商品搜索|订单搜索|多租户搜索|数据增长 10 倍|常见反模式" elasticsearch/roadmap/12-senior-es-and-search-engineering/01-capacity-and-shard-sizing.md
```

Expected: all required sections are found.

- [ ] **Step 3: Commit Task 2**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/01-capacity-and-shard-sizing.md
git commit -m "Add Elasticsearch capacity and shard sizing notes"
```

Expected: commit succeeds and includes only the capacity document.

---

### Task 3: Production Topology And Data Tiers

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md`

- [ ] **Step 1: Create the topology document**

Create `02-production-topology-and-data-tiers.md` with these sections and required content:

```markdown
# 12.2 生产拓扑与 Data Tiers

> **轨道**：A core / B prerequisite
>
> **目标**：能解释生产 ES 集群如何拆节点角色、如何做冷热分层、如何隔离 ingest/query/merge/snapshot 的资源竞争。

## 节点角色怎么拆

必须覆盖：

- master-eligible：管理 cluster state，不承载重查询和重写入。
- data：承载 shard 和实际读写。
- ingest：运行 pipeline，适合重解析或 enrich 任务隔离。
- coordinating：接入查询、分发、聚合结果，适合高 fan-out 查询入口。
- ML/transform：了解即可，不作为本路线重点。

## 常见生产拓扑

### 小型业务搜索集群

说明可以先简单，但要避免 master 和 data 被重负载同时拖垮。

### 中型业务搜索集群

说明 dedicated master、data node、coordinating node 的拆分。

### 日志/观测集群

说明 hot/warm/cold、data stream、ILM、snapshot 和保留期。

### 搜索平台集群

说明多租户接入、coordinating 层、query guardrail、资源配额。

## Data Tiers

必须解释：

- hot：高写入、高查询、SSD。
- warm：较少写入或只读，查询频率下降。
- cold：低频查询，成本优先。
- frozen/searchable snapshot：极低频历史查询，延迟换成本。

## 资源竞争

必须说明这些竞争：

- ingest pipeline 抢 CPU。
- 查询 fan-out 和聚合抢 CPU/heap。
- merge 抢 IO。
- snapshot/restore 抢网络和 IO。
- segment/cache/shard 元数据抢 heap。

## 隔离策略

必须覆盖：

- 节点角色隔离。
- 索引级 routing 和 allocation。
- query 入口限流。
- 大查询异步化或离线化。
- 日志集群和业务搜索集群拆分。

## 面试回答模板

### Q：生产 ES 集群你会怎么部署？

回答必须包含：

1. 先按业务类型区分：业务搜索、日志检索、搜索平台。
2. 小规模可以简单，但中大型要拆 dedicated master。
3. 数据节点按 hot/warm/cold 分层。
4. 查询入口可用 coordinating node 隔离。
5. ingest 重时拆 ingest node。
6. 用 ILM、allocation、SLO 和监控约束演进。

## 常见反模式

| 反模式 | 后果 | 改法 |
| --- | --- | --- |
| 所有角色混在高负载 data 节点 | GC/IO 抖动影响选主和查询 | dedicated master + data role 拆分 |
| 日志和核心业务搜索混跑 | 日志写入/merge 拖慢业务搜索 | 拆集群或至少拆数据层和资源预算 |
| snapshot 高峰期无限制运行 | IO 和网络争用 | snapshot 窗口、限速、监控 |
```

- [ ] **Step 2: Verify topology document**

Run:

```bash
rg -n "节点角色|master-eligible|coordinating|Data Tiers|hot|warm|cold|frozen|资源竞争|隔离策略|生产 ES 集群" elasticsearch/roadmap/12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md
```

Expected: all required topology concepts are found.

- [ ] **Step 3: Commit Task 3**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md
git commit -m "Add Elasticsearch production topology notes"
```

Expected: commit succeeds and includes only the topology document.

---

### Task 4: Failure Recovery And SLO

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md`

- [ ] **Step 1: Create the recovery/SLO document**

Create `03-failure-recovery-and-slo.md` with these sections and required content:

```markdown
# 12.3 故障恢复、RPO/RTO 与 SLO

> **轨道**：A core / B prerequisite
>
> **目标**：从“会处理 yellow/red”提升到“能设计搜索能力的可靠性目标、恢复策略、告警和演练”。

## ES 搜索能力的可靠性边界

必须说明：

- ES 常作为搜索视图，不一定是主数据源。
- RPO 取决于主库、同步链路、translog、snapshot 和可重放能力。
- RTO 取决于节点替换、shard recovery、snapshot restore、reindex 和业务降级。
- 强一致读应回源主库或采用业务补偿，不应默认依赖 ES。

## RPO/RTO 设计

必须给出模板：

```text
feature:
source of truth:
acceptable data loss:
acceptable search downtime:
rebuild path:
snapshot policy:
degraded mode:
verification drill:
```

## Snapshot 与 Restore

必须覆盖：

- SLM 定期快照。
- 快照仓库可用性。
- restore 演练。
- restore 后别名切换或只读校验。
- snapshot 不是替代主库备份。

## Disk Watermark

必须解释：

- low/high/flood-stage watermark 的风险。
- flood-stage 可能导致索引被设置 read-only block。
- 处理思路：扩容、删除过期数据、加速 ILM、迁移 shard、恢复写入 block 前确认空间。

## Unassigned Shard 诊断

必须使用这个顺序：

```text
_cluster/health
-> _cat/shards
-> _cluster/allocation/explain
-> 节点/磁盘/过滤规则/副本数/数据层/水位线
-> 修复
-> 验证 shard 分配
```

## SLO 与告警

必须包含：

- search availability。
- index freshness。
- P95/P99 latency。
- rejected requests。
- JVM memory pressure。
- disk watermark。
- unassigned shards。
- snapshot success。
- sync lag。

## 面试回答模板

### Q：ES red 了你怎么处理？

回答必须包含：

1. red 表示至少 primary 不可用，优先恢复数据可用性。
2. 查 `_cat/shards` 和 allocation explain。
3. 判断是节点丢失、磁盘、水位线、过滤规则、索引损坏还是恢复中。
4. 有主库可重建时评估 reindex；无主库时看 snapshot。
5. 恢复后补告警、容量、水位和演练缺口。

### Q：你怎么设计 ES 搜索服务 SLO？

回答必须包含：

- 可用性。
- 延迟。
- 新鲜度。
- 正确性边界。
- 降级策略。
- 恢复演练。
```

- [ ] **Step 2: Verify recovery/SLO document**

Run:

```bash
rg -n "RPO|RTO|SLO|Snapshot|Restore|Watermark|flood-stage|Unassigned Shard|allocation/explain|red|search availability|index freshness" elasticsearch/roadmap/12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md
```

Expected: all required recovery and SLO concepts are found.

- [ ] **Step 3: Commit Task 4**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md
git commit -m "Add Elasticsearch failure recovery and SLO notes"
```

Expected: commit succeeds and includes only the recovery/SLO document.

---

### Task 5: Performance Diagnostics Playbook

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/04-performance-diagnostics-playbook.md`

- [ ] **Step 1: Create the diagnostics document**

Create `04-performance-diagnostics-playbook.md` with these sections and required content:

```markdown
# 12.4 资深性能诊断 Playbook

> **轨道**：A core / B prerequisite
>
> **目标**：把性能调优从“列优化项”提升到“按症状、证据、机制、风险、修复、验证”系统排查。

## 诊断总原则

必须说明：

- 先判断慢在 query、fetch、aggregation、coordination、write、merge、GC、IO、network 哪一层。
- 先收证据，再改配置。
- 每次只改一个主要变量。
- 修复后用 P95/P99、rejected、queue、heap、CPU、IO、业务指标验证。

## 场景模板

```text
symptom:
first evidence:
likely mechanism:
risk:
fix options:
verification:
interview wording:
```

## High CPU

覆盖：expensive query、aggregation、script、highlight、merge、ingest pipeline、hot shard。

## High JVM Memory Pressure

覆盖：Fielddata、bucket explosion、query cache/request cache、too many shards、mapping explosion、large fetch。

## Rejected Requests

覆盖：search/write thread pool queue、bulk 并发、协调节点压力、下游重试风暴。

## Task Queue Backlog

覆盖：cluster state 更新、mapping 爆炸、shard allocation、snapshot、long-running tasks。

## Circuit Breaker Trips

覆盖：request breaker、fielddata breaker、parent breaker、聚合桶数、返回字段、查询并发。

## Mapping Explosion

覆盖：动态字段、日志无边界 key、flattened、dynamic_templates、字段治理。

## Hot Spotting

覆盖：routing 倾斜、大租户、热点时间窗口、单 shard 过载、写入热点。

## Segment And Merge Backlog

覆盖：refresh 太频繁、bulk 太碎、更新/删除太多、IO 不足、merge throttling。

## Query/Fetch/Aggregation/Coordination Isolation

必须说明如何区分：

- query 慢：profile API、倒排索引、过滤条件、fan-out。
- fetch 慢：`_source` 大、高亮、大字段。
- aggregation 慢：Doc Values、bucket 数、高基数、Fielddata。
- coordination 慢：shard 太多、TopN merge、coordinating node 压力。

## 面试回答模板

### Q：线上 ES 查询突然变慢怎么排查？

回答必须按这个顺序：

1. 先确认范围：单索引、单租户、单查询、全局。
2. 区分 query/fetch/aggregation/coordination。
3. 看 slowlog、profile、thread pool、JVM、CPU、IO、shard 分布。
4. 根据证据改查询、mapping、分页、返回字段、shard/routing 或资源。
5. 用 P95/P99 和业务指标验证。
```

- [ ] **Step 2: Verify diagnostics document**

Run:

```bash
rg -n "High CPU|High JVM Memory Pressure|Rejected Requests|Task Queue Backlog|Circuit Breaker|Mapping Explosion|Hot Spotting|Segment And Merge|Query/Fetch/Aggregation/Coordination|线上 ES 查询突然变慢" elasticsearch/roadmap/12-senior-es-and-search-engineering/04-performance-diagnostics-playbook.md
```

Expected: all required scenarios are found.

- [ ] **Step 3: Commit Task 5**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/04-performance-diagnostics-playbook.md
git commit -m "Add Elasticsearch senior diagnostics playbook"
```

Expected: commit succeeds and includes only the diagnostics document.

---

### Task 6: Search Relevance Engineering

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/05-search-relevance-engineering.md`

- [ ] **Step 1: Create the relevance document**

Create `05-search-relevance-engineering.md` with these sections and required content:

```markdown
# 12.5 搜索质量与相关性工程

> **轨道**：B core
>
> **目标**：从“会写 Query DSL”提升到“能治理搜索质量”：召回、排序、评估、实验和发布。

## 搜索质量不是一个分数

必须解释：

- precision。
- recall。
- NDCG。
- CTR/CVR/GMV 等业务指标。
- 零结果率。
- 用户改搜率。
- 搜索延迟和成本。

## Analyzer 与 Synonym 治理

覆盖：

- index-time synonym 和 query-time synonym 取舍。
- 同义词变更的发布流程。
- 中文分词误切、过切、漏召。
- 拼音、前缀、纠错、停用词的业务风险。

## Query Rewrite

覆盖：

- 用户词归一化。
- 类目/品牌/型号识别。
- 同义词扩展。
- typo tolerance。
- 禁用危险查询模式。

## Relevance Toolbelt

必须说明：

- `multi_match` 类型选择。
- `dis_max` 和 tie breaker。
- boost。
- `rank_feature`。
- `function_score`。
- `rescore`。
- rerank 与 ES rescore 的边界。

## Product Search、Content Search、Log Search 差异

必须比较：

- 商品搜索重业务排序和转化。
- 内容搜索重语义和相关性。
- 日志搜索重过滤、时间范围和可解释性。

## A/B Test 与发布

覆盖：

- 离线评估集。
- 人工标注。
- shadow query。
- 小流量实验。
- 指标观察。
- 回滚条件。

## 面试回答模板

### Q：搜索结果不准，你怎么优化？

回答必须包含：

1. 先定义“不准”：召回不够、排序不对、误召回、零结果、业务指标下降。
2. 收集 query、点击、转化、人工标注和 bad case。
3. 判断是 analyzer、query rewrite、mapping、召回策略、排序特征还是业务规则问题。
4. 离线评估和线上 A/B 分开做。
5. 发布要可灰度、可观测、可回滚。
```

- [ ] **Step 2: Verify relevance document**

Run:

```bash
rg -n "precision|recall|NDCG|Analyzer|Synonym|Query Rewrite|multi_match|dis_max|rank_feature|function_score|rescore|A/B Test|搜索结果不准" elasticsearch/roadmap/12-senior-es-and-search-engineering/05-search-relevance-engineering.md
```

Expected: all relevance concepts are found.

- [ ] **Step 3: Commit Task 6**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/05-search-relevance-engineering.md
git commit -m "Add Elasticsearch search relevance engineering notes"
```

Expected: commit succeeds and includes only the relevance document.

---

### Task 7: Lucene Query Execution Deep Dive

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md`

- [ ] **Step 1: Create the Lucene execution document**

Create `06-lucene-query-execution-deep-dive.md` with these sections and required content:

```markdown
# 12.6 Lucene 查询执行心智模型

> **轨道**：B core
>
> **目标**：不用读源码，也能用资深搜索工程师的语言解释 Lucene 查询如何执行、为什么某些查询快、某些查询慢。

## 面试边界

必须说明：

- 这里讲 interview-level mental model。
- 不要求背 Lucene 源码类名和完整调用栈。
- 能解释执行直觉、性能影响和排查方向即可。

## 从 Term 到 Posting List

覆盖：

- term dictionary。
- FST 定位。
- posting list。
- doc ID 有序。
- frequency、positions、offsets 的作用边界。

## Boolean Query 执行直觉

覆盖：

- must/filter/should/must_not 的执行含义。
- posting list 交集、并集、排除。
- 高选择性 filter 为什么重要。
- filter context 和 bitset/cache 的直觉。

## Scorer 与 Collector 心智模型

覆盖：

- Scorer 负责遍历和计算匹配分数。
- Collector 负责收集 TopK。
- TopK collection 为什么和排序字段、score、size 有关。

## Skip Data 与 Block Pruning

覆盖：

- 长 posting list 不能逐个 doc 扫到底。
- skip data 帮助跳过不可能匹配区间。
- block-level max score 帮助剪枝。

## WAND / Block-Max WAND 直觉

必须明确这是 optional deep dive。

覆盖：

- 目标是减少不可能进入 TopK 的候选文档评分。
- 对高频词、TopK 查询有帮助。
- 不是所有查询都能明显获益。

## 慢查询如何映射到执行模型

必须覆盖：

- wildcard/regexp 可能 term 枚举过大。
- 低选择性查询候选集过大。
- script score/function score 可能对大量候选执行。
- 深分页扩大 TopK 收集。
- 聚合是另一条按字段读取和分桶路径。

## 面试回答模板

### Q：Lucene 为什么能快速找到文档？

回答必须包含：

1. analyzer 把文本变成 term。
2. FST/term dictionary 快速定位 term。
3. posting list 给出候选 doc ID。
4. Scorer 计算分数。
5. Collector 收集 TopK。
6. skip/block pruning 减少无效候选。
```

- [ ] **Step 2: Verify Lucene execution document**

Run:

```bash
rg -n "interview-level|Term|Posting List|Boolean Query|Scorer|Collector|TopK|Skip Data|Block|WAND|慢查询|Lucene 为什么能快速找到文档" elasticsearch/roadmap/12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md
```

Expected: all Lucene execution concepts are found.

- [ ] **Step 3: Commit Task 7**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md
git commit -m "Add Lucene query execution interview notes"
```

Expected: commit succeeds and includes only the Lucene execution document.

---

### Task 8: Hybrid Search And Rerank

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/07-hybrid-search-and-rerank.md`

- [ ] **Step 1: Create the hybrid search document**

Create `07-hybrid-search-and-rerank.md` with these sections and required content:

```markdown
# 12.7 Hybrid Search 与 Rerank

> **轨道**：B core
>
> **目标**：能解释现代搜索系统为什么常用 BM25 + vector + rerank，而不是只靠单一检索方式。

## 三阶段搜索架构

必须说明：

```text
candidate generation
-> score fusion / coarse ranking
-> rerank
```

## BM25 Retrieval

覆盖：

- 精确关键词强。
- 可解释性强。
- 对语义改写和同义表达弱。

## Vector Retrieval

覆盖：

- 语义召回强。
- 对精确词、型号、ID、数字可能不稳定。
- 成本和延迟更高。

## Hybrid Retrieval

覆盖：

- BM25 和 vector 互补。
- score normalization/fusion 是难点。
- 候选集大小影响 recall、latency 和 cost。

## Rerank Stage

覆盖：

- rerank 只处理候选集，不处理全量文档。
- 可以用规则、学习排序模型或 LLM/reranker。
- 最大风险是延迟、成本和稳定性。

## Failure Modes

必须包含：

- vector recall misses exact terms。
- BM25 misses semantic matches。
- rerank latency too high。
- score fusion unstable。
- embedding drift。
- query distribution changes。

## 面试回答模板

### Q：为什么不直接用向量搜索替代 BM25？

回答必须包含：

1. BM25 对精确词、品牌、型号、ID、日志关键词强。
2. 向量对语义相似强，但精确约束和可解释性弱。
3. hybrid 用两者互补。
4. rerank 在较小候选集上做更贵的排序。
5. 设计要平衡 recall、latency、cost 和 explainability。
```

- [ ] **Step 2: Verify hybrid search document**

Run:

```bash
rg -n "candidate generation|BM25|Vector Retrieval|Hybrid Retrieval|Rerank|score fusion|Failure Modes|向量搜索替代 BM25" elasticsearch/roadmap/12-senior-es-and-search-engineering/07-hybrid-search-and-rerank.md
```

Expected: all hybrid search concepts are found.

- [ ] **Step 3: Commit Task 8**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/07-hybrid-search-and-rerank.md
git commit -m "Add Elasticsearch hybrid search and rerank notes"
```

Expected: commit succeeds and includes only the hybrid search document.

---

### Task 9: Search Platform Governance

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/08-search-platform-governance.md`

- [ ] **Step 1: Create the governance document**

Create `08-search-platform-governance.md` with these sections and required content:

```markdown
# 12.8 搜索平台治理

> **轨道**：B core
>
> **目标**：从“维护一个 ES 集群”提升到“设计一个可被多个业务安全使用的搜索平台”。

## 平台工程视角

必须说明：

- 平台面对的是多个业务方、多个租户、多种查询质量。
- 平台要提供安全默认值，而不是把 ES 原始能力全部暴露出去。
- 治理目标是稳定性、成本、相关性发布、可观测和开发效率。

## Multi-tenant Index Strategy

覆盖：

- shared index。
- index per tenant。
- large tenant dedicated index。
- routing by tenant。
- 数据隔离、成本、热点和运维复杂度取舍。

## Query Budget And Guardrails

覆盖：

- max size。
- deep pagination limit。
- wildcard/regexp/script 限制。
- aggregation bucket 限制。
- timeout。
- circuit breaker。
- query template。

## Per-tenant Quota And Isolation

覆盖：

- QPS quota。
- bulk quota。
- expensive query quota。
- traffic shaping。
- tenant-level dashboard。

## Relevance Release Process

覆盖：

- synonym 变更流程。
- query rewrite 变更流程。
- ranking config 版本化。
- shadow traffic。
- A/B test。
- rollback。

## Search Observability

覆盖：

- query latency。
- zero-result rate。
- click-through rate。
- top bad queries。
- rejected requests。
- hot shards。
- per-tenant cost。

## Cost Governance

覆盖：

- storage cost。
- query cost。
- vector/rerank cost。
- snapshot cost。
- cold data retention。

## 面试回答模板

### Q：如果你负责公司统一搜索平台，你会怎么治理？

回答必须包含：

1. 不直接暴露 ES 任意查询能力。
2. 用 query template 和 guardrail 限制危险查询。
3. 按租户做 quota、监控和隔离。
4. 相关性变更走版本化、灰度、A/B 和回滚。
5. 成本按存储、查询、向量、rerank、snapshot 分摊和治理。
```

- [ ] **Step 2: Verify governance document**

Run:

```bash
rg -n "平台工程|Multi-tenant|Query Budget|Guardrails|Quota|Relevance Release|Search Observability|Cost Governance|统一搜索平台" elasticsearch/roadmap/12-senior-es-and-search-engineering/08-search-platform-governance.md
```

Expected: all governance concepts are found.

- [ ] **Step 3: Commit Task 9**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/08-search-platform-governance.md
git commit -m "Add Elasticsearch search platform governance notes"
```

Expected: commit succeeds and includes only the governance document.

---

### Task 10: Senior Case Studies

**Files:**
- Create: `elasticsearch/roadmap/12-senior-es-and-search-engineering/09-senior-case-studies.md`

- [ ] **Step 1: Create the case studies document**

Create `09-senior-case-studies.md` with these sections and required content:

```markdown
# 12.9 资深面试 Case Studies

> **轨道**：A+B synthesis
>
> **目标**：把第 12 章的资深能力转成系统设计和项目叙述。每个案例都要能讲需求、约束、索引设计、查询路径、同步路径、容量模型、故障模式、观测和取舍。

## Case Study 模板

```text
requirements:
constraints:
index design:
query path:
sync path:
capacity model:
failure modes:
observability:
tradeoffs:
interview narrative:
```

## 案例 1：电商商品搜索 10x 流量增长

必须覆盖：

- 商品索引 mapping。
- 商品名分析和同义词。
- brand/category/price/status 过滤。
- BM25 + business boost。
- shard sizing 和 query fan-out。
- reindex/alias 灰度。
- 热点查询和缓存。

## 案例 2：订单搜索与 MySQL 正确性边界

必须覆盖：

- MySQL 是 source of truth。
- ES 是搜索视图。
- CDC/MQ 同步。
- 幂等、乱序、校对。
- 强一致查询回源。
- 审计和修复。

## 案例 3：日志检索与 ILM/Data Tiers

必须覆盖：

- data stream。
- index template。
- rollover。
- hot/warm/cold。
- retention。
- snapshot。
- 查询时间范围限制。

## 案例 4：多租户 SaaS 搜索平台

必须覆盖：

- shared index vs index per tenant vs large tenant dedicated index。
- routing。
- quota。
- query guardrails。
- per-tenant observability。
- noisy neighbor。

## 案例 5：BM25 + Vector + Rerank Hybrid Search

必须覆盖：

- candidate generation。
- BM25 recall。
- vector recall。
- score fusion。
- rerank。
- latency budget。
- fallback。

## 案例 6：ES Mapping 变更与 Reindex 迁移

必须覆盖：

- 新索引。
- alias。
- dual write 或暂停写入窗口。
- reindex。
- 校验。
- 切换。
- rollback。

## 资深叙述原则

必须说明：

- 先讲约束，不先讲技术名词。
- 每个设计选择要有 tradeoff。
- 每个风险要有观测和回滚。
- 每个性能判断要有指标。
- 每个一致性判断要说明 source of truth。
```

- [ ] **Step 2: Verify case studies document**

Run:

```bash
rg -n "Case Study 模板|电商商品搜索|订单搜索|日志检索|多租户 SaaS|Hybrid Search|Reindex 迁移|资深叙述原则" elasticsearch/roadmap/12-senior-es-and-search-engineering/09-senior-case-studies.md
```

Expected: all case studies are found.

- [ ] **Step 3: Commit Task 10**

Run:

```bash
git add elasticsearch/roadmap/12-senior-es-and-search-engineering/09-senior-case-studies.md
git commit -m "Add Elasticsearch senior case studies"
```

Expected: commit succeeds and includes only the case studies document.

---

### Task 11: Update Roadmap And Existing Chapter Touch Points

**Files:**
- Modify: `elasticsearch/elasticsearch-roadmap.md`
- Modify: `elasticsearch/roadmap/03-analysis/03-analysis.md`
- Modify: `elasticsearch/roadmap/04-query-dsl/04-query-dsl.md`
- Modify: `elasticsearch/roadmap/06-storage-internals/06-storage-internals.md`
- Modify: `elasticsearch/roadmap/08-performance-tuning/08-performance-tuning.md`
- Modify: `elasticsearch/roadmap/10-production-advanced/10-production-advanced.md`
- Modify: `elasticsearch/roadmap/11-interview/01-internals-question-map.md`

- [ ] **Step 1: Update top-level roadmap**

In `elasticsearch/elasticsearch-roadmap.md`:

1. Add stage 12 to the overview after stage 11:

```text
阶段12
资深 ES 与搜索工程
(A/B 双轨，持续加深)
```

2. Add a navigation row:

```markdown
| **12** | [资深 ES 与搜索工程](./roadmap/12-senior-es-and-search-engineering/) | A线生产治理 / B线搜索工程 / 容量规划 / 搜索质量 / Lucene执行 / Hybrid Search / 平台治理 / 资深案例 | 阶段1-11 |
```

3. Add a short section after stage 11:

```markdown
## 阶段 12：资深 ES 与搜索工程（A/B 双轨，持续加深）

> 阶段 12 不重写前 1-11 章，而是在已有基础上补资深工程师判断力。A 线面向 Java 后端资深工程师，强调生产治理；B 线面向搜索/ES 平台工程师，强调搜索质量、Lucene 执行、Hybrid Search 和平台治理。

入口：[roadmap/12-senior-es-and-search-engineering/](./roadmap/12-senior-es-and-search-engineering/)
```

- [ ] **Step 2: Add senior extension links to existing chapters**

Append a short section near each file's final summary or next-stage note.

In `03-analysis.md`, add:

```markdown
## 资深扩展

如果你要走搜索工程方向，继续看阶段 12 的 [搜索质量与相关性工程](../12-senior-es-and-search-engineering/05-search-relevance-engineering.md)，重点关注同义词治理、query rewrite、召回率和误召回的取舍。
```

In `04-query-dsl.md`, add:

```markdown
## 资深扩展

如果你要理解搜索质量和查询执行，继续看阶段 12 的 [搜索质量与相关性工程](../12-senior-es-and-search-engineering/05-search-relevance-engineering.md) 和 [Lucene 查询执行心智模型](../12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md)。
```

In `06-storage-internals.md`, add:

```markdown
## 资深扩展

如果你要从“知道 Segment 和倒排索引”继续深入到搜索执行模型，继续看阶段 12 的 [Lucene 查询执行心智模型](../12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md)。
```

In `08-performance-tuning.md`, add:

```markdown
## 资深扩展

如果你要把调优升级成系统化排障能力，继续看阶段 12 的 [资深性能诊断 Playbook](../12-senior-es-and-search-engineering/04-performance-diagnostics-playbook.md)。
```

In `10-production-advanced.md`, add:

```markdown
## 资深扩展

如果你要从“知道生产特性”升级到“能负责生产治理”，继续看阶段 12 的 [生产拓扑与 Data Tiers](../12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md) 和 [故障恢复、RPO/RTO 与 SLO](../12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md)。
```

In `11-interview/01-internals-question-map.md`, add:

```markdown
## 资深扩展

如果面试目标提高到资深 Java 后端或搜索平台方向，继续看阶段 12 的 [资深 ES 与搜索工程 A/B 双轨](../12-senior-es-and-search-engineering/README.md)，并用 [资深面试 Case Studies](../12-senior-es-and-search-engineering/09-senior-case-studies.md) 练系统设计叙述。
```

- [ ] **Step 3: Verify roadmap links**

Run:

```bash
test -d elasticsearch/roadmap/12-senior-es-and-search-engineering
rg -n "阶段 12|12-senior-es-and-search-engineering|资深扩展|搜索质量与相关性工程|Lucene 查询执行|资深性能诊断|RPO/RTO|Case Studies" elasticsearch/elasticsearch-roadmap.md elasticsearch/roadmap/03-analysis/03-analysis.md elasticsearch/roadmap/04-query-dsl/04-query-dsl.md elasticsearch/roadmap/06-storage-internals/06-storage-internals.md elasticsearch/roadmap/08-performance-tuning/08-performance-tuning.md elasticsearch/roadmap/10-production-advanced/10-production-advanced.md elasticsearch/roadmap/11-interview/01-internals-question-map.md
```

Expected: stage 12 directory exists and all new link references are found.

- [ ] **Step 4: Commit Task 11**

Run:

```bash
git add elasticsearch/elasticsearch-roadmap.md elasticsearch/roadmap/03-analysis/03-analysis.md elasticsearch/roadmap/04-query-dsl/04-query-dsl.md elasticsearch/roadmap/06-storage-internals/06-storage-internals.md elasticsearch/roadmap/08-performance-tuning/08-performance-tuning.md elasticsearch/roadmap/10-production-advanced/10-production-advanced.md elasticsearch/roadmap/11-interview/01-internals-question-map.md
git commit -m "Link Elasticsearch senior track from existing roadmap"
```

Expected: commit succeeds and includes only the roadmap/touchpoint files.

---

### Task 12: Final Documentation Verification

**Files:**
- Verify: `elasticsearch/roadmap/12-senior-es-and-search-engineering/*.md`
- Verify: `elasticsearch/elasticsearch-roadmap.md`
- Verify: senior extension touchpoint files

- [ ] **Step 1: Verify all stage 12 files exist**

Run:

```bash
find elasticsearch/roadmap/12-senior-es-and-search-engineering -maxdepth 1 -type f -name '*.md' | sort
```

Expected output:

```text
elasticsearch/roadmap/12-senior-es-and-search-engineering/01-capacity-and-shard-sizing.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/04-performance-diagnostics-playbook.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/05-search-relevance-engineering.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/07-hybrid-search-and-rerank.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/08-search-platform-governance.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/09-senior-case-studies.md
elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md
```

- [ ] **Step 2: Scan for placeholder text**

Run:

```bash
rg -n 'TB''D|TO''DO|待''定|待''补|占''位|后续''补|fi''ll in|implement'' later' elasticsearch/roadmap/12-senior-es-and-search-engineering elasticsearch/elasticsearch-roadmap.md elasticsearch/roadmap/03-analysis/03-analysis.md elasticsearch/roadmap/04-query-dsl/04-query-dsl.md elasticsearch/roadmap/06-storage-internals/06-storage-internals.md elasticsearch/roadmap/08-performance-tuning/08-performance-tuning.md elasticsearch/roadmap/10-production-advanced/10-production-advanced.md elasticsearch/roadmap/11-interview/01-internals-question-map.md
```

Expected: no matches.

- [ ] **Step 3: Verify A/B coverage**

Run:

```bash
rg -n "A 线|B 线|A-track|B-track|Senior Java|搜索工程|搜索平台|容量规划|相关性|Lucene|Hybrid Search|平台治理|Case Studies" elasticsearch/roadmap/12-senior-es-and-search-engineering
```

Expected: output includes README and the relevant stage 12 documents.

- [ ] **Step 4: Verify local links resolve**

Run this shell snippet:

```bash
for link in \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/01-capacity-and-shard-sizing.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/04-performance-diagnostics-playbook.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/05-search-relevance-engineering.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/07-hybrid-search-and-rerank.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/08-search-platform-governance.md \
  elasticsearch/roadmap/12-senior-es-and-search-engineering/09-senior-case-studies.md; do \
  test -f "$link" || exit 1; \
done
```

Expected: command exits 0.

- [ ] **Step 5: Check Markdown diff and git status**

Run:

```bash
git diff --check
git status --short
git log --oneline -12
```

Expected:

- `git diff --check` prints no whitespace errors.
- `git status --short` shows only expected changes if final task is not committed, or clean after all commits.
- log shows task commits for stage 12.

- [ ] **Step 6: Report completion**

Report:

```text
Implemented Elasticsearch stage 12 senior A/B track.

Created:
- elasticsearch/roadmap/12-senior-es-and-search-engineering/README.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/01-capacity-and-shard-sizing.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/02-production-topology-and-data-tiers.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/03-failure-recovery-and-slo.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/04-performance-diagnostics-playbook.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/05-search-relevance-engineering.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/06-lucene-query-execution-deep-dive.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/07-hybrid-search-and-rerank.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/08-search-platform-governance.md
- elasticsearch/roadmap/12-senior-es-and-search-engineering/09-senior-case-studies.md

Updated:
- elasticsearch/elasticsearch-roadmap.md
- stage 3, 4, 6, 8, 10, and 11 touchpoints

Verification:
- all stage 12 files exist
- no placeholder text found
- A/B track coverage present
- local links resolve
- git diff --check passes
```
