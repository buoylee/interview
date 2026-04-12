# 阶段 7：集群架构与高可用（1 周）

> **目标**：理解 ES 集群的完整架构。学完本阶段后，你应该能说清节点角色划分、分片路由算法、选主流程、脑裂防护、写入一致性模型，以及节点故障后的恢复全过程。
>
> **前置依赖**：阶段 6（存储原理——Segment/Translog/写入链路，集群一致性建立在此之上）
>
> **为后续阶段铺路**：本阶段的分片规划、节点角色划分是阶段 8（性能调优）中容量规划和查询优化的直接基础。
>
> **视角转换**：阶段 6 看的是**单个 Shard 内部**（Segment 怎么写、怎么读）；本阶段从**集群全局**看：多个 Shard 如何分布、多个节点如何协作、故障时如何恢复。

---

## 7.1 节点角色详解

ES 集群中的每个节点可以承担一个或多个角色。生产环境推荐**角色分离**，避免一个节点同时做太多事情。

### 五种核心角色

```
┌────────────────────────────── ES 集群 ─────────────────────────────────┐
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │ Master Node  │  │ Master Node  │  │ Master Node  │  ← 3 个专用 Master│
│  │ (Eligible)   │  │ (Eligible)   │  │ ★ Active ★   │     管理集群状态  │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                 │
│  │  Data Node   │  │  Data Node   │  │  Data Node   │  ← N 个 Data    │
│  │ [Shard 0-P]  │  │ [Shard 1-P]  │  │ [Shard 2-P]  │     存储+查询   │
│  │ [Shard 1-R]  │  │ [Shard 2-R]  │  │ [Shard 0-R]  │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                 │
│                                                                        │
│  ┌──────────────┐  ┌──────────────┐                                   │
│  │ Coordinating │  │ Coordinating │  ← M 个专用 Coordinating          │
│  │    Node      │  │    Node      │    接收请求、路由、汇总             │
│  └──────────────┘  └──────────────┘                                   │
│                                                                        │
└────────────────────────────────────────────────────────────────────────┘
```

| 角色 | 职责 | 资源消耗 | 配置 |
|------|------|---------|------|
| **Master-eligible** | 参与选主；当选后管理集群状态（索引创建删除、分片分配决策） | CPU 低，内存低 | `node.roles: [master]` |
| **Data** | 存储数据，执行 CRUD、搜索、聚合 | CPU/内存/IO 密集 | `node.roles: [data]` |
| **Coordinating** | 接收客户端请求，路由到正确的 Shard，汇总各 Shard 结果 | CPU/内存（汇总时） | `node.roles: []`（所有角色去掉） |
| **Ingest** | 执行 Ingest Pipeline（写入前的数据预处理） | CPU | `node.roles: [ingest]` |
| **ML** | 执行机器学习任务（异常检测等） | CPU/内存 | `node.roles: [ml]` |

> 默认情况下，一个节点同时是所有角色。开发环境可以这样用，但生产环境不行。

### 生产集群推荐架构

```
3 个专用 Master + N 个 Data + M 个 Coordinating

为什么 Master 要专用？
  Master 管理集群状态，如果同时做 Data 节点的查询/聚合，
  CPU/内存压力大时可能影响集群管理 → 整个集群不稳定

为什么要独立 Coordinating？
  大查询的汇总阶段消耗大量内存（特别是深度分页和大聚合），
  独立 Coordinating 避免冲击 Data 节点
```

### 为什么 Master 要奇数个？

```
法定人数（Quorum）= N/2 + 1

3 个 Master → 法定人数 2 → 最多容忍 1 个宕机
5 个 Master → 法定人数 3 → 最多容忍 2 个宕机
7 个 Master → 法定人数 4 → 最多容忍 3 个宕机

偶数个有什么问题？
4 个 Master → 法定人数 3 → 最多容忍 1 个宕机（和 3 个一样！浪费了一台机器）
6 个 Master → 法定人数 4 → 最多容忍 2 个宕机（和 5 个一样！）

→ 偶数个不如少一台用奇数个，容忍力一样但更省资源
→ 生产中 3 个 Master 最常见（容忍 1 个宕机足够了）
```

---

## 7.2 分片（Shard）机制

### 路由算法

```
shard_num = hash(_routing) % number_of_primary_shards
```

- 默认 `_routing = _id`（文档 ID）
- 所以**知道文档 ID 就能算出它在哪个 Shard**——不需要广播查询所有 Shard

```
示例：3 个 Primary Shard

文档 _id = "abc123"
  → hash("abc123") = 78654321（某个整数）
  → 78654321 % 3 = 0
  → 路由到 Shard 0

文档 _id = "xyz789"
  → hash("xyz789") = 12345678
  → 12345678 % 3 = 2
  → 路由到 Shard 2
```

### 为什么 Primary Shard 数量创建后不可变？

```
假设原来 3 个 Shard：hash("abc123") % 3 = 0 → 文档在 Shard 0

如果改成 5 个 Shard：hash("abc123") % 5 = 1 → 去 Shard 1 找

但文档实际还在 Shard 0 → 找不到了！

→ 改变 Shard 数量就打破了路由映射关系
→ 所有文档都要重新路由 → 这就是 Reindex
→ 所以 primary shard 数量创建后不可变
```

> 这也是阶段 2 强调"Mapping 设计必须提前"的另一个原因——分片数也要提前规划好。

### 自定义 routing

```json
// 写入时指定 routing
PUT /orders/_doc/1?routing=user_001
{ "user_id": "user_001", "order_no": "ORD-2024-001" }

// 同一用户的所有订单都路由到同一个 Shard
PUT /orders/_doc/2?routing=user_001
{ "user_id": "user_001", "order_no": "ORD-2024-002" }
```

自定义 routing 的好处：
- **查询性能提升**：`GET /orders/_search?routing=user_001` 只查一个 Shard，不广播
- **聚合精确性**：同一维度的数据在同一 Shard 上，terms 聚合精确
- **多租户场景**：每个租户的数据通过 routing 隔离在指定 Shard

### 分片数量规划

| 规则 | 说明 |
|------|------|
| 单 Shard 推荐 10-50GB | 太小浪费资源，太大恢复慢 |
| 每个节点总 Shard 数：内存(GB) × 20 以内 | 每个 Shard 有 Lucene 固定开销 |
| 经验公式 | `分片数 ≈ 预估数据量 / 单 Shard 目标大小` |

**分片过多的问题：**
- 每个 Shard 都有 Lucene 内存开销（Segment 元数据、FST、缓存等）
- Master 需要管理所有 Shard 的状态 → Shard 数量越多，集群状态越大，Master 压力越大
- 搜索时协调节点要合并所有 Shard 的结果

**分片过少的问题：**
- 单个 Shard 过大（>50GB） → 恢复几十 GB 的 Shard 非常耗时
- 无法水平扩展 → 1 个 Shard 只能在 1 个节点上
- 查询并行度低

> **面试怎么答**："分片数设置多少合适？"
>
> 单个 Shard 建议 10-50GB。用预估数据量除以目标 Shard 大小得到分片数。太多的问题是每个 Shard 有内存固定开销、Master 管理压力大、搜索合并成本高；太少的问题是单 Shard 过大恢复慢、无法水平扩展。还要考虑副本数——总分片数 = primary × (1 + replica)。比如 100GB 数据、目标每 Shard 25GB → 4 个 Primary、1 个 Replica → 总共 8 个 Shard。

---

## 7.3 节点发现与选主

### ES 7.x+ 选主机制

ES 7.0 起引入了新的选主机制，取代了旧的 Zen Discovery，核心改进是引入了 **Voting Configuration**。

```
旧版（ES 6.x-）：
  手动配置 discovery.zen.minimum_master_nodes = master_nodes / 2 + 1
  配错了 → 脑裂风险

新版（ES 7.x+）：
  Voting Configuration 自动管理参与投票的节点集合
  不再需要手动配置 minimum_master_nodes → 大幅降低脑裂风险
```

### 选主流程

```
1. 节点启动 → 通过 seed_hosts 配置发现其他节点
   discovery.seed_hosts: ["node1:9300", "node2:9300", "node3:9300"]

2. Master-eligible 节点互相交换信息

3. 发起选举 → 每个节点投票
   - 默认投给 cluster state 版本最高的节点（数据最新）
   - 版本相同时投给节点 ID 最小的

4. 获得法定人数（majority）票的节点当选 Active Master

5. Active Master 向所有节点同步 Cluster State
```

### Cluster State（集群状态）

集群状态是 Master 维护的**元数据**，包含：

```
Cluster State：
  ├── 集群名称和节点列表
  ├── 所有索引的 Mapping
  ├── 所有索引的 Settings（分片数、副本数等）
  ├── 分片分配表（哪个 Shard 在哪个节点）
  ├── Index Template
  ├── Ingest Pipeline
  └── ...
```

- Master 是 Cluster State 的**唯一修改者**
- 每次变更（创建索引、修改 Mapping、分片重分配等）Master 发布新版本到所有节点
- **频繁变更集群状态会成为瓶颈**——所以不要频繁创建/删除索引（如一秒一个）

---

## 7.4 脑裂（Split Brain）

### 什么是脑裂？

```
正常状态：
  ┌─────┐  ┌─────┐  ┌─────┐
  │Node1│──│Node2│──│Node3│
  │     │  │★ M ★│  │     │
  └─────┘  └─────┘  └─────┘
  Node2 是 Active Master

网络分区：
  ┌─────┐  │  ┌─────┐  ┌─────┐
  │Node1│  │  │Node2│──│Node3│
  │     │  │  │★ M ★│  │     │
  └─────┘  │  └─────┘  └─────┘
            ↑ 网络隔离

  Node1 联系不到 Master → 认为 Master 挂了 → 自己选自己为 Master

  结果：两个 Master！
  ┌─────┐     ┌─────┐  ┌─────┐
  │Node1│     │Node2│──│Node3│
  │★ M ★│     │★ M ★│  │     │
  └─────┘     └─────┘  └─────┘

  两个 Master 独立接受写入 → 数据不一致 → 灾难！
```

### ES 7.x+ 如何防止脑裂

```
Voting Configuration 自动维护法定人数

3 个 Master-eligible 节点 → 法定人数 = 2（需要至少 2 票才能当选）

网络分区后：
  Node1 独自一人 → 只有 1 票 → 不够法定人数 → 不能选主
  Node2 + Node3 → 2 票 → 达到法定人数 → Node2 继续当 Master

  → 不会出现两个 Master → 脑裂被阻止
```

> **ES 6.x 及更早版本**需要手动配置 `discovery.zen.minimum_master_nodes = master_nodes / 2 + 1`。配错了（比如设成 1）就可能脑裂。7.x+ 自动管理，这个风险被大幅降低。

---

## 7.5 写入一致性模型

### In-Sync Copies

ES 维护一个 **in-sync copies** 集合——与 Primary 保持数据同步的所有副本（包括 Primary 本身）。

```
正常状态：in-sync = {Primary, Replica-1, Replica-2}

写入流程：
  Client → Primary → 转发到 Replica-1 和 Replica-2
         ← Replica-1 确认
         ← Replica-2 确认
         ← Primary 返回成功

如果 Replica-2 持续写入失败：
  → Master 把 Replica-2 从 in-sync 集合中移除
  → in-sync = {Primary, Replica-1}
  → 后续写入只需 Primary + Replica-1 确认即可

Replica-2 恢复后：
  → 通过 Peer Recovery 追赶数据（translog 或 segment copy）
  → 追赶完毕 → 重新加入 in-sync 集合
```

### 写入确认机制

```json
PUT /products/_doc/1?wait_for_active_shards=2
{ "name": "test" }
```

| wait_for_active_shards | 含义 | 一致性 | 可用性 |
|----------------------|------|--------|--------|
| `1`（默认） | 只需 Primary 活跃 | 最弱 | 最高 |
| `2` | Primary + 至少 1 个 Replica 活跃 | 中等 | 中等 |
| `all` | 所有 in-sync 副本活跃 | 最强 | 最低（任一副本宕机就拒绝写入） |

注意：`wait_for_active_shards` 只是**等待这些分片处于活跃状态**后才执行写入。写入 Primary 后转发到 Replica 的过程是**异步**的。它**不保证**所有 Replica 都写入成功后才返回（那是 `all` 的语义）。

> **面试怎么答**："ES 如何保证数据不丢失？"
>
> 多层保护。第一层：Translog（WAL）——写入时同步写 translog 并 fsync，断电后从 translog 回放。第二层：副本机制——Primary 写入后转发到所有 in-sync Replica，数据至少两份。第三层：wait_for_active_shards 控制写入需要多少副本活跃。第四层：in-sync copies 机制——持续写入失败的副本会被移出 in-sync 集合，恢复后通过 peer recovery 追赶数据再重新加入。但 ES 不是强一致性系统——写入 Primary 后、Replica 确认前如果 Primary 宕机，可能丢少量数据。

---

## 7.6 分片分配与再平衡

### Shard Allocation 策略

Master 负责决定每个 Shard 分配到哪个节点。分配遵循的规则：

```
规则 1：Primary 和 Replica 不在同一节点
  → 防止节点宕机时同时丢失主副本

规则 2：尽量均匀分布到各节点
  → 负载均衡

规则 3：遵守 Allocation Awareness（机架感知）
  → Primary 和 Replica 分配到不同机架/可用区

规则 4：遵守 Allocation Filtering（过滤规则）
  → 可限制某些索引只分配到某些节点
```

### Shard Allocation Awareness——机架感知

```yaml
# 节点配置（每个节点标记自己的机架/可用区）
node.attr.rack_id: rack_1    # Node 1, 2 在 rack_1
node.attr.rack_id: rack_2    # Node 3, 4 在 rack_2

# 索引配置
cluster.routing.allocation.awareness.attributes: rack_id
```

效果：ES 会把 Primary 和 Replica 分配到**不同的 rack**，即使同一个 rack 里有多个节点。这样一个机架整体故障也不会同时丢主副本。

### Allocation Filtering——控制分片分配

```json
// 把索引 logs-2024-01 只分配到 "warm" 标记的节点
PUT /logs-2024-01/_settings
{
  "index.routing.allocation.require.data_tier": "warm"
}
```

配合 Hot-Warm-Cold 架构使用：
- Hot 节点（SSD）：存放最近的活跃数据
- Warm 节点（HDD）：存放较旧但仍需查询的数据
- Cold 节点（大容量 HDD）：存放归档数据，很少查询

### 再平衡触发条件

- 新节点加入集群 → 分片迁移到新节点
- 节点离开集群 → 丢失的副本在其他节点上重建
- 新建索引 → 分片分配到负载低的节点
- 手动触发：`POST /_cluster/reroute` API

---

## 7.7 故障恢复

### 节点宕机后会发生什么？

```
初始状态：3 Data 节点，索引 3 分片 1 副本

  Node 1          Node 2          Node 3
  ┌──────┐       ┌──────┐       ┌──────┐
  │S0-P  │       │S1-P  │       │S2-P  │
  │S1-R  │       │S2-R  │       │S0-R  │
  └──────┘       └──────┘       └──────┘

集群状态：🟢 Green

──────── Node 2 宕机 ────────

  Node 1          Node 2          Node 3
  ┌──────┐       ┌──────┐       ┌──────┐
  │S0-P  │       │ DEAD │       │S2-P  │
  │S1-R  │       │      │       │S0-R  │
  └──────┘       └──────┘       └──────┘

步骤 1：Master 检测到 Node 2 离线（默认超时 30s）
步骤 2：S1-P 丢失 → S1-R (Node 1) promote 为新的 S1-P
        S2-R 丢失 → S2-P (Node 3) 没有副本了

集群状态：🟡 Yellow（所有 Primary 可用，但部分 Replica 缺失）

  Node 1          Node 3
  ┌──────┐       ┌──────┐
  │S0-P  │       │S2-P  │
  │S1-P ★│       │S0-R  │
  └──────┘       └──────┘

步骤 3：Master 在剩余节点上创建新的 Replica
        → S1-R → Node 3
        → S2-R → Node 1

  Node 1          Node 3
  ┌──────┐       ┌──────┐
  │S0-P  │       │S2-P  │
  │S1-P  │       │S0-R  │
  │S2-R ★│       │S1-R ★│
  └──────┘       └──────┘

步骤 4：新 Replica 通过 Peer Recovery 从 Primary 复制数据
        → 使用 translog 回放（增量）或 segment copy（全量）

集群状态：🟢 Green（恢复完成）
```

### Peer Recovery

新 Replica 从 Primary 获取数据的过程：

```
阶段 1：File-based Recovery（全量）
  Primary 把所有 Segment 文件复制给新 Replica

阶段 2：Translog-based Recovery（增量）
  复制过程中新写入的数据通过 Translog 回放

优化（ES 7.x+）：
  如果新 Replica 对应的旧节点恢复了（还保留着 Segment 文件）
  → ES 优先让旧节点作为 Replica → 只需 translog 增量恢复
  → 大幅减少恢复时间和网络传输
```

### 集群健康状态

```
GET /_cluster/health

🟢 Green：所有 Primary + 所有 Replica 都正常分配
🟡 Yellow：所有 Primary 正常，部分 Replica 未分配
           → 搜索正常、数据不丢、但冗余度不足
           → 单节点集群永远是 Yellow（P 和 R 不能在同一节点）
🔴 Red：部分 Primary 未分配
        → 部分数据不可搜索、有数据丢失风险
        → 需要立即处理！
```

> **面试怎么答**："一个节点宕机后会发生什么？恢复流程是怎样的？"
>
> Master 检测到节点离线后（默认 30 秒），首先将该节点上的 Primary Shard 的对应 Replica promote 为新 Primary，保证搜索不中断，此时集群从 Green 变为 Yellow（Primary 都在但部分 Replica 缺失）。然后 Master 在其他节点上创建新的 Replica，新 Replica 通过 Peer Recovery 从 Primary 复制数据——先复制 Segment 文件（全量），再回放复制期间的 Translog（增量）。恢复完成后集群回到 Green。如果宕机的节点恢复上线且还保留着数据，ES 会优先让它作为 Replica 并只做增量恢复，减少网络传输。

---

## 面试高频题与参考答案

### Q1：ES 如何保证数据不丢失？

**答**：（见 7.5 节面试回答）

### Q2：分片数设置多少合适？设置太多或太少有什么问题？

**答**：（见 7.2 节面试回答）

### Q3：Primary Shard 数量为什么创建后不可改？

**答**：因为文档路由使用 `hash(_routing) % number_of_primary_shards` 算法。如果改变分母（分片数），同一个 _routing 值算出的 shard 编号就变了，已有数据的路由映射全部失效，查询时去新的 shard 找不到文档。要改变分片数只能创建新索引并 Reindex。这也是为什么生产中要提前规划好分片数量，结合阶段 2 的 Index Template 和 Alias 来做索引管理。

### Q4：ES 如何避免脑裂？

**答**：脑裂是网络分区导致集群中出现两个 Master。ES 7.x+ 引入了 Voting Configuration 自动管理法定人数（quorum）来防止脑裂。选主需要获得法定人数（majority = N/2 + 1）的票数。3 个 Master-eligible 节点时法定人数是 2，网络分区后少数派一侧只有 1 票无法选主，多数派一侧有 2 票继续正常运作。ES 6.x 及之前需要手动配置 `minimum_master_nodes`，配置错误会导致脑裂风险。

### Q5：一个节点宕机后会发生什么？恢复流程是怎样的？

**答**：（见 7.7 节面试回答）

### Q6：集群状态 Red/Yellow/Green 分别代表什么？

**答**：Green 表示所有 Primary 和 Replica 分片都正常分配，集群完全健康。Yellow 表示所有 Primary 正常但部分 Replica 未分配，数据可以正常搜索和写入但冗余度不足，单节点集群永远是 Yellow。Red 表示部分 Primary 未分配，意味着部分索引的数据不可搜索且有数据丢失风险，需要立即排查处理。

常见的 Yellow 场景：新创建了副本但还在恢复中、某节点短暂离线导致副本未分配。常见的 Red 场景：数据磁盘满了导致 Shard 无法分配、多个节点同时宕机导致某些 Primary 丢失。

---

## 动手实践

### 练习 1：搭建 3 节点集群并观察

```yaml
# docker-compose.yml
version: '3.8'
services:
  es01:
    image: elasticsearch:8.12.0
    environment:
      - node.name=es01
      - cluster.name=practice-cluster
      - discovery.seed_hosts=es02,es03
      - cluster.initial_master_nodes=es01,es02,es03
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9200:9200"
    networks:
      - esnet

  es02:
    image: elasticsearch:8.12.0
    environment:
      - node.name=es02
      - cluster.name=practice-cluster
      - discovery.seed_hosts=es01,es03
      - cluster.initial_master_nodes=es01,es02,es03
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9201:9200"
    networks:
      - esnet

  es03:
    image: elasticsearch:8.12.0
    environment:
      - node.name=es03
      - cluster.name=practice-cluster
      - discovery.seed_hosts=es01,es02
      - cluster.initial_master_nodes=es01,es02,es03
      - xpack.security.enabled=false
      - "ES_JAVA_OPTS=-Xms512m -Xmx512m"
    ports:
      - "9202:9200"
    networks:
      - esnet

  kibana:
    image: kibana:8.12.0
    environment:
      - ELASTICSEARCH_HOSTS=http://es01:9200
      - xpack.security.enabled=false
    ports:
      - "5601:5601"
    networks:
      - esnet

networks:
  esnet:
    driver: bridge
```

```
# 启动后，在 Kibana 或命令行中：

# 1. 查看节点列表和角色
GET /_cat/nodes?v

# 2. 查看集群健康状态
GET /_cat/health?v

# 3. 查看 Master 是谁
GET /_cat/master?v
```

### 练习 2：观察分片分布

```
# 1. 创建 3 分片 1 副本的索引
PUT /cluster_test
{
  "settings": {
    "number_of_shards": 3,
    "number_of_replicas": 1
  },
  "mappings": {
    "properties": {
      "name": { "type": "keyword" }
    }
  }
}

# 2. 查看分片在节点间的分布
GET /_cat/shards/cluster_test?v
# 观察：3 个 Primary 和 3 个 Replica 分布在 3 个节点上
# 注意：Primary 和 Replica 不在同一节点

# 3. 写入数据
POST /_bulk
{"index": {"_index": "cluster_test", "_id": "1"}}
{"name": "doc_1"}
{"index": {"_index": "cluster_test", "_id": "2"}}
{"name": "doc_2"}
{"index": {"_index": "cluster_test", "_id": "3"}}
{"name": "doc_3"}

# 4. 查看路由——每个文档在哪个 Shard
# 用 _search_shards API 查看路由信息
GET /cluster_test/_search_shards?routing=doc_1

# 或直接看所有分片的文档分布
GET /_cat/shards/cluster_test?v
```

### 练习 3：模拟节点故障 + 观察恢复

```
# 1. 确认集群 Green
GET /_cat/health?v

# 2. 停掉 es03 节点
# 在 Docker 中执行：docker stop <es03_container_id>

# 3. 持续观察集群状态变化
GET /_cat/health?v
# 预期：Green → Yellow（es03 上的 Primary 被 promote，Replica 缺失）

# 4. 观察分片重分配
GET /_cat/shards/cluster_test?v
# 预期：es03 的分片消失，部分 Replica 标记为 UNASSIGNED
# 等待一会儿：新 Replica 在 es01 或 es02 上创建

# 5. 等恢复完成
GET /_cat/health?v
# 预期：Yellow → Green

# 6. 重启 es03
# docker start <es03_container_id>

# 7. 观察 es03 重新加入后的分片再平衡
GET /_cat/shards/cluster_test?v
# 预期：部分分片迁移回 es03，实现均衡

# 8. 清理
DELETE /cluster_test
```

---

## 本阶段总结

学完本阶段，你应该掌握了以下心智模型：

```
节点角色（生产推荐）：
  3 专用 Master（奇数个，法定人数防脑裂）
  + N 个 Data（存储+查询，CPU/内存/IO 密集）  
  + M 个 Coordinating（接收请求、路由、汇总）

分片机制：
  路由公式：hash(_routing) % primary_shards
  Primary 数量不可变（改了路由就乱）
  单 Shard 建议 10-50GB
  自定义 routing → 查询只查一个 Shard

选主与防脑裂：
  ES 7.x+：Voting Configuration 自动管理法定人数
  法定人数 = N/2 + 1 → 3 Master 容忍 1 宕机

写入一致性：
  Primary 写入 + 转发到 in-sync Replica
  wait_for_active_shards 控制确认级别
  写入失败的 Replica → 移出 in-sync → 恢复后 peer recovery 追赶

故障恢复流程：
  节点宕机 → Replica promote → 创建新 Replica → Peer Recovery
  Green → Yellow → Peer Recovery → Green

集群健康：
  Green = 全正常  |  Yellow = Primary 在但 Replica 缺  |  Red = Primary 缺，紧急！
```

**下一阶段**：阶段 8 性能调优——你现在同时掌握了存储原理（阶段 6）和集群架构（阶段 7），可以真正理解每一条调优建议"为什么有效"了。写入优化（bulk size、refresh_interval、translog async）、查询优化（filter 缓存、routing、force merge）、JVM 调优（堆内存两条红线）、容量规划——都是基于前两个阶段的原理。
