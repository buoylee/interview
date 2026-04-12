# 阶段 8：性能调优（1 周）

> **目标**：掌握 ES 全方位的性能调优方法论。学完本阶段后，你应该能系统性优化写入和查询性能、正确配置 JVM 堆内存、设置 OS 层参数、使用监控诊断工具定位瓶颈，以及为生产系统做容量规划。
>
> **前置依赖**：阶段 6（存储原理——理解 refresh/flush/merge/Segment 才能理解写入优化）+ 阶段 7（集群架构——理解分片/副本/节点角色才能理解查询优化和容量规划）
>
> **为什么调优放在最后？** 每一条调优建议的背后都有原理支撑。"refresh_interval 调大"背后是 Segment 生成机制（阶段 6）；"filter 优先于 must"背后是 Node Query Cache（阶段 4）；"堆内存不超 32GB"背后是 JVM CompressedOops。不懂原理的调优是**照搬配置**，懂原理的调优才是**对症下药**。

---

## 8.1 写入优化

### 优化 1：批量写入（_bulk）

单条写入的网络开销巨大——每条文档一个 HTTP 请求。`_bulk` 一次提交一批文档，大幅减少网络往返。

```
# 单条写入：N 条文档 = N 次 HTTP 请求
PUT /products/_doc/1 { ... }   ← 1 次请求
PUT /products/_doc/2 { ... }   ← 1 次请求
...                            ← N 次请求

# 批量写入：N 条文档 = 1 次 HTTP 请求
POST /_bulk
{"index": {"_index": "products"}}
{ ... }
{"index": {"_index": "products"}}
{ ... }
...
```

**最佳 batch size：**

| 参数 | 建议 | 理由 |
|------|------|------|
| 每批大小 | **5-15 MB**（不是条数！） | 太小浪费网络，太大占内存 |
| 并发数 | 2-4 个并发的 _bulk 请求 | 充分利用写入线程池 |

找最优值的方法：从 5MB 开始测，逐步增大到 10MB、15MB、20MB，观察吞吐量。通常在 5-15MB 时吞吐量达到峰值，之后增大也没有显著提升。

### 优化 2：调大 refresh_interval

```
原理回顾（阶段 6）：
  每次 refresh 产生一个新 Segment
  → refresh 越频繁 → Segment 越多 → merge 压力越大 → IO 消耗越高
  → 大批量导入时 refresh_interval=1s 会严重拖慢写入
```

```json
// 大批量导入前：禁用 refresh
PUT /products/_settings
{ "index.refresh_interval": "-1" }

// 导入完成后：恢复
PUT /products/_settings
{ "index.refresh_interval": "1s" }
```

**效果**：写入性能提升可达 **2-5 倍**。

### 优化 3：Translog 异步刷盘

```
原理回顾（阶段 6）：
  默认每次写入都 fsync translog → 磁盘 IO 瓶颈
  改为异步：每 5s 批量 fsync → 减少磁盘 IO
  代价：最多丢 5 秒数据
```

```json
PUT /products/_settings
{
  "index.translog.durability": "async",
  "index.translog.sync_interval": "5s"
}
```

**适用场景**：可以容忍少量数据丢失的场景（日志、指标），不适合交易数据。

### 优化 4：导入时副本设为 0

```
原理回顾（阶段 7）：
  每条文档写 Primary 后还要转发到 Replica → 写入量翻倍
  导入时去掉 Replica → 写入量减半
```

```json
// 导入前：去掉副本
PUT /products/_settings
{ "index.number_of_replicas": 0 }

// 导入完成后：恢复副本
PUT /products/_settings
{ "index.number_of_replicas": 1 }
```

恢复副本后 ES 会自动做一次全量复制（Peer Recovery）。

### 优化 5：Index Sorting（预排序）

```json
PUT /products
{
  "settings": {
    "index.sort.field": ["created_at"],
    "index.sort.order": ["desc"]
  }
}
```

写入时按指定字段对 Segment 内的文档预排序。查询时如果排序字段和 index sort 一致，可以提前终止（early termination）——找到足够的文档后不需要遍历整个 Segment。

**代价**：写入稍慢（需要排序），且只用于按固定字段排序的场景。

### 优化 6：合理的线程池配置

```
GET /_cat/thread_pool/write?v

查看 write 线程池的状态：
  active：当前正在执行的写入线程数
  queue：等待队列中的请求数
  rejected：被拒绝的请求数（队列满了）

如果 rejected > 0 → 写入压力超过处理能力
  → 减小客户端并发
  → 或增加节点
```

### 写入优化速查表

| 优化项 | 原理（阶段） | 效果 | 代价 |
|-------|------------|------|------|
| _bulk 批量写入 | 减少网络往返 | ★★★★★ | 无 |
| refresh_interval → -1 | 减少 Segment 创建（阶段 6） | ★★★★ | 导入期间不可搜索 |
| translog async | 减少磁盘 fsync（阶段 6） | ★★★ | 最多丢 5 秒数据 |
| replica → 0 | 减少副本写入（阶段 7） | ★★★★ | 导入期间无冗余 |
| index sorting | 预排序+early termination（阶段 6） | ★★ | 写入变慢 |

---

## 8.2 查询优化

### 优化 1：filter 优先于 must

```
原理回顾（阶段 4）：
  filter：不打分 + 结果自动缓存到 Node Query Cache（Bitset）
  must：打分 + 不缓存
  同一条件放 filter 比 must 快得多
```

```json
// ❌ 状态过滤放在 must 里（不需要打分却在打分）
{ "bool": { "must": [{ "term": { "status": "active" } }] } }

// ✅ 状态过滤放在 filter 里
{ "bool": { "filter": [{ "term": { "status": "active" } }] } }
```

**原则：不需要影响排序的条件一律放 filter**。

### 优化 2：routing 定向查询

```
原理回顾（阶段 7）：
  不指定 routing → 查询广播到所有 Shard → 每个 Shard 都要搜
  指定 routing → 只查一个 Shard → 减少 N-1 个 Shard 的搜索
```

```
// 查询某用户的所有订单——只查一个 Shard
GET /orders/_search?routing=user_001
{ "query": { "term": { "user_id": "user_001" } } }
```

5 个 Shard 的索引，指定 routing 后查询量减少 80%。

### 优化 3：避免深度分页

```
原理回顾（阶段 4）：
  from=10000, size=10 → 每个 Shard 返回 10010 条
  → 5 个 Shard = 50050 条在内存排序 → 内存爆炸
```

**方案：用 search_after 替代 from+size**（阶段 4 已详述）。

### 优化 4：避免危险查询

```
// ❌ 前缀通配符——全索引扫描
{ "wildcard": { "name.keyword": "*手机" } }

// ❌ 正则查询——CPU 密集
{ "regexp": { "name.keyword": ".*手机.*" } }

// ❌ script 排序——比原生慢 10-100 倍
{ "sort": { "_script": { "script": "doc['price'].value * 0.8" } } }

// ✅ 替代方案：
// 通配符前缀 → 用 edge_ngram 或 reverse token filter
// script 排序 → 预计算字段值存为独立字段
```

### 优化 5：_source 过滤

```json
// 只返回需要的字段（不返回完整 _source）
GET /products/_search
{
  "_source": ["name", "price"],
  "query": { "match_all": {} }
}

// 或排除某些字段
{
  "_source": { "excludes": ["description", "large_field"] },
  "query": { "match_all": {} }
}
```

特别是大字段（description 等）不需要返回时，过滤掉能减少网络传输和反序列化时间。

### 优化 6：force merge 只读索引

```
原理回顾（阶段 6）：
  搜索要遍历所有 Segment → Segment 越少越快
  只读索引（如历史日志）→ force merge 成 1 个 Segment → 查询提速
```

```
POST /logs-2024-01/_forcemerge?max_num_segments=1
```

### 优化 7：Index Sorting + Early Termination

```json
// 如果索引按 created_at 降序预排了
// 查询"最新 10 条"时可以提前终止——找到 10 条就不继续扫了
GET /products/_search
{
  "size": 10,
  "sort": [{ "created_at": "desc" }],
  "track_total_hits": false              // 不统计总数，允许提前终止
}
```

`track_total_hits: false` 告诉 ES 不需要精确总数，可以在找到足够文档后立即返回。

### 查询优化速查表

| 优化项 | 原理（阶段） | 效果 | 适用场景 |
|-------|------------|------|---------|
| filter 替代 must | 跳过打分+缓存（阶段 4） | ★★★★★ | 所有非排序条件 |
| routing 查询 | 只查一个 Shard（阶段 7） | ★★★★ | 多租户、按用户查 |
| search_after | 避免深度分页（阶段 4） | ★★★★ | 翻页场景 |
| 避免 wildcard/script | 全扫描/CPU 密集 | ★★★ | 全部场景 |
| _source 过滤 | 减少网络传输 | ★★ | 大字段场景 |
| force merge | 减少 Segment 数（阶段 6） | ★★★★ | 只读索引 |
| track_total_hits=false | early termination | ★★★ | 不需要总数的场景 |

---

## 8.3 JVM 与 GC 调优

### 堆内存两条红线

这是**面试必考**的知识点。

```
红线 1：堆内存 ≤ 物理内存的 50%

  总内存 64GB → 堆最多 32GB → 剩余 32GB 留给 OS Page Cache

  为什么？
  Lucene 重度依赖 OS Page Cache：
    Segment 文件 → 通过 mmap 映射到内存 → OS 自动缓存
    如果堆太大 → OS Cache 太小 → Segment 文件频繁从磁盘读 → 查询变慢

  ┌────────── 64GB 物理内存 ──────────┐
  │  ┌─────────┐  ┌─────────────────┐ │
  │  │ JVM 堆  │  │  OS Page Cache  │ │
  │  │  32GB   │  │     32GB        │ │
  │  │ ES 对象 │  │  Lucene Segment │ │
  │  └─────────┘  └─────────────────┘ │
  └───────────────────────────────────┘


红线 2：堆内存 ≤ ~31GB（通常约 30.5GB）

  为什么是 31GB？
  JVM 有个优化叫 CompressedOops（压缩对象指针）：
    堆 ≤ ~32GB 时：指针用 4 字节 → 内存利用率高
    堆 > ~32GB 时：指针变成 8 字节 → 同样的对象多占 ~50% 内存

  所以 32GB 堆反而可能比 31GB 堆可用内存更少！

  实际安全值约 30.5GB（用 -XX:+UnlockDiagnosticVMOptions -XX:+PrintCompressedOopsMode 验证）
```

```
# ES 堆内存配置（jvm.options）
-Xms30g
-Xmx30g     # 必须设成一样（避免动态调整的开销）
```

> **面试怎么答**："ES 堆内存为什么不能超过 32GB？"
>
> 两个原因。第一，留给 OS Page Cache。Lucene 通过 mmap 将 Segment 文件映射到内存，依赖操作系统的 Page Cache 加速读取。堆超过 50% 物理内存会挤压 Page Cache，导致 Segment 频繁从磁盘读，查询变慢。第二，CompressedOops。JVM 在堆 ≤ ~32GB 时使用压缩对象指针（4 字节），超过后指针变成 8 字节，同样的数据多占约 50% 内存。所以 33GB 堆的实际可用内存可能比 31GB 还少。生产中通常设 30-31GB。

### GC 调优要点

ES 8.x 默认使用 G1GC。关注两个指标：

```
# 查看 GC 统计
GET /_nodes/stats/jvm

关注：
  jvm.gc.collectors.young.collection_time_in_millis  → Young GC 总耗时
  jvm.gc.collectors.old.collection_time_in_millis    → Old GC 总耗时
  jvm.gc.collectors.old.collection_count             → Old GC 次数

告警阈值：
  Old GC 频率 > 每分钟 1 次 → 堆内存可能不够
  GC 停顿时间 > 1 秒 → 影响查询延迟
```

**常见 OOM 原因：**

| 原因 | 排查 | 解决 |
|------|------|------|
| Fielddata 加载 | text 字段做聚合 | 改用 .keyword 子字段 |
| 大聚合结果 | terms size 过大 | 减小 size，用 Composite 分页 |
| 深度分页 | from 值过大 | 用 search_after |
| 太多 buckets | 嵌套聚合层数多 | 减少嵌套层数 |
| 集群状态过大 | 索引/分片数过多 | 合并索引，减少分片 |

---

## 8.4 OS 层调优

### 四项必配参数

```bash
# 1. 文件描述符——ES 打开大量 Segment 文件
ulimit -n 65535
# 或在 /etc/security/limits.conf 中设置：
# elasticsearch  -  nofile  65535

# 2. 虚拟内存映射数——Lucene 使用 mmap
sysctl -w vm.max_map_count=262144
# 永久生效：/etc/sysctl.conf 加入 vm.max_map_count=262144

# 3. 禁用 swap——swap 会导致 GC 停顿时间飙升
swappiness = 1
# 或在 ES 配置中锁定内存：
# bootstrap.memory_lock: true

# 4. 使用 SSD
# Segment 文件的随机读写性能直接决定查询和 merge 速度
# SSD vs HDD 性能差距可达 10-100 倍
```

### 验证配置

```
# 检查文件描述符限制
GET /_nodes/stats/process

# 检查内存是否锁定
GET /_nodes?filter_path=**.mlockall
```

---

## 8.5 监控与诊断

### _cat APIs——快速诊断

```
# 集群健康
GET /_cat/health?v

# 节点列表（含 CPU、内存、磁盘使用）
GET /_cat/nodes?v&h=name,ip,heap.percent,ram.percent,cpu,load_1m,disk.used_percent,node.role

# 索引列表（含文档数、大小、健康状态）
GET /_cat/indices?v&s=store.size:desc

# 分片分布
GET /_cat/shards?v

# 线程池状态（重点关注 rejected）
GET /_cat/thread_pool?v&h=name,active,queue,rejected

# 待完成任务
GET /_cat/pending_tasks?v
```

### 慢查询日志

```json
// 慢搜索日志——搜索耗时超阈值时记录
PUT /products/_settings
{
  "index.search.slowlog.threshold.query.warn": "10s",
  "index.search.slowlog.threshold.query.info": "5s",
  "index.search.slowlog.threshold.query.debug": "2s",
  "index.search.slowlog.threshold.query.trace": "500ms",
  "index.search.slowlog.level": "info"
}

// 慢索引日志——写入耗时超阈值时记录
PUT /products/_settings
{
  "index.indexing.slowlog.threshold.index.warn": "10s",
  "index.indexing.slowlog.threshold.index.info": "5s"
}
```

日志输出到 ES 的日志文件中（`<ES_HOME>/logs/<cluster_name>_index_search_slowlog.log`），包含完整的查询 DSL，方便定位慢查询。

### Hot Threads API——定位 CPU 瓶颈

```
GET /_nodes/hot_threads

# 返回每个节点上 CPU 消耗最高的线程堆栈
# 典型场景：
#   - 大量 merge 操作 → Lucene merge 线程占 CPU
#   - 复杂查询 → search worker 线程占 CPU
#   - script 执行 → painless 编译/执行占 CPU
```

### profile API——查询性能诊断

```json
GET /products/_search
{
  "profile": true,
  "query": {
    "bool": {
      "must": [{ "match": { "name": "手机" } }],
      "filter": [{ "term": { "status": "active" } }]
    }
  }
}
```

返回结果包含每个 Shard 上每个查询组件的**纳秒级耗时**：

```
profile.shards[0].searches[0].query[0]:
  type: BooleanQuery
  time_in_nanos: 125000
  children:
    - type: TermQuery (match → "手机")
      time_in_nanos: 100000       ← match 阶段耗时
    - type: TermQuery (filter → status=active)
      time_in_nanos: 5000         ← filter 阶段耗时（命中了缓存，很快）
```

### 诊断流程速查

```
问题：查询慢
  │
  ├── 是哪个索引慢？ → _cat/indices 看索引大小和文档数
  │
  ├── 是单个查询慢还是整体慢？
  │     ├── 单个查询 → profile API 分析查询计划
  │     └── 整体慢 → _cat/nodes 看 CPU/内存/IO
  │
  ├── 慢在哪个阶段？
  │     ├── query 阶段 → 优化查询（filter、routing、避免 script）
  │     ├── fetch 阶段 → _source 过滤
  │     └── merge 阶段（后台） → 检查 Segment 数量，考虑 force merge
  │
  └── 看慢查询日志 → 找到具体的慢查询 DSL

问题：写入慢
  │
  ├── _cat/thread_pool 看 write 线程池是否 rejected
  ├── 检查 refresh_interval 和 translog 配置
  ├── 检查 _bulk 批量大小
  └── 检查副本数量
```

---

## 8.6 容量规划

### 规划三步法

```
步骤 1：预估数据量
  ├── 当前数据量
  ├── 增长速率（每天/每月新增多少）
  ├── 保留周期（数据保留多久）
  └── 数据膨胀系数（原始数据 → ES 索引后通常 1.5-2 倍）

步骤 2：计算分片数
  ├── 总数据量 = 当前 + 增长 × 保留周期
  ├── 目标单 Shard 大小 = 10-50GB
  ├── Primary Shard 数 = 总数据量 / 目标 Shard 大小
  └── 总 Shard 数 = Primary × (1 + Replica)

步骤 3：计算节点数
  ├── 单节点 Shard 数上限 ≈ 内存(GB) × 20
  ├── 节点数 ≥ 总 Shard 数 / 单节点上限
  ├── 考虑 N+1 冗余（至少多一个节点）
  └── 磁盘：预留 50% 空间给 merge
```

### 实际案例

```
场景：电商商品搜索
  当前商品数：200 万
  每条文档平均大小：2KB
  数据总量：200万 × 2KB = 4GB
  膨胀后（含索引结构）：4GB × 2 = 8GB
  预估增长：3 年后 500 万商品 → 20GB

  分片规划：
    20GB / 20GB(目标) = 1 个 Primary Shard
    考虑查询并行度 → 设 3 个 Primary（每个约 7GB）
    1 个 Replica → 总 6 个 Shard

  节点规划：
    3 节点（每节点 2 个 Shard）
    内存：16GB 起步（8GB 堆 + 8GB Page Cache）
    磁盘：20GB × 2(副本) × 1.5(merge预留) = 60GB SSD
```

```
场景：日志分析
  每天日志量：50GB
  保留90天：50 × 90 = 4.5TB
  按天分索引：90 个索引

  分片规划：
    每天 50GB / 25GB = 2 个 Primary Shard
    1 个 Replica → 每天 4 个 Shard → 90 天 360 个 Shard

  节点规划：
    6 个 Data 节点（每节点 60 个 Shard）
    内存：64GB（32GB 堆 + 32GB Page Cache）
    磁盘：4.5TB × 1.5(merge预留) ÷ 6 = 1.1TB SSD/节点

  + 配合 ILM（Index Lifecycle Management）：
    Hot（最近 7 天，SSD）→ Warm（8-30 天，HDD）→ Cold（31-90 天）→ Delete
```

### 读写比的影响

| 场景 | Replica 数 | 理由 |
|------|-----------|------|
| 写多读少（日志） | 0 或 1 | 副本越多写入越慢 |
| 读多写少（搜索） | 1 或 2 | 副本越多搜索吞吐越大（多个副本并行处理搜索请求） |
| 高可用要求 | 至少 1 | 容忍单节点故障 |

---

## 面试高频题与参考答案

### Q1：ES 写入慢怎么优化？说出 5 种方法

**答**：

第一，使用 _bulk 批量写入，每批 5-15MB。第二，调大 refresh_interval，大批量导入时设为 -1（导入完恢复），减少 Segment 创建。第三，Translog 设为 async 刷盘，减少 fsync 次数。第四，导入时临时把副本数设为 0，减少写入量（导入完恢复副本）。第五，合理的文档设计——减少字段数量、避免 nested 类型嵌套过多（每个嵌套对象是一个隐藏 Lucene 文档）。

额外方法：使用 Index Sorting 预排序配合查询的 early termination；控制 _bulk 并发数，避免 write 线程池 rejected。

### Q2：ES 查询慢怎么排查和优化？

**答**：排查步骤：先用慢查询日志定位具体的慢查询 DSL，然后用 profile API 分析查询在每个 Shard 上的各阶段耗时，找到瓶颈是在 query 阶段还是 fetch 阶段。

优化方向：第一，不需要打分的条件放 filter 而非 must（filter 不打分+可缓存）。第二，多租户场景用 routing 查询只查一个 Shard。第三，避免深度分页（from+size 改 search_after）。第四，避免高成本查询（wildcard 前缀通配、script 排序）。第五，_source 过滤只返回需要的字段。第六，只读索引做 force merge 合并 Segment。第七，设置 track_total_hits=false 允许提前终止。

### Q3：ES 堆内存为什么不能超过 32GB？

**答**：（见 8.3 节面试回答）

### Q4：如何做 ES 的容量规划？

**答**：三步法。第一步预估数据量：当前量 + 增长速率 × 保留周期，乘以膨胀系数（约 1.5-2 倍）。第二步算分片数：总数据量除以目标单 Shard 大小（10-50GB），再乘以 (1+副本数) 得到总 Shard 数。第三步算节点数：总 Shard 数除以单节点 Shard 上限（约 内存GB × 20），磁盘需预留约 50% 空间给 merge 操作。

还需考虑读写比——写多读少场景减少副本数，读多写少场景增加副本数提升搜索吞吐。日志类数据用按时间分索引 + ILM 做 Hot-Warm-Cold 分层存储。

---

## 动手实践

### 练习 1：对比不同写入配置的性能

```
# 1. 创建索引——默认配置
PUT /perf_test_default
{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0, "refresh_interval": "1s" },
  "mappings": { "properties": { "title": { "type": "text" }, "value": { "type": "integer" } } }
}

# 2. 创建索引——优化配置
PUT /perf_test_optimized
{
  "settings": { "number_of_shards": 1, "number_of_replicas": 0, "refresh_interval": "-1",
                "index.translog.durability": "async" },
  "mappings": { "properties": { "title": { "type": "text" }, "value": { "type": "integer" } } }
}

# 3. 批量写入测试数据到两个索引（用脚本生成 _bulk 请求）
# 观察两个索引的写入耗时差异

# 4. 恢复 refresh_interval
PUT /perf_test_optimized/_settings
{ "index.refresh_interval": "1s" }

# 5. 清理
DELETE /perf_test_default
DELETE /perf_test_optimized
```

### 练习 2：profile API 分析查询性能

```
# 使用阶段 4 的测试数据，或重新创建

# 1. 对比 must vs filter 的性能
GET /query_practice/_search
{
  "profile": true,
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "手机" } },
        { "term": { "status": "active" } },        // status 放 must
        { "range": { "price": { "gte": 3000 } } }  // price 放 must
      ]
    }
  }
}

GET /query_practice/_search
{
  "profile": true,
  "query": {
    "bool": {
      "must": [
        { "match": { "name": "手机" } }             // 只有搜索词放 must
      ],
      "filter": [
        { "term": { "status": "active" } },          // status 放 filter
        { "range": { "price": { "gte": 3000 } } }    // price 放 filter
      ]
    }
  }
}

# 对比两次 profile 中各查询组件的 time_in_nanos
```

### 练习 3：慢查询日志

```
# 1. 创建索引并开启慢查询日志
PUT /slowlog_test
{
  "settings": {
    "number_of_shards": 1,
    "number_of_replicas": 0,
    "index.search.slowlog.threshold.query.warn": "0ms",    // 设为 0ms，所有查询都记录
    "index.search.slowlog.threshold.query.info": "0ms"
  },
  "mappings": {
    "properties": { "name": { "type": "text" } }
  }
}

# 2. 写入一些数据
PUT /slowlog_test/_doc/1
{ "name": "test document for slow log" }

# 3. 执行查询
GET /slowlog_test/_search
{ "query": { "match": { "name": "test" } } }

# 4. 查看 ES 日志文件中的慢查询记录
# Docker 中：docker logs <es_container> | grep slowlog

# 5. 清理
DELETE /slowlog_test
```

---

## 本阶段总结

学完本阶段，你应该掌握了以下心智模型：

```
写入优化五板斧（按效果排序）：
  1. _bulk 批量写入（5-15MB/批）
  2. refresh_interval → -1（导入时）
  3. replica → 0（导入时）
  4. translog → async（可容忍少量丢失时）
  5. index sorting（预排序场景）

查询优化核心原则：
  不打分的条件 → filter（不打分+可缓存）
  多租户 → routing（只查一个 Shard）
  翻页 → search_after（不用 from+size）
  只读索引 → force merge（减少 Segment）
  不需要总数 → track_total_hits=false

JVM 铁律：
  堆内存 ≤ 50% 物理内存（留给 OS Page Cache）
  堆内存 ≤ ~31GB（CompressedOops）
  Xms = Xmx（避免动态调整）

OS 四必配：
  ulimit -n 65535+
  vm.max_map_count = 262144
  swappiness = 1 或 memory_lock
  磁盘用 SSD

诊断工具：
  慢查询日志 → 找到具体慢查询
  profile API → 分析查询耗时
  hot_threads → 定位 CPU 瓶颈
  _cat APIs → 集群/节点/索引/分片状态

容量规划三步法：
  数据量 → 分片数 → 节点数
  单 Shard 10-50GB | 磁盘预留 50% | 读写比决定副本数
```

**至此，阶段 6-8"懂原理"层全部完成！**

```
阶段 6  存储原理（Lucene 倒排索引、Segment 、写入链路、NRT）
阶段 7  集群架构（节点角色、分片路由、选主、脑裂、故障恢复）
阶段 8  性能调优（写入优化、查询优化、JVM、OS、监控诊断、容量规划）
  ↓
  你现在可以深入理解 ES 的"为什么"，并具备生产调优能力
  ↓
  接下来进入"能落地"层——将 ES 嵌入真实系统架构
```

**下一阶段**：阶段 9 数据同步与架构集成——面试几乎必问"数据怎么从 MySQL 同步到 ES"。同步双写、MQ 异步、Canal CDC、Logstash JDBC 各有什么优缺点？如何保证一致性？这是连接 ES 知识和系统架构能力的关键。
