# 12.3 故障恢复、RPO/RTO 与 SLO

> **轨道**：A core / B prerequisite
>
> **目标**：从“会处理 yellow/red”提升到“能设计搜索能力的可靠性目标、恢复策略、告警和演练”。

生产 ES 的可靠性设计，不能只停留在“加 replica、做 Snapshot、看到 red 再处理”。资深工程师要能先定义 ES 在业务链路里的职责边界，再把 RPO、RTO、SLO、告警阈值和 runbook 串起来。否则团队很容易在故障时发现：主库能恢复但搜索不可用，或者搜索能查但数据已经落后，或者有快照却没有演练过 Restore。

## ES 搜索能力的可靠性边界

ES 经常是业务系统的搜索视图、读模型或近实时索引，不一定是 source of truth。订单、支付、库存、账号、权限这类强一致数据，事实源通常在 MySQL、PostgreSQL、Kafka 事件日志、对象存储或其他主系统里；ES 负责检索、过滤、排序、聚合和召回。如果面试里默认把 ES 当主库，会暴露可靠性边界不清。

几个边界必须先讲清楚：

- **写入可见性不是持久性保证**：refresh 后文档能被搜索到，只说明进入了可搜索 segment；业务写入是否真正可靠，还要看主库事务、消息投递、ES primary 写入、replica 复制、translog 的 fsync/commit 策略（`index.translog.durability`）、节点故障和重试幂等。flush 只是创建 Lucene commit 并开启新的 translog generation，不能等同于每次写入的基础持久化机制；搜索“可见”也不能等同于业务“已提交”。
- **replica 不是 backup**：replica 能提高 shard 可用性和读扩展，也能在节点故障时提升为 primary；但误删索引、错误 update_by_query、mapping 变更、逻辑脏数据、勒索或集群级错误会同步影响 primary 和 replica。备份要靠主库备份、事件日志可重放、Snapshot 仓库和恢复演练。
- **Snapshot 不是连续备份**：Snapshot 是某个时间点的快照策略，不覆盖两次快照之间的所有写入。它不能替代主库备份，也不能替代 CDC、消息日志、重放任务和业务补偿。
- **强一致读不应默认依赖 ES**：需要强一致的订单详情、权限校验、库存扣减和资金状态，应回源主库或采用业务补偿。ES 可以做候选召回和用户体验优化，但不能把近实时搜索当作交易一致性边界。
- **RPO 取决于整条链路**：主库、同步链路、消息堆积、消费者幂等、translog、Snapshot 周期、快照仓库、可重放事件和补数能力都会影响实际数据损失窗口。
- **RTO 取决于恢复路径**：节点替换、shard recovery、allocation、Snapshot Restore、reindex、别名切换、查询降级、主库回源和业务限流，都会决定从故障到恢复服务的时间。

面试里可以把 ES 的可靠性拆成三层：业务事实源保证数据不丢，同步链路保证搜索视图尽快追上，ES 集群保证可查询和可恢复。不要把这三层混成一个“ES 高可用”。

## RPO/RTO 设计

RPO/RTO 不能只写“尽量不丢、尽快恢复”。要按功能定义，因为不同搜索能力的可靠性目标差异很大：前台商品搜索、后台订单检索、日志审计、运营报表和风控召回，对数据损失、搜索停机和降级体验的容忍度完全不同。

可以使用这个设计模板：

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

示例填法：

| 字段 | 商品搜索 | 订单后台检索 | 日志检索 |
| --- | --- | --- | --- |
| `feature` | 前台商品搜索 | 客服和商家订单搜索 | 生产日志查询 |
| `source of truth` | 商品库、库存/价格服务、商品变更事件 | 交易库、订单事件、支付状态服务 | 日志源、Kafka、对象存储归档 |
| `acceptable data loss` | 通常不接受长期丢数据，可接受分钟级索引延迟 | 不接受业务事实丢失，ES 可接受短时落后并回源确认 | 取决于日志链路，常按采集和归档能力定义 |
| `acceptable search downtime` | 秒级到分钟级，核心链路需要降级兜底 | 分钟级可接受，但关键订单必须可回源 | 按运维场景分级，线上事故期要求更高 |
| `rebuild path` | 从商品库或事件日志 reindex，alias 切换 | 从交易库按时间/租户补数，必要时分批 reindex | 从 Kafka、对象存储或日志归档重放 |
| `snapshot policy` | 保护索引结构和快速恢复，不替代商品库备份 | 保护历史索引，不能替代交易库备份 | 按保留期和成本做 SLM，和归档策略配合 |
| `degraded mode` | 热门商品缓存、类目页降级、主库小范围查询 | 精确订单号回源，复杂搜索暂停或异步 | 限制时间窗、关闭大聚合、异步导出 |
| `verification drill` | 定期演练 Restore 到临时索引并校验召回和延迟 | 演练按时间段补数和别名切换 | 演练仓库可用性、历史 Restore 和宽时间窗降级 |

设计 RPO/RTO 时要问五个问题：

1. 这个功能的事实源在哪里，ES 丢了是否能重建。
2. 同步链路是否有可重放日志，重放速度是否追得上生产写入。
3. Snapshot 周期和保留期能覆盖哪些事故，不能覆盖哪些事故。
4. Restore 或 reindex 期间用户看到什么，是报错、缓存、回源还是降级结果。
5. 演练是否验证过真实耗时，而不是只写在文档里。

## Snapshot 与 Restore

Snapshot 与 Restore 的定位是“恢复 ES 索引和集群状态的一种手段”，不是完整业务备份体系。它适合处理节点损坏、索引误删、历史索引恢复、跨集群迁移和灾备演练；它不适合承担所有写入的连续保护，也不能替代主库备份和事件日志。

生产设计要覆盖这些点：

- **SLM 定期快照**：使用 Snapshot Lifecycle Management 定义快照频率、保留数量、保留时间和执行窗口。高写入集群要避开业务峰值，并监控 snapshot duration、失败率、仓库延迟和对象存储成本。
- **快照仓库可用性**：注册 snapshot repository 时要让 ES 校验仓库，或用 `_snapshot/<repository>/_verify` 做人工验证。仓库验证要覆盖 master 和 data 节点对仓库的访问能力，不能只在一个节点上确认对象存储凭据可用。
- **repository 权限和隔离**：对象存储 bucket、NFS、共享文件系统或云仓库要限制写权限、生命周期、跨地域复制和删除保护。仓库如果和生产集群同故障域，灾备价值会下降。
- **Restore 演练**：至少演练恢复到临时索引或临时集群，验证 restore 速度、缺失索引、mapping、settings、ILM、alias、index template、security 配置和应用兼容性。
- **Restore 后校验**：恢复后先做只读校验，检查文档数、关键查询、抽样一致性、索引健康、segment 状态和延迟。确认后再通过 alias 切换、读流量灰度或业务配置切换承接查询。
- **恢复窗口评估**：大索引 Restore 会消耗网络、磁盘 IO、对象存储带宽和 recovery 线程，也可能和查询、merge、relocation 抢资源。RTO 必须用演练耗时修正。
- **不能替代主库备份**：如果 ES 是读模型，真正的业务 RPO 仍取决于主库、事件日志和补数能力。Snapshot 只能恢复某个快照点的 ES 状态，两次快照之间的数据要靠重放或补偿。

一个容易踩的坑是“有快照等于能恢复”。资深回答要补上：repository 是否验证过、快照是否按策略成功、Restore 是否演练过、恢复后如何校验、别名如何切、恢复期间业务如何降级。

## Disk Watermark

磁盘水位线不是普通容量告警，而是会直接影响 shard allocation 和写入能力的保护机制。ES 会根据 low、high、flood-stage watermark 逐步限制分配、迁移 shard，并在极端情况下保护节点磁盘。

关键概念：

- **low watermark**：节点磁盘超过低水位后，ES 不会再把 shard 分配到该节点；但这个限制不阻止新建索引 primary shard 的首次分配，会阻止这些 primary 的 replica 继续分配。风险是扩容和恢复时没有足够落点，replica 长时间 unassigned。
- **high watermark**：节点磁盘超过高水位后，ES 会尝试把 shard 从该节点迁走。风险是 relocation 消耗 IO 和网络，如果全体节点都接近高水位，集群没有地方可迁。
- **flood-stage watermark**：节点达到 flood-stage 后，ES 可能把相关索引设置为 `index.blocks.read_only_allow_delete`，防止继续写入撑爆磁盘。磁盘使用率回到高水位以下后，ES 可能自动释放该 block；操作时要确认是否已自动解除，只有水位健康后仍残留时才手动移除。
- **frozen flood-stage**：frozen 或 searchable snapshot 场景也有对应水位控制，不能因为数据冷就忽略本地缓存和磁盘上限。

处理思路按优先级来：

1. 先确认影响范围：`_cluster/health`、`_cat/allocation`、`_cat/shards`、节点磁盘、索引 read-only block、写入失败日志和业务错误率。
2. 立刻止血：暂停大规模写入、reindex、force merge、Restore、历史查询和批量导出，避免继续制造 IO 和磁盘增长。
3. 释放空间：删除过期数据、加速 ILM rollover/delete、清理无用索引、降低临时 replica、清理失败重建任务产生的旧索引。删除前必须确认业务保留期和事实源。
4. 扩容或迁移：增加 data node、扩磁盘、调整 allocation，让 shard 有可迁移目标。不要只临时调高 watermark 掩盖容量不足。
5. 恢复写入：空间稳定并低于高水位后，先确认 `index.blocks.read_only_allow_delete` 是否已自动释放；如果水位健康后 block 仍残留，再手动清除，并验证写入、refresh、replica allocation 和查询延迟。
6. 复盘容量：补增长预测、磁盘 SLO、ILM、snapshot 窗口、告警阈值和演练缺口。

面试里要避免一句“删点数据就行”。水位线故障通常说明容量模型、保留期、ILM、写入峰值或恢复窗口至少有一个没有被治理。

## Unassigned Shard 诊断

Unassigned Shard 不是一个原因，而是一类结果。诊断要按证据链走，避免看到 yellow/red 就直接 reroute 或强制 allocate。尤其是 red，通常表示至少有 primary shard 不可用，错误操作可能扩大数据损失。

推荐 runbook 顺序：

```text
_cluster/health
-> _cat/shards
-> _cluster/allocation/explain
-> 节点/磁盘/过滤规则/副本数/数据层/水位线
-> 修复
-> 验证 shard 分配
```

具体步骤：

1. **看健康状态**：`_cluster/health` 区分 green、yellow、red。yellow 通常是 replica 未分配，red 表示至少有 primary 未分配或不可用，优先恢复数据可用性。
2. **定位 shard**：用 `_cat/shards?v&h=index,shard,prirep,state,unassigned.reason,node` 找出哪个 index、哪个 shard、primary 还是 replica、unassigned reason 是什么。
3. **解释 allocation**：用 `_cluster/allocation/explain` 查看 `can_allocate`、`allocate_explanation`、`node_allocation_decisions` 和 deciders。需要磁盘细节时带 `include_disk_info=true`。
4. **检查节点和磁盘**：确认节点是否丢失、是否正在重启、磁盘是否超过 watermark、是否有 read-only block、是否有同 shard 副本已在目标节点。
5. **检查过滤规则和数据层**：看 index allocation filters、tier preference、ILM 阶段、node roles、awareness、forced awareness、exclude/include 规则是否让 shard 无处可去。
6. **检查副本数和容量**：节点数不足时，replica 不可能和 primary 分到同一节点；小集群设置过多 replica 会长期 yellow。容量不足时增加 replica 只会放大问题。
7. **检查索引和 shard copy**：如果 primary 没有 valid shard copy，要判断是否有节点可恢复、是否有 Snapshot 可 Restore，或者是否能从 source of truth reindex。不要把 stale primary 强制分配当作常规手段。
8. **修复并验证**：修复后观察 `_cat/shards`、`_cluster/health`、recovery、业务查询、写入成功率和延迟，确认 allocation 收敛而不是反复迁移。

常见原因和处理：

| 现象 | 可能原因 | 处理方向 |
| --- | --- | --- |
| primary unassigned，red | 节点丢失、无有效 shard copy、索引损坏、磁盘不可用 | 优先找回节点或磁盘；无可用 copy 时评估 Snapshot Restore 或从事实源 reindex |
| replica unassigned，yellow | 节点数不足、replica 数过高、同节点不能放同 shard 副本 | 增加节点、降低 replica、调整拓扑和容量 |
| allocation explain 指向 disk decider | low/high/flood-stage watermark 或空间不足 | 释放空间、扩容、迁移 shard，确认水位后恢复写入 |
| explain 指向 filter/tier | allocation include/exclude、ILM tier preference、节点角色不匹配 | 修正 index settings、ILM、node roles 或迁移策略 |
| 反复 relocating | 节点磁盘接近水位、awareness 约束、负载不均 | 先处理容量和约束，再看均衡策略 |

资深表达的重点是：先解释为什么不能分配，再选择修复动作；不要用 reroute 掩盖磁盘、过滤规则、数据层或容量问题。

## SLO 与告警

ES 搜索服务的 SLO 要覆盖用户体验、数据新鲜度、系统保护和恢复能力。只监控 JVM 或集群 green 不够，因为集群 green 也可能 P99 很差、数据同步延迟很高、关键租户查询不可用。

建议按四类指标设计：

| 类别 | SLO / 指标 | 典型告警阈值 | 说明 |
| --- | --- | --- | --- |
| 可用性 | search availability、写入成功率、关键接口错误率 | 5 分钟内搜索成功率低于 99.9%；关键接口 5xx 或 ES timeout 超过预算 | 按核心业务、租户或 API 分层，不要只看集群总成功率 |
| 延迟 | P95/P99 latency、慢查询比例、coordinating reduce 耗时 | P95 连续 10 分钟超过目标；P99 超过目标 2 倍；慢查询日志突增 | 前台搜索和后台导出要分开统计 |
| 新鲜度 | index freshness、CDC lag、Kafka lag、refresh 后可见延迟 | 新鲜度超过业务承诺，例如商品变更 5 分钟未可搜；同步 lag 连续上升 | 新鲜度要从 source of truth 到 ES 可搜索结果端到端计算 |
| 资源保护 | rejected requests、JVM memory pressure、GC、breaker、CPU、IO、disk watermark | search/write rejected > 0 持续出现；JVM pressure 高于阈值；触发 high/flood watermark；breaker 触发 | 这类是早期过载信号，要和业务降级联动 |
| 恢复能力 | unassigned shards、recovery time、snapshot success、repository 验证、SLM 失败 | primary unassigned 立即 P0/P1；replica unassigned 按影响分级；Snapshot 连续失败；repository _verify 失败 | 恢复类指标决定事故时有没有退路 |

告警设计要有分级：

- **P0/P1**：red、primary unassigned、核心搜索不可用、写入大面积失败、flood-stage 导致核心索引 read-only、Snapshot Restore 关键恢复失败。
- **P2**：yellow 且 replica unassigned 持续、high watermark、rejected requests 持续、P99 明显劣化、index freshness 超过业务承诺、JVM memory pressure 长时间高位。
- **P3**：low watermark、SLM 单次失败、snapshot duration 异常增长、shard 数增长过快、mapping 字段数接近治理阈值、历史查询慢查询突增。

一个实用 runbook 可以这样组织：

1. **确认用户影响**：search availability、错误率、P95/P99、影响租户、影响索引和是否可降级。
2. **确认集群状态**：health、unassigned shards、节点存活、master 稳定性、pending tasks、磁盘 watermarks。
3. **判断故障类型**：容量水位、节点故障、allocation 约束、查询过载、写入过载、同步链路延迟、snapshot/repository 异常。
4. **先止血**：限流、降级、关闭大查询、暂停重任务、回源主库、切缓存、暂停非核心写入或导出。
5. **再恢复**：扩容、释放空间、修正 allocation、恢复节点、Restore、reindex、补数、alias 切换。
6. **最后验证**：health green/yellow 是否符合预期，关键查询是否恢复，index freshness 是否追平，告警是否关闭，RPO/RTO 是否满足。
7. **复盘固化**：补容量阈值、SLM 策略、repository 验证、演练记录、告警分级和自动化脚本。

SLO 的关键不是指标越多越好，而是每个告警都能指向明确动作：谁处理、先看什么、怎么降级、怎么恢复、何时升级。

## 面试回答模板

### Q：ES red 了你怎么处理？

我会先把 red 当作数据可用性事件处理，因为 red 表示至少有 primary shard 不可用，不能只盯着集群颜色。

1. 先确认影响范围：看 `_cluster/health`，确认 red 的 index、primary unassigned 数量、业务查询和写入是否受影响，必要时先触发业务降级或限流。
2. 用 `_cat/shards` 定位具体 shard，再用 `_cluster/allocation/explain` 看 allocation 决策，判断是节点丢失、磁盘 watermark、过滤规则、tier 不匹配、副本数、索引损坏，还是 recovery 正在进行。
3. 如果是节点短暂丢失，先判断节点能否安全恢复；如果是磁盘水位，先释放空间或扩容，确认磁盘使用率低于高水位且 read-only block 已自动释放；只有水位健康后 `index.blocks.read_only_allow_delete` 仍残留时才手动清除；如果是 allocation 规则，修正 index settings、ILM 或节点角色。
4. 如果 primary 没有 valid copy，要回到可靠性边界：有主库或事件日志时评估 reindex/补数；没有可重建来源时检查最近 Snapshot，并 Restore 到临时索引或临时集群后校验。
5. 恢复后验证 `_cat/shards`、cluster health、关键查询、写入成功率、index freshness 和延迟。最后复盘容量、水位、repository、Snapshot 成功率、告警阈值和恢复演练缺口。

总结句：red 的处理不是直接 reroute，而是先判断 primary 为什么不可用，再选择找回节点、释放空间、修正规则、Restore 或从事实源重建。

### Q：你怎么设计 ES 搜索服务 SLO？

我会先按业务功能拆 SLO，而不是给整个 ES 集群一个笼统可用性数字。因为 ES 可能只是搜索读模型，不同功能的 source of truth、RPO、RTO 和降级方式不同。

- **可用性**：定义 search availability，比如核心商品搜索成功率、订单检索成功率、写入链路成功率。按核心业务、租户和接口分层，避免平均值掩盖核心业务故障。
- **延迟**：定义 P95/P99 latency，把前台搜索、后台管理、日志查询、导出任务分开。大查询可以异步或离线，不应该和用户前台搜索共享同一延迟目标。
- **新鲜度**：定义 index freshness，从主库或事件进入同步链路开始，到 ES 可搜索结果出现为止。商品、订单、日志的新鲜度承诺不同，要分别设告警。
- **正确性边界**：明确 ES 不是强一致事实源，强一致读回源主库；ES 负责召回和搜索体验，数据不一致时通过补数、重放、幂等和校验修复。
- **降级策略**：包括缓存热门结果、限制时间窗、关闭大聚合、后台查询异步化、精确 ID 回源、临时只读、限流低优先级租户。
- **恢复演练**：定期演练 Snapshot Restore、repository _verify、reindex、alias 切换、节点故障、磁盘 flood-stage、unassigned shard runbook，并用实际耗时修正 RPO/RTO。

面试最后可以补一句：我不会只看 green/yellow/red，而是把可用性、延迟、新鲜度、rejected、JVM memory pressure、disk watermark、unassigned shards、snapshot success 和 sync lag 放进同一套告警和 runbook，保证事故时知道先保护业务还是先恢复数据。
