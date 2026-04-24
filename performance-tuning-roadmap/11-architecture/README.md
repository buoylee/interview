# 阶段 11：架构级性能优化学习指南

> 本阶段目标：从“发现并修复瓶颈”升级为“在架构设计中主动降低瓶颈概率”。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-caching-strategy.md](./01-caching-strategy.md) | Cache-Aside、穿透、击穿、雪崩、一致性 |
| 2 | [02-connection-pooling.md](./02-connection-pooling.md) | 连接池大小、泄漏、等待队列、客户端复用 |
| 3 | [06-performance-patterns.md](./06-performance-patterns.md) | 批处理、预计算、懒加载、零拷贝、对象池 |
| 4 | [07-protocol-serialization.md](./07-protocol-serialization.md) | HTTP/gRPC、JSON/Protobuf、压缩和连接复用 |
| 5 | [04-database-architecture.md](./04-database-architecture.md) | 读写分离、分库分表、冷热数据、CQRS |
| 6 | [03-async-reactive.md](./03-async-reactive.md) | 异步、响应式、背压和线程模型 |
| 7 | [05-jvm-production-tuning.md](./05-jvm-production-tuning.md) | 生产 JVM 参数、容器环境和 GC 选择 |

---

## 本阶段主线

架构优化要先判断瓶颈类型：

```text
读多写少 → 缓存 / 读写分离 / 预计算
连接等待 → 连接池 / 复用 / 下游容量
序列化开销大 → 协议和编码选择
吞吐不够 → 批处理 / 异步 / 分区 / 并行化
数据量过大 → 分表 / 归档 / CQRS
```

---

## 最小完成标准

学完后应该能做到：

- 为一个接口设计缓存策略并说明一致性风险
- 用公式和压测结果估算连接池大小
- 判断 JSON、Protobuf、压缩、HTTP/2/gRPC 的取舍
- 识别至少 3 种架构级性能模式
- 写出一份生产 JVM 参数选择理由

---

## 本阶段产物

建议留下：

- 一份接口缓存设计
- 一份连接池容量计算
- 一份序列化/协议压测对比
- 一份架构优化前后指标对比
- 一份风险和回滚方案

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 为了性能过早引入复杂架构 | 先证明瓶颈和收益 |
| 缓存只考虑命中率 | 同时考虑一致性、穿透、雪崩和失效策略 |
| 连接池越大越好 | 连接池大小受下游容量和等待时间约束 |
| 异步一定更快 | 异步适合 I/O 等待，不自动减少总工作量 |

---

## 下一阶段衔接

阶段 11 解决架构设计。阶段 12 会进入容器和云原生运行环境，处理 cgroup、K8s 和 Service Mesh 带来的性能约束。

