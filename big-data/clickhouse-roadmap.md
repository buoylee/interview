# ClickHouse 学习路线

> 学习顺序:**Spark → Flink → ClickHouse**(本篇第 3 站)
> 前置:已学完 Spark、Flink,理解数据管道的上游处理
> 目标:掌握 OLAP 查询核心,能设计实时数仓的查询层
> 预计时间:2-3 周(比 Spark/Flink 概念少,但性能调优是大坑)

---

## 一、心智模型

### ClickHouse 是什么
**一句话**:ClickHouse 是**为 OLAP 查询而生的列式数据库**——存列不存行,算聚合时只读用到的列,再配上向量化执行,所以"查几十亿行常常秒级返回"。

### 和其他组件的关系
```
Kafka → Flink(实时计算)→  [ ClickHouse ] ← BI 看板 / API 查询
                               ↑
                           你在学的东西
```

### ClickHouse 的设计哲学(必须记住)
1. **一个查询榨干整台机器**:向量化 + 多线程,不追求高并发
2. **写多读少优化**:批量写入很快,单行 insert 会死
3. **不要 Update/Delete**:数据是不可变的,改数据靠"重建"
4. **读聚合,不读明细**:适合 SUM/COUNT/GROUP BY,不适合点查

**理解了这 4 条,你就懂了 ClickHouse 的一切取舍**。

---

## 二、分阶段学习路线

### 阶段 1:环境 + 快速上手(2 天)

**目标**:跑通 ClickHouse,体验"快"到底有多快

- [ ] **安装**
  - Docker 最快:`docker run -d --name ch -p 8123:8123 -p 9000:9000 clickhouse/clickhouse-server`
  - 或 `brew install clickhouse`

- [ ] **客户端**
  - `clickhouse-client`(CLI)
  - HTTP 接口(`curl localhost:8123`)
  - DBeaver / DataGrip 图形化

- [ ] **第一个表**
  - 导入官方示例数据集(如 `ontime`、`hits`)
  - 跑几个聚合查询,感受速度
  - 和 MySQL 做同样查询对比耗时

**产出**:能跑聚合查询,能感性理解 ClickHouse 的速度

---

### 阶段 2:存储引擎核心 - MergeTree(5-7 天,重中之重)

**目标**:理解 ClickHouse 为什么快,存储引擎是核心

- [ ] **列式存储原理** ⭐⭐⭐
  - 行存 vs 列存对比图
  - 为什么列存适合聚合:只读需要的列、压缩率高
  - 压缩算法:LZ4(默认,快)、ZSTD(压得狠)

- [ ] **MergeTree 家族概览**
  - `MergeTree`(基础)
  - `ReplacingMergeTree`(去重)
  - `SummingMergeTree`(预聚合 SUM)
  - `AggregatingMergeTree`(预聚合任意函数)
  - `CollapsingMergeTree` / `VersionedCollapsingMergeTree`(更新场景)
  - `ReplicatedMergeTree`(副本,生产必用)

- [ ] **MergeTree 核心结构** ⭐⭐⭐
  - **分区(PARTITION BY)**:通常按天/月
  - **排序键(ORDER BY)**:决定数据物理顺序,**查询性能的命脉**
  - **主键(PRIMARY KEY)**:稀疏索引,默认等于 ORDER BY
  - **Granule**:索引粒度(默认 8192 行一个标记)
  - **Data Part**:磁盘上的数据目录,后台 Merge

- [ ] **索引机制**
  - **稀疏主键索引**:不是每行都有索引,而是每 N 行一个标记
  - **跳数索引(Skipping Index)**:`minmax` / `set` / `bloom_filter`
  - 和 MySQL B+Tree 索引的本质区别

- [ ] **数据合并(Merge)**
  - 后台自动合并小 Part 成大 Part
  - 合并时机、合并策略
  - TTL 机制:自动删除过期数据

**产出**:能画出 MergeTree 的数据组织图,能解释排序键的选择原则

---

### 阶段 3:查询执行 - 为什么这么快(3-4 天)

**目标**:理解向量化执行,建立性能直觉

- [ ] **向量化执行**
  - 一次处理一批数据(默认 65536 行),不是一行一行
  - 利用 SIMD CPU 指令
  - 和传统 Volcano 模型的对比

- [ ] **多线程执行**
  - 单查询天然多核并行
  - `max_threads` 参数

- [ ] **查询执行计划**
  - `EXPLAIN PLAN` / `EXPLAIN PIPELINE` / `EXPLAIN ESTIMATE`
  - 看懂输出

- [ ] **函数与表达式**
  - ClickHouse 有超多内置函数,**比 MySQL 丰富得多**
  - `uniq` / `uniqExact` / `quantile` / `topK` 等分析函数
  - **HyperLogLog** 在 ClickHouse 里的实现

**产出**:能用 `EXPLAIN` 分析查询,能写高效的聚合 SQL

---

### 阶段 4:物化视图 & Projection(4-5 天,工程核心)

**目标**:掌握 ClickHouse 最重要的性能手段

- [ ] **物化视图(Materialized View)** ⭐⭐⭐
  - 预聚合常用查询,把结果存下来
  - 写入触发:源表插入数据时,视图自动更新
  - 和其他数据库物化视图的区别:**是"另一张表",不是虚拟表**
  - 常配合 `AggregatingMergeTree` + `AggregateFunction` 类型

- [ ] **Projection(22.3+)**
  - "表内置的物化视图",对用户透明
  - 查询时引擎自动选择
  - 比 MV 更简单,推荐新项目用

- [ ] **使用模式**
  - 原始表:明细数据,ReplicatedMergeTree
  - 物化视图:按小时/天预聚合
  - 查询时直接查视图,速度 10 倍+

**产出**:为一个明细表设计 3 个物化视图,解决不同查询模式

---

### 阶段 5:分布式 & 副本(3-4 天)

**目标**:理解生产环境的部署形态

- [ ] **ReplicatedMergeTree(副本)**
  - 通过 ZooKeeper(或 ClickHouse Keeper)协调
  - 多副本高可用
  - 写任意副本,自动同步

- [ ] **Distributed 表(分布式)**
  - 不存数据,只做路由
  - `ON CLUSTER` 建表语法
  - 写入:本地写或用 Distributed 表自动分发
  - 读取:并行查询所有分片,汇总结果

- [ ] **分片策略**
  - Hash 分片 / Random 分片
  - Sharding Key 的选择

- [ ] **ClickHouse Keeper**
  - 取代 ZooKeeper,官方推荐(更轻、更快)

**产出**:本地 Docker 搭 2 分片 2 副本集群

---

### 阶段 6:数据接入 & 对接生态(3-4 天)

**目标**:把 ClickHouse 接入真实数据管道

- [ ] **从 Kafka 导入**
  - **Kafka 引擎表**:ClickHouse 直接消费 Kafka(简单场景)
  - **Flink → ClickHouse**:生产推荐(用 flink-connector-clickhouse)
  - **批量写入最佳实践**:每次写 1w-10w 行,间隔 1s+

- [ ] **从 MySQL 同步**
  - `MaterializedMySQL` 引擎(实验性)
  - **主流方案**:MySQL → Flink CDC → ClickHouse

- [ ] **S3 / HDFS 外部表**
  - 直接查询 Parquet / CSV

- [ ] **写入性能**
  - 为什么"不要单行 INSERT"
  - `async_insert` 异步批量写入(21.11+)

**产出**:搭建 Flink → ClickHouse 实时链路

---

### 阶段 7:性能调优 & 运维(4-5 天,面试重点)

**目标**:能回答"ClickHouse 查询很慢,怎么排查?"

- [ ] **查询优化**
  - `system.query_log` 分析慢查询
  - 排序键设计原则
  - 避免 SELECT *,永远指定列
  - Prewhere 优化:`WHERE` 中低基数过滤提前执行
  - Bitmap / RoaringBitmap 在大规模去重中的应用

- [ ] **并发优化**
  - `max_concurrent_queries` 默认 100
  - 物化视图降查询压力
  - 前置 Redis 缓存

- [ ] **常见坑**
  - **小文件问题**:Part 太多触发 `Too many parts` 错误
  - **ZooKeeper 压力**:写入频繁导致 ZK 瓶颈 → 换 CH Keeper
  - **Merge 慢**:后台合并跟不上写入速度
  - **JOIN 性能差**:大表 JOIN 尽量避免,用字典(Dictionary)或物化视图

- [ ] **Dictionary(字典)**
  - 小维表常驻内存,JOIN 极快
  - 从 MySQL/HTTP/文件加载

- [ ] **监控**
  - `system.metrics` / `system.events` / `system.asynchronous_metrics`
  - Prometheus + Grafana 官方模板

**产出**:准备 5 个常见慢查询 Case 的优化思路

---

### 阶段 8:云原生 & 新特性(2 天)

**目标**:了解 2026 的最新进展

- [ ] **ClickHouse Cloud**
  - 官方托管服务,存算分离
  - 基于对象存储(S3)+ 本地缓存

- [ ] **存算分离架构**
  - SharedMergeTree(Cloud 引擎)
  - 本地集群也可通过 `S3 Disk` 实现冷热分离

- [ ] **Query Cache(23.x+)**
  - 结果缓存,终于弥补了并发短板

- [ ] **Parallel Replicas**
  - 单查询利用多副本并行,提升吞吐

---

## 三、实战项目建议

**项目 1:日志分析系统**
- 数据源:Nginx 日志(gb 级造数据)
- ClickHouse 建表 + 物化视图
- 实现:按时间/URL/状态码多维度聚合查询
- 和 Elasticsearch 做性能对比

**项目 2:实时用户行为分析**
- Flink(上游已学)清洗埋点数据 → Kafka
- ClickHouse 消费 + 物化视图预聚合
- 实现:漏斗分析、留存分析、路径分析

**项目 3:高并发查询改造**
- 用 Redis 做结果缓存
- ClickHouse 只处理缓存穿透
- 压测:从 50 QPS 提升到 2000 QPS

---

## 四、高频面试题清单

### 基础
1. ClickHouse 为什么查询快?(列存 + 向量化 + 多线程)
2. MergeTree 的核心机制是什么?
3. 分区(PARTITION BY)和排序键(ORDER BY)的区别?
4. ClickHouse 的主键索引和 MySQL 的区别?(稀疏 vs 稠密)
5. ClickHouse 为什么不适合 OLTP?

### 存储引擎
6. MergeTree 家族有哪些?各自场景?
7. ReplacingMergeTree 去重是实时的吗?
8. 数据合并(Merge)是什么时候发生的?
9. TTL 怎么工作?

### 物化视图
10. 物化视图原理?和普通视图区别?
11. `AggregatingMergeTree` 为什么要配合 `AggregateFunction`?
12. Projection 和 Materialized View 的区别?

### 分布式
13. Distributed 表和 Replicated 表的区别?
14. 写入 Distributed 表和本地表有什么区别?
15. 分布式查询的执行流程?
16. ClickHouse Keeper vs ZooKeeper?

### 性能
17. ClickHouse 并发能到多少?为什么不高?怎么优化?
18. `Too many parts` 错误怎么处理?
19. 大表 JOIN 怎么办?
20. 如何排查一个慢查询?

### 场景题
21. 10 亿条订单,设计一张 ClickHouse 表支持多维分析
22. C 端 1w QPS 查询怎么扛?
23. 每分钟 100w 条数据,怎么写入最合理?
24. ClickHouse 数据要做删除,但它不擅长,怎么办?

---

## 五、学习资源

### 官方文档(质量极高,必读)
- https://clickhouse.com/docs
- 重点:Engines(MergeTree 家族)、Query Optimization、Operations

### 博客
- ClickHouse 官方博客:https://clickhouse.com/blog
- Altinity 博客(深度技术文章)

### 书籍
- 《ClickHouse: The Definitive Guide》(2024, O'Reilly,最新)
- ClickHouse 官方 Tutorial

### 实战数据集
- 官方示例:`hits`(1 亿行网站访问日志)、`ontime`(航班数据)
- 都能从 `https://clickhouse.com/docs/en/getting-started/example-datasets/` 下载

---

## 六、检查点(每阶段结束自测)

- [ ] 能解释列式存储为什么快
- [ ] 能设计一张 MergeTree 表并说明排序键选择理由
- [ ] 能用物化视图 + AggregatingMergeTree 做预聚合
- [ ] 能搭建 2 分片 2 副本集群
- [ ] 能画出 Flink → ClickHouse 实时链路
- [ ] 能排查并优化一个慢查询
- [ ] 能回答 15 个以上面试题

---

## 七、学完三件套后你应该能

- [ ] 画出完整的**实时数仓架构图**(Kafka → Flink → ClickHouse)
- [ ] 回答"实时数仓怎么设计"这类系统设计题
- [ ] 独立搭建一套端到端的 Demo
- [ ] 深入理解批处理(Spark)、流处理(Flink)、查询(ClickHouse)的**各自边界**
- [ ] 在面试中横向对比同类产品(Spark vs Flink、ClickHouse vs Druid/Pinot)

---

**至此三件套完结。建议下一站:Iceberg(数据湖)或 Milvus(向量库,结合 LLM 方向)**
