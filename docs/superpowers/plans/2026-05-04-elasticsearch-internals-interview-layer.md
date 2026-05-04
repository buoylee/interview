# Elasticsearch Internals Interview Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an `elasticsearch/roadmap/11-interview/` layer that converts the existing Elasticsearch learning notes into interview-ready internals follow-up chains.

**Architecture:** Keep stages 1-10 as the source-of-truth learning material. Add six focused stage 11 documents that summarize high-frequency interview questions, answer shape, mechanism chains, follow-ups, production wording, and links back to source chapters. Update the top-level roadmap only for navigation and stage 11 visibility.

**Tech Stack:** Markdown documentation in this repository; verification with `rg`, `find`, `sed`, and `git diff`.

---

## File Structure

Create:

- `elasticsearch/roadmap/11-interview/01-internals-question-map.md`
  - Responsibility: map high-frequency internals questions to priority levels and source chapters.
- `elasticsearch/roadmap/11-interview/02-write-path-deep-dive.md`
  - Responsibility: answer write-path internals follow-ups from client request to segment, translog, refresh, flush, and merge.
- `elasticsearch/roadmap/11-interview/03-search-path-deep-dive.md`
  - Responsibility: answer search-path follow-ups from query analysis to shard scoring, query/fetch phases, result merge, and pagination.
- `elasticsearch/roadmap/11-interview/04-storage-structures.md`
  - Responsibility: explain storage structures used in deeper internals questions: inverted index, term dictionary, FST, posting list, Doc Values, Stored Fields, Fielddata, and segments.
- `elasticsearch/roadmap/11-interview/05-cluster-and-shard.md`
  - Responsibility: answer distributed follow-ups about routing, primary/replica replication, election, cluster state, allocation, recovery, and oversharding.
- `elasticsearch/roadmap/11-interview/06-production-troubleshooting.md`
  - Responsibility: turn mechanisms into production troubleshooting interview answers.

Modify:

- `elasticsearch/elasticsearch-roadmap.md`
  - Responsibility: link stage 11 to the new directory and fix existing stage 7 and stage 10 path links so the navigation table points at real directories.

No automated tests are required because this is a documentation-only change. Verification is file presence, link target existence, required section presence, and no placeholder text.

---

### Task 1: Create Stage 11 Directory And Question Map

**Files:**
- Create: `elasticsearch/roadmap/11-interview/01-internals-question-map.md`

- [ ] **Step 1: Create the directory and question map file**

Create `elasticsearch/roadmap/11-interview/01-internals-question-map.md` with this content:

```markdown
# 阶段 11：ES 原理面试追问地图

> **目标**：把前 10 个阶段学过的 Elasticsearch 知识整理成面试追问链。学完本阶段后，你应该能先给出一句话答案，再按面试官追问展开到底层机制、设计取舍和生产排查。
>
> **前置依赖**：阶段 1-10。这里不重新讲完整知识，只负责把已有知识转成面试可输出的结构。

## 使用方式

每个问题都按三个层级准备：

1. **一句话答案**：先稳住问题，不展开细枝末节。
2. **核心链路**：把机制按顺序讲清楚。
3. **追问与生产场景**：面试官继续问时，能接到设计取舍、故障排查或系统设计。

建议练习方式：

- 先遮住答案，只看问题，用 30 秒讲一句话答案。
- 再用 2 分钟讲核心链路。
- 最后用一个生产场景收尾，证明你不是只背概念。

## 问题优先级

| 标记 | 含义 |
| --- | --- |
| 必会 | 普通后端和中高级后端 ES 面试都高频出现 |
| 加分 | 能体现生产经验和系统设计能力 |
| 深挖 | 搜索基础设施或强底层面试可能继续追问 |

## 高频问题地图

| 主题 | 问题 | 优先级 | 关联章节 |
| --- | --- | --- | --- |
| 倒排索引与分词 | ES 为什么适合全文搜索？ | 必会 | 阶段 1、3、4、6 |
| 倒排索引与分词 | `match` 和 `term` 的本质区别是什么？ | 必会 | 阶段 2、3、4 |
| 倒排索引与分词 | 为什么 `text` 字段适合全文检索，`keyword` 字段适合过滤和聚合？ | 必会 | 阶段 2、3、5 |
| 写入链路 | 为什么 ES 是近实时搜索？ | 必会 | 阶段 6 |
| 写入链路 | refresh、flush、merge 分别做什么？ | 必会 | 阶段 6、8 |
| 写入链路 | translog 解决什么问题？ | 必会 | 阶段 6 |
| 写入链路 | 为什么更新文档不是原地修改？ | 必会 | 阶段 6 |
| 查询链路 | 一个 `match` 查询从请求到返回经历了什么？ | 必会 | 阶段 3、4、6 |
| 查询链路 | BM25 是什么，为什么会影响排序？ | 必会 | 阶段 4 |
| 查询链路 | 深度分页为什么慢？ | 必会 | 阶段 4、8 |
| 存储结构 | Doc Values 为什么适合排序和聚合？ | 必会 | 阶段 2、5、6 |
| 存储结构 | Fielddata 为什么容易导致堆内存压力？ | 必会 | 阶段 5、8 |
| 存储结构 | FST、Term Dictionary、Posting List 分别是什么？ | 加分 | 阶段 6 |
| 分片与集群 | 文档如何路由到 shard？ | 必会 | 阶段 7 |
| 分片与集群 | primary shard 数为什么不能随便改？ | 必会 | 阶段 2、7、8 |
| 分片与集群 | ES 如何避免脑裂？ | 必会 | 阶段 7 |
| 分片与集群 | 节点宕机后分片如何恢复？ | 必会 | 阶段 7 |
| 调优与排查 | 查询突然变慢怎么排查？ | 必会 | 阶段 4、6、7、8 |
| 调优与排查 | 写入吞吐下降怎么排查？ | 必会 | 阶段 6、7、8、9 |
| 调优与排查 | 集群 yellow/red 怎么处理？ | 必会 | 阶段 7、10 |
| 调优与排查 | 聚合 OOM 或 circuit breaker 触发怎么处理？ | 加分 | 阶段 5、8、10 |
| Lucene 深挖 | Posting List 压缩、skip data、TopK 收集怎么工作？ | 深挖 | 阶段 6，可选补充 |
| Lucene 深挖 | Block-Max WAND、Scorer 执行细节是什么？ | 深挖 | 可选补充 |

## 面试回答模板

```text
一句话答案：
核心链路：
为什么这样设计：
常见追问：
生产场景怎么说：
关联章节：
```

## 本阶段学习顺序

1. 先读本文件，确认必会问题。
2. 再读 `02-write-path-deep-dive.md` 和 `03-search-path-deep-dive.md`，这是最高频的两条主链。
3. 再读 `04-storage-structures.md` 和 `05-cluster-and-shard.md`，补底层结构和分布式追问。
4. 最后读 `06-production-troubleshooting.md`，把原理转成排查叙述。

## 过关标准

学完阶段 11 后，你至少应该能做到：

- 用 1 分钟讲清楚为什么 ES 是近实时搜索。
- 用 2 分钟讲清楚一次写入如何变成可搜索数据。
- 用 2 分钟讲清楚一次 `match` 查询如何执行。
- 解释 Doc Values、Fielddata、Segment、translog、routing 的作用。
- 面对查询慢、写入慢、yellow/red、聚合 OOM，能按症状、证据、机制、修复、验证来回答。
```

- [ ] **Step 2: Verify the file exists and has required headings**

Run:

```bash
test -f elasticsearch/roadmap/11-interview/01-internals-question-map.md
rg -n "^#|^## 问题优先级|^## 高频问题地图|^## 面试回答模板|^## 过关标准" elasticsearch/roadmap/11-interview/01-internals-question-map.md
```

Expected:

- `test -f` exits with status 0.
- `rg` prints the main title and the four required sections.

- [ ] **Step 3: Commit task 1**

Run:

```bash
git add elasticsearch/roadmap/11-interview/01-internals-question-map.md
git commit -m "Add Elasticsearch internals question map"
```

Expected: commit succeeds and only the new question map file is included.

---

### Task 2: Add Write Path Deep Dive

**Files:**
- Create: `elasticsearch/roadmap/11-interview/02-write-path-deep-dive.md`

- [ ] **Step 1: Create the write-path file**

Create `elasticsearch/roadmap/11-interview/02-write-path-deep-dive.md` with this content:

```markdown
# ES 写入链路原理追问

> **目标**：把写入、refresh、flush、translog、segment、merge 讲成一条连续链路。面试时不要只背名词，要能解释为什么 ES 是近实时、为什么更新不是原地修改、为什么写入调优会影响搜索可见性。

## Q1：为什么 Elasticsearch 是近实时搜索？

### 一句话答案

因为文档写入后不是每次立刻生成可搜索的 Lucene commit，而是先进入内存缓冲区和 translog，等 refresh 周期把内存中的数据打开成新的可搜索 segment，所以写入成功到搜索可见之间通常有短暂延迟。

### 核心链路

```text
写入请求
-> coordinating node 路由到 primary shard
-> primary shard 写入 index buffer
-> 同时追加 translog
-> refresh 生成新的 searchable segment
-> searcher 重新打开后搜索可见
-> flush 执行 Lucene commit 并清理旧 translog
-> merge 后台合并小 segment
```

### 为什么这样设计

如果每次写入都立刻做完整磁盘提交，吞吐会很低。ES 用 refresh 把“搜索可见”和“磁盘持久提交”拆开：refresh 保证较快可见，translog 保证 refresh 前的数据在故障后可恢复，flush 再周期性做更重的提交。

### 常见追问

**refresh 和 flush 有什么区别？**

refresh 让新写入的数据对搜索可见；flush 做 Lucene commit，并清理已经安全提交的 translog。refresh 不等于真正的持久提交。

**refresh_interval 调大有什么影响？**

写入吞吐通常提升，因为 segment 生成频率下降；搜索可见延迟变大，因为数据要等更久才 refresh。

### 生产场景怎么说

如果是日志或批量导入场景，可以临时调大 `refresh_interval`，甚至导入期间关闭自动 refresh，导入完成后手动 refresh。这样提升写入吞吐，但要明确接受搜索可见性延迟。

### 关联章节

- 阶段 6：存储原理与读写链路
- 阶段 8：性能调优

## Q2：refresh、flush、merge 分别做什么？

### 一句话答案

refresh 让数据可搜索，flush 做持久提交并清理 translog，merge 把多个小 segment 合并成更大的 segment 来降低查询和文件管理成本。

### 核心链路

```text
refresh:
index buffer -> new segment -> searcher reopen -> searchable

flush:
Lucene commit -> fsync committed segment metadata -> translog generation rollover

merge:
small segments -> larger segment -> delete marker cleanup -> fewer segments
```

### 为什么这样设计

Segment 是不可变的。不可变让读操作可以无锁并发，也方便缓存和文件系统管理，但代价是更新和删除不能原地修改，只能新增版本或打删除标记。merge 用后台合并消化这些代价。

### 常见追问

**force merge 什么时候用？**

适合只读索引，例如历史日志索引进入 warm/cold 阶段后。不要对高写入活跃索引频繁 force merge，否则会产生大量 IO，影响写入和查询。

**segment 太多会怎样？**

每次查询需要访问更多 segment，文件句柄和内存元数据压力也会上升，延迟可能变差。

### 生产场景怎么说

如果查询变慢且 `_cat/segments` 显示 segment 数很多，要结合写入速率、refresh_interval、merge backlog 和 IO 使用率判断。历史只读索引可以考虑 force merge，活跃索引更应该调 refresh、bulk 和 shard 设计。

### 关联章节

- 阶段 6：Segment 生命周期
- 阶段 8：写入优化、查询优化
- 阶段 10：ILM

## Q3：translog 解决什么问题？

### 一句话答案

translog 是 ES 的写前日志，用来保护还没有完成 Lucene commit 的写入操作，节点异常后可以通过 translog 回放恢复数据。

### 核心链路

```text
写入请求
-> 写 index buffer
-> 追加 translog
-> 根据 durability 策略 fsync translog
-> refresh 后可搜索
-> flush 后 Lucene commit
-> 清理旧 translog generation
```

### 为什么这样设计

Lucene commit 成本较高，不适合每条写入都执行。translog 让 ES 可以把重提交延后，同时仍然有故障恢复能力。

### 常见追问

**translog durability=request 和 async 区别？**

`request` 默认更安全，每次请求后尽量 fsync；`async` 性能更好，但节点崩溃时可能丢失最近一小段尚未 fsync 的写入。

**写入成功是否意味着马上能搜到？**

不一定。写入成功代表 primary 和必要 replica 已处理写入；搜索可见还要等 refresh。

### 生产场景怎么说

金融、订单、库存类数据通常不为了吞吐牺牲 translog 安全性。日志或可重放数据在高吞吐导入时可以评估 async，但必须接受故障窗口。

### 关联章节

- 阶段 6：Translog
- 阶段 7：写入一致性模型

## Q4：为什么更新文档不是原地修改？

### 一句话答案

因为 Lucene segment 是不可变的，更新文档本质上是把旧文档标记删除，再写入一个新版本，后续由 merge 物理清理旧版本。

### 核心链路

```text
update document
-> locate old doc
-> mark old doc as deleted
-> index new document version
-> refresh 后新版本可见
-> merge 时清理旧版本
```

### 为什么这样设计

不可变 segment 简化并发读、缓存和文件系统使用。ES 用追加写和后台合并换取搜索性能和并发读稳定性。

### 常见追问

**频繁更新有什么问题？**

会产生更多删除标记和新 segment，增加 merge 压力，写入和查询都可能受影响。

**ES 适合高频更新的主存储吗？**

通常不适合。ES 更适合作为搜索和分析引擎，主数据仍应放在 MySQL、PostgreSQL 等数据库中，再同步到 ES。

### 生产场景怎么说

如果业务字段频繁变化，应该减少 ES 文档更新频率，做异步合并、批量更新，或调整建模方式，避免把高频变化字段放进大文档里频繁重建。

### 关联章节

- 阶段 2：数据建模
- 阶段 6：Segment 不可变
- 阶段 9：数据同步

## Q5：primary 和 replica 写入如何协调？

### 一句话答案

写请求会先路由到目标 primary shard，primary 执行写入后再复制给 replica，满足等待条件后返回客户端。

### 核心链路

```text
client
-> coordinating node
-> route to primary shard
-> primary validates and writes
-> primary forwards operation to replica shards
-> replicas acknowledge
-> response returns to client
```

### 为什么这样设计

Primary 作为单分片写入顺序的协调者，避免同一文档在多个副本上发生写入顺序冲突。Replica 提供冗余和读扩展。

### 常见追问

**wait_for_active_shards 有什么作用？**

它控制写入前需要多少活跃 shard。设置更严格能提高副本安全性，但也可能在副本不可用时降低可用性。

**replica 写失败怎么办？**

primary 可以成功但副本失败会导致集群状态或副本健康变化，后续需要恢复副本或重新分配 shard。面试中重点说清 primary 是写入协调点，replica 是复制和高可用保障。

### 生产场景怎么说

如果写入延迟升高，要看 replica 是否慢、节点 IO 是否高、网络是否抖动、bulk 并发是否过大，以及 `wait_for_active_shards` 是否设置得过于严格。

### 关联章节

- 阶段 6：写入全链路
- 阶段 7：集群架构与高可用
- 阶段 8：写入调优
```

- [ ] **Step 2: Verify required write-path questions exist**

Run:

```bash
rg -n "^## Q[1-5]|^### 一句话答案|^### 核心链路|^### 生产场景怎么说" elasticsearch/roadmap/11-interview/02-write-path-deep-dive.md
```

Expected: `rg` prints Q1-Q5 and repeated answer-template headings.

- [ ] **Step 3: Commit task 2**

Run:

```bash
git add elasticsearch/roadmap/11-interview/02-write-path-deep-dive.md
git commit -m "Add Elasticsearch write path interview notes"
```

Expected: commit succeeds and only the write-path document is included.

---

### Task 3: Add Search Path Deep Dive

**Files:**
- Create: `elasticsearch/roadmap/11-interview/03-search-path-deep-dive.md`

- [ ] **Step 1: Create the search-path file**

Create `elasticsearch/roadmap/11-interview/03-search-path-deep-dive.md` with this content:

```markdown
# ES 查询链路原理追问

> **目标**：把一次查询从请求文本、分词、倒排索引、打分、query phase、fetch phase 到结果合并讲清楚。面试时重点说明查询为什么快、什么时候慢、慢在哪里。

## Q1：一个 `match` 查询从请求到返回经历了什么？

### 一句话答案

`match` 查询会先使用字段对应的 analyzer 分析查询文本，再到每个相关 shard 上查倒排索引、计算相关性分数，最后由 coordinating node 合并各 shard 的 TopN 结果并 fetch 文档内容返回。

### 核心链路

```text
client search request
-> coordinating node
-> query text analyzed by field analyzer
-> terms lookup in term dictionary
-> posting list returns candidate doc IDs
-> shard-level BM25 scoring
-> query phase returns TopN doc IDs and scores
-> fetch phase loads _source
-> coordinating node merges and returns hits
```

### 为什么这样设计

倒排索引让 ES 能从 term 快速定位候选文档，而不是扫描所有文档。分布式查询让每个 shard 局部算 TopN，coordinating node 只合并候选结果，避免集中扫描全量数据。

### 常见追问

**为什么 `match` 会分词？**

因为 `match` 是全文查询，会使用字段 analyzer 把查询文本转成 term，再用这些 term 查询倒排索引。

**查询会打到所有 shard 吗？**

默认会打到目标索引的相关 shard。使用 routing 可以把查询限制到特定 shard，减少 fan-out。

### 生产场景怎么说

如果查询延迟高，要先看是 fan-out 太大、单 shard 查询慢、fetch 阶段 `_source` 太大、排序/聚合成本高，还是 coordinating node 合并压力大。

### 关联章节

- 阶段 3：分词与文本分析
- 阶段 4：Query DSL
- 阶段 6：读取全链路

## Q2：`match` 和 `term` 的本质区别是什么？

### 一句话答案

`match` 会分析查询文本，适合查 `text` 全文字段；`term` 不分析查询文本，按精确 term 匹配，适合查 `keyword`、数值、枚举等精确字段。

### 核心链路

```text
match:
query text -> analyzer -> terms -> inverted index

term:
exact input value -> direct term lookup -> inverted index
```

### 为什么这样设计

全文搜索要处理自然语言，需要分词、归一化、同义词等分析过程。精确过滤要保持输入值的整体语义，不能随意拆分。

### 常见追问

**为什么用 term 查 text 字段经常查不到？**

因为 text 字段索引时已经被 analyzer 拆成多个 term，`term` 查询不会分析输入，输入值如果和索引中的 term 不完全一致就匹配不到。

**为什么 keyword 常用于聚合？**

keyword 不分词，整体值稳定，通常有 Doc Values，适合排序、过滤和聚合。

### 生产场景怎么说

电商商品名一般用 `text` 做全文搜索，同时用 `.keyword` 子字段做排序、去重或精确过滤。状态、类型、ID、租户号一般直接建成 `keyword`。

### 关联章节

- 阶段 2：Mapping 与数据建模
- 阶段 3：分词
- 阶段 4：Query DSL

## Q3：BM25 是什么，为什么影响排序？

### 一句话答案

BM25 是 ES 默认的相关性打分模型，它综合词频、逆文档频率和字段长度归一化，决定一个文档和查询词的相关程度。

### 核心链路

```text
query terms
-> term frequency: 查询词在文档中出现多少
-> inverse document frequency: 查询词是否稀有
-> field length normalization: 字段越短命中越集中
-> final score
```

### 为什么这样设计

搜索排序不能只看是否命中，还要判断哪个文档更相关。稀有词通常区分度更高，短字段中的命中通常更集中，重复出现也会提高相关性但不能无限放大。

### 常见追问

**为什么某些文档明明包含关键词却排在后面？**

可能因为字段更长、词频低、命中的词更常见，或其他字段 boost、function_score、排序条件影响了最终结果。

**怎么调业务排序？**

可以用字段 boost、function_score、rescore 或业务排序字段，把文本相关性和销量、时间、质量分等业务信号结合。

### 生产场景怎么说

商品搜索通常不能只靠 BM25。可以先用 BM25 保证文本相关性，再用 function_score 融合销量、库存、点击率、上架时间和人工权重。

### 关联章节

- 阶段 4：BM25、function_score、rescore

## Q4：深度分页为什么慢？

### 一句话答案

因为 `from + size` 深度分页要求每个 shard 都取出更多候选结果，再由 coordinating node 全局排序和丢弃前面的结果，页数越深，排序、内存和网络成本越高。

### 核心链路

```text
from=10000,size=10
-> each shard collects top 10010
-> coordinating node merges shard results
-> discard first 10000
-> return 10 hits
```

### 为什么这样设计

分布式搜索不知道某个 shard 的局部第 10010 名在全局排序中排第几，所以每个 shard 都必须返回足够多的候选结果给 coordinating node 合并。

### 常见追问

**search_after 怎么解决？**

`search_after` 使用上一页最后一条记录的排序值继续向后查，不再从头跳过大量结果，适合用户连续翻页。

**scroll 和 PIT 怎么选？**

scroll 适合后台批量遍历和导出；PIT 配合 search_after 适合稳定视图下的深分页；普通用户翻页优先 search_after，不建议用 scroll 承载在线搜索。

### 生产场景怎么说

如果产品要求跳到第 1000 页，要先挑战需求。搜索系统通常限制最大页数，或改成 search_after、游标翻页、导出任务，避免在线查询拖垮集群。

### 关联章节

- 阶段 4：深度分页
- 阶段 8：查询优化

## Q5：query phase 和 fetch phase 分别做什么？

### 一句话答案

Query phase 在各 shard 上执行查询并返回 TopN 文档 ID 和分数；fetch phase 根据最终命中的文档 ID 拉取 `_source`、高亮、字段等完整结果。

### 核心链路

```text
query phase:
shards execute query -> local top hits -> coordinating node merges global top hits

fetch phase:
coordinating node asks owning shards -> load _source/stored fields/highlight -> return full hits
```

### 为什么这样设计

先只返回轻量的 ID 和分数，可以减少网络传输和内存占用。只有全局 TopN 确定后，才加载真正需要返回的文档内容。

### 常见追问

**fetch phase 会慢在哪里？**

`_source` 很大、高亮字段很大、返回字段太多、跨 shard 请求多，都会让 fetch phase 变慢。

**怎么优化？**

控制返回字段，避免大字段默认返回，必要时使用 stored fields、docvalue_fields 或业务侧拆分详情查询。

### 生产场景怎么说

搜索列表页不应该返回完整大文档。可以只返回列表必要字段，详情页再按 ID 查询完整内容。

### 关联章节

- 阶段 4：搜索执行流程
- 阶段 6：读取链路
```

- [ ] **Step 2: Verify required search-path questions exist**

Run:

```bash
rg -n "^## Q[1-5]|match|BM25|深度分页|query phase|fetch phase" elasticsearch/roadmap/11-interview/03-search-path-deep-dive.md
```

Expected: `rg` prints Q1-Q5 and the main search-path terms.

- [ ] **Step 3: Commit task 3**

Run:

```bash
git add elasticsearch/roadmap/11-interview/03-search-path-deep-dive.md
git commit -m "Add Elasticsearch search path interview notes"
```

Expected: commit succeeds and only the search-path document is included.

---

### Task 4: Add Storage Structures Deep Dive

**Files:**
- Create: `elasticsearch/roadmap/11-interview/04-storage-structures.md`

- [ ] **Step 1: Create the storage-structures file**

Create `elasticsearch/roadmap/11-interview/04-storage-structures.md` with this content:

```markdown
# ES 存储结构原理追问

> **目标**：把倒排索引、Term Dictionary、FST、Posting List、Doc Values、Stored Fields、Fielddata、Segment 这些底层结构讲清楚。面试中重点解释它们分别解决什么问题，以及代价是什么。

## Q1：什么是倒排索引？

### 一句话答案

倒排索引是从 term 到文档列表的映射，让搜索引擎可以通过关键词快速找到包含它的文档，而不是逐条扫描所有文档。

### 核心链路

```text
document text
-> analyzer produces terms
-> term -> doc IDs
-> query term lookup
-> candidate documents
```

### 为什么这样设计

全文搜索的核心问题是“给定词，找文档”。倒排索引直接按这个访问模式组织数据，因此比按文档逐条扫描更适合搜索。

### 常见追问

**倒排索引和 B+ 树有什么区别？**

B+ 树更适合范围查询、排序和主键查找；倒排索引更适合多 term 的全文检索和相关性排序。

### 生产场景怎么说

搜索商品标题、文章正文、日志 message 时，用倒排索引能快速定位候选文档；订单号、状态、租户号这类精确字段则更依赖 keyword 和过滤。

### 关联章节

- 阶段 1：倒排索引直觉
- 阶段 3：分词
- 阶段 6：Lucene 底层结构

## Q2：Term Dictionary、FST、Posting List 分别是什么？

### 一句话答案

Term Dictionary 保存所有 term，FST 帮助快速定位 term，Posting List 保存包含该 term 的文档 ID 及相关信息。

### 核心链路

```text
query term
-> FST narrows term lookup
-> Term Dictionary confirms exact term
-> Posting List returns doc IDs
-> scoring uses frequency, positions, norms and statistics
```

### 为什么这样设计

Term 数量可能很大，不能低效扫描全部 term。FST 以较小内存支持快速前缀定位，Posting List 则把候选文档压缩存储，支持高效交并集和打分。

### 常见追问

**Posting List 里只有 doc ID 吗？**

不止。还可能包含词频、位置、offset 等信息，具体取决于字段索引配置。这些信息会影响短语查询、高亮和打分。

**skip data 是什么？**

这是深挖内容。Posting List 很长时，可以用跳跃结构加速跳过不可能匹配的 doc 区间，避免逐个 doc ID 扫描。

### 生产场景怎么说

如果 wildcard、regexp、前缀查询使用不当，可能导致 term 枚举范围过大，即使倒排索引存在也会慢。生产上应限制这类查询或用 edge_ngram、completion 等更合适的建模方式。

### 关联章节

- 阶段 4：模式匹配查询
- 阶段 6：FST、Posting List

## Q3：Doc Values 为什么适合排序和聚合？

### 一句话答案

Doc Values 是面向列的磁盘结构，按字段组织每个文档的值，适合排序、聚合和脚本访问这类“按字段扫描很多文档”的场景。

### 核心链路

```text
inverted index:
term -> doc IDs

doc values:
doc ID -> field value

aggregation/sort:
matching doc IDs -> read field values -> compute buckets/order
```

### 为什么这样设计

倒排索引适合从 term 找文档，但聚合和排序经常是拿到一批 doc ID 后读取某个字段值。Doc Values 按列存储，减少 heap 压力，并更适合这种访问模式。

### 常见追问

**为什么 keyword 字段适合聚合？**

keyword 保留整体值，并默认支持 Doc Values，聚合时可以稳定读取字段值。

**text 字段为什么不能直接聚合？**

text 字段被分词后不再代表原始整体值。若强行对 text 聚合，通常需要启用 Fielddata，会占用大量 heap。

### 生产场景怎么说

做品牌、状态、城市、租户等聚合时，应使用 keyword 或数值字段。不要对大文本字段开 Fielddata 来聚合，应该建 `.keyword` 子字段或重新设计 mapping。

### 关联章节

- 阶段 2：Mapping
- 阶段 5：聚合
- 阶段 6：Doc Values

## Q4：Fielddata 为什么容易造成堆内存压力？

### 一句话答案

Fielddata 会把 text 字段的倒排结构加载并转换成便于按文档访问的内存结构，数据量大时会占用大量 JVM heap，容易触发 GC 或 circuit breaker。

### 核心链路

```text
text field aggregation/sort
-> fielddata loads terms into heap
-> heap usage rises
-> GC pressure or circuit breaker
```

### 为什么这样设计

text 字段默认是为全文搜索设计的，不是为聚合和排序设计的。Fielddata 是一种补救机制，但代价很高。

### 常见追问

**怎么避免 Fielddata 问题？**

建模时给需要聚合、排序的字符串字段增加 keyword 子字段；聚合使用 `field.keyword`，不要直接对 `field` 做 terms aggregation。

### 生产场景怎么说

如果线上 heap 突然升高，且慢查询或 profile 显示对 text 字段聚合排序，要立刻改查询使用 keyword 字段。长期修复是调整 mapping 并 reindex。

### 关联章节

- 阶段 2：text vs keyword
- 阶段 5：Doc Values 与 Fielddata
- 阶段 8：内存调优

## Q5：Segment 不可变有什么好处和代价？

### 一句话答案

Segment 不可变让搜索可以无锁并发、缓存更稳定、文件系统友好；代价是更新删除不能原地修改，会产生删除标记和 merge 成本。

### 核心链路

```text
immutable segment
-> concurrent search without modifying old data
-> update creates new version
-> delete creates delete marker
-> merge compacts segments and removes deleted docs
```

### 为什么这样设计

搜索引擎重读多写少和并发读性能。不可变 segment 让读路径简单稳定，把写入和删除的复杂度转移到后台 merge。

### 常见追问

**删除文档会马上释放磁盘吗？**

不会。删除先是标记删除，等后续 merge 才会物理清理。

**更新频繁有什么影响？**

会增加删除标记和 merge 压力，进而影响 IO、CPU 和查询延迟。

### 生产场景怎么说

高频更新场景要谨慎使用 ES 作为主存储。可以通过批量更新、降低更新频率、拆分高频字段、优化 refresh 和 shard 设计来控制成本。

### 关联章节

- 阶段 6：Segment 生命周期
- 阶段 8：写入优化
```

- [ ] **Step 2: Verify storage topics exist**

Run:

```bash
rg -n "倒排索引|Term Dictionary|FST|Posting List|Doc Values|Fielddata|Segment" elasticsearch/roadmap/11-interview/04-storage-structures.md
```

Expected: `rg` prints all required storage topics.

- [ ] **Step 3: Commit task 4**

Run:

```bash
git add elasticsearch/roadmap/11-interview/04-storage-structures.md
git commit -m "Add Elasticsearch storage internals interview notes"
```

Expected: commit succeeds and only the storage-structures document is included.

---

### Task 5: Add Cluster And Shard Deep Dive

**Files:**
- Create: `elasticsearch/roadmap/11-interview/05-cluster-and-shard.md`

- [ ] **Step 1: Create the cluster-and-shard file**

Create `elasticsearch/roadmap/11-interview/05-cluster-and-shard.md` with this content:

```markdown
# ES 分片与集群原理追问

> **目标**：把 routing、primary/replica、选主、脑裂、cluster state、分片分配、故障恢复和 oversharding 讲成分布式系统问题，而不是只背 ES 名词。

## Q1：文档如何路由到 shard？

### 一句话答案

ES 根据 routing 值计算 hash，再对 primary shard 数取模，决定文档属于哪个 primary shard；默认 routing 是文档 `_id`，也可以显式指定。

### 核心链路

```text
document id or custom routing
-> hash(routing)
-> modulo number_of_primary_shards
-> target primary shard
-> replica copies follow primary
```

### 为什么这样设计

哈希路由能让文档较均匀分布到多个 primary shard，也让同一个 routing 的文档稳定落到同一个 shard。

### 常见追问

**什么时候使用自定义 routing？**

多租户或强关联数据场景可以按 tenant_id、user_id 等 routing，让相关查询只打一个 shard，减少 fan-out。但要防止热点租户导致 shard 倾斜。

### 生产场景怎么说

如果某租户数据量特别大，自定义 routing 可能造成单 shard 热点。设计多租户索引时要权衡查询效率、热点风险和隔离要求。

### 关联章节

- 阶段 2：多租户索引设计
- 阶段 7：分片路由
- 阶段 8：查询优化

## Q2：primary shard 数为什么不能直接修改？

### 一句话答案

因为文档路由依赖 `hash(routing) % number_of_primary_shards`，如果 primary shard 数变化，已有文档的 shard 归属会整体改变，因此通常需要新建索引并 reindex。

### 核心链路

```text
old shard count = 5
hash(id) % 5 -> shard A

new shard count = 8
hash(id) % 8 -> shard B
```

### 为什么这样设计

固定 primary shard 数让路由计算简单稳定。如果允许随意修改，就必须重分布大量历史数据，复杂度和成本都很高。

### 常见追问

**那如何扩容？**

可以增加 replica 提升读吞吐；使用 rollover 新建更多 shard 的新索引；必要时新建目标索引并 reindex；特定场景可以使用 split/shrink，但有前提条件。

### 生产场景怎么说

建索引前要做容量规划，结合单 shard 目标大小、数据增长、查询模式和 ILM。日志类数据通过时间分索引和 rollover 缓解长期扩容问题。

### 关联章节

- 阶段 2：索引设计模式
- 阶段 7：Shard 机制
- 阶段 8：容量规划

## Q3：ES 如何避免脑裂？

### 一句话答案

ES 通过 master-eligible 节点投票和多数派机制选主，只有获得法定多数的节点才能成为 master，网络分区时少数派不能单独选主。

### 核心链路

```text
master-eligible nodes
-> voting configuration
-> election requires majority
-> majority side can elect master
-> minority side cannot form valid cluster master
```

### 为什么这样设计

脑裂的本质是多个 master 同时管理集群状态，导致写入和分片元数据分歧。多数派选主保证同一时刻只有一个合法 master。

### 常见追问

**为什么推荐 3 个 master-eligible 节点？**

3 个节点可以容忍 1 个 master-eligible 节点故障，同时仍然保留多数派。2 个节点容错和选主都比较尴尬。

### 生产场景怎么说

生产集群通常至少 3 个专用 master-eligible 节点，避免和重负载 data 节点混用，降低 GC 或 IO 抖动影响选主稳定性的风险。

### 关联章节

- 阶段 7：节点发现与选主、脑裂

## Q4：节点宕机后分片如何恢复？

### 一句话答案

如果 primary 所在节点宕机，ES 会把可用 replica 提升为新的 primary，再为缺失副本重新分配 shard，并通过恢复流程补齐数据。

### 核心链路

```text
node failure detected
-> master updates cluster state
-> replica promoted to primary if needed
-> unassigned replica shards allocated to nodes
-> shard recovery copies missing segment/translog data
-> cluster returns toward green
```

### 为什么这样设计

Primary/replica 模型让单节点故障时服务可以继续。Master 负责集群状态和分片分配，data 节点负责实际 shard 数据恢复。

### 常见追问

**yellow 和 red 有什么区别？**

yellow 表示 primary 都可用但部分 replica 不可用；red 表示至少有 primary shard 不可用，部分数据不可读或不可写。

### 生产场景怎么说

看到 yellow 先查未分配 replica 的原因，可能是单节点集群、副本数过多、磁盘水位、节点不足或 allocation 规则限制。看到 red 要优先恢复 primary，查节点、磁盘、快照和分片分配解释。

### 关联章节

- 阶段 7：故障恢复
- 阶段 10：快照与恢复

## Q5：为什么 oversharding 会伤害性能？

### 一句话答案

Shard 是有成本的。Shard 太多会增加 cluster state、文件句柄、segment 元数据、调度、查询 fan-out 和 master 管理压力。

### 核心链路

```text
too many shards
-> larger cluster state
-> more segments and file handles
-> more per-shard query overhead
-> more coordination cost
-> higher heap and CPU pressure
```

### 为什么这样设计

每个 shard 本质上都是一个 Lucene index，有独立的 segment、缓存、统计信息和生命周期。分片提升并行和容量，但不是越多越好。

### 常见追问

**怎么规划 shard？**

根据数据量、增长速度、查询模式、单 shard 目标大小、节点数和 ILM 策略规划。避免为小索引创建大量 shard。

### 生产场景怎么说

如果集群 heap 高、查询 fan-out 大、master 压力高，同时 shard 数远超数据规模，要考虑合并小索引、调整模板、shrink 只读索引或用 rollover 控制 shard 大小。

### 关联章节

- 阶段 7：Shard 机制
- 阶段 8：容量规划
- 阶段 10：ILM
```

- [ ] **Step 2: Verify cluster topics exist**

Run:

```bash
rg -n "routing|primary shard|脑裂|yellow|red|oversharding|cluster state" elasticsearch/roadmap/11-interview/05-cluster-and-shard.md
```

Expected: `rg` prints all required cluster topics.

- [ ] **Step 3: Commit task 5**

Run:

```bash
git add elasticsearch/roadmap/11-interview/05-cluster-and-shard.md
git commit -m "Add Elasticsearch shard and cluster interview notes"
```

Expected: commit succeeds and only the cluster-and-shard document is included.

---

### Task 6: Add Production Troubleshooting Interview Notes

**Files:**
- Create: `elasticsearch/roadmap/11-interview/06-production-troubleshooting.md`

- [ ] **Step 1: Create the troubleshooting file**

Create `elasticsearch/roadmap/11-interview/06-production-troubleshooting.md` with this content:

```markdown
# ES 生产排查面试追问

> **目标**：把 ES 原理转成线上问题排查表达。面试官问“查询慢怎么办”“写入慢怎么办”“yellow/red 怎么办”时，按症状、证据、机制、修复、验证来回答。

## 回答框架

```text
症状：
第一轮检查：
可能机制：
证据：
修复选项：
验证方式：
面试表达：
```

## 场景 1：查询突然变慢

### 症状

接口 P95/P99 上升，ES `_search` 请求耗时增加，业务搜索列表响应变慢。

### 第一轮检查

- 查慢查询日志，确认慢的是 query、fetch、sort 还是 aggregation。
- 用 profile API 看具体 query 子句耗时。
- 看是否有深度分页、大 size、wildcard、regexp、script、复杂 nested 查询。
- 看 shard 数和单 shard 数据量，确认是否 fan-out 过大。
- 看节点 CPU、heap、GC、IO、thread pool search queue。

### 可能机制

查询慢通常不是单一原因。常见机制包括：查询条件无法有效利用倒排索引、深度分页导致每个 shard 取大量候选、fetch 阶段拉取大 `_source`、聚合读大量 Doc Values、segment 太多、节点资源瓶颈或 shard 分布不均。

### 证据

```text
slowlog
profile API
_cat/thread_pool/search
_nodes/stats/jvm,indices,fs,thread_pool
_cat/shards
_cat/segments
```

### 修复选项

- 改写查询：filter 替代不需要打分的 must，避免前缀过宽的 wildcard。
- 深分页改成 search_after 或 PIT。
- 控制返回字段，避免列表页返回大 `_source`。
- 优化 mapping，给过滤/聚合字段使用 keyword。
- 调整 shard 和 routing，降低无效 fan-out。
- 对只读索引评估 force merge。

### 验证方式

对比优化前后的 slowlog、profile API、P95/P99、search thread pool queue、CPU、heap 和业务接口耗时。

### 面试表达

我会先区分慢在 query phase 还是 fetch phase。如果 profile 显示 query 慢，就看查询是否命中倒排索引、是否深分页或 fan-out 太大；如果 fetch 慢，就看 `_source`、高亮和返回字段。定位后再分别做查询改写、字段裁剪、分页改造、shard/routing 优化，并用慢查询日志和 P99 验证。

## 场景 2：写入吞吐下降

### 症状

bulk 请求变慢，写入队列堆积，数据同步延迟增加。

### 第一轮检查

- 看 bulk size 和客户端并发是否过大或过小。
- 看 write thread pool queue/rejected。
- 看 refresh_interval、replica 数、translog durability。
- 看磁盘 IO、merge backlog、segment 数。
- 看是否有热点 shard 或 routing 倾斜。
- 看 MySQL、MQ、CDC 链路是否上游已经堆积。

### 可能机制

写入慢可能来自客户端批量策略、refresh 太频繁、replica 写入慢、merge 压力、磁盘 IO 瓶颈、热点 shard 或同步链路堆积。

### 证据

```text
_cat/thread_pool/write
_nodes/stats/indices/indexing,merge,refresh,translog
_cat/shards
_cat/segments
iostat or container disk metrics
MQ lag or CDC lag
```

### 修复选项

- 调整 bulk size 和并发。
- 批量导入期间调大 refresh_interval，导入后手动 refresh。
- 写多读少场景降低 replica，导入完成后恢复。
- 优化 shard 数和 routing，避免热点。
- 扩容 data 节点或提升磁盘能力。
- 上游同步增加幂等和重试，避免乱序覆盖。

### 验证方式

观察写入 TPS、bulk latency、rejected 数、refresh/merge 时间、数据同步 lag 和业务可见延迟。

### 面试表达

我会把写入慢拆成客户端、ES 写入链路、磁盘和上游同步四层。先看 rejected、merge、refresh、IO 和 shard 分布，再决定是调 bulk、refresh_interval、replica，还是处理热点 shard 和上游 lag。

## 场景 3：heap 使用率高或频繁 GC

### 症状

JVM heap 长期高水位，GC 时间变长，查询或写入出现抖动。

### 第一轮检查

- 看是否有大聚合、对 text 字段启用 Fielddata、script 查询。
- 看 shard 数是否过多导致元数据和缓存压力。
- 看 query cache、request cache、fielddata cache。
- 看是否有大量 segment 或高 cardinality 聚合。
- 看堆大小是否超过压缩指针建议范围。

### 可能机制

heap 高通常和 Fielddata、聚合桶过多、shard/segment 元数据过多、缓存压力、查询并发高或 JVM 配置不合理有关。

### 证据

```text
_nodes/stats/jvm,indices/fielddata,indices/query_cache,indices/request_cache
_cat/fielddata
_cat/shards
_cat/segments
GC logs
```

### 修复选项

- 禁止对 text 字段聚合，改用 keyword。
- 降低 terms aggregation size，减少嵌套层级。
- 使用 composite 分页聚合。
- 合理控制 shard 数。
- 检查堆大小和 GC 策略。

### 验证方式

对比 heap 曲线、GC pause、fielddata 使用量、circuit breaker 次数和查询延迟。

### 面试表达

heap 高我不会先盲目加内存，而是先找是谁占用 heap：Fielddata、聚合、缓存、shard 元数据还是查询并发。证据明确后再改 mapping、查询、聚合方式或 shard 设计。

## 场景 4：聚合 OOM 或 circuit breaker 触发

### 症状

聚合查询失败，返回 circuit breaker 异常，或者节点 heap 飙升。

### 第一轮检查

- 看聚合字段是不是 keyword/numeric/date，而不是 text。
- 看 terms size、嵌套聚合层数和 bucket 数。
- 看 cardinality 是否很高。
- 看是否一次聚合全量历史数据。

### 可能机制

聚合要为大量 bucket 和中间状态分配内存。高基数字段、大 size、多层嵌套和 text Fielddata 都可能让内存暴涨。

### 证据

```text
failed search response
_nodes/stats/breaker
profile API
field mapping
_cat/fielddata
```

### 修复选项

- 降低 bucket 数和 size。
- 用 filter 先缩小数据范围。
- 使用 composite aggregation 分页拉取。
- 高基数去重用 cardinality 近似聚合。
- 改 mapping，用 keyword/数值字段聚合。

### 验证方式

观察 breaker 触发次数、heap 使用、聚合耗时、结果精度是否满足业务。

### 面试表达

聚合问题我会先看字段类型和 bucket 数。ES 聚合不是无限内存计算，必须控制基数、范围和桶数量。需要全量大聚合时，考虑离线计算、分页聚合或预聚合。

## 场景 5：集群 yellow 或 red

### 症状

Cluster health 变成 yellow 或 red，部分索引副本或主分片不可用。

### 第一轮检查

- `_cluster/health` 看影响范围。
- `_cat/shards` 找 unassigned shard。
- `_cluster/allocation/explain` 看为什么不能分配。
- 看节点是否宕机、磁盘水位、allocation 规则、副本数和节点数。
- red 时优先确认 primary shard 是否可恢复。

### 可能机制

yellow 表示 primary 可用但 replica 未完全分配；red 表示至少有 primary 不可用。原因可能是节点故障、磁盘水位、节点数量不足、分配规则限制、索引损坏或恢复中。

### 证据

```text
GET _cluster/health
GET _cat/shards?v
GET _cluster/allocation/explain
GET _cat/nodes?v
GET _cat/allocation?v
```

### 修复选项

- 恢复故障节点。
- 增加节点或降低 replica 数。
- 释放磁盘空间或扩容磁盘。
- 修正 allocation filtering。
- red 且 primary 丢失时从 snapshot 恢复。

### 验证方式

确认 unassigned shard 归零或符合预期，cluster health 恢复 green/yellow，业务读写恢复。

### 面试表达

yellow 和 red 优先级不同。yellow 主要是副本不可用，先查分配原因；red 影响 primary，要优先恢复数据可用性。排查时我会用 allocation explain 找 ES 自己给出的不能分配原因。

## 场景 6：数据同步延迟或不一致

### 症状

MySQL 已更新，但 ES 搜索结果延迟或显示旧数据。

### 第一轮检查

- 区分 ES refresh 延迟和同步链路延迟。
- 看 MQ/CDC lag。
- 看消费端失败、重试、死信。
- 看是否有乱序消息覆盖新版本。
- 看 ES 写入是否被 rejected 或慢。

### 可能机制

ES 作为搜索副本通常是最终一致。延迟可能来自 refresh、MQ 堆积、CDC 延迟、消费者失败、bulk 写入慢或乱序覆盖。

### 证据

```text
database update time
message event time
consumer process time
ES index response time
document version or updated_at
MQ lag / CDC lag
```

### 修复选项

- 使用版本号或更新时间做幂等保护。
- 消费端失败进入重试和死信。
- 建立全量校对和修复任务。
- 调整 bulk 和 refresh 策略。
- 对强一致需求回源数据库确认。

### 验证方式

检查同步 lag、错单数、校对差异、重试成功率和 ES 文档版本。

### 面试表达

我会明确 ES 通常不是主库，而是搜索视图。同步一致性的核心是最终一致、幂等、乱序保护、重试死信和定期校对。强一致读不能只依赖 ES。

## 本阶段总结

生产排查面试不要只说“看日志、看监控”。更好的回答是：

```text
先定位症状属于 query、fetch、write、merge、heap、shard、sync 哪一层；
再收集对应证据；
用 ES 的底层机制解释为什么会慢或失败；
给出不会扩大故障面的修复；
最后说明如何验证结果。
```
```

- [ ] **Step 2: Verify troubleshooting scenarios exist**

Run:

```bash
rg -n "^## 场景 [1-6]|查询突然变慢|写入吞吐下降|heap|聚合 OOM|yellow|数据同步" elasticsearch/roadmap/11-interview/06-production-troubleshooting.md
```

Expected: `rg` prints all six troubleshooting scenarios.

- [ ] **Step 3: Commit task 6**

Run:

```bash
git add elasticsearch/roadmap/11-interview/06-production-troubleshooting.md
git commit -m "Add Elasticsearch production troubleshooting interview notes"
```

Expected: commit succeeds and only the troubleshooting document is included.

---

### Task 7: Update Top-Level Elasticsearch Roadmap Navigation

**Files:**
- Modify: `elasticsearch/elasticsearch-roadmap.md`

- [ ] **Step 1: Update the navigation table paths**

In `elasticsearch/elasticsearch-roadmap.md`, update the stage navigation table so these rows use real paths:

```markdown
| **7** | [集群架构与高可用](./roadmap/07-cluster-architecture/) | 节点角色 / 分片路由 / 选主 / 脑裂 / 一致性模型 / 故障恢复 / 分片分配与再平衡 | 阶段6 |
| **10** | [生产运维与高级特性](./roadmap/10-production-advanced/) | ILM / 快照恢复 / 滚动升级 / 安全 / ELK 架构 / Suggester / Geo / 向量搜索 / ES 8.x | 阶段8 + 阶段9 |
| **11** | [面试串联](./roadmap/11-interview/) | ES 原理追问链 / 写入链路 / 查询链路 / 存储结构 / 分片集群 / 生产排查 / 项目叙述 | 全部 |
```

- [ ] **Step 2: Add a short stage 11 implementation note**

In the `## 阶段 11：面试串联（持续）` section, replace the opening paragraph with:

```markdown
> 将所有知识融会贯通，以面试视角重新组织。阶段 1-10 负责把 ES 学懂，阶段 11 负责把这些原理讲出来，尤其是写入链路、查询链路、存储结构、分片集群和生产排查这些面试追问链。
```

Then add this subsection before `### 11.1 Top 30 高频面试题`:

```markdown
### 11.0 原理追问链

新增独立目录：[roadmap/11-interview/](./roadmap/11-interview/)

建议按这个顺序练：

1. `01-internals-question-map.md`：先确认 ES 底层必会问题。
2. `02-write-path-deep-dive.md`：写入、refresh、flush、translog、segment、merge。
3. `03-search-path-deep-dive.md`：match 查询、BM25、query/fetch、深度分页。
4. `04-storage-structures.md`：倒排索引、FST、Posting List、Doc Values、Fielddata。
5. `05-cluster-and-shard.md`：routing、primary/replica、选主、脑裂、故障恢复。
6. `06-production-troubleshooting.md`：查询慢、写入慢、heap 高、聚合 OOM、yellow/red、同步延迟。

每个问题按「一句话答案 → 核心链路 → 为什么这样设计 → 常见追问 → 生产场景」来练。
```

- [ ] **Step 3: Verify links point to existing paths**

Run:

```bash
test -d elasticsearch/roadmap/07-cluster-architecture
test -d elasticsearch/roadmap/10-production-advanced
test -d elasticsearch/roadmap/11-interview
rg -n "07-cluster-architecture|10-production-advanced|11-interview|11\\.0 原理追问链" elasticsearch/elasticsearch-roadmap.md
```

Expected:

- All `test -d` commands exit with status 0.
- `rg` prints the updated stage 7, stage 10, stage 11 links and the `11.0` subsection.

- [ ] **Step 4: Commit task 7**

Run:

```bash
git add elasticsearch/elasticsearch-roadmap.md
git commit -m "Update Elasticsearch roadmap interview navigation"
```

Expected: commit succeeds and only the top-level roadmap file is included.

---

### Task 8: Final Documentation Verification

**Files:**
- Verify: `elasticsearch/roadmap/11-interview/*.md`
- Verify: `elasticsearch/elasticsearch-roadmap.md`

- [ ] **Step 1: Verify all stage 11 files exist**

Run:

```bash
find elasticsearch/roadmap/11-interview -maxdepth 1 -type f -name '*.md' | sort
```

Expected output:

```text
elasticsearch/roadmap/11-interview/01-internals-question-map.md
elasticsearch/roadmap/11-interview/02-write-path-deep-dive.md
elasticsearch/roadmap/11-interview/03-search-path-deep-dive.md
elasticsearch/roadmap/11-interview/04-storage-structures.md
elasticsearch/roadmap/11-interview/05-cluster-and-shard.md
elasticsearch/roadmap/11-interview/06-production-troubleshooting.md
```

- [ ] **Step 2: Scan for placeholders**

Run:

```bash
rg -n 'TB''D|TO''DO|待''定|待''补|占''位|后续''补' elasticsearch/roadmap/11-interview elasticsearch/elasticsearch-roadmap.md
```

Expected: no matches.

- [ ] **Step 3: Verify every stage 11 file has interview answer language**

Run:

```bash
rg -n "一句话答案|核心链路|常见追问|生产场景|面试表达" elasticsearch/roadmap/11-interview
```

Expected: every stage 11 file appears in the output. `01-internals-question-map.md` should include the template; files 02-05 should include answer headings; file 06 should include production interview wording.

- [ ] **Step 4: Review the final diff**

Run:

```bash
git diff --stat HEAD~7..HEAD
git log --oneline -7
```

Expected:

- The diff stat includes six new files under `elasticsearch/roadmap/11-interview/` and one modified `elasticsearch/elasticsearch-roadmap.md`.
- The log shows the seven task commits.

- [ ] **Step 5: Report completion**

Report:

```text
Implemented Elasticsearch stage 11 interview layer.

Created:
- elasticsearch/roadmap/11-interview/01-internals-question-map.md
- elasticsearch/roadmap/11-interview/02-write-path-deep-dive.md
- elasticsearch/roadmap/11-interview/03-search-path-deep-dive.md
- elasticsearch/roadmap/11-interview/04-storage-structures.md
- elasticsearch/roadmap/11-interview/05-cluster-and-shard.md
- elasticsearch/roadmap/11-interview/06-production-troubleshooting.md

Updated:
- elasticsearch/elasticsearch-roadmap.md

Verification:
- all files exist
- no placeholder text found
- roadmap links point to existing directories
```
