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
