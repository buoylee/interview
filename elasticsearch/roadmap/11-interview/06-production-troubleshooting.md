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
- 深分页改成 search_after；需要稳定分页视图时用 PIT + search_after，PIT 本身不是 search_after 的替代。
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
- 写多读少或可重建索引的受控回填场景，临时降低 replica，导入完成后恢复；这会降低节点故障时的副本冗余和 HA，不能作为常规线上优化。
- 优化 shard 数和 routing，避免热点。
- 扩容 data 节点或提升磁盘能力。
- 上游同步增加幂等和重试，避免乱序覆盖。

### 验证方式

观察写入 TPS、bulk latency、rejected 数、refresh/merge 时间、数据同步 lag 和业务可见延迟。

### 面试表达

我会把写入慢拆成客户端、ES 写入链路、磁盘和上游同步四层。先看 rejected、merge、refresh、IO 和 shard 分布，再决定是调 bulk、refresh_interval，还是处理热点 shard 和上游 lag。降低 replica 只适合受控回填、可重建索引或临时容量兜底，因为它会牺牲副本冗余和高可用。

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
_nodes/stats/jvm,indices/fielddata,query_cache,request_cache
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
- 增加节点，或在确认索引可重建、业务可承受冗余下降时临时降低 replica 数；降低副本会削弱节点故障期间的 HA，不应替代容量修复。
- 释放磁盘空间或扩容磁盘。
- 修正 allocation filtering。
- red 且 primary 丢失时从 snapshot 恢复。

### 验证方式

确认 unassigned shard 归零或符合预期，cluster health 恢复 green/yellow，业务读写恢复；如果临时降低过 replica，还要确认副本数已按容量计划恢复。

### 面试表达

yellow 和 red 优先级不同。yellow 主要是副本不可用，先查分配原因；red 影响 primary，要优先恢复数据可用性。排查时我会用 allocation explain 找 ES 自己给出的不能分配原因。

## 场景 6：数据同步延迟或不一致

### 症状

MySQL 已更新，但 ES 搜索结果延迟或显示旧数据。

### 第一轮检查

- 区分 ES refresh 延迟和同步链路延迟，比如对比 `GET index/_doc/id` 和 `_search` 结果，必要时做一次受控 `_refresh` 验证。
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
GET index/_doc/id vs _search
_nodes/stats/indices/refresh
controlled POST index/_refresh check
MQ lag / CDC lag
```

### 修复选项

- 使用版本号或更新时间做幂等保护。
- 消费端失败进入重试和死信。
- 建立全量校对和修复任务。
- 调整 bulk 和 refresh 策略。
- 对强一致需求回源数据库确认。

### 验证方式

检查同步 lag、错单数、校对差异、重试成功率、ES 文档版本、refresh stats，以及手动 `_refresh` 前后 `_doc` 和 `_search` 是否一致。

### 面试表达

我会明确 ES 通常不是主库，而是搜索视图。先用 `GET index/_doc/id`、`_search`、refresh stats 或受控 `_refresh` 判断是 ES 近实时可见性问题，还是同步链路没有写到 ES。同步一致性的核心是最终一致、幂等、乱序保护、重试死信和定期校对。强一致读不能只依赖 ES。

## 本阶段总结

生产排查面试不要只说“看日志、看监控”。更好的回答是：

```text
先定位症状属于 query、fetch、write、merge、heap、shard、sync 哪一层；
再收集对应证据；
用 ES 的底层机制解释为什么会慢或失败；
给出不会扩大故障面的修复；
最后说明如何验证结果。
```
