# 12.2 生产拓扑与 Data Tiers

> **轨道**：A core / B prerequisite
>
> **目标**：能解释生产 ES 集群如何拆节点角色、如何做冷热分层、如何隔离 ingest/query/merge/snapshot 的资源竞争。

生产拓扑不是背一套固定节点数，而是先回答三个问题：业务类型是什么、SLO 是什么、主要资源瓶颈是什么。日志检索、订单搜索、商品搜索和多租户搜索平台对延迟、写入、保留期、隔离和成本的要求不同，同一个 `node.roles` 配置在一个场景里合理，在另一个场景里可能就是风险源。

资深面试回答要避免说“生产一定要 X 个节点、Y 个 shard、Z 个角色”。更可靠的表达是：先按 workload 和 SLO 建立拓扑假设，再用监控、压测、故障演练和成本模型验证。

## 节点角色怎么拆

Elasticsearch 节点角色拆分的目标，是把不同性质的资源消耗放到合适的节点池里，避免一个局部高负载拖垮集群控制面、读写面或生命周期任务。

| 角色 | 主要职责 | 典型资源压力 | 拆分判断 |
| --- | --- | --- | --- |
| master-eligible | 参与选主，维护 cluster state，调度 shard allocation、index metadata、mapping、ILM 等集群级变更 | CPU 抖动、heap、GC、网络延迟、磁盘抖动都会影响控制面稳定性 | 中大型或高 SLO 集群通常做 dedicated master，不承载重查询、重写入、重 ingest |
| data / data roles | 承载 shard，执行实际索引、查询、聚合、refresh、merge、recovery | CPU、heap、磁盘 IO、page cache、文件句柄、网络 | 按数据热度和硬件成本拆成 `data_hot`、`data_warm`、`data_cold`、`data_frozen`，也可能使用 `data_content` 承载非时间序列业务数据 |
| ingest | 执行 ingest pipeline，例如 grok、解析、字段清洗、enrich、geoip、script | CPU、heap、pipeline queue、外部 enrich 数据访问 | pipeline 重、写入峰值明显、解析规则复杂时拆 dedicated ingest node，避免抢 data node 的索引和 merge 资源 |
| coordinating | 接收请求，转发到 shard，合并 TopN、聚合和 scroll/search_after 等结果 | CPU、heap、网络、结果集 reduce、聚合 bucket 合并 | 高 fan-out 查询、跨大量索引查询、多租户平台入口、Dashboard 集中入口适合拆 coordinating-only node |
| ML / transform | 机器学习、transform、持续聚合等后台任务 | CPU、内存、长任务调度 | 本路线了解即可；如果使用这些能力，要像 ingest 一样纳入资源隔离和调度窗口 |

几个关键点要讲清楚：

- 每个节点默认都可以承担 coordinating 行为；面试里说的 coordinating node 通常指不放 data、master、ingest 等职责的 coordinating-only 入口节点。
- master-eligible 节点负责集群控制面，不能被复杂查询、bulk 写入、pipeline 解析、snapshot IO 或磁盘水位抖动拖住。控制面抖动会放大成选主、shard relocation、mapping 更新和索引创建问题。
- data 不是一个单一概念。生产里要区分热写入数据、内容类业务索引、温冷历史数据和 searchable snapshot 数据，常见角色包括 `data_hot`、`data_content`、`data_warm`、`data_cold`、`data_frozen`。
- dedicated role 不是越多越好。拆角色会增加节点池、容量碎片、运维复杂度和跨节点网络成本；只有当资源竞争、SLO 或故障域需要时才拆。
- 角色拆分必须和 shard allocation、ILM、索引模板、路由、限流、监控和成本预算一起设计。只改 `node.roles`，不改数据流向和查询入口，隔离效果通常有限。

## 常见生产拓扑

生产拓扑的讨论顺序应该是：业务类型、读写比例、数据保留期、P95/P99 延迟、RPO/RTO、AZ 故障域、成本约束，然后才是节点角色。

### 小型业务搜索集群

小型业务搜索通常是订单检索、后台管理搜索、内部知识库或中低 QPS 商品搜索。数据量、写入和查询都不大时，可以先采用较简单的混合角色拓扑，但要明确它的边界。

实用判断：

- 可以让节点同时承担 master-eligible、data、ingest 和 coordinating，但要控制 ingest pipeline、聚合、深分页、批量导出和后台重建索引的强度。
- 如果查询延迟或写入成功率是核心 SLO，即使规模不大，也要避免 master-eligible 节点长期被重写入、重聚合或磁盘高水位影响。
- 至少要用 replica、快照、磁盘水位告警、慢查询日志和恢复演练证明故障可控。小集群最容易出现的问题不是拓扑太简单，而是没有明确的容量边界和恢复路径。
- 当出现频繁 GC、search/write rejected、master 日志抖动、cluster state 更新慢、单节点磁盘接近水位线时，应该优先分析资源竞争，而不是盲目加 shard。

面试里可以这样说：小规模可以简单启动，但要用 SLO 和监控定义退出条件。一旦控制面和数据面被同一类峰值一起拖住，就要拆 dedicated master 或拆重负载入口。

### 中型业务搜索集群

中型业务搜索通常已经有稳定线上流量、明确 P95/P99 延迟、可预期增长和多业务依赖。此时拓扑重点从“能跑”变成“故障可控、变更可控、资源竞争可控”。

常见拆法：

- dedicated master-eligible 节点只负责控制面，避免承载 data shard、重查询和重 ingest。
- data node 承载业务索引，根据查询和写入压力选择 SSD、CPU、heap 和 replica 策略。
- coordinating-only node 作为 ES 查询入口，承接客户端连接、查询 fan-out、TopN reduce 和聚合结果合并；业务限流和策略判断放在业务网关或 API 层。
- ingest node 在 pipeline 复杂或写入峰值明显时拆出，尤其是日志解析、富字段清洗、enrich、script 和多来源数据清洗。
- 如果同一个集群承载实时业务搜索和后台分析，要对后台导出、宽时间范围聚合、scroll、reindex、update_by_query 做限流或离线化。

这里的关键不是“必须有 coordinating node”，而是判断查询入口是否已经成为资源竞争点。如果大部分查询只打少量 shard、结果集小、聚合轻，coordinating-only 层收益可能有限；如果多租户、跨索引、宽时间范围和聚合多，入口层隔离价值就很高。

### 日志/观测集群

日志、指标、审计和 tracing 数据通常是高写入、按时间查询、保留期长、冷热差异明显。拓扑重点是 data stream、ILM、rollover、Data Tiers、snapshot 和查询时间窗治理。

常见设计：

- hot tier 使用 `data_hot` 节点承接当前写入和高频查询，硬件优先给 SSD、CPU、IO 和足够 page cache。
- warm tier 使用 `data_warm` 节点承接写入停止或低频查询的数据，通常查询 SLA 低于 hot，成本也应更低。
- cold tier 使用 `data_cold` 节点承接低频历史查询，结合快照、较低 replica 或 searchable snapshot 控制成本。
- frozen tier 使用 `data_frozen` 和 searchable snapshots 承接极低频历史检索，用更高延迟换更低存储成本。
- snapshot 仓库、保留期、恢复时间和历史查询 SLA 必须一起定义；不能只说“老数据放 cold/frozen”。
- 查询入口必须限制默认时间范围。日志平台最大的风险之一，是一次 Dashboard 或导出任务跨大量历史索引，造成 shard fan-out、heap、IO 和 cache 抖动。

日志集群要特别关注 hot tier 的写入和 merge 压力。即使 warm/cold/frozen 成本低，hot 写入层如果没有足够 IO、CPU 和磁盘水位空间，整个数据流仍然会出问题。

### 搜索平台集群

搜索平台集群面向多个业务、租户或应用，不只是一个业务索引。拓扑重点是入口治理、租户隔离、资源配额、模板治理、查询 guardrail 和可观测性。

典型做法：

- 业务网关 / API 层作为业务入口，负责认证、租户识别、query rewrite、QPS quota、业务 guardrail、返回字段策略和慢查询采样。
- coordinating-only node 作为 ES 入口，接收 search/bulk 请求，fan out 到 shard，reduce TopN 和聚合结果，吸收协调侧 CPU、heap 和网络压力。
- 请求 timeout、深分页和聚合规模要用 ES 内建控制兜底，例如 request timeout、`index.max_result_window`、`search.max_buckets`，避免只靠网关约定。
- 大租户或高 SLO 业务可以独立索引、独立 shard allocation、独立 data node pool，甚至独立集群。
- 小租户可以共享索引并用 routing 降低 fan-out，但要监控 routing 倾斜和 hot shard。
- 写入入口要区分实时业务写入、批量导入、重建索引、补数任务和 reindex 任务，避免后台任务抢占线上查询资源。
- 平台要提供配额：QPS、并发、查询超时、最大时间范围、最大聚合 bucket、最大结果窗口、bulk 大小、reindex 窗口和 snapshot 窗口。

搜索平台的资深回答要体现治理能力：不是所有业务都应该拿到同样的低延迟和无限资源。不同租户按 SLO、预算和重要性分层，平台用隔离策略保证核心业务稳定，同时用成本模型约束低频和后台需求。

## Data Tiers

Data Tiers 的本质是把数据热度、硬件成本和查询延迟做分层。它不是“老数据随便扔到慢机器”，而是把生命周期、索引分配、查询入口和快照策略连起来。

| Tier | 常见角色 | 数据特点 | 资源取舍 | 常见风险 |
| --- | --- | --- | --- | --- |
| hot | `data_hot` | 当前写入、高频查询、最近时间窗口、业务核心索引 | SSD、较强 CPU/IO、足够 replica、较低延迟 | merge 压力、写入突增、磁盘水位、hot shard、pipeline 抢 CPU |
| warm | `data_warm` | 写入很少或只读，查询频率下降，仍需在线查询 | 成本低于 hot，可接受较高延迟 | 查询突发时拖慢节点，forcemerge/迁移窗口影响 IO |
| cold | `data_cold` | 低频历史数据、合规留存、审计回查 | 成本优先，查询 SLA 明确降级，可结合 searchable snapshot | 被当作热数据查询入口，宽范围聚合造成长尾延迟 |
| frozen | `data_frozen` | 极低频历史查询，通常依赖 searchable snapshots | 用延迟换存储成本，适合偶发检索 | 用户预期不匹配，历史查询并发过高时延迟不可控 |

补充几点：

- `data_content` 常用于内容类、非时间序列业务数据，例如商品、文档、知识库等长期在线查询数据。它不等同于 hot/warm/cold，但同样要按 SLO 和容量规划。
- searchable snapshot 可以降低冷冻历史数据的本地存储成本，但会改变查询延迟、缓存命中、网络和对象存储成本模型。
- hot/warm/cold/frozen 的迁移通常通过 ILM、索引模板和 allocation 控制。只定义节点角色，不定义生命周期策略，数据不会自动符合业务预期。
- 分层后要给用户或业务方明确查询体验：最近 7 天 P95 多少，3 个月前 P95 多少，1 年前是否异步查询，导出是否离线执行。
- 成本优化不能破坏恢复目标。冷层和 frozen 层要同时回答 snapshot、restore、RPO/RTO、对象存储可用性和跨 AZ/跨地域策略。

一句面试总结：Data Tiers 是用不同硬件和生命周期承载不同热度的数据，hot 保写入和低延迟，warm/cold/frozen 逐步用更高延迟和更强约束换成本；是否分层取决于保留期、查询频率、SLO 和预算。

## 资源竞争

ES 的生产问题经常不是某个 API 用错，而是多种任务抢同一组 CPU、heap、IO、网络和 page cache。拓扑拆分的价值，就是让这些竞争有边界、有告警、有降级路径。

### ingest pipeline 抢 CPU

grok、正则解析、script、enrich、geoip、字段归一化和复杂 pipeline 都会消耗 CPU 和 heap。高写入场景如果让 ingest 和 data 混跑，pipeline 峰值会影响 indexing、refresh、merge 和查询。

处理思路：

- pipeline 复杂时拆 dedicated ingest node。
- 对不同来源写入设置 bulk 大小、并发、队列和重试策略。
- 把重解析、补数、历史回灌放到低峰窗口。
- 能在上游完成的清洗不要全部压到 ES ingest pipeline。

### 查询 fan-out 和聚合抢 CPU/heap

一次查询打到很多 index、很多 shard、很多 segment 时，coordinating node 要等待分片响应并合并结果。聚合、排序、高亮、script、nested、深分页和大结果集会进一步推高 CPU 和 heap。

处理思路：

- 用时间范围、租户 routing、业务索引边界和别名减少 fan-out。
- 业务网关 / API 层承接租户识别、query rewrite、QPS quota、业务 guardrail 和慢查询采样；coordinating-only node 只承接 ES 请求 fan out、reduce、连接和协调侧资源隔离。
- 查询 timeout、最大结果窗口和最大聚合 bucket 用请求参数或集群/索引设置兜底，例如 request timeout、`index.max_result_window`、`search.max_buckets`。
- 大范围聚合、导出和报表尽量异步化、离线化或交给 OLAP。
- 对用户可见搜索和后台任务使用不同入口、不同限流和不同 SLO。

### merge 抢 IO

写入、更新、删除和 refresh 会产生 segment，后台 merge 会消耗磁盘 IO、CPU 和 page cache。hot tier 写入大、更新多、delete 多时，merge 很容易成为长尾延迟来源。

处理思路：

- hot data node 要有足够 SSD、IOPS、磁盘空闲和 page cache。
- 控制 refresh interval、bulk 大小和更新模式，不要让小批量高频写入制造过多 segment。
- force merge 更适合写入停止后的 warm/cold 阶段，并放在低峰窗口。
- 监控 merge time、merge throttle、segment count、IO wait 和写入延迟。

### snapshot/restore 抢网络和 IO

snapshot、restore、searchable snapshot、recovery 和 relocation 都会消耗网络、磁盘 IO 和对象存储带宽。它们通常和业务查询共享同一批 data node 资源。

处理思路：

- 给 snapshot 设置窗口、并发、限速和对象存储容量预算。
- restore 和大规模 recovery 要结合业务低峰、节点水位和查询降级。
- 不要在写入高峰和查询高峰同时做大规模快照、恢复、reindex 和 force merge。
- 监控 snapshot 时长、失败率、repository 延迟、网络吞吐和恢复速度。

### segment/cache/shard 元数据抢 heap

heap 压力常来自 shard 过多、segment 过多、mapping 字段过多、聚合 bucket 过多、fielddata、request cache、query cache 和 cluster state。磁盘还有空间，不代表 heap 和控制面健康。

处理思路：

- 控制 shard 数和小索引数量，避免 oversharding。
- 对 mapping 和动态字段做治理，避免字段爆炸。
- 限制大聚合、script、fielddata 和深分页。
- 看 heap、GC、breaker、cluster state size、segment count、field count 和 rejected，而不是只看磁盘。

## 隔离策略

隔离策略要从弱到强选择，目标是用最小复杂度满足 workload 和 SLO。能用查询入口限流解决的，不一定要拆集群；核心业务和日志洪峰互相影响时，拆集群反而是更简单可靠的隔离。

### 节点角色隔离

角色隔离适合把控制面、写入解析、查询入口和数据承载拆开：

- dedicated master-eligible 保护选主、cluster state 和 allocation 调度。
- dedicated ingest 隔离 pipeline CPU 和写入峰值。
- coordinating-only 入口隔离 fan-out、聚合 reduce、连接数和协调侧 CPU/网络；查询 guardrail 由业务网关 / API 层和 ES settings 共同约束。
- data_hot/data_warm/data_cold/data_frozen 分层隔离不同热度数据的硬件和 SLO。

角色隔离的代价是节点池变多、资源碎片增加、容量规划更复杂。因此要用指标证明拆分收益：比如 master 压力、pipeline CPU、coordinating heap、hot node IO 或 cold 查询拖慢热查询。

### 索引级 routing 和 allocation

索引级隔离适合按数据类型、租户、生命周期和硬件层级控制 shard 分布：

- 用 ILM 和 allocation 把索引从 hot 迁到 warm/cold/frozen。
- 用 routing 让租户查询只命中特定 shard，降低 fan-out。
- 用 index template 固化 shard、replica、tier preference、refresh、mapping 和 lifecycle。
- 大租户可以独立索引或独立 data node pool，小租户共享索引但设置配额。

routing 不是免费午餐。租户规模不均时，routing 可能制造 hot shard；按租户独立索引也可能制造大量小 shard。面试里要把这两个风险都讲出来。

### query 入口限流

查询入口是搜索平台最现实的隔离层：

- 按租户、应用、接口和用户设置 QPS、并发、超时和熔断。
- 限制默认时间范围、最大结果窗口、最大分页深度、最大聚合 bucket 和可排序字段。
- 对高成本查询做 explain/estimate、准入审核或异步任务化。
- 对批量导出、管理后台和 BI 查询使用单独入口或低优先级队列。

限流不是为了让查询失败，而是让系统在过载时按业务优先级退化。资深回答要能说清楚哪些查询同步返回、哪些降级、哪些转异步、哪些拒绝。

### 大查询异步化或离线化

有些需求不应该压在在线 ES 查询链路上：

- 跨半年或多年日志检索、全量导出、复杂报表、宽范围聚合、补数校验，适合异步任务或离线系统。
- 用户前台搜索要保护 P95/P99；后台分析可以接受分钟级甚至小时级延迟。
- 复杂聚合可以做预聚合、物化视图、ClickHouse/OLAP、离线计算或缓存。

面试里不要把 ES 当万能数据库。ES 擅长检索和近实时搜索，不适合无限制承载所有分析、导出和长任务。

### 日志集群和业务搜索集群拆分

日志和业务搜索混跑是常见风险。日志写入高、merge 重、保留期长、查询时间窗大；业务搜索通常要求低延迟、稳定 P99 和更强相关性控制。

隔离选择：

- 低规模时可以同集群但要拆 index、role、tier、限流和成本预算。
- 核心业务搜索有明确 SLO，且日志有明显洪峰或长保留期时，优先拆独立集群。
- 搜索平台内不同业务也可以按重要性拆集群、拆节点池或拆索引。

判断标准不是“日志一定不能和业务混跑”，而是混跑后一个 workload 的峰值是否会破坏另一个 workload 的 SLO。

## 面试回答模板

### Q：生产 ES 集群你会怎么部署？

我会先按业务类型和 SLO 选拓扑，而不是先背节点数。

1. 先区分业务类型：如果是业务搜索，我重点看 P95/P99、查询 QPS、更新频率、相关性、故障恢复和数据源一致性；如果是日志检索，我重点看写入量、保留期、data stream、ILM、hot/warm/cold/frozen 和历史查询 SLA；如果是搜索平台，我重点看多租户、query guardrail、配额、入口限流和隔离。
2. 小规模可以先简单混合角色，但要用监控定义边界：master-eligible 不能长期被重查询、重写入、磁盘水位或 ingest pipeline 拖垮。
3. 中大型或高 SLO 集群会拆 dedicated master，保护选主、cluster state 和 shard allocation，不让控制面承载 data shard、复杂查询和重 ingest。
4. 数据节点按数据热度和 SLO 分层：热数据放 `data_hot`，需要低延迟和高写入能力；温冷历史数据放 `data_warm`、`data_cold`；极低频历史查询可以考虑 `data_frozen` 和 searchable snapshot，用延迟换成本。
5. 查询入口如果 fan-out 高、聚合重、多租户集中或连接数多，会用 coordinating-only node 隔离 search/bulk fan out、reduce、连接数和协调侧 CPU/网络；租户识别、query rewrite、quota、慢查询采样和业务 guardrail 放在业务网关 / API 层，超时、分页和聚合上限再用 request timeout、`index.max_result_window`、`search.max_buckets` 等 ES 控制兜底。
6. ingest pipeline 如果解析、enrich、script 很重，会拆 ingest node，避免 pipeline CPU 抢 data node 的 indexing、merge 和 search 资源。
7. 日志、后台导出、reindex、snapshot、restore 和业务在线查询要分时、限流或拆资源池；核心业务和日志洪峰互相影响时，拆集群比复杂限流更可靠。
8. 最后用 ILM、allocation、index template、routing、SLO、慢查询、thread pool、breaker、GC、merge、snapshot 和恢复演练持续校正拓扑。

可以用一句话收束：我的拓扑设计目标不是角色拆得越细越好，而是让控制面稳定、热数据低延迟、历史数据成本可控、重查询和重写入有边界，并且任意节点或 AZ 故障时还能满足约定 SLO。

### Q：什么时候需要 dedicated master？

当集群规模、索引和 shard 数、mapping 变更、ILM 操作、节点变更、故障恢复或业务 SLO 已经让控制面稳定性变重要时，我会拆 dedicated master-eligible 节点。

重点不是“超过多少节点必须拆”，而是看证据：

- master 日志里 cluster state update 变慢。
- 节点 GC、磁盘或 CPU 抖动导致选主或 publish cluster state 不稳定。
- data node 上的查询、bulk、merge、snapshot 和 recovery 已经影响控制面。
- 业务不能接受短时间 yellow/red、索引创建失败、mapping 更新慢或 shard allocation 抖动。

拆 dedicated master 后，还要保证 master 节点自身的 CPU、heap、磁盘、网络和跨 AZ 延迟稳定；否则只是把问题换了位置。

### Q：Data Tiers 怎么做取舍？

我会按数据热度、查询频率、保留期和延迟目标拆：

- hot 承接写入和最近高频查询，给 SSD、CPU、IO 和更严格的水位控制。
- warm 承接只读或低频数据，降低成本但接受更高延迟。
- cold 面向低频历史查询和留存，成本优先，查询 SLA 要降级。
- frozen/searchable snapshot 面向极低频历史检索，用对象存储和缓存机制降低本地成本，但要接受更高延迟和更强查询约束。

Data Tiers 的风险是业务把冷数据当热数据查，或者只迁移数据不治理查询入口。正确做法是把 ILM、allocation、snapshot、查询时间窗、异步历史查询和用户可见 SLA 一起定义。

## 常见反模式

| 反模式 | 后果 | 改法 |
| --- | --- | --- |
| 所有角色混在高负载 data 节点 | GC、CPU、IO、磁盘水位和长查询抖动会影响选主、cluster state、查询和写入 | 按证据拆 dedicated master、ingest、coordinating 和 data roles |
| 日志和核心业务搜索混跑 | 日志洪峰、merge、宽时间范围查询和 snapshot 拖慢业务搜索 P99 | 拆集群，或至少拆 Data Tiers、查询入口、限流和资源预算 |
| snapshot 高峰期无限制运行 | IO、网络、对象存储带宽和 recovery 争用，查询和写入长尾变差 | 设置 snapshot 窗口、限速、并发、监控和恢复演练 |
| 把 coordinating node 当成性能银弹 | 如果 shard 过多、查询太宽、聚合太重，只加入口节点不会降低 data node 成本 | 先治理查询范围、routing、shard sizing、聚合和大结果集，再评估入口层 |
| dedicated master 仍承载 data 或 ingest | 控制面仍会被写入、merge、pipeline 和查询拖住 | master-eligible 节点保持轻负载，只服务控制面 |
| hot/warm/cold/frozen 只改节点角色 | 数据生命周期、allocation、查询入口和 SLA 没变，分层无法落地 | 用 ILM、index template、tier preference、snapshot 和查询策略一起实施 |
| cold/frozen 被当作在线热查询层 | 历史大范围查询造成高延迟、缓存抖动和对象存储成本上升 | 明确历史查询 SLA，做异步查询、默认时间窗、限流和低优先级入口 |
| 每个租户都独立索引 | 小租户产生大量小 shard，cluster state、heap、文件句柄和运维成本上升 | 小租户共享索引并用 routing，大租户独立索引或独立资源池 |
| 只按磁盘成本做 Data Tiers | 忽略查询延迟、恢复时间、snapshot、跨 AZ、对象存储和运维成本 | 同时评估成本、P95/P99、RPO/RTO、恢复演练和查询频率 |
| 后台 reindex、导出和业务查询共用入口 | 大任务占满 search/write 线程池和 coordinating heap，线上查询 rejected 或超时 | 后台任务异步化、低峰运行、单独入口、配额和可取消任务治理 |
| 拓扑设计不考虑 failure domains/AZ | 单节点或单 AZ 故障时 primary/replica、master quorum 或恢复带宽不可用 | 结合 AZ、replica、shard allocation awareness、容量冗余和恢复演练设计 |
| 资源竞争只靠扩容解决 | 扩容可能缓解磁盘，但不能解决 fan-out、hot shard、mapping 爆炸和无限制聚合 | 先定位 CPU/heap/IO/网络瓶颈，再选择拓扑、索引模型、限流或离线化 |
