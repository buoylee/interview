# Apache Flink 学习路线

> 学习顺序:**Spark → Flink → ClickHouse**(本篇第 2 站)
> 前置:已学完 [Spark 路线](./spark-roadmap.md),理解分布式计算基本概念
> 目标:掌握真·流处理的核心机制,能独立搭建实时数仓
> 预计时间:3-4 周

---

## 一、心智模型(和 Spark 的本质区别)

### Flink 是什么
**一句话**:Flink 是**以流为核心**的分布式计算引擎——数据一来就处理,不等攒批。

### Flink 和 Spark 的根本差异

| 维度 | Spark(Structured Streaming) | Flink |
|---|---|---|
| 本质 | **批是第一公民**,流是"小批量" | **流是第一公民**,批是"有界流" |
| 处理模式 | 微批(Micro-batch) | 真流(Event-driven) |
| 延迟 | 秒级 | 毫秒级 |
| 状态管理 | 较弱 | **核心竞争力** |
| 窗口 | 简单窗口 | 支持复杂窗口、CEP |

**一张图记住**:
```
Spark:  [批][批][批][批] → 一小块一小块处理
Flink:  →→→→→→→→→→→→    → 数据一个一个流过去
```

### 学 Flink 最大的门槛
**抽象概念多**:State、Watermark、Checkpoint、Time Semantics、CEP...
→ 千万别跳过概念直接写代码,**理解概念本身就是核心**。

---

## 二、分阶段学习路线

### 阶段 1:环境 + 第一个流任务(2-3 天)

**目标**:跑通 Flink,理解"流"到底长什么样

- [ ] **环境搭建**
  - 本地安装 Flink(`brew install apache-flink` 或 Docker)
  - 启动本地集群:`start-cluster.sh`
  - 访问 Flink Web UI(http://localhost:8081)

- [ ] **第一个任务:WordCount Streaming**
  - 用 `socketTextStream` 从 `nc -lk 9999` 读数据
  - 实现实时 WordCount
  - 在 Web UI 看任务状态、Metrics

- [ ] **架构核心组件**
  - JobManager(大脑)
  - TaskManager(工人)
  - Slot(并行度单位)
  - 理解和 Spark 的 Driver/Executor 对应关系

**产出**:能用 DataStream API 实现流式 WordCount

---

### 阶段 2:DataStream API 核心(5-7 天)

**目标**:掌握 Flink 最核心的 API

- [ ] **数据源 & 输出**
  - Source:Kafka、File、Socket、自定义
  - Sink:Kafka、JDBC、Elasticsearch、ClickHouse
  - 新版 `Source` / `Sink` API(Flink 1.14+)

- [ ] **基础转换算子**
  - `map` / `flatMap` / `filter`(无状态)
  - `keyBy`:按 key 分组,**流处理的核心操作**
  - `reduce` / `aggregate`:有状态聚合

- [ ] **Time Semantics(时间语义)** ⭐⭐⭐
  - **Event Time**:数据自带的时间(业务时间)
  - **Processing Time**:数据到达 Flink 的时间
  - **Ingestion Time**:进入 Flink Source 的时间
  - **面试必考**:为什么用 Event Time?

- [ ] **Watermark(水位线)** ⭐⭐⭐
  - 解决"数据乱序"问题
  - 核心思路:"我认为 T 时刻之前的数据都到齐了"
  - 如何生成 Watermark
  - Watermark 和窗口触发的关系

- [ ] **Window(窗口)** ⭐⭐⭐
  - **Tumbling Window**(滚动):不重叠
  - **Sliding Window**(滑动):有重叠
  - **Session Window**(会话):不活跃超时切分
  - **Global Window**:需自定义触发器
  - 窗口触发时机:Watermark 越过窗口结束时间

**产出**:能用 Flink 实现"每 5 分钟统计一次 Top 10 商品"

---

### 阶段 3:State(状态) - Flink 的灵魂(4-5 天)

**目标**:理解 Flink 为什么能做到真正的流处理

- [ ] **为什么需要 State**
  - 流处理是**持续运行**的,需要记住历史
  - 例子:累计 GMV、去重、连续登录检测

- [ ] **State 类型**
  - **Keyed State**(基于 `keyBy` 之后):
    - `ValueState` / `ListState` / `MapState` / `ReducingState` / `AggregatingState`
  - **Operator State**:算子级别的状态(较少用)

- [ ] **State Backend(状态后端)**
  - `MemoryStateBackend`:小状态、测试用
  - `FsStateBackend`:内存 + 文件系统(旧)
  - `RocksDBStateBackend`:磁盘,可存超大状态(生产首选)

- [ ] **State TTL**
  - 自动清理过期状态,防止状态无限增长

**产出**:用 `ValueState` 实现"连续 3 次登录失败告警"

---

### 阶段 4:Checkpoint & 容错(4-5 天,面试重点)

**目标**:理解 Flink 的容错核心,能回答 Exactly-Once

- [ ] **Checkpoint 机制** ⭐⭐⭐
  - 定期给所有算子状态拍快照
  - 失败后从最近一次 Checkpoint 恢复
  - **Chandy-Lamport 算法** 的应用(Barrier 对齐)

- [ ] **Barrier 对齐**
  - Barrier 在流中传播,算子收齐后触发快照
  - 对齐 vs 非对齐 Checkpoint(1.11+)

- [ ] **Savepoint**
  - 手动触发的 Checkpoint
  - 用于任务升级、迁移

- [ ] **Exactly-Once 语义** ⭐⭐⭐
  - Checkpoint 保证 Flink 内部 Exactly-Once
  - **端到端 Exactly-Once** 需要 Source 和 Sink 配合
  - Kafka Source(offset 存入 Checkpoint)+ Kafka Sink(两阶段提交)

- [ ] **Restart Strategy**
  - Fixed-delay / Failure-rate / Exponential-delay

**产出**:能画出 Checkpoint Barrier 对齐的时序图,解释端到端 Exactly-Once

---

### 阶段 5:Flink SQL(3-4 天)

**目标**:掌握工作中最常用的 API,**90% 实时数仓用 SQL 写**

- [ ] **基础**
  - `CREATE TABLE` 定义源/目标表(connector 机制)
  - `SELECT` 查询、`INSERT INTO` 写入
  - 时间属性、Watermark 在 DDL 中定义

- [ ] **流 SQL 特有概念**
  - **动态表(Dynamic Table)**:流 ↔ 表的对偶
  - **持续查询(Continuous Query)**:查询持续输出
  - **Changelog Stream**:INSERT / UPDATE / DELETE

- [ ] **窗口 TVF(Table-Valued Function)**
  - `TUMBLE` / `HOP` / `CUMULATE`
  - Flink 1.13+ 的新窗口语法,**比老 SQL 清晰很多**

- [ ] **Join**
  - Regular Join(状态会膨胀)
  - Interval Join(时间区间 Join)
  - Lookup Join(维表 Join,**实时数仓必用**)
  - Window Join

**产出**:用 Flink SQL 搭一个"实时订单大屏"Demo

---

### 阶段 6:CEP + 高级特性(3-4 天)

**目标**:了解 Flink 独特能力,区分于其他流引擎

- [ ] **CEP(Complex Event Processing)**
  - 检测复杂事件模式
  - 场景:连续 5 次登录失败、风控规则

- [ ] **Side Output(侧输出流)**
  - 一个流分流到多个下游

- [ ] **Async I/O**
  - 异步访问外部系统(数据库、HTTP)
  - 避免同步 IO 成为瓶颈

- [ ] **Broadcast State**
  - 规则动态下发(风控规则更新)

**产出**:用 CEP 实现一个简单的欺诈检测

---

### 阶段 7:生产实战(3-4 天)

**目标**:理解真实生产环境的坑

- [ ] **监控与运维**
  - Flink Metrics + Prometheus + Grafana
  - 反压(Backpressure)如何排查
  - Checkpoint 失败怎么办

- [ ] **性能调优**
  - 并行度设置(Slot、Task Manager 数量)
  - State Backend 调优(RocksDB 参数)
  - 网络缓冲调优

- [ ] **部署方式**
  - Standalone / YARN / **Kubernetes**(现代首选)
  - Flink on K8s Operator

- [ ] **实时数仓架构**
  - Kafka → Flink → Kafka(分层,ODS/DWD/DWS)
  - Flink CDC:直接同步 MySQL Binlog

**产出**:画出完整实时数仓架构图

---

## 三、实战项目建议

**项目 1:实时 PV/UV 统计**
- Kafka 模拟用户行为日志
- Flink SQL 按分钟窗口统计 PV/UV
- 结果写入 ClickHouse,前端轮询展示

**项目 2:实时风控**
- 用 CEP 检测"5 分钟内 3 次转账 + 金额 > 阈值"
- Side Output 输出告警流

**项目 3:实时数仓(高级)**
- MySQL → Flink CDC → Kafka(ODS)
- Flink SQL 清洗 → Kafka(DWD)
- Flink SQL 聚合 → ClickHouse(DWS/ADS)

---

## 四、高频面试题清单

### 核心概念
1. Flink 和 Spark Streaming 的区别?
2. Event Time vs Processing Time,为什么用 Event Time?
3. Watermark 是什么?怎么生成?
4. 三种窗口(Tumbling / Sliding / Session)的区别?
5. Flink 的 State 有哪些类型?

### 容错
6. Checkpoint 机制是怎么工作的?
7. Barrier 对齐是什么?为什么需要?
8. Flink 怎么做到端到端 Exactly-Once?
9. Checkpoint 和 Savepoint 的区别?

### Flink SQL
10. 动态表是什么?和普通表的区别?
11. Lookup Join 和 Regular Join 的区别?什么场景用?
12. Flink SQL 怎么处理 Changelog(CDC 数据)?

### 调优
13. 反压怎么排查?
14. 状态太大导致 Checkpoint 超时怎么办?
15. 数据倾斜在 Flink 里怎么处理?
16. 并行度怎么设置?

### 场景题
17. 如何实现"每分钟 UV Top10"?
18. 乱序数据到了怎么处理?
19. Flink 任务挂了,数据会丢吗?重复吗?
20. 维表变化了,怎么让正在运行的任务感知?

---

## 五、学习资源

### 官方文档(强烈推荐,质量高)
- https://nightlies.apache.org/flink/flink-docs-release-1.18/
- 重点:Concepts、DataStream API、Table API & SQL、State & Fault Tolerance

### 书籍
- 《Stream Processing with Apache Flink》(O'Reilly,经典)
- 《Flink 原理与实现》(如能找到英文版)

### 视频
- Flink Forward 大会视频(YouTube 官方频道)
- Confluent 的 Flink 教程系列

### 实战
- Flink SQL Cookbook(官方案例集)
- Ververica Platform Community Edition

---

## 六、检查点(每阶段结束自测)

- [ ] 能画出 Flink 架构图(JM/TM/Slot)
- [ ] 能解释 Event Time 和 Watermark 为什么必须一起用
- [ ] 能手写一个带 State 的 KeyedProcessFunction
- [ ] 能解释 Barrier 对齐和端到端 Exactly-Once
- [ ] 能用 Flink SQL 完成维表 Join
- [ ] 能排查反压并说出根因
- [ ] 能回答 15 个以上面试题

---

**学完本篇 → 进入 [ClickHouse 路线](./clickhouse-roadmap.md)**
