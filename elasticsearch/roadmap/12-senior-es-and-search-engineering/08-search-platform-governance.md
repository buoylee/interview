# 12.8 搜索平台治理

> **轨道**：B core
>
> **目标**：从“维护一个 ES 集群”提升到“设计一个可被多个业务安全使用的搜索平台”。

搜索平台治理的核心不是把 Elasticsearch API 包一层再开放出去，而是把搜索能力做成一个有边界、有预算、有发布流程、有成本归属的平台产品。平台面对的是多个业务方、多个 tenant、多种查询质量和不同成熟度的调用方；如果让每个业务直接拼任意 DSL，集群稳定性、搜索质量和成本都会被最弱的调用方拖垮。

资深候选人要能把治理讲成一套系统：索引怎么给不同租户和领域建模，查询怎么限制危险形态，资源怎么按租户分配，相关性怎么发布和回滚，观测怎么定位 bad case 和慢查询，成本怎么按存储、查询、向量、rerank、snapshot 分摊。ES 提供了一部分底层能力，例如 `index.max_result_window`、`search.max_buckets`、`search.allow_expensive_queries`、`timeout`、alias routing、circuit breaker 和 slow log；但业务治理不能全部寄托给 ES，tenant 身份、产品套餐、查询模板权限、quota、A/B 实验和成本归因通常必须在平台/API 层实现。

## 平台工程视角

统一搜索平台要先把服务对象讲清楚：它不是一个单一业务的 ES client，而是多个业务、多个应用、多个 tenant、多个搜索领域共同使用的基础能力。调用方可能包括商品搜索、订单搜索、内容搜索、知识库、日志排障、运营后台和 RAG 检索；它们对隔离、延迟、召回、排序、权限、成本和发布节奏的要求都不同。

平台工程的第一条原则是提供安全默认值，而不是把 ES 原始能力全部暴露出去。业务方应该调用平台定义好的 search API、query template、filter contract 和 ranking profile；只有经过审核的高级调用方才能使用受限 DSL 扩展。平台要把危险能力收口，例如无限 deep pagination、大窗口 aggregation、任意 script、leading wildcard、regexp、跨全量索引扫描、超大 `size`、无 tenant filter 的查询，以及未经评估的 rerank 模型调用。

治理目标可以拆成五类：

| 目标 | 具体含义 | 典型机制 |
| --- | --- | --- |
| 稳定性 | 单个 tenant 或 bad query 不能拖垮公共集群 | query budget、timeout、熔断、限流、慢查询治理、热点隔离 |
| 成本 | 资源使用可解释、可归因、可压缩 | per-tenant cost、quota、冷热分层、retention、vector/rerank 预算 |
| 相关性发布 | analyzer、synonym、query rewrite、ranking 变更可评估、可灰度、可回滚 | 版本化、shadow traffic、A/B test、alias 切换、rollback |
| 可观测 | 能定位是查询、索引、shard、租户、版本还是模型导致问题 | metrics、logs、traces、slow log、query diff、tenant dashboard |
| 开发效率 | 业务能快速接入搜索，但不会重复造危险 DSL | API contract、template registry、领域 schema、SDK、测试集 |

一个实用的治理边界可以这样划分：

| 层次 | 应该负责什么 | 不应该假设什么 |
| --- | --- | --- |
| API gateway / search service | tenant 身份、鉴权、quota、query template 选择、DSL allowlist/denylist、实验分桶、降级 | 不要把用户输入直接透传成 ES DSL |
| Search platform control plane | 索引策略、alias、schema 版本、ranking config、synonym 发布、成本归因、dashboard | 不要只靠口头约定让业务方“少查一点” |
| Elasticsearch | 倒排和向量检索、shard routing、alias/filter、index setting、cluster setting、breaker、slow log | 不要指望 ES 理解业务套餐、租户优先级和发布审批 |
| Observability / evaluation | latency、zero-result、CTR、bad query、hot shard、cost、实验指标 | 不要只看 ES 集群指标，忽略搜索质量和租户维度 |

面试里要特别强调：ES 是搜索执行引擎，不是完整的平台治理系统。`search.max_buckets` 可以限制 aggregation bucket 数，`index.max_result_window` 可以限制 `from + size`，circuit breaker 可以保护节点内存，但“某个 tenant 今天还能花多少查询预算”“某个 ranking profile 是否允许给这个业务用”“某个 synonym 变更是否通过灰度”这些必须由平台层控制。

## Multi-tenant Index Strategy

Multi-tenant index strategy 解决的是多个租户和领域如何共享或隔离索引。没有唯一正确答案，关键是按数据量、查询模式、隔离要求、成本和运维复杂度分层。

常见策略：

| 策略 | 适合场景 | 优点 | 风险 |
| --- | --- | --- | --- |
| shared index | 大量小 tenant，schema 接近，数据量和 QPS 都较小 | shard 利用率高，索引数量少，运维简单，冷启动成本低 | tenant filter 必须强制注入；大 tenant 容易制造 hot shard；成本归因和数据隔离更难 |
| index per tenant | tenant 数据量、权限和生命周期差异明显，或合规隔离要求较高 | 隔离清晰，quota 和成本容易归属，单租户迁移和删除简单 | 小 tenant 过多会造成 index/shard 膨胀，cluster state 和运维成本上升 |
| large tenant dedicated index | 少数大客户、大业务线或高价值 tenant 需要专属容量 | 可单独 shard sizing、扩容、压测、SLO 和发布节奏 | 需要容量规划和迁移流程，不能让 dedicated index 变成手工例外 |
| per-domain index | 商品、订单、内容、日志、知识库等领域 schema 和查询模式差异大 | mapping、analyzer、ranking、retention 能按领域优化 | 一个 tenant 可能跨多个 index，权限、alias 和成本归因要统一管理 |
| hybrid strategy | 小 tenant 共享，大 tenant 拆出；按领域分 index，再在领域内做 tenant 分层 | 兼顾成本和隔离，是平台常见形态 | 需要自动化迁移、路由表、alias 管理和容量水位线 |

shared index 的基本做法是所有文档都带 `tenant_id`，平台层在每个 query template 里强制注入 tenant filter，并在写入时校验文档的 tenant。为了减少 shard fanout，可以使用 routing by tenant，把 `_routing` 设置为 `tenant_id` 或稳定 hash 后的 routing key，让同一 tenant 的文档更集中。这样查询时带 `routing` 可以少打 shard，降低协调和查询成本。

routing 不是免费能力。单纯用 `tenant_id` 做 routing 时，大 tenant 会把流量和数据集中到少数 shard，形成 hot shard；小 tenant 太多时，某些 shard 也可能因为 tenant 分布不均变热。更稳妥的做法是：

- 小 tenant 使用 shared index + tenant filter + routing，配合 shard 级指标观察分布。
- 大 tenant 达到数据量、QPS、P99 latency 或成本阈值后迁移到 dedicated index。
- 超大 tenant 可以在业务内再做 routing key 拆分，例如 `tenant_id + category_bucket` 或 `tenant_id + hash_partition`，但 query 必须能带上对应路由或接受 fanout。
- routing 方案必须在索引创建和写入路径就确定，后续改变通常意味着 reindex。

alias 是多租户治理里的重要抽象，但也不能被误解成完整安全边界。常见用法：

- read alias：业务只查 `products_search_v_current`，底层可以指向一个或多个物理 index。
- write alias：写入只打 `is_write_index` 指向的新 index，便于 rollover 或重建。
- tenant alias：给特定 tenant 或 tenant group 绑定 filtered alias，并配置 `routing`、`index_routing` 或 `search_routing`，降低调用方出错概率。
- release alias：相关性或 schema 版本发布时，用 alias 从 `products_v17` 切到 `products_v18`。

filtered alias 可以把 `tenant_id` filter 固化到 alias 上，alias routing 也能把查询导向指定 shard；但如果调用方还能绕过 alias 直接访问底层 index，或者平台没有做鉴权和模板限制，alias 就不是安全隔离。面试中要明确：tenant isolation 的强约束应由鉴权、平台 API、索引权限、文档级权限或独立索引共同保证，alias 更多是访问抽象和运维发布工具。

一个实用的分层决策：

| 判断条件 | 倾向策略 |
| --- | --- |
| tenant 数量很多、每个 tenant 数据小、schema 一致 | shared index + 强制 tenant filter + routing |
| tenant 有合规隔离、删除、备份或专属 SLO 要求 | index per tenant 或 dedicated index |
| 领域 mapping/analyzer/ranking 差异明显 | per-domain index，不要为了租户强行混一套 schema |
| 某个 tenant 占据主要数据或 QPS | large tenant dedicated index，并建立迁移水位线 |
| 需要灰度 analyzer 或 ranking | 新 index + release alias，或 ranking profile 版本化 |

平台要维护一张 tenant/index routing registry：每个 tenant 属于哪个 domain、哪个 index 或 alias、使用什么 routing、当前 schema/analyzer/ranking 版本、quota 和成本归属是什么。没有这张注册表，多租户策略会散落在代码、配置和人工运维里，后续迁移、回滚、计费和排障都会很痛苦。

## Query Budget And Guardrails

Query Budget And Guardrails 是搜索平台治理的中枢。query budget 不是单个 ES 参数，而是平台给一次查询定义的资源预算：最大结果数、最大翻页深度、最多 aggregation bucket、最大 shard fanout、最大 vector candidate、最大 rerank window、最长 timeout、是否允许 expensive query、是否允许 script 或 wildcard，以及失败时如何降级。

平台层应该把搜索请求拆成模板化能力，而不是开放任意 DSL：

```text
business API
-> query template id
-> allowed filters / sort / facets / ranking profile
-> platform guardrail validation
-> ES DSL generated by platform
-> timeout / fallback / observability
```

常见 guardrail：

| 风险 | 平台/API 层控制 | ES 层辅助 |
| --- | --- | --- |
| 超大结果窗口 | 限制 `size` 和 `from + size`，深翻页改用 `search_after` + PIT 或业务游标 | `index.max_result_window` 防止超过 max result window |
| 深分页 | 禁止任意页码跳到几万页；只允许前几页或游标式翻页 | `index.max_result_window` 兜底 |
| 大 aggregation | facet 字段 allowlist，限制 bucket size、嵌套层数和 cardinality 场景 | `search.max_buckets` 限制总 bucket 数 |
| wildcard / regexp | 默认禁止 leading wildcard、宽泛 regexp；只允许 keyword 字段上的受控模板 | `search.allow_expensive_queries=false` 可限制部分 expensive queries |
| script query / script sort | 默认 denylist，只有审核后的内部模板可用 | script sandbox 和 cluster setting 只能兜底，不能表达业务权限 |
| vector / hybrid | 限制 `k`、`num_candidates`、filter 必填、rerank TopK 和模型 deadline | kNN 参数和 index setting 辅助控制成本 |
| cross-index 查询 | 通过 domain API 和 alias 限定目标 index | 索引权限和 alias 兜底 |
| 慢查询 | 按 query hash、template version、tenant 记录慢日志，触发降级或禁用模板 | slow log、profile API、task cancel、timeout |
| 内存压力 | 限制 size、bucket、highlight、script、sort 字段和并发 | circuit breaker 保护节点 |

`index.max_result_window` 的意义是阻止 `from + size` 无限制增大。面试里不要只说“调大 max_result_window”，更资深的回答是：先问业务为什么需要深分页；用户搜索通常只看前几页，运营导出应该走离线任务或 scroll/PIT 方案，后台审计可以用 search_after，不应该让在线搜索路径承受任意 deep pagination。

`search.max_buckets` 是 aggregation 的硬护栏之一，能限制一次响应里最多生成多少 bucket。它不能代替平台的 facet 设计，因为不同字段 cardinality 差异很大：品牌、类目、状态适合做 facet；用户 ID、trace ID、长文本 token、超高基数字段不应该开放给任意聚合。平台应该维护 aggregation allowlist，定义每个 facet 的最大 size、排序方式、是否允许 nested aggregation 和是否允许按 tenant 开启。

`timeout` 要按产品 SLO 和阶段预算配置。例如整体搜索 P95 目标 300 ms，可以给 query rewrite、ES retrieval、vector retrieval、rerank 和 feature service 分别设置 deadline。ES search request 的 `timeout` 是底层兜底，平台还要有上游请求 deadline 和 fallback；否则外部 rerank 或特征服务慢了，ES timeout 并不能保护整个链路。

circuit breaker 是最后防线，不是容量治理策略。breaker 触发说明节点为了保护内存拒绝了请求；平台应该在 breaker 之前就通过 query budget 限制危险请求。把 breaker 当成日常限流机制，会造成用户可见错误、P99 抖动和租户之间互相影响。

DSL allowlist/denylist 要做到字段级、操作级和模板级：

- allowlist：允许哪些 query type、哪些字段可搜索、哪些字段可排序、哪些字段可 facet、哪些 ranking profile 可用。
- denylist：禁止或限制 `script_score`、无边界 `regexp`、leading `wildcard`、高成本 `prefix`、大窗口 `terms`、无 filter 的 kNN、大范围时间扫描。
- template validation：每个 query template 有 owner、版本、预算、适用 domain、允许 tenant、上线状态和回滚版本。
- parameter validation：用户输入必须限制长度、字符集、filter 数量、terms 数量、时间范围和分页窗口。

慢查询处理不要只停在“看 slow log”。平台应该建立慢查询闭环：

1. 记录 query hash、tenant、domain、template id、template version、ranking version、index alias、routing、shard 数、size、bucket 数、timeout、fallback reason。
2. 把慢查询按 query pattern 聚合，区分偶发慢、固定模板慢、某 tenant 慢、某 shard 慢和某 release 后变慢。
3. 对固定模板慢查询做 profile 和 TopK diff，判断是 filter 选择性差、sort 字段问题、aggregation 爆炸、script、wildcard、vector candidate 太大，还是 shard 热点。
4. 对危险模板执行自动化动作：降低窗口、关闭 expensive branch、强制时间范围、回滚 ranking profile、隔离 tenant、或把导出类请求转异步。

## Per-tenant Quota And Isolation

Per-tenant Quota And Isolation 解决的是“公共搜索平台如何避免一个 tenant 把别人的预算花掉”。ES 的 thread pool、search queue、breaker 和 node resource 主要是集群级或节点级保护，不能天然表达 tenant 套餐、业务优先级和成本预算；因此 quota 的主战场在平台/API 层。

需要至少覆盖四类 quota：

| quota 类型 | 例子 | 平台动作 |
| --- | --- | --- |
| QPS quota | 每个 tenant 每秒搜索请求数、burst、并发上限 | token bucket、leaky bucket、按优先级排队、超限返回可解释错误 |
| bulk quota | 每分钟写入文档数、bulk request size、并发 bulk 数 | 写入队列、批大小限制、背压、按 tenant 拆分失败重试 |
| expensive query quota | aggregation、wildcard、regexp、vector、rerank、export 的预算 | 单独计费或扣点，低套餐禁用，高套餐限额 |
| storage quota | 文档数、primary store、向量字段存储、snapshot 保留 | 写入前检查、索引生命周期、超限只读或降级 |

traffic shaping 需要区分请求类型：

- online search：用户交互路径，优先级最高，严格 timeout 和小窗口。
- admin search：运营后台，允许更多 filter 和排序，但 QPS、size 和 aggregation 更保守。
- export / analytics：不走在线 search API，转异步任务或专门分析链路。
- bulk indexing：和 search 隔离队列，避免写入高峰影响查询 P99。
- relevance evaluation / shadow traffic：使用单独 budget，不能挤占线上 tenant。

tenant isolation 可以分层实现：

| 隔离层 | 做法 | 适合解决什么 |
| --- | --- | --- |
| 请求隔离 | API gateway 按 tenant 限流、鉴权、template 权限和优先级 | 防止流量和危险查询互相影响 |
| 查询隔离 | 强制 tenant filter、routing、alias、字段权限、query budget | 防止查错数据和 shard fanout |
| 索引隔离 | dedicated index、index per tenant、per-domain index | 大 tenant、合规、生命周期和成本隔离 |
| 集群隔离 | 独立集群或独立 data tier | 极高价值 tenant、强合规、资源曲线完全不同 |
| 发布隔离 | tenant 级 ranking profile、synonym version、A/B bucket | 防止相关性变更一次影响所有租户 |

tenant-level dashboard 至少要能回答这些问题：

- 这个 tenant 的 QPS、P95/P99 latency、error rate、timeout、rejected requests 是多少。
- 这个 tenant 的 query mix 是什么：普通关键词、facet、wildcard、vector、rerank、导出。
- 这个 tenant 命中了哪些 query template、ranking version、synonym version 和 experiment。
- 这个 tenant 的 storage、primary/replica、snapshot、vector memory、rerank 调用、CPU 时间大致成本是多少。
- 这个 tenant 是否制造 hot shard、slow query、breaker 或 high bucket aggregation。
- 这个 tenant 的 zero-result rate、CTR、改搜率和 top bad queries 是否异常。

面试里可以补一句：真正的 isolation 不是一个开关。小 tenant 主要靠 API quota、tenant filter、routing 和 shared index 成本效率；大 tenant 靠 dedicated index、专属容量和独立发布窗口；强合规 tenant 可能需要独立集群、文档级权限或加密与审计流程。

## Relevance Release Process

Relevance Release Process 负责让相关性变更可控。搜索质量变更通常不是代码发布那么简单，analyzer、synonym、query rewrite、ranking config、embedding model、rerank model 和业务规则都会改变 TopK；如果没有 release 过程，线上事故可能表现成 CTR 变化、转化下降、零结果上升、投诉增加或 P99 抖动。

需要版本化的对象：

| 对象 | 为什么要版本化 | 常见发布方式 |
| --- | --- | --- |
| analyzer | 分词、normalization、token filter 改变倒排结构 | 新 index + reindex + alias 切换 |
| synonym | 改变召回集合，可能引入误召回 | search-time synonym 可走灰度和 reload；index-time synonym 通常要重建索引 |
| query rewrite | 改变用户 query 到 DSL 的转换 | template version + shadow + A/B |
| ranking config | boost、function_score、rescore、fusion、rerank 特征权重 | ranking profile version + tenant/experiment 灰度 |
| embedding / vector | 改变语义召回空间和向量索引 | 新向量字段或新 index，双写/回放后切 alias |
| rerank model | 改变 TopK 排序和延迟成本 | model version + canary + fallback |

synonym 变更流程要防止“词表一改，全站误召回”。实用流程：

1. 提交规则时标明 owner、业务场景、适用 domain、单向/双向、上位词/下位词关系和示例 query。
2. 运行静态校验：循环扩展、跨类目扩展、过宽同义、敏感词、品牌词和型号词风险。
3. 用离线 query set 做 TopK diff、zero-result 改善、误召回抽样和 NDCG/precision 评估。
4. 对 search-time synonym，用版本化词表灰度到部分 tenant 或 experiment bucket；对 index-time synonym，创建新 index 版本并通过 alias 发布。
5. 线上观察 CTR、conversion、zero-result、改搜率、投诉、latency 和 bad queries，异常即 rollback 到上一版本。

query rewrite 变更也要 release 化。rewrite 包括分词前清洗、拼写纠错、实体识别、类目识别、品牌型号抽取、query 扩展、字段选择和意图路由。每个 rewrite 版本都应该在日志里记录，例如 `rewrite_version=2026-05-04.3`，否则 bad case 排查时无法解释同一个用户 query 为什么昨天和今天结果不同。

ranking config 版本化要覆盖：

- lexical ranking：字段 boost、tie breaker、phrase boost、minimum_should_match。
- business ranking：库存、地域、价格、质量分、时效、内容安全、权限。
- hybrid ranking：BM25/vector 权重、RRF 参数、candidate window、rerank input size。
- rerank model：模型版本、特征版本、deadline、fallback 策略。

shadow traffic 是发布前的安全网。平台把线上真实 query 复制到新版本，但不影响用户结果，用来比较 TopK overlap、latency、timeout、error、zero-result 和成本。shadow 不能替代 A/B test，因为它没有真实用户行为反馈；A/B test 才能判断 CTR、conversion、改搜率和业务目标是否改善。

A/B test 要避免只看一个指标。CTR 上升但 conversion 下降，可能说明结果更吸引点击但满足度变差；zero-result 下降但投诉上升，可能是 synonym 过度扩展；P95 持平但 P99 变差，可能是 rerank 或 vector tail latency 爆了。发布门禁应同时看质量、业务、稳定性和成本。

rollback 要预先设计，不要事故时临时想办法：

- ranking config、query rewrite、synonym search-time 版本能按 tenant 或 experiment bucket 回退。
- 新 index 发布通过 alias 切换，保留上一个稳定 index 到观察期结束。
- embedding 或 rerank 模型有 fallback 到旧模型、BM25-only 或 fusion coarse ranking。
- 发布日志记录谁在何时把哪个 tenant/domain 从哪个版本切到哪个版本。

## Search Observability

Search Observability 不能只看 ES cluster health。搜索平台的可观测性要同时覆盖系统稳定性、搜索质量、租户隔离、相关性版本和成本。一个结果不好，可能不是 ES 慢，而是 query rewrite 错了、synonym 误扩展、ranking profile 改了、tenant filter 太严、hot shard、vector 分支超时或 rerank fallback。

每次搜索请求建议记录这些维度：

| 维度 | 示例 |
| --- | --- |
| 租户和业务 | `tenant_id`、app、domain、套餐、优先级 |
| 查询身份 | query hash、normalized query、query length、query type、语言、head/tail bucket |
| 模板和版本 | query template id/version、rewrite version、synonym version、ranking profile、rerank model version |
| 索引和路由 | index alias、physical index、schema version、routing、shard count、primary/replica 命中 |
| 预算和保护 | size、from、bucket count、timeout、allowlist 命中、denylist 命中、fallback reason |
| 链路阶段 | rewrite latency、ES latency、vector latency、feature latency、rerank latency、total latency |
| 质量信号 | zero-result、top result ids、CTR、conversion、改搜、退出、人工 bad case 标签 |
| 成本信号 | docs examined 近似值、bucket 数、vector candidate、rerank candidate、CPU 时间、模型调用成本 |

核心指标：

| 指标 | 为什么重要 |
| --- | --- |
| query latency | P50/P95/P99 要按 tenant、domain、template、index alias、routing 和 release version 拆开 |
| zero-result rate | 直接反映召回和 filter 是否过严，也可能暴露 synonym/analyzer 问题 |
| click-through rate | 衡量结果吸引点击，但必须和 conversion、改搜率、退出率一起看 |
| top bad queries | 用于建立人工标注集、回归测试和 query rewrite 优先级 |
| rejected requests | 说明 thread pool、queue、quota 或 breaker 压力，需要区分 ES rejected 和平台 quota rejected |
| hot shards | 常来自 routing 不均、大 tenant、时间热点、segment 状态或某类查询集中 |
| per-tenant cost | 让平台能按租户解释成本，决定是否升配、限额、迁移或优化 |
| timeout / fallback | 判断是 ES retrieval、vector、feature service 还是 rerank 超预算 |
| slow query patterns | 按 query hash 和 template 聚合，比单条 slow log 更适合治理 |

slow query handling 的 observability 重点是“可归因”。一条 slow log 只告诉你某次 ES 查询慢；平台日志要能告诉你它来自哪个 tenant、哪个 query template、哪个 release、哪个 alias、带了什么 routing、生成多少 bucket、是否用了 wildcard、是否进入 rerank、最终是否 fallback。没有这些维度，慢查询只能靠人工猜。

质量 observability 要做 TopK diff。发布新 synonym、rewrite、ranking 或 rerank 时，平台应该能抽样比较旧版本和新版本的 Top 10/Top 50：哪些文档新增、哪些消失、名次变化多少、是否点击过、是否同类目、是否有库存或权限。面试里这比“上线后看 CTR”更资深，因为它能在放量前发现明显误召回。

成本 observability 要按 tenant 和请求类型拆。一个 tenant 可能 QPS 不高，但每次都做大 aggregation 或 rerank，实际成本远高于普通关键词查询；另一个 tenant 可能 storage 很大但查询少，主要成本在 primary/replica 和 snapshot。没有 per-tenant cost，平台就只能按总账扩容，无法做治理。

## Cost Governance

Cost Governance 的目标不是简单省机器，而是让搜索能力的成本可见、可控、可分摊。搜索平台成本通常来自五块：storage cost、query cost、vector/rerank cost、snapshot cost 和 cold data retention。每一块都要有 owner、指标和治理动作。

storage cost 包括 primary store、replica、segment、doc values、stored fields、_source、倒排、向量字段和多版本索引。控制手段：

- shard sizing 合理，避免大量小 shard 和过大的 hot shard。
- 只索引真正需要搜索、排序、聚合和展示的字段；高基数和长文本字段谨慎开 doc values、fielddata、highlight。
- mapping 模板按 domain 管理，避免业务随意新增字段造成 mapping explosion。
- 使用 ILM、rollover、delete policy 管理时间型数据。
- 相关性发布保留旧 index 要有观察期和删除计划，不能无限保留多版本。

query cost 来自 QPS、shard fanout、filter 选择性、sort、aggregation、highlight、script、wildcard、vector candidate 和 deep pagination。控制手段：

- query template 绑定预算，不同模板有不同 size、bucket、timeout 和 allowlist。
- 对 routing、alias 和 index pattern 做收口，避免一次查询扫不必要的 index。
- 对 expensive query 单独计量和 quota，后台导出转异步。
- 对 head query、稳定 filter、embedding 和 rerank 特征做有边界缓存，cache key 必须包含 tenant、权限、地区、版本和实验桶。
- 对慢查询按模板治理，而不是单纯扩容。

vector/rerank cost 要单独管理，因为它常常不是 ES 节点成本的一部分。embedding 生成、向量索引内存、HNSW 构建、`num_candidates`、rerank 模型 CPU/GPU、feature fetch 和 batch 策略都会影响账单。控制手段：

- 限制哪些 domain 和 tenant 可以开启 vector 或 rerank。
- 给 `k`、`num_candidates`、fusion window、rerank TopK 和模型 deadline 设置预算。
- 强 exact intent query 默认降低或关闭 vector 分支，避免语义召回浪费。
- embedding model 升级时做双版本成本评估，不只看相关性指标。
- rerank 只处理小候选集，超时 fallback 到 coarse ranking。

snapshot cost 包括快照频率、保留周期、对象存储容量、跨区域复制和恢复演练成本。治理动作：

- 按 domain 和 tenant 定义 RPO/RTO，不同数据不需要同样的 snapshot 策略。
- 对可重建的搜索视图，明确 source of truth 和重建耗时，避免把 ES snapshot 当唯一备份。
- 旧 index、旧 embedding 版本、旧 synonym 发布版本要有保留期限。
- 定期做恢复演练，验证 snapshot 不是只存在对象存储里的心理安慰。

cold data retention 要按查询价值决定。日志、订单、内容、知识库的冷数据访问模式不同：

- 最近热数据放 hot tier，支撑低延迟查询和高写入。
- 历史低频数据进入 warm/cold tier 或单独历史索引，查询模板更保守。
- 长期审计或合规数据可以转对象存储、离线分析或低成本检索路径。
- 在线搜索 API 不应该默认跨多年冷数据扫描；必须由用户显式选择时间范围和历史模式。

成本治理最后要回到平台产品机制：tenant dashboard 展示本月 storage、query、vector、rerank、snapshot 和 cold retention 成本；超过套餐就限流、降级、迁移或收费；平台优化优先处理 cost per successful search 最高、或对 P99 影响最大的 tenant/template。

## 面试回答模板

### Q：如果你负责公司统一搜索平台，你会怎么治理？

可以这样回答：

1. 我不会直接暴露 ES 任意查询能力。统一搜索平台应该提供领域化 search API、query template、ranking profile 和受控 filter/sort/facet，而不是让业务方直接拼 DSL 打到集群。
2. 我会用 query template 和 guardrail 限制危险查询。平台层做 DSL allowlist/denylist、参数校验、max size、deep pagination limit、wildcard/regexp/script 限制、aggregation bucket 预算、vector/rerank 窗口预算和 timeout；ES 层再用 `index.max_result_window`、`search.max_buckets`、`search.allow_expensive_queries`、circuit breaker 和 slow log 兜底。
3. 我会按 tenant 做 quota、监控和隔离。小 tenant 可以 shared index + tenant filter + routing，大 tenant 或强合规 tenant 拆 dedicated index 或独立集群；API 层做 QPS quota、bulk quota、expensive query quota、traffic shaping 和 tenant-level dashboard。
4. 相关性变更必须走版本化、灰度、A/B 和回滚。analyzer、synonym、query rewrite、ranking config、embedding、rerank model 都要有版本；上线前做离线评估和 shadow traffic，上线时按 tenant 或 experiment 灰度，异常时通过配置回退或 alias rollback。
5. 成本按存储、查询、向量、rerank、snapshot 分摊和治理。storage cost 看 shard、replica、mapping、retention；query cost 看 QPS、fanout、bucket、sort、deep pagination；vector/rerank cost 看 candidate window、模型调用和 deadline；snapshot 和 cold data retention 按 RPO/RTO 和访问价值设计。

面试里最后可以收束成一句话：我会把 ES 当成执行引擎，把搜索平台当成受控产品来建设；平台层负责身份、模板、quota、release、observability 和 cost governance，ES 设置负责底层护栏和执行效率，两者结合才能让多个业务安全地共享搜索能力。
