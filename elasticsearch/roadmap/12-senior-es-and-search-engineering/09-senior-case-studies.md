# 12.9 资深面试 Case Studies

> **轨道**：A+B synthesis
>
> **目标**：把第 12 章的资深能力转成系统设计和项目叙述。每个案例都要能讲需求、约束、索引设计、查询路径、同步路径、容量模型、故障模式、观测和取舍。

资深面试里的 Case Study 不是背一个 ES API 清单，而是把业务约束、可靠性边界、搜索质量、容量模型和变更治理讲成一条能落地的工程链路。好的回答通常先说明“系统必须保护什么”，再解释“为什么选择这套索引和查询路径”，最后补上“出问题怎么发现、怎么止血、怎么回滚”。

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

使用这个模板时，不要把每一项写成孤立知识点。`requirements` 和 `constraints` 决定 index design；index design 决定 query fan-out、mapping、shard sizing 和缓存边界；sync path 决定 source of truth、一致性、rebuild 和 rollback；observability 要能覆盖 tradeoffs 中承认的风险。

## 案例 1：电商商品搜索 10x 流量增长

### 需求与约束

业务从常规流量进入大促阶段，商品搜索 QPS 增长 10x，核心诉求是前台搜索 P95/P99 稳定、可售商品优先、相关性不能明显下降，同时商品价格、库存、上下架状态需要分钟级甚至更短的新鲜度。搜索请求通常包含关键词、brand/category/price/status 过滤、排序、分页和少量 facet。

关键约束：

- 商品库、库存服务、价格服务是事实源；ES 是商品搜索视图，不承担交易正确性。
- 商品名、品牌、型号、类目和属性既要支持 BM25 召回，也要支持业务排序和过滤。
- 流量增长 10x 不一定只是磁盘增长，可能同时放大 query fan-out、coordinating reduce、缓存击穿、refresh、merge 和 rejected。
- 相关性变更、同义词变更、mapping 变更都必须能灰度、观测和回滚。

### 架构决策

商品索引一般不按天拆，而是按业务域或语言区域维护主索引，通过 read alias 指向当前线上版本，例如 `products_search_current -> products_v18`。写入可以通过 write alias 或商品同步服务写入当前版本；发生 mapping、analyzer、index-time synonym 或向量字段变更时，创建新索引、重建数据、灰度校验后切 alias。

商品 mapping 的核心思路：

- `product_id`、`brand_id`、`category_id`、`seller_id`、`status`、`region` 用 `keyword` 或数值类型，服务过滤、聚合、路由和精确查询。
- `price` 建议用分为单位的整数或 `scaled_float`，避免浮点比较风险；排序和范围过滤依赖 Doc Values。
- `title` 使用 `text` 字段承载商品名分析，同时保留 `title.keyword` 或规范化字段做 exact/phrase/去重。
- `brand_name`、`model`、`category_path`、`sku_attrs` 需要区分可搜索字段和可过滤字段，不把所有属性都动态展开成无限 mapping。
- 长描述、营销文案和富文本字段要谨慎进入默认召回，避免噪声、磁盘膨胀和高亮成本。

商品名分析要把业务词典、品牌词、型号、单位、大小写、全半角、同义词和拼写纠错分层处理。稳定、长期不变、领域共识强的同义词可以考虑 index-time，但运营词、活动词、类目相关词更适合 query-time synonym 或 query rewrite，因为它们需要灰度和快速回滚。错误同义词会造成误召回，例如把跨类目品牌词、型号词、泛化词无条件扩展，可能让 CTR 上升但转化下降。

查询路径可以拆成：

```text
Search API
-> query rewrite / synonym / intent detection
-> ES bool query: filter + BM25 should/must
-> business boost / function_score / rank_feature
-> optional rescore or rerank
-> result enrichment from price/inventory if needed
```

`brand/category/price/status` 这类硬约束放在 filter context，先收缩候选集；商品名、品牌名、型号、类目文本用 `multi_match`、`dis_max`、phrase boost 和字段 boost 保护 exact intent；业务 boost 用库存、销量、质量分、发货时效、商家服务分等轻量特征调顺序，但不能让业务分完全压过文本相关性，除非这是明确的运营策略。

### 取舍

- 单个商品主索引便于相关性治理和跨类目搜索，但长期增长后需要重新评估 shard sizing、replica 和 reindex 时间。
- 按类目拆索引可以隔离大类目和减少部分查询 fan-out，但跨类目搜索、召回融合和 alias 管理更复杂。
- replica 可以提高读能力和可用性，但会增加写入复制、磁盘、refresh 和 merge 成本。
- query-time synonym 发布快、可回滚，但查询更复杂；index-time synonym 查询成本低，但词表变更通常要 reindex。
- 热门 query 缓存能吸收大促 head traffic，但库存、价格、地区、实验版本和个性化会压低复用率，cache key 必须包含影响结果的版本和权限条件。

### 风险控制

容量上先用样本 mapping 估算索引膨胀，再按商品量、字段数、排序/facet、replica、磁盘水位和恢复时间规划节点。primary shard 不靠拍脑袋，要同时验证单 shard size、segment count、query fan-out、coordinating node reduce、P99 latency 和节点故障后的 recovery time。10x 流量下，常见动作是增加 read replica、扩 data node、拆 coordinating-only 入口、限制高成本 facet、治理 deep pagination，并对热门 query 做服务层短 TTL 缓存或预计算。

发布上用版本化策略：

1. 新建 `products_v19`，固化 mapping、settings、analyzer、synonym 和 ranking profile。
2. 从商品库或商品事件日志全量构建，而不是只依赖旧 ES 索引复制。
3. 对比文档数、字段抽样、TopK diff、zero-result、P95/P99、CPU、heap、rejected 和搜索质量指标。
4. 小流量或租户灰度 read alias。
5. 观察期内保留 `products_v18`，异常时 alias 回滚。

缓存风险要单独治理：缓存击穿时会把 head query 同时打到 ES；可以用请求合并、热点预热、短 TTL、多级缓存和限流保护。库存、价格和上下架状态如果要求强一致，不应该完全依赖缓存中的搜索结果，必要时在返回前批量校验或在交易链路回源。

### 指标与可观测

系统指标：

- search availability、P95/P99、timeout、search rejected、breaker、CPU、heap、GC、segment count、merge time、query fan-out、coordinating reduce latency。
- shard size、primary/replica 分布、hot shard、cache hit ratio、refresh latency、bulk latency、CDC/MQ lag。
- alias 当前版本、ranking profile version、synonym version、query template version。

质量指标：

- CTR、CVR、GMV、zero-result rate、改搜率、TopK overlap、bad query 分桶、品牌/型号 exact query 的命中率。
- 同义词命中后的转化变化，避免只看 CTR。

### 面试叙述

可以这样讲：我会先把问题定义为“前台商品搜索在 10x QPS 下仍要守住延迟、相关性和新鲜度”，而不是直接说加节点。ES 负责召回和排序，商品库、库存和价格仍是 source of truth。索引上用商品域主索引和 alias 管理版本，mapping 区分 text 召回字段与 keyword/numeric 过滤字段；查询上先用 filter 收缩，再用 BM25、字段 boost 和业务轻量特征排序；容量上用 shard size、fan-out、replica、coordinating reduce 和缓存命中率验证。所有 analyzer、synonym、boost 和 mapping 变更都走新索引、灰度、指标观察和 alias rollback。

## 案例 2：订单搜索与 MySQL 正确性边界

### 需求与约束

订单搜索面向客服、商家后台、用户订单列表和运营排查。常见查询包括订单号、用户 ID、商家 ID、手机号脱敏字段、状态、支付状态、履约状态、创建时间、更新时间和售后状态。这个场景的第一原则是正确性边界清晰：MySQL 或交易库是 source of truth，ES 是搜索视图。

关键约束：

- 订单创建、支付、退款、发货和售后状态的强一致判断不能依赖 ES。
- ES 可以近实时落后；关键查询必须能回源 MySQL 确认。
- CDC/MQ 同步会遇到延迟、乱序、重复、丢消息、部分失败和回放。
- 订单数据有权限、审计、合规和修复要求，不能把搜索便利性放在正确性前面。

### 架构决策

订单索引按访问模式设计。常见做法是按时间滚动或按月/季度索引，配合 read alias 覆盖最近和历史订单；如果租户或商家维度很强，可以在文档中保留 `tenant_id`、`seller_id`、`user_id`，并评估 routing。查询大多带时间范围，因此时间索引能减少历史查询成本；但跨多年订单查询会增加 fan-out，需要默认时间窗和后台异步查询。

订单 mapping 的重点：

- `order_id` 用 `keyword`，通常作为 ES `_id`，保证幂等覆盖。
- `tenant_id`、`user_id`、`seller_id`、`status`、`payment_status`、`fulfillment_status` 用 `keyword` 或数值枚举，服务过滤和权限。
- `created_at`、`updated_at` 用 `date`，所有后台查询默认带时间范围。
- 金额用整数分或定点类型，避免浮点误差。
- 可搜索的收件人、手机号、地址等字段要脱敏、最小化索引，并遵守权限和审计策略。

同步路径推荐：

```text
MySQL transaction
-> outbox or binlog CDC
-> Kafka / MQ
-> idempotent index consumer
-> bulk write to ES
-> reconciliation / repair job
```

消费者用 `order_id` 做幂等键，用订单版本号、binlog 位点、业务事件序号或 `updated_at` 处理乱序。收到旧事件时不覆盖新状态；删除或取消要明确是物理删除、逻辑删除还是状态更新。失败消息进入重试队列和 DLQ，修复任务可以按订单 ID、时间窗口、租户或 binlog 位点重放。

查询路径要按正确性分级：

- 精确订单号、支付状态确认、退款状态确认：优先 MySQL 或 ES 命中后回源确认。
- 后台列表搜索：ES 负责候选召回和过滤，返回前可对敏感状态批量回源或展示“搜索视图可能延迟”的业务语义。
- 审计、财务、结算和法务导出：不走在线 ES 搜索链路，优先主库、数仓、审计库或异步任务。
- ES 不可用或同步 lag 超过阈值：精确订单号回源，复杂搜索降级、暂停或异步化。

### 取舍

- ES 提供灵活搜索和后台检索体验，但不能成为订单事实源。
- CDC 异步同步吞吐高、对交易链路侵入低，但会带来新鲜度和乱序问题。
- 同步写 MySQL 后再同步写 ES 看似简单，但会把 ES 故障耦合到交易写入，且仍然要处理部分失败。
- 按时间拆索引便于 retention、冷热分层和历史查询控制，但跨时间范围查询会增加 fan-out。
- routing by tenant/user 能减少 fan-out，但大商家或大租户会形成 hot shard，需要 dedicated index 或拆分路由。

### 风险控制

正确性风险的控制核心是“可校对、可重放、可回源”：

- MySQL 保存完整事实和审计轨迹，ES 文档保留 `source_version`、`event_time`、`cdc_offset`、`indexed_at`。
- 同步消费者保证幂等，旧版本事件不覆盖新版本文档。
- 建立 reconciliation job：按时间窗口、租户、订单状态做 count、checksum、抽样字段比对和缺失订单扫描。
- 修复任务支持从 MySQL 或事件日志批量补数，不把 ES `_reindex` 当成修复业务事实的唯一手段。
- 所有强一致接口明确回源策略；ES lag、DLQ 堆积或校对失败时自动标记搜索视图不可信。

Snapshot 只能保护 ES 某个时间点的索引状态，不能替代 MySQL backup、binlog、事件日志和业务补偿。订单索引误删时，可以 Snapshot Restore 到临时索引并校验，也可以从 MySQL 重建；如果是逻辑脏数据，优先从 source of truth 修复后重放。

### 指标与可观测

同步指标：

- CDC lag、Kafka lag、consumer lag、bulk error rate、DLQ size、retry count、乱序丢弃数、幂等覆盖数、index freshness。
- MySQL 与 ES 的 count/checksum mismatch、抽样字段 mismatch、修复任务成功率和耗时。

查询指标：

- 订单搜索 P95/P99、timeout、回源比例、回源失败率、强一致查询数量、降级次数。
- 按租户、商家、时间范围和 query template 统计 slow query、fan-out、返回结果数。

审计指标：

- 哪些订单被搜索、由谁搜索、返回前是否回源、是否发生修复、修复来源和版本。

### 面试叙述

可以这样讲：订单搜索我会先划清边界，MySQL 是 source of truth，ES 是近实时搜索视图。交易状态、支付状态和退款状态的强一致判断必须回源，ES 只负责候选召回和后台检索体验。同步链路用 CDC/MQ，消费者按订单版本和事件位点做幂等与乱序保护；风险通过 reconciliation、DLQ、重放和审计修复。这样回答能体现我不是把 ES 当数据库，而是把正确性、可观测和恢复路径一起设计。

## 案例 3：日志检索与 ILM/Data Tiers

### 需求与约束

日志检索服务生产排障、审计回查和运营分析。写入是持续高吞吐，查询主要集中在最近几小时或几天，但合规可能要求保存数月到数年。系统要支持按 service、env、level、trace id、host、message 和时间范围检索，同时避免一次宽时间范围查询拖垮 hot tier。

关键约束：

- 日志是典型时间序列，写入和 retention 比单条记录更新更重要。
- 最近数据要求低延迟，历史数据可以接受更高延迟或异步查询。
- 字段动态性强，容易 mapping explosion。
- Snapshot、retention 和 Data Tiers 必须一起设计，不能只说“老数据放冷层”。

### 架构决策

推荐采用 data stream：

```text
logs-prod-default
-> backing indices by rollover
-> ILM: hot -> warm -> cold -> delete or archive
```

index template 固化 settings、mapping、lifecycle、routing allocation 和字段治理。典型字段包括 `@timestamp`、`service`、`env`、`level`、`host`、`trace_id`、`span_id`、`message`、`tags` 和有限的结构化业务字段。`message` 用 text 承接全文检索；service、level、host、trace_id 等用 keyword；高基数、不可控的 labels 要限制数量，必要时用扁平结构承接，不允许无限动态字段进入 mapping。

rollover 不简单等同于“每天一个索引”。更稳妥的条件是按 `max_primary_shard_size`、`max_age` 和必要的最小条件组合，让每个 backing index 的 shard size 稳定。hot tier 承接当前写入、refresh、merge 和最近查询；warm tier 承接低频历史查询和只读数据；cold tier 或 searchable snapshot 用更高延迟换成本；超过业务 retention 的数据删除或归档到对象存储。

查询入口必须默认带时间范围：

- 默认查询最近 15 分钟、1 小时或 24 小时，按产品场景配置。
- 查询超过阈值时提示用户缩小范围、转异步任务或使用历史查询入口。
- 大聚合、导出、全量扫描、跨月查询与在线排障搜索隔离。
- trace id、order id、request id 这类强选择性查询可以走更宽时间窗，但仍要有 timeout 和结果窗口限制。

### 取舍

- data stream + ILM 适合追加写入和生命周期管理，但不适合频繁更新同一日志文档。
- rollover 按大小能稳定 shard，但低流量场景要防止过多小 shard。
- warm/cold 降低成本，但查询 P95/P99 和 restore 时间会变差，必须明确用户预期。
- 降低历史索引 replica 能省磁盘，但会影响可用性和恢复窗口。
- Snapshot 能帮助误删、迁移和灾备恢复，但不是连续备份，也不替代日志源、Kafka 或对象存储归档。

### 风险控制

写入风险：

- ingest pipeline 的 grok、解析、enrich、script 很耗 CPU，高峰期要拆 dedicated ingest node 或把清洗前移。
- bulk 大小和并发要有背压，避免 write queue、merge backlog 和磁盘水位一起恶化。
- hot tier 保留足够 SSD、IOPS、CPU、page cache 和磁盘空闲给 refresh、merge、snapshot 和 recovery。

查询风险：

- 平台/API 层限制时间范围、size、aggregation bucket、wildcard、regexp、高亮和导出。
- 对 Dashboard 自动刷新、宽时间范围查询和事故期间热点查询做限流。
- 对历史查询使用异步任务、低优先级队列或单独入口。

数据治理风险：

- index template 禁止无边界动态字段，设置字段上限、dynamic_templates 和 label 规范。
- ILM 阶段迁移、rollover、forcemerge、snapshot 和 delete 必须有告警；ILM stuck 会让 hot tier 被历史数据填满。
- Snapshot repository 要定期 verify，Restore 要演练到临时索引或临时集群，并校验 mapping、template、alias 和查询延迟。

### 指标与可观测

- ingest TPS、bulk latency、bulk failure、pipeline latency、ingest CPU、write rejected、merge time、segment count、refresh latency。
- backing index size、primary shard size、rollover frequency、ILM phase、ILM error、hot/warm/cold 数据量。
- query latency by time range、fan-out shard count、slow query、aggregation bucket、timeout、Dashboard query QPS。
- disk watermark、snapshot success、snapshot duration、repository latency、restore drill time。
- mapping field count、动态字段新增速率、cluster state size、pending mapping tasks。

### 面试叙述

可以这样讲：日志检索我会按时间序列设计，核心是 data stream、index template、rollover、ILM 和 Data Tiers。hot tier 保障当前写入和最近查询，warm/cold 用更高延迟换成本，retention 和 snapshot 由业务合规和恢复目标决定。查询入口默认限制时间范围，大查询转异步，避免一次 Dashboard 跨大量 backing index 造成 fan-out。风险上重点盯 mapping explosion、ingest CPU、merge、disk watermark、ILM stuck 和 Snapshot Restore 演练。

## 案例 4：多租户 SaaS 搜索平台

### 需求与约束

多租户 SaaS 搜索平台同时服务大量客户，每个 tenant 可能有文档、商品、工单、订单或知识库搜索。平台要保证租户隔离、低接入成本、可控延迟、配额、成本归因和搜索质量发布治理。最大风险是 noisy neighbor：一个大 tenant、坏 query 或批量导入把公共集群拖慢。

关键约束：

- tenant 身份、权限和套餐不能只靠 ES 理解，必须由平台/API 层控制。
- 不同 tenant 的数据量、QPS、schema、合规要求和 SLO 差异很大。
- shared index、index per tenant、large tenant dedicated index 没有绝对优劣，要按规模和隔离要求分层。
- routing 能降低 fan-out，也可能制造 hot shard。

### 架构决策

平台层提供统一 Search API，而不是开放任意 ES DSL：

```text
API gateway / Search service
-> tenant auth + quota
-> query template / ranking profile
-> guardrail validation
-> ES alias/routing/index registry
-> observability and cost attribution
```

索引策略分层：

| 策略 | 适合场景 | 优点 | 风险 |
| --- | --- | --- | --- |
| shared index | 大量小租户，schema 接近，单租户数据和 QPS 小 | shard 利用率高，运维简单，成本低 | tenant filter 必须强制注入，大租户可能 hot shard，成本归因较难 |
| index per tenant | 租户数量可控，隔离、删除、备份或生命周期要求强 | 隔离清晰，迁移和删除简单 | 小租户过多会造成 index/shard 膨胀和 cluster state 压力 |
| large tenant dedicated index | 少数大客户、高价值客户或高 SLO 租户 | 可单独 shard sizing、扩容、发布和压测 | 需要自动化迁移、路由表和容量水位，不能变成人工特例 |

shared index 场景下，所有文档必须带 `tenant_id`，平台在 query template 中强制注入 tenant filter，并可使用 routing by tenant 降低 shard fan-out。大 tenant 达到数据量、QPS、P99、存储成本或 hot shard 阈值后迁移到 dedicated index。平台维护 tenant/index registry：tenant 当前属于哪个 index/alias、routing key、schema version、ranking profile、quota、成本归属和迁移状态。

guardrails 必须覆盖：

- QPS、并发、bulk 大小、写入速率、storage quota。
- `size`、`from + size`、深分页、`search_after` 使用规则。
- aggregation 字段 allowlist、最大 bucket、最大 nested 层级。
- wildcard、regexp、script、expensive query、highlight、sort 字段和 `_source` 返回字段。
- vector candidate、rerank TopK、模型 deadline 和 fallback。

ES 层的 `index.max_result_window`、`search.max_buckets`、request timeout、slow log、circuit breaker、filtered alias 和 alias routing 是底层护栏；平台层负责租户身份、套餐、预算、模板权限、实验分桶和发布审批。

### 取舍

- shared index 成本效率高，但隔离和大租户治理更难。
- index per tenant 隔离清楚，但小租户过多会导致 oversharding、cluster state 和运维复杂度上升。
- dedicated index 能保护大租户和公共集群，但需要自动化迁移、压测和容量归因。
- routing 减少 fan-out，但租户规模不均会造成 hot shard；改变 routing 往往需要 reindex。
- 更严格的 query guardrail 会限制业务灵活性，但能保护平台 SLO。

### 风险控制

noisy neighbor 的控制要从入口、索引和集群三层做：

- 入口层：token bucket、并发上限、优先级队列、低套餐降级、超限可解释错误。
- 查询层：强制 tenant filter、query template、DSL allowlist/denylist、timeout、最大结果窗口、最大 aggregation bucket。
- 索引层：大 tenant dedicated index、热租户迁移、routing 拆分、字段数量上限、自定义字段准入。
- 集群层：独立 data node pool、独立集群、冷热分层、snapshot 窗口和后台任务限流。

权限风险不能只靠 filtered alias。alias 是访问抽象和运维工具，如果调用方能绕过 alias 查底层 index，就不是安全边界。安全隔离要靠平台鉴权、索引权限、文档级权限、tenant filter 强制注入和审计共同保证。

发布风险也要租户化。synonym、query rewrite、ranking profile、embedding model 和 rerank model 都要版本化，支持按 tenant 或 experiment bucket 灰度；异常时能回滚到上一个版本。

### 指标与可观测

per-tenant dashboard 至少覆盖：

- QPS、并发、P95/P99、error rate、timeout、fallback、rejected、slow query。
- query mix：keyword、facet、wildcard、aggregation、vector、rerank、export。
- storage、primary/replica、snapshot、vector memory、rerank 调用、CPU 时间和成本。
- tenant 对应 index、routing、schema version、ranking version、synonym version、experiment。
- hot shard、mapping field count、large query、zero-result rate、CTR、改搜率和 bad query。

平台全局还要看 cluster health、JVM memory pressure、breaker、thread pool、disk watermark、snapshot success、ILM、shard count 和 index count。

### 面试叙述

可以这样讲：多租户搜索平台我不会让业务直接拼 ES DSL，而是用平台 API 收口 tenant、quota、query template 和 guardrail。索引策略按租户规模分层，小 tenant 用 shared index + tenant filter + routing，大 tenant 迁移到 dedicated index，强隔离场景可以 index per tenant 或独立集群。治理上重点防 noisy neighbor：入口限流、查询预算、危险 DSL 拦截、per-tenant observability 和自动化迁移水位。这样能同时说明成本、隔离、稳定性和平台治理。

## 案例 5：BM25 + Vector + Rerank Hybrid Search

### 需求与约束

Hybrid Search 常见于知识库、内容搜索、商品搜索和企业问答。用户既会输入精确词、品牌型号、错误码、文档编号，也会输入自然语言问题和同义表达。目标是提高召回和排序质量，同时守住延迟、成本、可解释性和 fallback。

关键约束：

- BM25 保护 exact intent 和可解释性，Vector 负责语义召回，Rerank 只处理小候选集。
- 向量检索不能替代关键词检索，尤其是型号、数字、ID、错误码和权限场景。
- rerank 不能修复 candidate generation 完全漏掉的文档。
- embedding、vector index、fusion 和 rerank 都会增加延迟、成本和发布风险。

### 架构决策

推荐三阶段：

```text
candidate generation
-> score fusion / coarse ranking
-> rerank
```

candidate generation 阶段并行执行 BM25 recall 和 vector recall。硬过滤必须前置或至少在召回阶段生效，例如 tenant、权限、状态、时间范围、可售状态、内容安全和语言。BM25 分支使用 multi-field lexical query、phrase boost、minimum_should_match 和业务字段保护精确意图；Vector 分支使用 query embedding 和文档 `dense_vector` 字段做 kNN 召回，`k` 和 `num_candidates` 根据 recall/latency 实验确定。

score fusion 阶段对多路候选去重，并用 rank-based fusion、RRF 或稳定的规则融合。不要直接把 BM25 `_score` 和 vector similarity 当成同一量纲相加；它们的分布随 query、字段、IDF、模型和候选窗口变化。RRF 的工程价值是回避原始分数不可比问题，让多个召回器的排名共同投票。

rerank 阶段只处理融合后的 TopK，例如 50 到 200 个候选。可以使用 ES `rescore` 做轻量二阶段排序，也可以调用外部 LTR、cross-encoder 或 reranker model。rerank 必须有 batch、deadline、版本、特征日志和 fallback；超时则返回 fusion coarse ranking。

一个实用延迟预算：

- query rewrite / embedding：head query 可缓存 embedding，超时 fallback 到 BM25。
- BM25 retrieval：主路径，保证 exact query 低延迟。
- Vector retrieval：受 `k`、`num_candidates`、filter、segment 和内存影响，设置分支 timeout。
- fusion：去重、RRF、业务轻量特征，不做重模型。
- rerank：只对小窗口执行，超过 deadline 返回 coarse ranking。

### 取舍

- BM25 成本低、可解释、精确词强，但对语义改写和弱词面重叠不够好。
- Vector 语义召回强，但对数字、型号、ID、权限和可解释性弱，且成本更高。
- RRF 稳定、易解释，但不能表达所有分数强弱；加权 score fusion 更灵活，也更容易不稳定。
- rerank 提升 TopK 排序，但会增加 P95/P99、模型成本和特征一致性风险。
- 候选窗口越大，recall 和 rerank 纠错空间越好，但 latency、CPU、内存和模型成本越高。

### 风险控制

Hybrid 的风险要按阶段定位：

- BM25 漏召：检查 analyzer、synonym、query rewrite、字段 boost、minimum_should_match 和字段建模。
- Vector 误召：保护 exact query，对品牌、型号、ID、错误码降低 vector 权重或关闭 vector 分支。
- fusion 不稳定：优先用 rank-based 方法，记录每个候选来自哪个召回器、原始 rank 和 fusion 分。
- rerank 慢：限制 TopK、batch 调用、设置 deadline、缓存静态特征、超时返回 coarse ranking。
- embedding drift：模型版本化，新模型先 shadow、离线评估、灰度；必要时新向量字段或新索引。
- filter 后候选不足：观察 BM25/vector 分支候选数、过滤前后数量和 TopK overlap，调整候选窗口或 query 分桶策略。

fallback 必须上线前定义：

- embedding 服务失败：BM25-only。
- vector 分支超时：BM25 + business boost。
- fusion 配置异常：上一稳定 fusion 或 BM25 coarse ranking。
- rerank 模型超时：fusion 结果直接返回。
- 模型发布异常：按模型版本或 experiment bucket 回滚。

### 指标与可观测

质量指标：

- recall@K、NDCG@10、MRR、TopK overlap、zero-result、CTR、CVR、改搜率。
- exact query bucket、semantic query bucket、tail query bucket、低词面重叠 query bucket 分开统计。
- BM25-only、Vector-only、Hybrid、Rerank 后 TopK diff 和 bad case 归因。

系统指标：

- BM25 latency、Vector latency、fusion latency、Rerank latency、overall P95/P99。
- BM25 candidate 数、Vector candidate 数、overlap、fusion 后候选数、rerank 输入数。
- embedding cache hit、embedding service timeout、vector memory、HNSW 查询耗时、model QPS、model cost、fallback reason。

发布指标：

- query rewrite version、embedding model version、vector field/index version、fusion profile version、rerank model version、experiment bucket。

### 面试叙述

可以这样讲：Hybrid Search 我会先拆成 candidate generation、fusion 和 rerank。BM25 保护精确意图和可解释性，Vector 补语义召回，fusion 用 RRF 或稳定规则避免分数不可比，rerank 只在小候选集上做更贵判断。每个阶段都有 latency budget 和 fallback：向量失败返回 BM25，rerank 超时返回 coarse ranking。上线靠离线评估、shadow query、A/B test、TopK diff 和模型版本回滚，不会把向量当成替代倒排的银弹。

## 案例 6：ES Mapping 变更与 Reindex 迁移

### 需求与约束

常见需求包括字段类型改错、keyword/text multi-field 调整、analyzer 变更、synonym 策略变化、nested 建模修正、向量字段新增或 embedding 模型升级。这类变更往往不能在原索引上原地完成，需要新索引和 Reindex 迁移。

关键约束：

- mapping 中很多字段类型和 analyzer 不能对既有字段无损修改。
- 迁移期间要尽量保持读写可用，并明确数据新鲜度和一致性边界。
- ES 如果只是搜索视图，source of truth 应优先是 MySQL、业务主库、对象存储或事件日志，而不是旧 ES 索引。
- rollback 必须在切换前设计好，不能等事故时才想 alias 怎么切。

### 架构决策

标准迁移路径：

```text
create new index
-> bind write/read alias strategy
-> backfill or reindex
-> dual write or controlled write pause
-> verification
-> read alias switch
-> observe
-> cleanup old index after retention window
```

alias 设计示例：

- `orders_search_read -> orders_v7`
- `orders_search_write -> orders_v7`，并设置 `is_write_index`。
- 新建 `orders_v8` 后，回填历史数据。
- 灰度读流量确认后，将 read alias 从 `orders_v7` 切到 `orders_v8`。
- 写入 alias 的切换要和 dual write 或暂停写入窗口配合，避免漏写。

数据来源选择要谨慎：

- 业务事实源可重建时，优先从 MySQL、事件日志、对象存储或主数据服务重建新索引。
- 旧 ES 索引只适合复制“当前搜索视图”，不能修复旧视图里已经存在的脏数据、漏数据或字段丢失。
- 使用 `_reindex` 时要设置 slices、requests per second、任务监控和低峰窗口，避免抢占线上查询、merge、snapshot 和恢复资源。
- 对向量字段或 analyzer 变更，通常需要重新计算 embedding 或重新分词，因此更应从事实源或离线特征管道构建。

写入一致性有两种常见方式：

- dual write：新旧索引同时写入，适合写入不中断，但要处理部分失败、幂等、乱序和补偿。
- controlled write pause：短暂停写或冻结变更窗口，适合低流量内部系统，但需要业务接受短窗口新鲜度延迟。

### 取舍

- dual write 保持业务连续性，但写入链路复杂，失败补偿和监控要求高。
- 暂停写入窗口简单，但会牺牲新鲜度或业务可用性。
- 从 source of truth 重建正确性最好，但耗时可能更长，需要限速和回放能力。
- 从旧 ES `_reindex` 快，但会复制旧索引中的逻辑错误，也可能受旧 mapping 限制。
- alias 切换快且可回滚，但如果写入 alias 和读 alias 治理混乱，可能出现读写不一致。

### 风险控制

迁移前：

- 明确变更原因、影响字段、查询模板、排序、聚合、同步链路、回滚路径和验收指标。
- 创建新 index template、mapping、settings、analyzer、ILM 和 alias 配置。
- 对旧索引做 Snapshot 或确保可从 source of truth 重建。Snapshot 是 ES 恢复手段，不替代主库备份。
- 压测新索引的写入、查询、聚合、TopK、P95/P99 和磁盘膨胀。

迁移中：

- backfill/reindex 限速，避开高峰，监控 task、bulk failure、rejected、merge backlog、disk watermark、CPU、heap 和 IO。
- dual write 记录新旧写入成功状态，失败进入补偿队列；暂停写入窗口要有明确开始、结束和异常退出条件。
- 对新旧索引做 count、checksum、关键字段抽样、业务主键缺失扫描、TopK diff、zero-result diff、慢查询对比和权限校验。
- 灰度读流量或 shadow query，按 query template、租户、领域和版本观察。

切换与 rollback：

- alias 切换要原子执行，把 read alias 从旧索引切到新索引。
- 观察期内保留旧索引、旧 alias 配置、旧 ranking profile、旧 synonym 和旧应用配置。
- 如果新索引错误率、P99、相关性、缺失率或同步 lag 触发阈值，立即把 read alias 切回旧索引。
- 如果写入已经切到新索引，rollback 后要决定写入继续 dual write、回放到旧索引，还是短暂停写再修复；不能只切 read alias 就认为完全回滚。
- 清理旧索引必须等观察期、补偿任务、Snapshot/Restore 演练和业务确认完成。

### 指标与可观测

- backfill progress、reindex task speed、requests per second、bulk error、retry、DLQ、dual write mismatch。
- new vs old doc count、checksum、missing IDs、field sample mismatch、TopK overlap、zero-result diff。
- query latency、P95/P99、CPU、heap、GC、merge time、segment count、disk watermark、search/write rejected。
- alias 当前指向、write alias `is_write_index`、template version、mapping version、analyzer version、sync lag。
- rollback trigger：错误率、数据缺失率、P99、核心 query TopK 变化、业务投诉、同步延迟。

### 面试叙述

可以这样讲：Mapping 变更我不会在原索引上硬改，而是新建索引、重建数据、校验、alias 切换和保留 rollback。数据源优先从 MySQL 或事件日志等 source of truth 重建；旧 ES `_reindex` 只能复制搜索视图，不能修复脏数据。迁移期间用 dual write 或暂停写入窗口保护新鲜度，用 count、checksum、TopK diff、P99、rejected 和业务抽样校验。切换通过 alias 原子完成，旧索引保留观察期，异常时 read alias 回滚，并处理写入回放边界。

## 资深叙述原则

资深候选人的叙述重点不是“我知道哪些 ES 名词”，而是“我能为一个真实搜索系统负责”。可以用这些原则检查自己的回答：

1. 先讲约束，不先讲技术名词。先说明业务目标、SLO、source of truth、数据规模、查询形态、保留期、合规和成本，再讲 shard、ILM、alias、BM25、Vector、Rerank。
2. 每个设计选择要有 tradeoff。shared index 省成本但隔离弱；routing 降低 fan-out 但可能 hot shard；query-time synonym 可回滚但查询变重；dual write 连续性好但补偿复杂。
3. 每个风险要有观测和回滚。synonym 误召回要看 TopK diff、CTR/CVR 和 bad case；reindex 风险要有 count/checksum、alias rollback 和旧索引保留；Hybrid 风险要有 fallback reason 和模型版本回滚。
4. 每个性能判断要有指标。不要说“加缓存就好了”，要说明 P95/P99、query fan-out、cache hit ratio、coordinating reduce、search rejected、breaker、CPU、heap、merge 和 shard size。
5. 每个一致性判断要说明 source of truth。订单、支付、库存、权限等强一致场景必须回源；ES 是搜索视图时，Snapshot、replica 和 `_reindex` 都不能替代主库备份、事件日志、校对和重放。
6. 每个变更要有发布过程。mapping、analyzer、synonym、ranking、embedding、rerank model 都要版本化、灰度、观测和 rollback。
7. 每个搜索质量改动要有评估闭环。离线 query set、TopK diff、bad case、A/B test、CTR/CVR、zero-result、改搜率和延迟成本要一起看。
8. 每个生产方案要有降级路径。ES 慢了能否限制时间窗、关闭 vector/rerank、回源 MySQL、返回缓存、转异步或限流低优先级租户。

面试最后可以用一句话收束：我会把 ES 当成可治理的搜索执行引擎，而不是万能数据库；先守住事实源和 SLO，再用 mapping、shard sizing、ILM、query guardrail、相关性评估和 alias/reindex 发布流程把搜索能力做稳。
