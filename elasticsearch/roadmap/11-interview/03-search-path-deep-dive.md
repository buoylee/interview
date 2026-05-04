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

因为 `from + size` 深度分页要求每个 shard 都取出更多候选结果，再由 coordinating node 全局排序和丢弃前面的结果，页数越深，排序、内存和网络成本越高。默认 `index.max_result_window` 是 10000，超过这个窗口还会被 ES 直接拒绝。

### 核心链路

```text
from=9990,size=10
-> each shard collects top 10000
-> coordinating node merges shard results
-> discard first 9990
-> return 10 hits
```

### 为什么这样设计

分布式搜索不知道某个 shard 的局部第 10000 名在全局排序中排第几，所以每个 shard 都必须返回足够多的候选结果给 coordinating node 合并。

### 常见追问

**search_after 怎么解决？**

`search_after` 使用上一页最后一条记录的排序值继续向后查，不再从头跳过大量结果。现代稳定深分页通常推荐 PIT + search_after，既保留一致视图，又避免 `from` 深分页的跳过成本。

**scroll 和 PIT 怎么选？**

PIT 配合 search_after 是稳定深分页的现代推荐模式。scroll 更偏 legacy 或有边界的后台批量遍历、导出场景，适合可以接受持有 search context 的任务，不应作为在线深分页的默认方案。

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
