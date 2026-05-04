# 12.4 资深性能诊断 Playbook

> **轨道**：A core / B prerequisite
>
> **目标**：把性能调优从“列优化项”提升到“按症状、证据、机制、风险、修复、验证”系统排查。

资深工程师排查 ES 性能问题，重点不是背优化清单，而是把一个线上症状拆成可验证的瓶颈层：query、fetch、aggregation、coordination、indexing、merge、GC、storage、network、cluster state。每一步都要能回答“证据是什么、这个证据指向什么机制、现在改什么风险最小、改完怎么证明有效”。

这份 Playbook 的默认立场是：先保护业务，再定位机制，最后固化治理。不要一看到慢查询就加 shard、调线程池、关 cache、加 heap 或升配置；这些动作都可能把原问题放大，尤其是在 fan-out、mapping explosion、bucket explosion 或 hot shard 没被识别时。

## 诊断总原则

先把问题分层，再谈优化。排查时至少回答这几个问题：

- 范围：是单索引、单租户、单查询模板、单节点、单 shard、单时间窗口，还是全局变慢。
- 链路：慢在 query、fetch、aggregation、coordination、write、refresh、merge、GC、IO、network、cluster state 哪一层。
- 证据：来自 `_nodes/stats`、`_cat/thread_pool`、slow log、profile API、tasks API、hot threads、GC/heap、circuit breakers、业务 P95/P99 和客户端错误。
- 机制：是倒排扫描太宽、Doc Values 聚合太重、`_source` 太大、coordinating reduce 太重、bulk 并发过高、merge backlog、routing 倾斜、mapping explosion，还是存储 IO 不足。
- 风险：当前最可能影响的是查询延迟、写入成功率、节点稳定性、heap、磁盘水位、恢复速度，还是控制面。
- 修复：短期先限流、降级、缩小查询范围、暂停后台任务或扩容；长期再改 mapping、索引模型、routing、生命周期、查询模板和容量模型。
- 验证：修复后看 P95/P99、rejected、queue、heap、GC、CPU、IO wait、merge、breaker、slow log 数量、业务错误率和新鲜度是否恢复。

一条可靠的排查路径：

```text
业务症状
-> 影响范围
-> ES 指标和日志证据
-> 定位瓶颈层
-> 临时止血
-> 根因修复
-> 指标验证
-> Runbook/Guardrail 固化
```

常用信号和用途：

| 信号 | 看什么 | 主要用于判断 |
| --- | --- | --- |
| `_nodes/stats` | `jvm`、`indices.search`、`indices.indexing`、`indices.segments`、`indices.merge`、`fs`、`thread_pool`、`breaker` | CPU/heap/GC、查询和写入耗时、segment/merge、磁盘 IO、breaker |
| `_cat/thread_pool` | `active`、`queue`、`rejected`、`completed`，重点看 `search`、`write`、`get`、`management` | search/write 是否过载，是否存在 rejected requests 和队列堆积 |
| slow log | 哪些 query/fetch/index 慢、慢在哪些索引、是否集中在租户或模板 | 识别慢查询、慢 fetch、大 `_source`、写入慢 |
| profile API | Query phase 内部耗时，collector、rewrite、scorer、aggregation 子阶段 | 分辨倒排查询、filter、script、aggregation 是否昂贵 |
| tasks API | `_tasks?detailed=true`、`_tasks/<task_id>`、长时间运行的 reindex/update_by_query/snapshot/search | 识别后台长任务、堆积任务、取消低优先级任务 |
| hot threads | `GET _nodes/hot_threads` 输出中 CPU 密集线程栈 | 识别 expensive query、script、merge、GC、pipeline 或 Lucene collector |
| GC/heap | old gen、JVM memory pressure、GC 次数和耗时、allocation rate | 判断 heap 是否被聚合、fielddata、mapping、shard、cache 或 fetch 压垮 |
| circuit breakers | `_nodes/stats/breaker` 的 estimated、limit、tripped | 判断 request、fielddata、parent breaker 是否被查询或聚合触发 |

调优原则：

- 先收证据，再改配置；没有证据时只做低风险止血。
- 每次只改一个主要变量，否则无法判断效果。
- 先区分读过载、写过载、后台任务过载和资源故障，避免错误扩散。
- 不把线程池队列调大当根因修复。队列变大通常只会让延迟更高、失败更晚。
- 不把加 heap 当万能方案。heap 过大可能增加 GC 停顿，heap 压力的根因常是 shard、segment、mapping、fielddata 或聚合。
- 不把扩节点当唯一答案。扩容能缓解资源不足，但不能修复错误 routing、无边界聚合、深分页、动态字段爆炸和不合理索引模型。
- 修复后必须用 P95/P99、rejected、queue、heap、CPU、IO、业务指标验证，而不是只看集群 green。

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

使用这个模板时，不要把 `fix options` 写成“调参”。先写清楚证据和机制，例如“search queue 上升 + hot threads 显示 aggregation collector + profile API 显示 terms aggregation 高基数”，再讨论限制 bucket、改 mapping、预聚合、拆查询或转 OLAP。

## High CPU

### symptom

节点 CPU 长时间高位，查询 P95/P99 上升，search/write queue 增长，hot node 或 hot shard 明显，业务侧开始出现 timeout。可能是单节点高，也可能是全体 data node 或 coordinating node 高。

### first evidence

- `_nodes/stats?human&filter_path=nodes.*.name,nodes.*.os.cpu,nodes.*.process.cpu,nodes.*.thread_pool,nodes.*.indices.search,nodes.*.indices.indexing,nodes.*.indices.merge`
- `_cat/thread_pool/search,write?v&h=node_name,name,active,queue,rejected,completed`
- `GET _nodes/hot_threads`，看 CPU 热点栈是 search、write、merge、script、aggregation、highlight、ingest pipeline 还是 GC。
- slow log 判断是否有 expensive query、宽时间范围查询、深分页、高亮、script、nested、wildcard/regexp、无选择性 filter。
- profile API 对典型慢查询加 `"profile": true`，确认 query、collector、aggregation 哪一段耗时。
- `_cat/shards` 或 `_nodes/stats` 对比各节点 search/indexing/merge 指标，确认是否 hot shard 或 routing 倾斜。

### likely mechanism

- expensive query：低选择性过滤、宽时间范围、`wildcard`/`regexp`、复杂 bool、script query、nested、parent-child、向量召回或高成本排序。
- aggregation：高基数字段、bucket 数过大、多层聚合、pipeline aggregation、宽时间范围聚合。
- highlight：大文本字段、高亮大量命中文档、返回字段过多。
- merge：高写入、refresh 太频繁、bulk 太碎、更新/删除太多，后台 merge 抢 CPU 和 IO。
- ingest pipeline：grok、正则、script、enrich、geoip、复杂字段清洗抢 CPU。
- hot shard：routing 倾斜、大租户、热点时间窗口或单 primary 承载过多读写。
- coordination：查询打到大量 shard，coordinating node 做 TopN merge 或 aggregation reduce 消耗 CPU。

### risk

CPU 高本身不是根因，但会触发连锁反应：search rejected、write rejected、客户端重试风暴、GC 抖动、merge backlog、index freshness 下降。若高 CPU 集中在 master-eligible 节点，还可能影响 cluster state 更新和 allocation。

### fix options

短期止血：

- 对高成本查询限流、降低并发、缩小默认时间范围、关闭或降级高亮和大聚合。
- 暂停或错峰 reindex、update_by_query、delete_by_query、force merge、snapshot、历史导出。
- 对批量写入降低 bulk 并发，增大合理 bulk 批量，避免小请求风暴。
- 对 ingest pipeline 峰值临时扩 ingest 节点或把重解析移到上游/低峰。
- 对 hot shard 的大租户临时拆入口、限流或迁移到独立索引/节点池。

长期修复：

- 改查询模板：强制时间窗和租户过滤，禁用危险查询模式，替换低选择性 wildcard/regexp，治理深分页。
- 改 mapping：为过滤、排序、聚合字段使用合适的 keyword/numeric/date + Doc Values；避免对 text 字段做聚合和排序。
- 改索引模型：用 routing 降低 fan-out，给大租户独立索引，日志类用 rollover 控制 shard size。
- 改平台治理：查询成本预算、租户配额、慢查询采样、shadow query、A/B 发布和查询模板评审。
- 改资源隔离：dedicated ingest、coordinating-only node、hot/warm 分层、后台任务低峰窗口。

### verification

CPU 降低只是第一层验证，还要看 P95/P99、search/write rejected、thread pool queue、hot threads、slow log 条数、merge time、业务 timeout、index freshness 和客户端重试量是否同步恢复。

### interview wording

“High CPU 我不会直接说加机器。先用 hot threads 和 `_nodes/stats` 判断 CPU 花在 query、aggregation、merge、ingest 还是 coordination；再用 slow log 和 profile API 证明是哪类查询或任务。短期先限流和降级高成本入口，长期才改 query、mapping、routing、索引模型和资源隔离。”

## High JVM Memory Pressure

### symptom

JVM memory pressure 高，old gen 长时间高位，GC 频繁或停顿变长，查询延迟抖动，breaker 触发，节点可能被 OOM killer 或长 GC 拖离集群。

### first evidence

- `_nodes/stats?filter_path=nodes.*.name,nodes.*.jvm.mem.pools.old,nodes.*.jvm.gc,nodes.*.breakers,nodes.*.indices.segments,nodes.*.indices.fielddata,nodes.*.indices.query_cache,nodes.*.indices.request_cache`
- GC 日志或监控看 old GC 次数、耗时、allocation rate 和 stop-the-world 停顿。
- `_nodes/stats/breaker` 看 request、fielddata、in_flight_requests、parent breaker 的 estimated、limit、tripped。
- slow log 和 profile API 找大聚合、script、fetch 大字段、返回大量 hits 的查询。
- mapping 和 field count，判断是否 mapping explosion、too many shards、too many segments。

### likely mechanism

- Fielddata：对 text 字段排序、聚合或 script 访问，导致 fielddata 加载到 heap。
- bucket explosion：高基数 `terms`、多层聚合、宽时间范围、大 `size`，request breaker 或 parent breaker 承压。
- query cache/request cache：缓存竞争、低命中高淘汰，或者缓存了大量代价高但复用少的结果。
- too many shards：每个 shard/segment/mapping 都有元数据成本，oversharding 推高 heap。
- mapping explosion：动态字段、无边界 JSON key、日志 label/tag 爆炸，cluster state 和 segment metadata 增长。
- large fetch：`_source` 大、返回字段多、高亮大字段、一次返回 hits 太多，fetch phase 占用 heap 和网络。
- 大量 scroll/search_after/export：长时间上下文、批量导出和客户端慢消费占用资源。

### risk

heap 压力会先表现为延迟抖动和 breaker，随后可能出现 search rejected、节点离群、master 不稳定和 shard relocation。盲目增大 heap 可能减少 page cache 并加重 GC 停顿。

### fix options

短期止血：

- 降低大聚合并发，限制 `size`、bucket 数、时间范围和返回字段。
- 禁止对 text 字段临时聚合/排序，关闭危险查询模板或降级到近似结果。
- 对导出、报表、宽时间范围查询转异步或低峰执行。
- 暂停 mapping 失控写入源，阻断动态字段继续增长。
- 如 breaker 频繁触发，先降低请求复杂度和并发，不把 breaker limit 调大当首选。

长期修复：

- 用 keyword/numeric/date + Doc Values 支撑聚合和排序，避免 fielddata。
- 治理动态字段：`dynamic_templates`、字段白名单、`flattened`、日志 key 归一化、字段准入流程。
- 控制 shard 和 index 数，合并小索引，用 rollover 让 shard size 稳定。
- 建立聚合 guardrail：`search.max_buckets`、查询成本预算、租户配额、预聚合或 OLAP 分流。
- 精简 `_source` 返回，使用 source filtering、stored fields 或业务侧详情回源。

### verification

看 old gen 是否下降并稳定、GC 耗时是否减少、breaker tripped 是否停止增长、request latency 是否恢复、rejected 是否消失、fielddata/segments/mapping 指标是否停止膨胀。

### interview wording

“JVM pressure 我会先分清是 fielddata、聚合 bucket、shard/segment metadata、mapping explosion、cache 还是 fetch 大字段。证据来自 `_nodes/stats` 的 jvm、segments、fielddata、cache、breaker 和 GC 日志。修复不是先加 heap，而是减少 heap 上的错误对象和无边界请求。”

## Rejected Requests

### symptom

客户端收到 429 或 rejected execution，查询或写入失败率上升，重试后延迟更差。`search` 或 `write` thread pool 的 rejected 持续增长。

### first evidence

- `_cat/thread_pool/search,write,get?v&h=node_name,name,active,queue,rejected,completed`
- `_nodes/stats?filter_path=nodes.*.name,nodes.*.thread_pool.search,nodes.*.thread_pool.write,nodes.*.indices.search,nodes.*.indices.indexing,nodes.*.jvm,nodes.*.fs`
- 客户端日志看 429、timeout、retry 次数和重试间隔。
- slow log 判断是否少量慢请求占满线程池。
- hot threads 判断线程池在执行 query、aggregation、fetch、bulk indexing、pipeline、merge 还是等待 IO。

### likely mechanism

- search thread pool queue 满：高并发查询、慢查询、聚合、高亮、深分页、跨大量 shard fan-out。
- write thread pool queue 满：bulk 并发过高、小 bulk 太多、单文档写入风暴、pipeline 重、refresh/merge 跟不上。
- 协调节点压力：coordinating node 接收大量请求、等待 shard 响应、TopN merge 或 reduce 占资源。
- 下游重试风暴：客户端无退避重试，少量 429 放大成更多请求。
- hot shard 或 hot node：全局流量不高，但局部节点 queue 和 rejected 高。

### risk

rejected 是保护信号，不是单纯错误。把 thread pool queue 调大可能让请求排队更久，增加超时、堆积和重试风暴。要先降低进入系统的无效负载。

### fix options

短期止血：

- 客户端做指数退避、jitter 和最大重试次数，停止同步重试风暴。
- 降低 bulk 并发，合并过小 bulk，给低优先级写入限流。
- 对高成本查询按租户、接口、query template 限流，关闭大聚合、导出和深分页。
- 暂停 reindex/update_by_query/delete_by_query 等后台任务或转低峰。
- 如果是协调节点瓶颈，临时增加 coordinating-only node 或分流入口。

长期修复：

- 建立查询和写入配额：QPS、并发、timeout、最大时间范围、最大 bucket、最大结果窗口、bulk 大小。
- 调整索引模型和 routing，减少 fan-out 和 hot shard。
- 对写入链路拆 ingest/data，优化 pipeline，把复杂清洗前移。
- 为不同业务入口拆优先级，核心搜索和后台报表不要共享无边界入口。
- 用压测确定可承载并发，不把默认线程池当容量规划。

### verification

`_cat/thread_pool` 中 queue 回落、rejected 不再增长；客户端 429 和 retry 下降；P95/P99、写入成功率、indexing latency、search latency 恢复；业务端吞吐没有被重试虚高掩盖。

### interview wording

“rejected 说明线程池在保护节点。我会先看是 search 还是 write rejected，再看是全局过载还是 hot node。短期先限流和修客户端退避，长期改 query、bulk、routing、资源隔离和平台配额，而不是先把队列调大。”

## Task Queue Backlog

### symptom

集群状态更新慢，索引创建/删除/mapping 更新/ILM/shard allocation 延迟，pending tasks 堆积，master 日志出现 cluster state update 慢或 publication 慢。

### first evidence

- `_cluster/pending_tasks` 看任务来源、插入时间、优先级和等待时长。
- `_tasks?detailed=true&actions=*reindex,*update_by_query,*delete_by_query,*snapshot,*search,*cluster*` 看长任务。
- `_nodes/stats?filter_path=nodes.*.name,nodes.*.jvm,nodes.*.process.cpu,nodes.*.thread_pool.management,nodes.*.indices.mappings,nodes.*.indices.shards`
- master 节点日志看 cluster state publication、mapping update、allocation、snapshot、ILM 相关慢日志。
- mapping 字段数、index 数、shard 数、模板变更频率。

### likely mechanism

- cluster state 更新过多：频繁创建/删除索引、频繁 rollover、小索引过多、模板频繁变更。
- mapping 爆炸：动态字段持续进入 mapping，每次字段新增都要更新 cluster state。
- shard allocation 堆积：节点丢失、磁盘水位、tier 不匹配、恢复和 relocation 并发。
- snapshot 或 restore：大量 shard 元数据、仓库延迟、恢复任务占用调度。
- long-running tasks：reindex、update_by_query、delete_by_query、transform、长时间 search 或 scroll。
- master 资源不足：dedicated master CPU/heap/磁盘/网络压力，或 master 同时承载重查询和写入。

### risk

Task queue backlog 影响的是控制面。它可能不立刻让查询失败，但会让 mapping 更新、索引创建、allocation、ILM、快照和恢复变慢。控制面被拖住时，盲目继续创建索引或动态字段会放大事故。

### fix options

短期止血：

- 暂停批量建索引、动态字段写入源、reindex/update_by_query/delete_by_query、低优先级 snapshot/restore。
- 降低 rollover 或批量导入频率，避免继续制造小索引和 mapping update。
- 对长任务评估取消：`POST _tasks/<task_id>/_cancel`，只取消可重试、低优先级任务。
- 如果 allocation 因磁盘或 tier 约束卡住，先修水位和节点角色，不要反复 reroute。

长期修复：

- 控制索引和 shard 数，日志类用 data stream + 合理 rollover，避免每租户每天一堆小索引。
- 动态字段治理：模板、字段白名单、`flattened`、字段准入和异常 key 阻断。
- dedicated master 保持轻负载，不承载 data、ingest 和重查询。
- 建立后台任务窗口和并发控制，snapshot/reindex/force merge 避开高峰。
- 对 cluster state size、pending tasks 等控制面指标建告警。

### verification

`_cluster/pending_tasks` 清空或等待时长下降；mapping update 和 index creation 恢复；allocation 收敛；master CPU/heap/GC 稳定；业务写入不再触发持续 cluster state update。

### interview wording

“Task queue backlog 我会当控制面问题处理。先看 pending tasks 和 tasks API，判断是 cluster state、mapping、allocation、snapshot 还是长任务。止血是暂停继续制造控制面变更，根因是减少小索引、动态字段、无窗口后台任务和 master 资源竞争。”

## Circuit Breaker Trips

### symptom

查询或写入返回 circuit_breaking_exception，聚合、排序、script、fetch 或 bulk 请求失败，breaker tripped 计数增长。

### first evidence

- `_nodes/stats/breaker` 看 request、fielddata、in_flight_requests、parent breaker 的 estimated、limit、tripped。
- `_nodes/stats?filter_path=nodes.*.name,nodes.*.jvm.mem,nodes.*.indices.fielddata,nodes.*.indices.segments,nodes.*.thread_pool.search`
- slow log 和 profile API 找触发 breaker 的查询模板。
- 客户端错误日志记录 index、tenant、query template、请求体大小、返回字段和聚合参数。

### likely mechanism

- request breaker：大聚合、bucket 数过多、高基数字段、多层 reduce、宽时间范围。
- fielddata breaker：对 text 字段做聚合、排序或 script 访问。
- parent breaker：多个请求并发叠加，heap 总压力过高。
- in_flight_requests：请求体或响应体过大，bulk 太大，返回 hits 太多。
- fetch 太大：大 `_source`、高亮字段、返回字段无边界。
- 查询并发过高：单个请求可承受，但并发后总估算超过限制。

### risk

breaker 是保护机制。直接调高 breaker limit 可能把可控异常变成长 GC 或 OOM。必须先证明估算过于保守或硬件确实能承受，否则优先降低请求成本。

### fix options

短期止血：

- 降低聚合 size、层数和时间范围，限制高基数字段聚合。
- 精简返回字段和 `_source`，关闭大字段高亮。
- 降低并发，给租户和报表入口限流。
- 停止对 text 字段排序/聚合，临时禁用触发 fielddata 的查询。
- 对 bulk 请求控制单批大小，避免 in_flight_requests 过大。

长期修复：

- 改 mapping：聚合/排序字段用 keyword/numeric/date + Doc Values；避免 fielddata。
- 建立 query guardrail：最大 bucket、最大时间窗、最大返回字段、最大结果数、租户并发上限。
- 对高成本聚合做预聚合、缓存、异步任务或迁移到 OLAP。
- 对大结果详情回源，不在搜索请求里返回大 `_source`。
- 只有在有压测证据和容量余量时，才调整 breaker 相关配置。

### verification

breaker tripped 不再增长，JVM old gen 和 GC 稳定，P95/P99 恢复，慢查询和高成本聚合下降，客户端 circuit_breaking_exception 消失。

### interview wording

“breaker trip 不是简单把阈值调大。我要先看是 request、fielddata、parent 还是 in-flight breaker，再回到具体查询和并发。多数情况下修的是聚合规模、字段类型、返回字段、查询并发和平台 guardrail。”

## Mapping Explosion

### symptom

字段数持续增长，mapping 更新频繁，cluster state 变大，master 压力上升，heap 变高，写入变慢，查询和 Kibana/管理接口变慢。日志类索引尤其常见。

### first evidence

- index mapping 字段数、动态字段新增速率、`index.mapping.total_fields.limit` 是否接近或触发。
- `_cluster/pending_tasks` 是否有 mapping update 堆积。
- `_nodes/stats?filter_path=nodes.*.name,nodes.*.jvm,nodes.*.indices.mappings,nodes.*.indices.segments`
- master 日志是否出现 mapping update、cluster state publication 慢。
- 采样文档看是否存在无边界 key：用户 ID、trace label、HTTP header、JSON 动态属性、业务自定义 tag。

### likely mechanism

- 动态字段打开，日志或业务 JSON 中无边界 key 被自动映射为字段。
- 每个租户、用户、版本、label 都生成字段，导致 mapping explosion。
- 多层 object/nested 结构把字段数量放大。
- 索引模板缺少 dynamic_templates 或字段白名单。
- 上游日志格式变化没有准入，错误 payload 被直接写入 ES。

### risk

Mapping explosion 不只是某个索引字段多。它会推高 cluster state、master heap、segment metadata、查询字段解析成本和写入 mapping update 成本。继续写入动态字段会让控制面持续恶化。

### fix options

短期止血：

- 阻断异常写入源或将动态字段写入隔离索引。
- 临时关闭不受控路径的 dynamic，或把无边界对象改成单字段承接。
- 提高字段限制只能作为短期缓冲，不能当修复。
- 暂停造成大量 mapping update 的导入任务。

长期修复：

- 对日志无边界 key 使用 `flattened`，或将 labels/tags 作为键值数组而不是字段爆炸。
- 用 `dynamic_templates`、字段白名单、字段命名规范和 schema registry 治理字段。
- 按业务域拆模板，字段变更走评审和发布流程。
- 对租户自定义字段做数量上限、类型约束和索引策略。
- 老索引通过 reindex 或生命周期淘汰，不在热路径继续扩散。

### verification

字段数增长停止，mapping update pending tasks 消失，master heap/GC 稳定，写入延迟下降，cluster state publication 恢复，新增异常字段被上游或模板拦截。

### interview wording

“mapping explosion 的根因通常是动态字段和无边界 key。我的止血动作是先阻断字段继续增长，长期用 flattened、dynamic_templates、字段准入和模板治理。只提高 total fields limit 是拖延，不是治理。”

## Hot Spotting

### symptom

某些节点 CPU、heap、IO、search/write queue 明显高于其他节点；某些 shard 查询或写入远高于同索引其他 shard。全局资源看似够，但局部节点出现 rejected 和长尾延迟。

### first evidence

- `_cat/thread_pool/search,write?v&h=node_name,name,active,queue,rejected,completed` 对比节点差异。
- `_nodes/stats?human&filter_path=nodes.*.name,nodes.*.indices.search,nodes.*.indices.indexing,nodes.*.indices.merge,nodes.*.fs,nodes.*.jvm,nodes.*.os.cpu`
- `_cat/shards?v&h=index,shard,prirep,state,docs,store,node` 结合业务流量判断单 shard 是否过载。
- slow log 按 tenant、routing key、index、时间窗口聚合。
- hot threads 看热点节点是否在同类查询、写入、merge 或 pipeline。

### likely mechanism

- routing 倾斜：大租户、大用户、大商家或热点 key 被路由到同一 shard。
- 大租户和小租户混在同一 shared index，大租户吞掉单 shard 资源。
- 热点时间窗口：日志/指标当前写入只打少数 hot shard。
- 单 shard 过载：primary 数太少或 shard size/文档数过大。
- 写入热点：bulk 请求集中到单索引、单 routing key、单 data node。
- 查询热点：Dashboard、榜单、热门关键词或缓存击穿集中打某些 shard。

### risk

Hot spotting 会让平均指标失真。集群平均 CPU 50% 不代表没有节点已经拒绝请求。错误地全局扩容可能缓解但不根治 routing 倾斜和大租户问题。

### fix options

短期止血：

- 对热点租户、热点查询、热点写入源限流或熔断。
- 分流查询入口，暂停宽时间范围 Dashboard 和后台导出。
- 对大租户临时独立索引或迁移到独立节点池需要谨慎评估，优先先降载。
- 如 shard 分布不均，先查 allocation 约束和磁盘水位，再决定 relocation。

长期修复：

- 多租户使用 shared index + routing 时，识别大租户并迁移到独立索引或专属 shard 策略。
- 重新设计 routing key，避免业务天然倾斜；必要时给超大 key 做拆分路由。
- 日志/时间序列用 rollover 和足够 primary 承接热写入，控制单 shard 热度。
- 建租户级指标：QPS、写入量、latency、rejected、CPU/heap 归因、字段数。
- 对热门查询做缓存、预计算或异步刷新。

### verification

节点间 CPU/heap/IO/thread pool queue 差异收敛，热点 shard 的 search/indexing 指标下降，rejected 停止增长，租户级 P95/P99 恢复。

### interview wording

“Hot spotting 要看局部，不看平均。我会按 node、shard、tenant、routing key 分解 `_nodes/stats`、thread pool 和 slow log。短期先保护热点入口，长期改 routing、大租户隔离、rollover 和租户级配额。”

## Segment And Merge Backlog

### symptom

写入延迟上升，查询长尾变差，磁盘 IO wait 高，segment 数量增长，merge time 或 merge throttle 增加，index freshness 变差。更新和删除多的索引更明显。

### first evidence

- `_nodes/stats?human&filter_path=nodes.*.name,nodes.*.indices.segments,nodes.*.indices.merge,nodes.*.indices.refresh,nodes.*.indices.indexing,nodes.*.fs,nodes.*.thread_pool.write`
- hot threads 看是否 merge 线程占 CPU。
- OS/云监控看磁盘 IOPS、吞吐、IO wait、队列深度。
- slow log 看 index slow log 和 search slow log 是否同时出现。
- 业务写入侧看 bulk 大小、bulk 并发、更新/删除比例、refresh interval。

### likely mechanism

- refresh 太频繁，小 segment 过多，后续 merge 压力增加。
- bulk 太碎，请求数过多，写入吞吐低且 segment 生成频繁。
- 更新/删除太多，deleted docs 增加，merge 必须清理旧版本。
- IO 不足，hot tier 磁盘无法同时承载写入、refresh、merge、查询和 snapshot。
- merge throttling 生效，写入被保护性放慢。
- force merge 在高峰执行，和在线查询/写入抢 IO。

### risk

merge backlog 是写入链路和存储层问题，但会反过来影响查询。只增加写入并发会制造更多 segment 和 merge；只调 refresh 也可能牺牲业务新鲜度。

### fix options

短期止血：

- 降低 bulk 并发，合并过小 bulk，暂停低优先级回灌、reindex、update_by_query。
- 临时放宽 refresh interval，但要确认业务能接受搜索新鲜度下降。
- 暂停高峰期 force merge、snapshot、历史导出和大范围查询。
- 对写入热点索引限流，保护核心查询。

长期修复：

- 为 hot tier 提供足够 SSD/IOPS、CPU、page cache 和磁盘空闲。
- 调整写入模式：合理 bulk size、幂等批处理、减少无效 update、避免频繁 delete。
- 用 rollover 控制 shard size 和写入窗口，避免单 shard 长期承压。
- force merge 只放在写入停止后的 warm/cold 阶段和低峰窗口。
- 对高更新业务重新评估是否适合 ES，或是否需要事件合并、延迟写入和主库回源。

### verification

segments 数量趋稳，merge backlog 和 throttle 降低，磁盘 IO wait 下降，write queue/rejected 恢复，index freshness 追平，查询 P99 回落。

### interview wording

“Segment 和 merge backlog 我会当写入与存储层瓶颈看。证据是 `_nodes/stats` 的 segments、merge、refresh、indexing 加磁盘 IO。短期降写入和后台任务，长期改 bulk、refresh、rollover、更新模式和 hot tier IO 能力。”

## Query/Fetch/Aggregation/Coordination Isolation

线上查询慢时，必须把 search request 拆成 query、fetch、aggregation、coordination 四个阶段，再和 indexing/storage 分开判断。否则容易把所有慢都归因于“ES 查询慢”。

### query 慢

证据：

- slow log 中 query phase 慢，fetch 不明显。
- profile API 显示某些 query、filter、rewrite、scorer、collector 耗时高。
- `_nodes/stats` 的 search query time 上升，CPU 高，hot threads 出现 Lucene search/scorer/collector。
- 查询 fan-out 很大，命中大量 shard 或宽时间范围索引。

常见原因：

- 倒排索引扫描范围大，filter 选择性差。
- wildcard/regexp/prefix 使用不当，script query、nested、parent-child、向量查询昂贵。
- bool 条件复杂，排序字段不合适，索引没有按业务过滤边界设计。
- 一次查询打到太多 index/shard。

处理：

- 短期限制时间范围、租户范围、危险查询模式和并发。
- 长期改 query template、mapping、routing、索引拆分、搜索入口 guardrail。

### fetch 慢

证据：

- slow log 中 fetch phase 慢。
- query 命中不慢，但返回大 `_source`、大字段、高亮或大量 hits 后延迟上升。
- `_nodes/stats` search fetch time 上升，网络出流量和 heap 压力变高。

常见原因：

- `_source` 大，返回字段无过滤。
- 高亮大文本字段，尤其是返回大量结果时。
- 深分页或一次取太多 hits。
- stored fields/docvalue_fields/source filtering 没有按业务设计。

处理：

- 短期减少 `size`、关闭高亮、只返回必要字段、详情回源。
- 长期拆搜索摘要和详情字段，设计 source filtering，限制分页和导出。

### aggregation 慢

证据：

- profile API 显示 aggregations 耗时高。
- request breaker 或 parent breaker 接近上限或 tripped。
- JVM old gen、GC、search queue 上升；slow log 集中在报表/Dashboard 查询。
- 聚合字段高基数、时间范围宽、bucket 数巨大。

常见原因：

- 高基数 `terms` 聚合、多层 bucket、过大的 `size`。
- 对 text 字段触发 Fielddata。
- 宽时间范围和多 shard fan-out 导致 reduce 成本高。
- 把在线搜索集群当 OLAP 使用。

处理：

- 短期限制 bucket、时间范围、并发，关闭低优先级 Dashboard。
- 长期用 keyword/numeric/date + Doc Values、预聚合、rollup/transform/OLAP、异步报表和 `search.max_buckets` guardrail。

### coordination 慢

证据：

- data node shard 查询时间不高，但 coordinating node CPU/heap 高。
- 查询跨大量 index/shard，TopN merge、aggregation reduce、排序合并耗时。
- `_cat/thread_pool` 中协调入口节点 search queue/rejected 高。
- 客户端等待时间明显大于 shard 执行时间。

常见原因：

- oversharding 或查询索引范围太宽。
- coordinating-only node 资源不足，或者业务网关把全部重查询打到少数入口。
- 大结果集、深分页、大聚合 reduce。
- 跨集群/跨网络查询，network 和序列化开销高。

处理：

- 短期缩小索引范围、降低 size 和聚合复杂度，分流入口。
- 长期控制 shard 数，按时间/租户 routing，增加或隔离 coordinating-only node，建立查询成本预算。

### indexing 慢

证据：

- `_nodes/stats` 的 indexing time、indexing pressure、write queue/rejected 上升。
- index slow log 变多，bulk 客户端延迟上升。
- hot threads 指向 write、pipeline、merge，或磁盘 IO wait 高。
- refresh、merge、translog、pipeline 指标异常。

常见原因：

- bulk 并发过高或太碎。
- ingest pipeline 重，script/grok/enrich 抢 CPU。
- refresh interval 太短，更新/删除太多。
- replica 过多，单 shard 写入热点，磁盘 IO 不足。

处理：

- 短期限流写入、调整 bulk 并发和批量、放宽 refresh、暂停回灌。
- 长期优化 pipeline、rollover、routing、hot tier IO、写入缓冲和同步链路。

### storage 慢

证据：

- `_nodes/stats` 的 fs、merge、refresh、segments 指标异常。
- OS/云监控显示 IO wait、磁盘队列、吞吐或 IOPS 达上限。
- 查询和写入都慢，merge/snapshot/recovery/relocation 同时运行。
- 磁盘水位接近 high 或 flood-stage。

常见原因：

- hot tier IO 不足，merge、query、snapshot、recovery 抢同一块盘。
- shard 太大恢复慢，segment 太多，force merge 高峰执行。
- 查询读取大量 doc values/source，page cache 命中低。
- 存储类型和业务 SLO 不匹配。

处理：

- 短期暂停 snapshot/force merge/reindex/导出，限流写入和宽查询。
- 长期升级 hot tier 存储、冷热分层、调整生命周期、减少 segment 压力、明确历史查询 SLA。

### 面试中的隔离表达

可以这样说：

“我会先用 slow log 判断 query phase 还是 fetch phase 慢；用 profile API 细分 query 和 aggregation；用 `_nodes/stats` 看 search、indexing、segments、merge、fs、jvm、breaker；用 `_cat/thread_pool` 看 search/write queue 和 rejected；用 tasks API 找长任务；用 hot threads 判断 CPU 栈。这样才能把 query/fetch/aggregation/coordination/indexing/storage 分开，而不是把所有问题都叫查询慢。”

## 面试回答模板

### Q：线上 ES 查询突然变慢怎么排查？

我会按证据链排查，不会直接改 shard、线程池或 heap。

1. 先确认范围：单索引、单租户、单查询模板、单节点、单 shard、某个时间窗口，还是全局变慢；同时看业务 P95/P99、错误率、timeout、重试量和是否有发布/回灌/流量突增。
2. 区分 query/fetch/aggregation/coordination：slow log 先看 query phase 还是 fetch phase；profile API 看倒排查询、collector 和 aggregation；看是否跨大量 shard，coordinating node 是否在 reduce、TopN merge 或大结果集上耗时。
3. 看系统证据：`_nodes/stats` 看 search、indexing、segments、merge、fs、jvm、breaker；`_cat/thread_pool` 看 search/write queue 和 rejected；tasks API 看 reindex、update_by_query、snapshot、long-running search；hot threads 看 CPU 栈；GC/heap 看 JVM memory pressure；circuit breakers 看是否有 request、fielddata、parent breaker。
4. 根据证据改动作：如果是 query 代价高，改查询模板、过滤边界、routing 和索引范围；如果是 fetch 慢，减少 `_source`、高亮和返回 hits；如果是 aggregation 慢，限制 bucket、改字段类型、做预聚合或转 OLAP；如果是 coordination 慢，减少 fan-out、控制 shard 数或拆 coordinating-only node；如果是 indexing/merge/storage 慢，调 bulk、refresh、pipeline、rollover、hot tier IO 和后台任务窗口。
5. 先做低风险止血：限流高成本租户、缩小时间窗、暂停后台任务、降低 bulk 并发、关闭大聚合/导出/高亮，必要时扩容或分流入口。
6. 最后验证：看 P95/P99、slow log 数量、profile 耗时、search/write rejected、queue、CPU、heap、GC、breaker、IO wait、merge backlog、业务错误率和新鲜度是否恢复。

总结句：

“资深排查的关键是把慢拆到具体阶段，并用指标证明。没有证据前不做魔法调参；有证据后短期先保护业务，长期再修 query、mapping、routing、索引模型、资源隔离和平台 guardrail。”
