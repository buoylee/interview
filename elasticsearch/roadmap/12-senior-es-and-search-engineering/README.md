# 阶段 12：资深 ES 与搜索工程 A/B 双轨

> **目标**：把前 1-11 章的 ES 使用、原理、生产和面试能力提升到资深工程师层级。A 线面向 Java 后端资深工程师，强调生产治理；B 线面向搜索/ES 平台方向，强调搜索质量、Lucene 执行和平台治理。
>
> **前置依赖**：阶段 1-11。

## 为什么需要第 12 章

前 1-11 章解决的是“能系统学会 ES，并能讲清楚常见原理追问”。第 12 章解决的是“能以资深工程师视角负责 ES”：能做容量规划、能设计生产拓扑、能定义 SLO、能排查复杂故障、能解释架构取舍，也能继续深入搜索质量、相关性和搜索平台工程。

这不是把 ES API 再学一遍，而是把面试问题提升到资深岗位会真实负责的范围：容量怎么估、集群怎么分层、故障怎么恢复、慢查询怎么定位、搜索效果怎么评估、Lucene 执行如何影响方案取舍，以及 Hybrid Search 和 rerank 如何落到可治理的平台能力。

## A/B 双轨定义

| 轨道 | 面向目标 | ES 的角色 | 核心能力 |
| --- | --- | --- | --- |
| A 线：后端资深生产治理 | Java 后端资深工程师 | ES 是业务系统中的搜索视图和生产依赖 | 容量规划、shard sizing、ILM、生产拓扑、故障恢复、SLO、troubleshooting、数据同步、生产治理、架构取舍 |
| B 线：搜索工程与平台深水区 | 搜索/推荐/ES 平台工程师 | 搜索本身是核心专业领域 | 搜索质量、相关性调优、Lucene 查询执行、Hybrid Search、rerank、多租户平台治理、相关性发布治理 |

A 线的过关重点是“我能对一个业务 ES 集群负责”：知道什么时候扩容、什么时候拆索引、怎么设计 hot/warm/cold、怎么守住 P95/P99、怎么处理 rejected、breaker、hot shard、恢复慢和数据同步风险。

B 线的过关重点是“我能把搜索当平台和专业能力建设”：知道召回、排序、重排、评估、实验、查询保护、租户隔离、相关性配置发布和成本治理如何一起工作。

## 推荐学习路径

### A only：Java 后端资深

```text
01 capacity and shard sizing
-> 02 production topology and data tiers
-> 03 failure recovery and SLO
-> 04 performance diagnostics playbook
-> 09 senior case studies 中的后端案例
```

适合目标是高级/资深 Java 后端、业务架构、稳定性负责人的学习者。面试时重点讲清楚生产所有权：容量、拓扑、SLO、故障恢复、成本、变更治理和跨系统边界。

### A + selected B：后端资深，同时补搜索工程加分项

```text
A only
-> 05 search relevance engineering
-> 07 hybrid search and rerank
-> 09 senior case studies 中的商品搜索和 hybrid search 案例
```

适合负责商品搜索、内容搜索、订单搜索、知识库搜索等业务搜索场景的后端工程师。你不一定要成为搜索平台专家，但要能解释相关性为什么变差、如何设计实验、Hybrid Search 为什么会引入延迟和成本取舍。

### Full A+B：搜索/ES 平台方向

```text
A only
-> 05 search relevance engineering
-> 06 Lucene query execution deep dive
-> 07 hybrid search and rerank
-> 08 search platform governance
-> 09 senior case studies 全量案例
```

适合搜索工程、推荐/搜索基础设施、ES 平台、企业知识库检索和 RAG 检索平台方向。学习重点从“能维护 ES”升级到“能建设可观测、可实验、可治理、可扩展的搜索平台”。

## 文档导航

| 文件 | 轨道 | 解决的问题 |
| --- | --- | --- |
| [01-capacity-and-shard-sizing.md](./01-capacity-and-shard-sizing.md) | A core / B prerequisite | 数据、节点、shard、replica 如何一起做容量规划 |
| [02-production-topology-and-data-tiers.md](./02-production-topology-and-data-tiers.md) | A core / B prerequisite | 生产集群如何拆角色、分层、隔离资源并控制故障域 |
| [03-failure-recovery-and-slo.md](./03-failure-recovery-and-slo.md) | A core / B prerequisite | ES 搜索能力如何定义 SLO、RPO/RTO、恢复策略和告警 |
| [04-performance-diagnostics-playbook.md](./04-performance-diagnostics-playbook.md) | A core / B prerequisite | 高 CPU、高 heap、rejected、breaker、热点和队列堆积如何证据化排查 |
| [05-search-relevance-engineering.md](./05-search-relevance-engineering.md) | B core | 搜索质量、召回、排序、query rewrite、相关性评估和 A/B test 如何设计 |
| [06-lucene-query-execution-deep-dive.md](./06-lucene-query-execution-deep-dive.md) | B core | Lucene 查询执行如何形成面试级心智模型 |
| [07-hybrid-search-and-rerank.md](./07-hybrid-search-and-rerank.md) | B core | BM25、向量、Hybrid Search、rerank 如何组合，并如何权衡延迟和成本 |
| [08-search-platform-governance.md](./08-search-platform-governance.md) | B core | 多租户搜索平台如何做 guardrail、隔离、观测、发布和平台治理 |
| [09-senior-case-studies.md](./09-senior-case-studies.md) | A+B synthesis | 把资深 ES 与搜索工程能力转成系统设计和项目叙述 |

## 过关标准

学完 A 线后，你应该能：

- 解释一个业务搜索系统的容量模型和 shard 规划，并说明数据增长 10 倍时先验证哪些假设。
- 设计生产拓扑、数据层、副本、rollover、ILM 和故障域隔离策略。
- 定义搜索链路的 SLO、告警、降级、恢复流程，并说明 RPO/RTO 对方案的影响。
- 按证据排查查询慢、写入慢、heap 高、rejected、breaker、hot shard、segment merge 和恢复慢。
- 说明 ES 与 MySQL、Redis、Kafka、ClickHouse、对象存储在一致性、查询能力、成本和恢复上的边界。

学完 B 线后，你还应该能：

- 设计搜索质量指标和相关性调优闭环，说明离线评估、线上实验和人工标注各自解决什么问题。
- 解释 query rewrite、boost、function_score、rescore、rerank 在检索链路中的位置。
- 用面试级语言解释 Lucene 查询执行、Scorer、Collector、TopK、WAND 的直觉。
- 设计 BM25 + vector + rerank 的 Hybrid Search pipeline，并说清召回、延迟、成本和可解释性的取舍。
- 说明多租户搜索平台如何做限流、隔离、模板、观测、相关性发布、成本治理和平台治理。
