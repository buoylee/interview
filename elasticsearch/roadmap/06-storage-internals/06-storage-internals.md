# 阶段 6：存储原理与读写链路（1.5 周）

> **目标**：理解 ES 底层存储设计的核心原理。学完本阶段后，你应该能说清 Lucene 倒排索引的完整结构（FST → Term Dictionary → Posting List）、Segment 不可变性的利弊、写入链路的每一步（Index Buffer → refresh → flush → merge）、translog 的作用，以及近实时搜索的根源。
>
> **前置依赖**：阶段 1-5（完整的"会用"能力——带着使用经验看原理，理解会深得多）
>
> **为后续阶段铺路**：本阶段是阶段 7（集群架构）和阶段 8（性能调优）的基础。集群的写入一致性建立在 Segment + Translog 之上；性能调优的每一条建议（refresh_interval、force merge、bulk size）都需要理解本阶段的原理才能知道"为什么有效"。
>
> **学习心态转换**：前五个阶段是"怎么用"（HOW），从这里开始是"为什么这样设计"（WHY）。面试中阶段 6-8 的问题区分度最高——能答好的人通常对 ES 有真正的理解。

---

## 6.1 Lucene 底层数据结构——倒排索引的完整面貌

阶段 1 中你学的倒排索引是一个简化版本：`Term → Document List`。实际的 Lucene 倒排索引要精密得多，由**三层结构**组成。

### 倒排索引的三层结构

```
┌─────────────────────────────────────────────────────┐
│                    内存                              │
│  ┌─────────────────────────────────────────┐        │
│  │  Term Index（FST - Finite State Transducer）│     │
│  │  前缀索引，快速定位 Term Dictionary 位置     │     │
│  │  只存前缀，不存完整 Term → 非常小，常驻内存  │     │
│  └──────────────────┬──────────────────────┘        │
│                     │ 定位到磁盘上的位置             │
├─────────────────────┼───────────────────────────────┤
│                    磁盘                              │
│                     ▼                               │
│  ┌─────────────────────────────────────────┐        │
│  │  Term Dictionary（词项字典）              │        │
│  │  按字典序排列的所有 Term                   │        │
│  │  每个 Term 指向它的 Posting List          │        │
│  └──────────────────┬──────────────────────┘        │
│                     │                               │
│                     ▼                               │
│  ┌─────────────────────────────────────────┐        │
│  │  Posting List（倒排列表）                 │        │
│  │  每个 Term 对应的文档 ID 列表              │        │
│  │  + Position（位置信息，match_phrase 用）   │        │
│  │  + Offset（偏移量，高亮用）                │        │
│  │  + Payload（自定义负载，如权重）            │        │
│  └─────────────────────────────────────────┘        │
└─────────────────────────────────────────────────────┘
```

### 第一层：Term Index（FST）

**问题**：Term Dictionary 存在磁盘上，可能有几百万个 Term。搜索一个 Term 时，不可能从头遍历整个 Dictionary。

**解决**：Term Index 是一个**压缩前缀树**，常驻内存。它不存完整的 Term，只存前缀，指向 Term Dictionary 在磁盘上的**块位置**。

```
查找 Term "apple" 的过程：

Term Index (内存中的 FST)：
  a → 指向 Term Dictionary 的 Block 3
  ap → 指向 Block 3 的第 100 字节
  app → 指向 Block 3 的第 120 字节

找到 Block 位置后，只需读取磁盘上一小块数据
→ 在 Block 内二分查找 "apple"
→ 找到 → 读取它的 Posting List
```

**FST（Finite State Transducer）** 是一种非常紧凑的数据结构：
- 共享前缀和后缀 → 极小的内存占用（通常只有 Term Dictionary 的 1/10）
- 支持快速前缀查找（`O(len(term))`）
- 这就是为什么 ES 能在几百万个 Term 中毫秒级找到目标

> 阶段 2 提到的 `completion` 类型（自动补全）也是基于 FST 的——整个 FST 加载到内存，前缀查找极快。

### 第二层：Term Dictionary

磁盘上按字典序排列的 Term 列表。每个 Term 记录了它在 Posting List 中的位置偏移。

```
Term Dictionary (磁盘)：
  Term        | Posting List 位置
  ------------|------------------
  "apple"     | offset: 0x1A3E
  "application"| offset: 0x1B2C
  "apply"     | offset: 0x1C00
  ...
```

按字典序排列的好处：
- 支持二分查找
- 支持前缀查找（`prefix` 查询）
- Term Index 可以通过前缀快速定位到 Dictionary 中的某个块

### 第三层：Posting List

每个 Term 对应的**文档 ID 列表**，以及可选的位置信息。

```
Term "手机" 的 Posting List：
  ┌──────────────────────────────────────────┐
  │ Doc IDs:     [2, 5, 13, 24, 56, 89]     │  ← 哪些文档包含"手机"
  │ Frequencies: [1, 2,  1,  3,  1,  2]     │  ← 在每个文档中出现几次（TF）
  │ Positions:   [[3], [1,5], [7], ...]      │  ← 出现在什么位置（match_phrase 用）
  │ Offsets:     [[10,12], [0,2,20,22], ...] │  ← 字符偏移量（高亮用）
  └──────────────────────────────────────────┘
```

> **串联阶段 4**：Frequencies 就是 BM25 公式中 **TF（词频）** 的数据来源。阶段 4 讲到"TF 越高分数越高但有饱和度"——现在你知道这个 TF 值物理上存在 Posting List 里，搜索时直接读取，不需要临时计算。Positions 则是 `match_phrase`（短语匹配）判断 Term 顺序的依据，Offsets 是高亮（Highlight）定位关键词位置的依据。

### Posting List 的编码优化

几百万个文档 ID 直接存储太浪费空间。Lucene 使用了两种核心压缩技术：

#### Frame of Reference（FOR）——增量编码 + 位压缩

```
原始 Doc IDs:     [2, 5, 13, 24, 56, 89]

步骤 1：增量编码（Delta Encoding）
  → [2, 3, 8, 11, 32, 33]     // 存差值而非绝对值

步骤 2：位压缩（Bit Packing）
  最大差值 33 只需要 6 个 bit
  → 每个数字用 6 bit 存储（而非 32 bit）
  → 压缩率约 6/32 ≈ 19%
```

#### Roaring Bitmaps——高效求交集/并集

当你用 `bool` 查询做 AND/OR 组合时，ES 需要对多个 Posting List 做交集或并集。Roaring Bitmaps 是做这个运算的高效数据结构。

```
bool 查询：brand="华为" AND category="手机"

brand="华为" 的 Posting List:     [2, 4, 6, 15, 23, 45, ...]
category="手机" 的 Posting List:  [2, 3, 6, 8, 15, 20, 23, ...]

交集（AND）→ [2, 6, 15, 23, ...]

Roaring Bitmaps 把文档 ID 空间分成 65536 大小的块：
  - 稀疏块用有序数组
  - 稠密块用 bitset
  → 交集/并集运算比普通排序合并快得多
```

> **面试怎么答**："倒排索引中的 FST 是什么？为什么用它？"
>
> FST（Finite State Transducer）是 Lucene 用于 Term Index 的压缩前缀树，常驻内存。Term Dictionary 存在磁盘上可能有几百万个 Term，不能每次搜索都遍历。FST 存储 Term 的前缀，共享公共前缀和后缀，内存占用极小（通常是 Term Dictionary 的 1/10），支持 O(len(term)) 的查找。搜索时先在内存 FST 中定位到 Term Dictionary 的磁盘块位置，再只读那一小块数据做精确查找，大幅减少磁盘 IO。

### Doc Values——顺便从底层理清

阶段 5 你学了 Doc Values 是"列式存储，用于排序和聚合"。现在从底层补充：

```
倒排索引（Inverted Index）           Doc Values（列式存储）
  方向：Term → Doc                   方向：Doc → Value
  用途：搜索                          用途：排序/聚合
  结构：FST + Dictionary + Posting   结构：类似 Parquet 的列文件

  两者在写入时同时构建，存在同一个 Segment 文件中
```

Doc Values 的物理存储也做了压缩（如数值用增量编码，字符串用字典编码），存在磁盘上通过 OS Page Cache 按需加载。

### Stored Fields vs _source

```
_source：文档的完整原始 JSON，存在 Segment 中
  - 写入时完整保存，读取时完整返回
  - GET /products/_doc/1 返回的内容就是 _source
  - 优点：不丢失任何字段，Reindex 可以直接用
  - 缺点：存储空间大且每次读取都返回完整 JSON

Stored Fields：单独标记某些字段为 stored
  - "name": { "type": "text", "store": true }
  - 可以只读取指定字段，不返回完整 _source
  - 缺点：每个 stored field 单独存储在磁盘上，读取多个字段需要多次磁盘 IO
```

**ES 为什么默认用 _source？**

_source 把所有字段打包存储在一起，一次磁盘 IO 就能读取所有字段。而 stored fields 每个字段分散存储，读取 N 个字段需要 N 次 IO。对于通常需要返回多个字段的搜索结果，_source 更高效。

如果只需要返回部分字段，用 `_source 过滤`（而不是 stored fields）：

```
GET /products/_search
{
  "_source": ["name", "price"],    // 在 _source 上过滤，只返回两个字段
  "query": { "match_all": {} }
}
```

---

## 6.2 Segment 生命周期——ES 存储设计的核心

### Segment 不可变性

**Segment 一旦写入就不可修改**。这是 Lucene（因此也是 ES）存储设计的**最核心原则**。

```
Index = 多个 Shard
Shard = 一个 Lucene 实例 = 多个 Segment + 一个 Commit Point
Segment = 一组不可变的倒排索引文件 + Doc Values 文件 + Stored Fields 文件

┌──────────────── Shard ─────────────────┐
│                                        │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐ │
│  │Seg 0 │ │Seg 1 │ │Seg 2 │ │Seg 3 │ │  ← 多个不可变的 Segment
│  └──────┘ └──────┘ └──────┘ └──────┘ │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ Commit Point                     │  │  ← 记录当前所有有效 Segment 的列表
│  │ [Seg 0, Seg 1, Seg 2, Seg 3]    │  │
│  └──────────────────────────────────┘  │
│                                        │
│  ┌──────────────────────────────────┐  │
│  │ Translog (WAL)                   │  │  ← 未持久化的写入记录
│  └──────────────────────────────────┘  │
└────────────────────────────────────────┘
```

### 不可变的优势

| 优势 | 解释 |
|------|------|
| **无锁并发读** | 读操作不需要加锁——Segment 内容不会变，任意多个线程同时读都安全 |
| **OS Cache 友好** | 不变的文件可以长期驻留在操作系统的 Page Cache 中，热数据读取接近内存速度 |
| **便于压缩** | 写入时一次性压缩，不需要考虑后续修改 |
| **简化复制** | 副本同步只需复制 Segment 文件，不需要传输变更日志 |

### 不可变的代价

| 代价 | 解释 |
|------|------|
| **更新 ≠ 原地修改** | 更新文档 = 在新 Segment 中写入新版本 + 在旧 Segment 中标记旧版本为已删除 |
| **删除 ≠ 物理删除** | 删除只是在 `.del` 文件中标记，物理删除要等 merge 时才执行 |
| **Segment 会越来愈多** | 每次 refresh 产生一个新 Segment → 需要后台 merge 合并 |

```
更新文档的实际过程：

原始文档 doc_1（在 Segment 0 中）：
  { "name": "iPhone 15", "price": 7999 }

执行 PUT /products/_doc/1 { "price": 6999 }：

  步骤 1：旧 Segment 0 中 doc_1 被标记为 .del（不是删除文件，是标记）
  步骤 2：新 Segment 3 中写入新版本的 doc_1：{ "name": "iPhone 15", "price": 6999 }
  步骤 3：搜索时，遍历所有 Segment，遇到 .del 标记的跳过

  ⚠️ 旧 doc_1 实际仍占用磁盘空间，直到 Segment 0 被 merge 到新的大 Segment 时才物理清理
```

### 完整写入链路

```
文档写入
   │
   ▼
┌─────────────────────────────────────────────────────────┐
│ ① Index Buffer（内存）                                   │
│   写入到 Shard 的内存缓冲区                               │
│   同时写入 Translog（落盘 → 防丢数据）                     │
│   此时文档 ❌ 不可搜索                                    │
└───────────────────────┬─────────────────────────────────┘
                        │ refresh（默认每 1s）
                        ▼
┌─────────────────────────────────────────────────────────┐
│ ② 新 Segment（OS Page Cache）                           │
│   Index Buffer 的内容被写成一个新的 Segment 文件           │
│   文件在 OS Cache 中（未 fsync 到磁盘）                   │
│   此时文档 ✅ 可搜索（近实时搜索的来源！）                  │
└───────────────────────┬─────────────────────────────────┘
                        │ flush（默认每 30min 或 translog 512MB）
                        ▼
┌─────────────────────────────────────────────────────────┐
│ ③ 持久化 Segment（磁盘）                                │
│   OS Cache 中的 Segment 文件 fsync 到磁盘                 │
│   更新 Commit Point                                     │
│   清空 Translog                                         │
│   此时数据 ✅ 持久化（不怕断电）                           │
└───────────────────────┬─────────────────────────────────┘
                        │ merge（后台持续执行）
                        ▼
┌─────────────────────────────────────────────────────────┐
│ ④ 合并后的大 Segment                                     │
│   多个小 Segment 合并为一个大 Segment                     │
│   .del 标记的文档在此时物理删除                            │
│   减少 Segment 数量 → 提升查询性能                        │
└─────────────────────────────────────────────────────────┘
```

### refresh——近实时搜索的来源

```
refresh 做了什么：
  Index Buffer (内存) → 写成一个新 Segment → 放进 OS Cache (不落盘)

refresh 后：
  新 Segment 可以被搜索 → 文档"可见"了
  但还没 fsync 到磁盘 → 如果断电，这个 Segment 会丢失

refresh_interval 默认 1s：
  → 写入后最多 1s 搜不到 → 这就是 "近实时（Near Real-Time）" 的含义
```

**refresh_interval 的生产调优：**

| 场景 | 配置 | 理由 |
|------|------|------|
| 默认 | `1s` | 适合大部分搜索场景 |
| 大批量数据导入 | `30s` 或 `-1`（禁用） | 减少 refresh 次数 → 减少 Segment 创建 → 大幅提升写入速度 |
| 实时性要求极高 | 写入后手动调用 `POST /index/_refresh` | 确保立即可搜索 |

```json
// 修改 refresh_interval
PUT /products/_settings
{
  "index.refresh_interval": "30s"
}

// 大批量导入时禁用 refresh
PUT /products/_settings
{
  "index.refresh_interval": "-1"
}

// 导入完成后恢复
PUT /products/_settings
{
  "index.refresh_interval": "1s"
}
```

### Translog——Write-Ahead Log

Translog 解决的问题：refresh 把 Segment 放进 OS Cache 但不落盘，flush 才落盘——如果 refresh 后、flush 前机器断电，OS Cache 中的 Segment 会丢失。

```
写入流程（含 Translog）：

文档写入
  → ① 写入 Index Buffer（内存）
  → ② 同步写入 Translog 并 fsync 到磁盘                ← 保护点！
  → 返回客户端"写入成功"

--- refresh（1s 后）---
  → ③ Index Buffer 写成 Segment 到 OS Cache
  → Translog 保留（因为 Segment 还没持久化）

--- flush（30min 后）---
  → ④ OS Cache 中的 Segment fsync 到磁盘
  → ⑤ 清空 Translog（数据已持久化，不再需要 WAL）

如果步骤③之后、④之前断电：
  → 重启后从 Translog 回放 → 重建丢失的 Segment
  → 数据不丢！
```

**Translog 的持久性配置：**

| 配置 | 行为 | 性能 | 数据安全 |
|------|------|------|---------|
| `index.translog.durability: request`（默认） | 每次写入操作后都 fsync translog | 较慢 | ✅ 最安全 |
| `index.translog.durability: async` | 每 5 秒（可配置）fsync 一次 | 更快 | ⚠️ 最多丢 5 秒数据 |

```json
// 异步 translog（提升写入性能，牺牲少量安全性）
PUT /logs/_settings
{
  "index.translog.durability": "async",
  "index.translog.sync_interval": "5s"
}
```

> **面试怎么答**："ES 的写入数据丢失怎么办？translog 的作用？"
>
> Translog 是 ES 的 Write-Ahead Log（预写日志）。文档写入时同步写入 Translog 并 fsync 到磁盘，然后才返回成功。refresh 后数据在 OS Cache 中的 Segment 里可以搜索，但还没持久化到磁盘。如果这时断电，重启后 ES 会从 Translog 回放操作重建丢失的 Segment，保证不丢数据。flush 操作会把 Segment fsync 到磁盘然后清空 Translog。默认配置下每次写入都会 fsync translog，可以设为 async 提升性能但最多丢几秒数据。

### Merge——后台合并

每次 refresh 都会产生一个新 Segment。随着时间推移，Segment 越来越多。搜索时要遍历所有 Segment，Segment 数量直接影响查询性能。

```
Merge 的过程：

合并前：                              合并后：
┌──────┐ ┌──────┐ ┌──────┐          ┌──────────────────┐
│Seg 0 │ │Seg 1 │ │Seg 2 │   ──→   │  Merged Segment  │
│100 docs│ │50 docs│ │30 docs│       │   150 docs       │
│.del: 5 │ │.del: 2│ │.del: 0│       │   .del: 0        │  ← 标记删除的文档被物理清理！
└──────┘ └──────┘ └──────┘          └──────────────────┘
                                    + 旧的 Seg 0/1/2 被删除
```

**Merge 的触发和策略：**

- **自动触发**：ES 后台持续评估，按 Tiered Merge Policy 策略合并
- **Tiered Merge Policy**：根据 Segment 大小分层，优先合并大小相近的小 Segment
- 每次 merge 有 IO 和 CPU 开销——ES 自动限流（`max_merge_at_once` 等参数）

**Force Merge——手动强制合并：**

```
# 将索引合并为 1 个 Segment
POST /logs-2024-01/_forcemerge?max_num_segments=1
```

| 场景 | 是否适合 force merge |
|------|-------------------|
| **只读索引**（历史日志、已关闭的按时间分的索引） | ✅ 非常适合——合并后查询性能大幅提升 |
| **活跃写入的索引** | ❌ 不要做——merge 消耗大量 IO，会影响正在写入和查询的性能 |

> **面试怎么答**："force merge 什么时候用？有什么风险？"
>
> force merge 适用于只读索引——比如按时间分的日志索引，过了写入期后用 force merge 合并为 1 个 Segment，减少搜索时遍历的 Segment 数量，显著提升查询性能。风险是 merge 过程消耗大量磁盘 IO 和 CPU，需要约 2 倍的磁盘空间（旧 Segment + 新 Segment 同时存在），对活跃写入的索引做 force merge 会严重影响写入和查询性能。

---

## 6.3 写入全链路——从客户端到磁盘

### 完整的分布式写入流程

```
Client
  │
  │ PUT /products/_doc/1
  ▼
Coordinating Node（协调节点，接收请求的任意节点）
  │
  │ 计算路由：shard_num = hash(_routing) % number_of_primary_shards
  │          默认 _routing = _id
  ▼
Primary Shard（目标 Primary 分片所在节点）
  │
  │ ① 写入 Index Buffer（内存）
  │ ② 写入 Translog 并 fsync
  │ ③ 返回 Primary 写入成功
  │
  │ 转发到所有 In-Sync Replica Shards
  │
  ├──→ Replica Shard 1：Index Buffer + Translog → 确认
  ├──→ Replica Shard 2：Index Buffer + Translog → 确认
  │
  │ 所有 in-sync 副本确认
  ▼
Coordinating Node → 返回 Client 成功
```

### Wait for Active Shards

控制写入时需要多少个分片副本确认才返回成功：

```json
# 请求级别设置
PUT /products/_doc/1?wait_for_active_shards=2
{ "name": "iPhone 15" }

# 索引级别设置
PUT /products/_settings
{
  "index.write.wait_for_active_shards": "all"   // 等所有副本确认
}
```

| 配置 | 行为 | 取舍 |
|------|------|------|
| `1`（默认） | 只等 Primary 确认 | 最快，但 Primary 宕机时副本可能还没同步到 |
| `2` | 等 Primary + 至少 1 个 Replica | 平衡速度和安全 |
| `all` | 等所有 in-sync 副本 | 最安全，但最慢——任一副本慢都会拖慢写入 |

### 版本冲突控制

ES 使用**乐观并发控制**，通过 `_seq_no` + `_primary_term` 防止并发更新冲突：

```
# 先读取文档，获取版本信息
GET /products/_doc/1
# 返回：_seq_no=5, _primary_term=1

# 带版本号更新——只有版本匹配才成功
PUT /products/_doc/1?if_seq_no=5&if_primary_term=1
{
  "name": "iPhone 15",
  "price": 6999
}

# 如果另一个请求已经更新了（_seq_no 变了），这次更新会返回 409 Conflict
```

---

## 6.4 读取全链路——搜索是怎么执行的

### 从 Shard 内部看搜索

阶段 4 讲了 Query Then Fetch 的宏观两阶段。现在从 Shard 内部看更细的过程：

```
一个 Shard 收到搜索请求后：

┌─────────── Shard 内部 ── ─────────────┐
│                                        │
│  遍历所有 Segment（这就是为什么 Segment  │
│  太多会影响查询性能！）                  │
│                                        │
│  Segment 0:                            │
│    Term Index (FST, 内存)              │
│    → Term Dictionary (磁盘)            │
│    → Posting List (磁盘)               │
│    → 匹配的 doc_ids + scores           │
│    → 过滤掉 .del 标记的文档             │
│                                        │
│  Segment 1: (同上)                     │
│  Segment 2: (同上)                     │
│  ...                                   │
│                                        │
│  合并所有 Segment 的结果                │
│  → 取 Top from+size 条                 │
│  → 返回 doc_id + score 给协调节点       │
└────────────────────────────────────────┘
```

**关键性能影响**：
- Segment 数量越多 → 需要遍历的 Segment 越多 → 查询越慢
- 这就是为什么 merge 和 force merge 能提升查询性能
- 也是为什么 refresh_interval 过小（产生大量小 Segment）会影响搜索

### DFS Query Then Fetch

普通的 Query Then Fetch 中，每个 Shard 用**本地**的 TF/IDF 统计值计算 BM25 分数。但不同 Shard 的数据分布可能不同，导致同一个 Term 在不同 Shard 上的 IDF 值不同，产生微妙的打分差异。

```
GET /products/_search?search_type=dfs_query_then_fetch
{
  "query": { "match": { "name": "手机" } }
}
```

DFS（Distributed Frequency Search）会先从所有 Shard 收集全局的 Term 频率，再发送给每个 Shard 用全局统计值打分。结果更准确，但多了一次网络往返。

**什么时候用 DFS？**
- 数据量小且 Shard 多时，本地 IDF 偏差较大 → 考虑用 DFS
- 数据量大时，每个 Shard 的统计值趋近全局值 → 默认的 Query Then Fetch 就够了

---

## 6.5 近实时搜索（NRT）完整总结

现在你可以**完整串联**这条因果链了：

```
WHY：为什么 ES 是"近实时"搜索而不是"实时"搜索？

BECAUSE：
  文档写入 → 先进 Index Buffer（内存，不可搜索）
          → 每 1s 执行一次 refresh
          → refresh 把 Index Buffer 写成新 Segment 到 OS Cache
          → 新 Segment 可搜索

  所以：写入后最多 1s 才可搜索 = "近实时"

WHY NOT 实时？
  → 如果每写一条都创建新 Segment → Segment 爆炸 → 查询性能崩溃
  → 所以必须攒 1s 的数据再一起写 Segment → 这 1s 就是延迟的来源

CAN WE MAKE IT 实时？
  → 写入后手动调用 _refresh → 可以，但浪费性能
  → 设 refresh_interval=0 → 可以但不推荐（Segment 太多）
```

> **面试怎么答**："为什么 ES 是近实时的？refresh 机制是什么？"
>
> ES 是近实时搜索，默认有最多 1 秒的搜索延迟。原因是文档写入后先进入内存中的 Index Buffer，不可搜索。每隔 1 秒（refresh_interval）执行一次 refresh 操作，把 Index Buffer 中的数据写成一个新的 Lucene Segment 到操作系统的 Page Cache 中。这个新 Segment 虽然还没有 fsync 到磁盘，但已经可以被搜索到了。之所以不每写一条就创建 Segment，是因为 Segment 数量太多会严重影响查询性能（搜索需要遍历所有 Segment），所以需要攒批次处理。大批量导入数据时可以把 refresh_interval 调大（如 30s 或 -1）来提升写入性能。

---

## 面试高频题与参考答案

### Q1：为什么 ES 是近实时的？refresh 机制是什么？

**答**：（见上方 6.5 节的面试回答）

### Q2：ES 的写入数据丢失怎么办？translog 的作用？

**答**：（见上方 6.2 Translog 节的面试回答）

### Q3：删除文档是立即删除吗？对性能有什么影响？

**答**：不是即时物理删除。ES 的 Segment 是不可变的，删除操作实际上是在 `.del` 文件中标记这个文档为已删除。搜索时遍历到被标记的文档会跳过它，但它仍然占用磁盘空间，且搜索时仍然要读到这个文档然后才知道要跳过。

物理删除发生在 Segment merge 的时候——多个小 Segment 合并为大 Segment 时，被标记删除的文档不会被复制到新 Segment 中，从而真正释放空间。

大量删除操作对性能的影响：1）磁盘空间不会立即释放；2）搜索时仍要读取和过滤被标记的文档，增加无效 IO；3）如果被删除的文档比例很高，可以考虑 force merge 来加速清理。

### Q4：Segment 不可变有什么好处？有什么代价？

**答**：好处：第一，支持无锁并发读——多个搜索线程可以同时读取 Segment 而不需要加锁。第二，OS Cache 友好——不变的文件可以长期缓存在操作系统 Page Cache 中。第三，便于压缩——写入时一次性压缩，不需要考虑后续修改。第四，简化副本同步——直接复制 Segment 文件即可。

代价：第一，更新和删除不是原地修改——更新是标记旧文档删除+写入新文档+等 merge 清理，有额外开销。第二，Segment 数量会不断增长——每次 refresh 产生新 Segment，需要后台 merge 合并。第三，merge 本身消耗 IO 和 CPU 资源。

### Q5：倒排索引中的 FST 是什么？为什么用它？

**答**：（见上方 6.1 Term Index 节的面试回答）

### Q6：force merge 什么时候用？有什么风险？

**答**：（见上方 6.2 Force Merge 节的面试回答）

---

## 动手实践

### 练习 1：refresh_interval 对写入性能和搜索延迟的影响

```
# 1. 创建索引，默认 refresh_interval=1s
PUT /refresh_test
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s"
  },
  "mappings": {
    "properties": {
      "title": { "type": "text" },
      "value": { "type": "integer" }
    }
  }
}

# 2. 写入一条文档
PUT /refresh_test/_doc/1
{ "title": "test document", "value": 1 }

# 3. 立即搜索——可能搜不到（还没 refresh）
GET /refresh_test/_search
{ "query": { "match_all": {} } }

# 4. 等 1 秒后再搜——应该能搜到了
GET /refresh_test/_search
{ "query": { "match_all": {} } }

# 5. 修改 refresh_interval 为 30s
PUT /refresh_test/_settings
{ "index.refresh_interval": "30s" }

# 6. 写入新文档
PUT /refresh_test/_doc/2
{ "title": "new document", "value": 2 }

# 7. 搜索——搜不到 doc 2（还没 refresh）
GET /refresh_test/_search
{ "query": { "match_all": {} } }

# 8. 手动 refresh
POST /refresh_test/_refresh

# 9. 再搜索——现在能搜到了
GET /refresh_test/_search
{ "query": { "match_all": {} } }

# 10. 清理
DELETE /refresh_test
```

### 练习 2：观察 Segment 和 force merge

```
# 1. 创建索引，refresh_interval 设短（1s）
PUT /segment_test
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "refresh_interval": "1s"
  },
  "mappings": {
    "properties": {
      "value": { "type": "integer" }
    }
  }
}

# 2. 逐条写入多条文档（每条单独触发 refresh → 产生独立 Segment）
PUT /segment_test/_doc/1
{ "value": 1 }
# 等 1-2 秒

PUT /segment_test/_doc/2
{ "value": 2 }
# 等 1-2 秒

PUT /segment_test/_doc/3
{ "value": 3 }
# 等 1-2 秒

PUT /segment_test/_doc/4
{ "value": 4 }
# 等 1-2 秒

PUT /segment_test/_doc/5
{ "value": 5 }

# 3. 查看 Segment 信息
GET /_cat/segments/segment_test?v
# 观察：应该有多个小 Segment（每个可能只有 1 条文档）

# 4. 执行 force merge，合并为 1 个 Segment
POST /segment_test/_forcemerge?max_num_segments=1

# 5. 再次查看 Segment 信息
GET /_cat/segments/segment_test?v
# 观察：只剩 1 个 Segment

# 6. 清理
DELETE /segment_test
```

### 练习 3：观察删除和 .del 标记

```
# 1. 创建索引并写入数据
PUT /del_test
{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0 },
  "mappings": { "properties": { "name": { "type": "keyword" } } }
}

POST /_bulk
{"index": {"_index": "del_test", "_id": "1"}}
{"name": "doc_1"}
{"index": {"_index": "del_test", "_id": "2"}}
{"name": "doc_2"}
{"index": {"_index": "del_test", "_id": "3"}}
{"name": "doc_3"}

# 2. 强制 refresh + 查看 Segment 信息
POST /del_test/_refresh
GET /_cat/segments/del_test?v
# 注意看 docs.count 和 docs.deleted 列

# 3. 删除一条文档
DELETE /del_test/_doc/2

# 4. refresh 后查看 Segment 信息
POST /del_test/_refresh
GET /_cat/segments/del_test?v
# 观察：docs.deleted 变成 1（标记删除但未物理清理）

# 5. 搜索——doc_2 不会出现在结果中
GET /del_test/_search
{ "query": { "match_all": {} } }

# 6. force merge 物理清理
POST /del_test/_forcemerge?max_num_segments=1

# 7. 再看 Segment
GET /_cat/segments/del_test?v
# 观察：docs.deleted 变成 0（物理删除完成）

# 8. 清理
DELETE /del_test
```

---

## 本阶段总结

学完本阶段，你应该掌握了以下心智模型：

```
Lucene 倒排索引三层结构：
  Term Index (FST, 内存) → Term Dictionary (磁盘) → Posting List (磁盘)
  搜索路径：FST 前缀定位 → Dictionary 精确查找 → Posting List 获取 doc_ids

Segment 不可变性（核心设计原则）：
  优势：无锁并发读、OS Cache 友好、便于压缩
  代价：更新=标记删除旧+写入新、Segment 数量增长、需要 merge

写入链路：
  文档 → Index Buffer + Translog(fsync)
       → [refresh 1s] → 新 Segment (OS Cache, 可搜索)
       → [flush 30min] → Segment 持久化 + 清 translog
       → [merge 后台] → 合并小 Segment + 物理清理已删除文档

近实时搜索（NRT）：
  写入后最多 1s 不可搜索 = refresh_interval 的延迟

数据安全保障：
  Translog (WAL) = refresh 和 flush 之间的防丢保护
  断电恢复：从 translog 回放

Posting List 压缩：
  FOR（增量编码+位压缩）减小存储
  Roaring Bitmaps 高效求交集/并集
```

**下一阶段**：阶段 7 集群架构与高可用——你现在理解了单个 Shard 内部的存储原理（Segment、Translog、写入链路），接下来从集群视角看：多个 Shard 如何分布在多个节点上？Master 怎么选举？一个节点宕机后分片怎么恢复？脑裂怎么防止？
