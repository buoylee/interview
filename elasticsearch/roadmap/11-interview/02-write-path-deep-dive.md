# ES 写入链路原理追问

> **目标**：把写入、refresh、flush、translog、segment、merge 讲成一条连续链路。面试时不要只背名词，要能解释为什么 ES 是近实时、为什么更新不是原地修改、为什么写入调优会影响搜索可见性。

## Q1：为什么 Elasticsearch 是近实时搜索？

### 一句话答案

因为文档写入后先进入内存缓冲区并追加 translog，refresh 会把缓冲区内容写成新的 segment，并让 searcher 重新打开后可以搜索这些尚未 Lucene commit 的 uncommitted segment，所以写入成功到搜索可见之间通常有短暂延迟。

### 核心链路

```text
写入请求
-> coordinating node 路由到 primary shard
-> primary shard 写入 index buffer
-> 同时追加 translog
-> refresh 生成新的 uncommitted searchable segment
-> searcher 重新打开后搜索可见
-> flush 执行 Lucene commit 并清理旧 translog
-> merge 后台合并小 segment
```

### 为什么这样设计

如果每次写入都立刻做完整磁盘提交，吞吐会很低。ES 用 refresh 把“搜索可见”和“磁盘持久提交”拆开：refresh 让新 segment 较快被 searcher 看到，但这些 segment 可以还没有进入 Lucene commit；translog 保护已经确认、但尚未包含在最近一次 Lucene commit 中的操作，即使这些操作已经 refresh 可见，故障恢复时仍可能依赖 translog 回放；flush 再周期性做更重的提交并推进 translog 清理。

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
Lucene commit -> fsync index files and commit point as needed -> translog generation rollover/trim

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

translog 是 ES 的写前日志，用来保护已经确认、但尚未包含在最近一次 Lucene commit 中的写入操作，节点异常后可以通过 translog 回放恢复数据。

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

Lucene commit 成本较高，不适合每条写入都执行。translog 让 ES 可以把重提交延后，同时仍然有故障恢复能力；即使写入已经 refresh 可搜索，只要还没有进入最近一次 Lucene commit，恢复时仍可能需要 translog。

### 常见追问

**translog durability=request 和 async 区别？**

`request` 默认更安全：primary 以及本次操作涉及的 allocated replica（已分配副本）上的 translog 都 fsync 并提交后，才向客户端确认；`async` 性能更好，但节点崩溃时可能丢失下一次同步间隔前尚未 fsync 的最近写入。

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

写请求会先路由到目标 primary shard，primary 执行写入后再复制给 replica，等待相关副本写入确认或记录 shard-level 副本失败后返回客户端。

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

它控制写入开始前需要多少活跃 shard copy，是一个 pre-write gate，不代表这些副本已经完成本次写入。设置更严格能提高写入前的副本可用性要求，但也可能在副本不可用时降低写入可用性。

**replica 写失败怎么办？**

primary 可以成功但副本失败，响应里可能带有 shard-level 副本失败信息，集群状态或副本健康也可能变化，后续需要恢复副本或重新分配 shard。面试中重点说清 primary 是写入协调点，replica 是复制和高可用保障。

### 生产场景怎么说

如果写入延迟升高，要看 replica 是否慢、节点 IO 是否高、网络是否抖动、bulk 并发是否过大，以及 `wait_for_active_shards` 是否设置得过于严格。

### 关联章节

- 阶段 6：写入全链路
- 阶段 7：集群架构与高可用
- 阶段 8：写入调优
