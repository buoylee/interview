# 12.1 容量规划与 Shard Sizing

> **轨道**：A core / B prerequisite
>
> **目标**：能以资深工程师视角回答“这个 ES 集群要多少节点、多少 shard、多少 replica、什么时候 rollover、数据增长 10 倍怎么办”。

## 资深工程师先看什么

资深工程师不会先问“primary shard 设几个”，而是先把业务负载问清楚。Shard sizing 是容量、查询形态、生命周期和故障恢复的共同结果，不是一个孤立参数。

优先确认这些输入：

- 数据量：每天写入多少文档，单条文档平均和 P95 大小是多少，是否有大字段、数组、nested、向量字段、长文本和 `_source` 保留要求。
- 保留期：热数据查几天，温数据查几个月，冷数据是否只做低频审计或离线回放。
- 增长率：未来 6 到 12 个月的数据增长、租户增长、字段增长和峰值写入增长是否可预期。
- 写入压力：平均写入 TPS、峰值写入 TPS、bulk 大小、refresh 间隔、更新比例、delete 比例、ingest pipeline 成本和 segment merge 压力。
- 查询压力：QPS、P95/P99 延迟目标、并发用户数、是否存在批量导出、分页深翻、Dashboard 刷新或定时任务。
- 查询形态：按时间、租户、关键词、状态、地理范围、权限过滤还是多条件组合；是否有聚合、排序、高亮、script、nested、parent-child、向量检索或 hybrid search。
- 一致性边界：ES 是主存储还是搜索视图；失败时允许丢多久数据、停多久查询、是否需要回源数据库兜底。
- 资源边界：数据节点磁盘、CPU、heap、文件句柄、网络、跨 AZ 流量和快照仓库成本。

面试里要体现一个判断：容量规划不是“算出一个数字就结束”，而是先建立假设，再用压测、样本导入和线上监控持续校正。没有 workload 的 shard 数都是猜测。

## 容量模型

容量模型先用于估算量级，不是最终采购公式。真实结果会被 mapping、字段类型、压缩率、查询并发、segment 数量、merge 策略、硬件和版本差异影响，必须用样本数据或生产指标验证。

基础估算框架：

```text
daily_raw_data = document_count_per_day * avg_document_size
indexed_data = daily_raw_data * index_expansion_factor
retention_data = indexed_data * retention_days
replicated_data = retention_data * (1 + replica_count)
disk_required = replicated_data / disk_watermark_target
node_count = disk_required / usable_disk_per_data_node
```

解释这些变量时要说清楚边界：

- `document_count_per_day` 和 `avg_document_size` 要看平均值和高分位值。日志类字段稳定，可以按时间窗口采样；订单、商品、内容类索引要关注大文档、nested 数组和富文本字段。
- `index_expansion_factor` 受 `_source`、倒排索引、Doc Values、stored fields、向量字段、分词器、multi-fields、nested 文档和压缩率影响。可靠做法是拿样本数据按真实 mapping 建索引，比较原始数据和索引落盘。
- `retention_days` 要拆成 hot、warm、cold，而不是只写一个总天数。热数据影响 SSD、CPU、heap 和 replica；温冷数据更多影响磁盘、恢复时间、查询 SLA 和快照策略。
- `replica_count` 不是只为读扩展服务，也决定节点故障时的可用性和恢复压力。replica 越多，磁盘和写入复制成本越高。
- `disk_watermark_target` 不能按 100% 算，要给 high watermark、flood-stage、segment merge、快照、恢复、relocation 和短期突增留空间。生产上通常保守控制在水位线以下，而不是让磁盘长期贴近上限。
- `node_count` 还要被 CPU、heap、文件句柄、网络、AZ 故障域和恢复时间修正。磁盘能放下不代表查询能扛住。

容量模型至少拆三张表：

| 维度 | 估算内容 | 关键风险 |
| --- | --- | --- |
| 存储 | 原始数据、索引膨胀、保留期、replica、磁盘水位 | 磁盘够但 merge、快照、恢复没有空间 |
| 读写 | 写入 TPS、bulk、refresh、查询 QPS、聚合和排序 | CPU、IO、thread pool、coordinating node 成为瓶颈 |
| 元数据 | shard 数、segment 数、mapping 字段数、index 数 | heap、cluster state、文件句柄和恢复调度压力上升 |

heap 不是按数据总量线性扩大。更常见的 heap 压力来自 shard 数过多、segment metadata 过多、mapping 爆炸、聚合 bucket 爆炸、fielddata、查询并发、request cache/query cache 竞争和大量小索引带来的 cluster state 更新。

## Shard Sizing 原则

Shard 是 Lucene index，有固定管理成本。每个 shard 都会带来 segment、文件句柄、缓存、统计信息、恢复调度、cluster state 和查询 fan-out 成本。因此 sizing 的目标不是“越多越并行”，而是在写入并行、查询 fan-out、恢复时间和运维成本之间取平衡。

常用决策框架：

1. 先按业务边界决定索引模型：时间序列、固定业务索引、多租户共享索引，还是大租户独立索引。
2. 再按热数据量和目标 shard size 反推 primary shard 数。
3. 然后用节点数和 replica 验证分布：同一 primary 和 replica 不能在同一节点，跨 AZ 时要考虑故障域。
4. 最后用压测和生产指标校正：看查询 fan-out、单 shard 延迟、merge、refresh、heap、文件句柄、recovery 和 relocation 时间。

经验区间只能当起点。很多普通日志、指标和业务搜索场景会把单个 primary shard 控制在几十 GB 以内，常见目标是约 10GB 到 50GB，并关注单 shard 文档数不要过大；但更小或更大的 shard 都可能合理，取决于查询形态、恢复目标、硬件、冷热层级和数据模型。

典型取舍：

- shard 太小：oversharding，cluster state 变大，segment 数和文件句柄增加，查询 fan-out 变多，coordinating node 合并成本上升，heap 被元数据消耗。
- shard 太大：单 shard 查询更重，refresh/merge 更容易形成局部压力，节点故障后的 recovery、relocation 和 rebalancing 时间变长。
- primary 太少：写入并行度不足，未来单索引增长后拆分困难，单 shard 热点更明显。
- primary 太多：每次查询打到更多 shard，低流量索引产生大量小 shard，管理成本超过并行收益。
- replica 太少：节点故障时可用性和读扩展不足，恢复期间风险升高。
- replica 太多：写入复制、磁盘、网络和 merge 成本上升，写多读少场景收益有限。

日志和时间序列索引通常用 data stream、ILM 和 rollover 控制 shard 大小，让长期增长通过新 backing index 承接。商品、订单、内容搜索通常不是简单按天切索引，要结合查询模式、租户隔离、更新频率、排序字段和 reindex 发布方式设计。

## Primary、Replica、Node 的关系

Primary、Replica 和 Node 要一起规划：

- primary 决定写入分布和基础并行度。写入先落 primary，再复制到 replica；primary 过少会限制单索引写入扩展，primary 过多会放大查询 fan-out 和管理成本。
- replica 提供高可用和读扩展。查询可以命中 primary 或 replica，节点故障时 replica 可提升为 primary；但 replica 会增加磁盘、网络、写入确认、refresh 和 merge 成本。
- node 决定 shard 分布、资源池和故障域。节点数太少时 replica 不能有效隔离；节点数增加后也要避免每个节点承载过多 shard。
- 单节点承载过多 shard 会增加 heap、文件句柄、segment 元数据、cluster state 处理和恢复调度压力。即使磁盘没满，也可能出现 GC、open file limit、search thread pool、recovery 慢或 master 压力。

规划时要用几个校验问题：

- 任意一个 data node 下线后，剩余节点是否能承载 primary、replica 和恢复流量。
- 任意一个 AZ 下线后，是否仍满足搜索可用性和写入策略。
- 热索引的 primary 是否能均匀分散到 hot data nodes，是否存在 routing 或租户导致的 hot shard。
- 查询是否需要打到大量 index 和 shard，coordinating node 是否会被 TopN merge、aggregation reduce 或大结果集拖慢。

一个常见面试表达是：primary 解决基础分片和写入并行，replica 解决 HA 和读扩展，node 解决资源和故障域；三者不能只按磁盘算，要同时检查 heap、CPU、IO、文件句柄、segment、查询 fan-out 和恢复时间。

## Rollover 决策

Rollover 的核心价值是把“无限增长的索引”变成“可控大小的一组索引”。它常用于 data stream、日志、指标、审计流水和其他按时间追加写入的数据。

常见触发条件：

- 按大小 rollover：用 `max_primary_shard_size` 控制单个 primary shard 尺寸，避免 shard 长到恢复和查询都不可控。
- 按时间 rollover：用 `max_age` 对齐业务查询、保留期、报表周期和 ILM 阶段迁移。
- 按文档数 rollover：适合文档大小相对稳定、单文档成本可预测的场景。
- 按最小条件保护：低流量索引可以设置最小 shard size 或类似保护条件，避免每天生成一堆极小 shard。

真实生产往往组合多个条件，但不是简单的“谁先满足谁触发”：rollover 会在任一 `max_*` 条件满足、且全部 `min_*` 条件也满足时触发。例如日志索引可以同时设置最大 primary shard size、最大索引年龄和最小 primary shard size：高峰期在满足最小保护后按大小切，低峰期也要等最小条件达标后再由时间条件触发，避免低流量环境产生太多小 shard。

Rollover 还要和 hot/warm/cold 生命周期配合：

- hot：承接写入和高频查询，需要更强 CPU、SSD、足够 replica、较高 merge 能力和严格水位控制。
- warm：通常只读或低频写，适合降低 replica、forcemerge、迁移到成本更低的节点，但要接受查询延迟变高。
- cold：面向低频查询、合规留存和审计回查，重点是成本、快照、恢复时间和查询 SLA；不要把冷层当热查询兜底。

风险取舍要讲清楚：rollover 太频繁会制造小 shard 和 cluster state 压力；rollover 太慢会产生大 shard，导致恢复慢、迁移慢和单 shard 查询重。合理策略要用 shard size、写入速率、查询时间范围、保留期和恢复目标一起决定。

## 四个典型场景

### 日志检索

日志检索通常是按时间追加写入，查询也以最近时间窗口为主。推荐思路是 data stream + ILM + rollover：

- 热层保存最近几天或几周，按写入速率设置 primary 数和 rollover 条件，保证 shard size 可控。
- 温层保存中期数据，降低查询 SLA，必要时 forcemerge 并迁移到 warm nodes。
- 冷层保存低频审计数据，优先考虑成本、快照和恢复时间。
- 查询入口要限制时间范围，避免默认跨半年索引查询造成 shard fan-out。
- 高写入场景关注 refresh interval、bulk 大小、ingest pipeline、merge、磁盘水位和 hot shard。

面试里可以说：日志不是靠“每天一个索引”解决一切，而是用 rollover 让每个 backing index 的 shard 大小稳定，再用 ILM 把不同热度的数据放到不同成本和 SLA 的节点上。

### 商品搜索

商品搜索通常是固定主索引或按业务域拆索引，不宜简单按天切。核心约束是查询相关性、排序、过滤、更新频率和发布稳定性。

常见设计：

- 用 alias 指向当前线上索引，重建索引后切 alias，实现 mapping 变更、分词变更和全量重建发布。
- primary shard 数按商品量、增长率、查询 QPS、排序字段和聚合需求估算，不只按磁盘估算。
- 更新频繁时关注 refresh、partial update、segment merge 和版本冲突；大促期间要预留写入和查询峰值。
- 排序字段、过滤字段、Doc Values、keyword/text multi-fields 会影响磁盘和 heap 间接压力。
- 相关性调优、召回和排序可能让查询更重，shard 过多会放大每次搜索的 fan-out 和 reduce 成本。

风险取舍：固定主索引便于查询和相关性治理，但单索引会持续增长；按类目或租户拆索引可以隔离风险，但会增加索引和 shard 管理成本，也可能让跨类目搜索变复杂。

### 订单搜索

订单搜索的第一原则通常是正确性优先。ES 更适合作为搜索视图，MySQL 或交易库仍是事实源。

容量和 shard 设计要围绕访问模式：

- 查询通常按用户、商户、租户、状态和时间过滤，时间范围很关键。
- 数据增长快但历史订单查询频率下降，可以按时间维度拆索引或使用 rollover，并配合冷热分层。
- 对强一致要求高的查询要回源确认，ES 结果用于候选召回或后台检索。
- 写入链路要关注 CDC、消息堆积、重试、幂等、延迟和补偿，不要把 ES 写入成功当交易成功。
- 聚合报表类需求要警惕大范围聚合拖垮搜索集群，必要时转向 OLAP 或预聚合。

风险取舍：按时间拆分便于保留期和冷热迁移，但用户跨多年订单查询会打到多个索引；按租户 routing 可以减少 fan-out，但大租户可能形成 hot shard，需要独立索引或拆分策略。

### 多租户搜索

多租户搜索要在隔离、成本和查询效率之间做选择。

三种常见策略：

| 策略 | 适合场景 | 优点 | 风险 |
| --- | --- | --- | --- |
| shared index + routing | 租户多、单租户数据小、查询多带 tenant_id | shard 利用率高，索引数量少，按 routing 减少 fan-out | 大租户可能 hot shard，mapping 需要统一 |
| index per tenant | 租户少、强隔离、mapping 差异明显 | 权限、生命周期、迁移和故障隔离清晰 | 小租户会制造大量小 shard，cluster state 和 heap 压力大 |
| 大租户独立索引，小租户共享 | 租户规模差异大 | 成本和隔离平衡，大租户可单独扩容和调优 | 路由、运维、迁移和查询入口更复杂 |

面试中不要只说“每个租户一个索引更隔离”。资深回答要补上 shard 爆炸、mapping 治理、routing 倾斜、大租户迁移、SLO 分层和成本分摊。

## 面试回答模板

### Q：你会怎么规划一个 ES 集群的 shard？

我不会先拍 primary shard 数，而是先把容量模型和访问模型问清楚：

1. 先问数据量、单文档大小、增长率、保留期、QPS/TPS、查询模式、更新比例、聚合/排序/高亮/向量检索和 P95/P99 SLO。
2. 用样本 mapping 估算 `index_expansion_factor`，再算 retention、replica 后的磁盘占用，并预留水位线、merge、恢复和突增空间。
3. 根据热数据规模和目标 shard size 反推 primary shard 数。目标 shard size 只用经验区间起步，例如许多场景会先落在几十 GB 以内，再用压测修正。
4. 根据 data node 数、AZ、故障域和 replica 验证 shard 分布，确保节点故障后仍有空间恢复，且单节点 shard 数、heap、文件句柄和 segment 开销可控。
5. 对时间序列用 data stream、rollover 和 ILM 控制长期增长；对商品、订单、多租户搜索结合 alias、routing、reindex、租户隔离和查询边界设计。
6. 上线后看真实指标校正：shard size、segment count、heap、GC、thread pool rejected、merge、refresh、query latency、hot shard、disk watermark、recovery time 和 slowlog。

总结句可以这样说：shard sizing 的目标是让每个 shard 足够大以避免 oversharding，又不能大到恢复和查询不可控；最终数字必须由业务负载和压测指标验证。

### Q：数据增长 10 倍怎么办？

我会先判断增长发生在哪个维度：写入 TPS、保留期、单文档大小、租户数量、查询 QPS、聚合复杂度，还是字段和 mapping 膨胀。不同增长点对应的动作不一样。

- 短期：扩 data node，检查磁盘水位和 shard 分布；必要时临时调整 replica、refresh、bulk、限流、查询时间范围和重查询入口，先避免写入拒绝、磁盘水位和 hot shard 扩散。
- 中期：重新设置 rollover 条件，让新增数据进入合理大小的 backing index；对过大的历史索引做 reindex 或 split 策略评估；把热、温、冷数据分层，降低老数据 replica 和查询 SLA；对大租户或热点业务拆独立索引。
- 长期：重做容量模型和生命周期策略，明确哪些查询应该进 ES，哪些应该进 OLAP、缓存或离线系统；治理 mapping、字段、聚合、深分页和导出；建立容量水位、增长预测和压测基线。

风险取舍要补一句：增长 10 倍不一定等于节点 10 倍。如果瓶颈是磁盘，扩容接近线性；如果瓶颈是查询 fan-out、聚合、heap、segment 或 hot shard，必须改索引模型、查询边界和生命周期策略。

## 常见反模式

| 反模式 | 后果 | 改法 |
| --- | --- | --- |
| 每天每租户一个索引 | 小租户制造大量小 shard，cluster state、heap、文件句柄和恢复成本上升 | shared index + routing，小租户合并，大租户单独索引 |
| primary shard 先随便设 | 后续扩容、恢复和重建成本不可控，可能长期被过大或过小 shard 绑定 | 建模时估算增长、目标 shard size、节点数和 rollover 策略 |
| 只按磁盘估算节点 | heap、CPU、IO、fan-out、segment merge、文件句柄和 recovery 被忽略 | 同时估算读写、聚合、shard 数、segment 数和故障恢复窗口 |
| replica 越多越好 | 写入复制成本、磁盘成本、网络成本和 merge 成本上升 | 按读 QPS、HA、AZ 和恢复目标设置 replica |
| shard 越多查询越快 | 查询 fan-out 和 reduce 成本上升，coordinating node 压力变大 | 用压测验证并行收益，控制 shard 数和查询索引范围 |
| shard 越大越省事 | 节点故障后 recovery 慢，relocation 慢，单 shard 查询和 merge 压力大 | 用 rollover、reindex 或业务拆分控制单 shard 尺寸 |
| 把 cold 当 hot 用 | 冷层成本低但延迟和恢复能力不匹配，突发查询会拖慢集群 | 明确 hot/warm/cold SLA，限制历史查询和大范围聚合 |
| 忽略 mapping 和字段增长 | 字段、Doc Values、向量、nested 和 segment metadata 推高磁盘与 heap 压力 | 建字段治理、模板评审、样本导入和 mapping 变更流程 |
| 不限制查询时间范围 | 一次查询打到大量索引和 shard，P99 抖动且成本不可控 | 默认时间窗、索引别名、路由、查询保护和大查询降级 |
| 没有压测和上线校正 | 规划数字无法解释生产瓶颈，扩容动作容易拍脑袋 | 建立基准压测、容量看板、增长预测和定期复盘 |
