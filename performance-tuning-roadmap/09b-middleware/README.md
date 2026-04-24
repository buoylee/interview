# 阶段 9b：中间件性能学习指南

> 本阶段目标：能排查 Redis 慢命令、大 Key、内存问题，以及 Kafka/RabbitMQ 的吞吐、积压和消费异常。

---

## 学习顺序

| 顺序 | 文件 | 学习重点 |
|------|------|----------|
| 1 | [01-redis-performance.md](./01-redis-performance.md) | SLOWLOG、大 Key、热 Key、Pipeline、连接池 |
| 2 | [02-redis-memory.md](./02-redis-memory.md) | INFO MEMORY、碎片率、淘汰策略、持久化影响 |
| 3 | [03-mq-performance.md](./03-mq-performance.md) | Kafka/RabbitMQ 吞吐模型、Producer/Consumer 调优 |
| 4 | [04-mq-debugging.md](./04-mq-debugging.md) | lag、积压、分区倾斜、Rebalance、消息丢失 |

---

## 本阶段主线

中间件排查要同时看客户端和服务端：

```text
应用延迟升高
→ Redis/MQ span 是否变慢
→ 中间件自身指标是否异常
→ 客户端连接池/批量/超时是否合理
→ 数据结构或消息模型是否放大问题
```

---

## 最小完成标准

学完后应该能做到：

- 用 Redis SLOWLOG 找到慢命令
- 用 `--bigkeys` 或 `memory usage` 找到大 Key
- 解释 Redis 内存碎片率和淘汰策略
- 判断 Kafka consumer lag 的来源
- 调整 producer batch 或 consumer poll 参数并复测

---

## 本阶段产物

建议留下：

- Redis 慢命令记录
- 大 Key 扫描结果
- Redis memory 摘要
- Kafka lag 图或命令输出
- 调优前后吞吐与延迟对比

---

## 常见误区

| 误区 | 正确做法 |
|------|----------|
| 线上使用 KEYS | 使用 SCAN，并控制批量 |
| 直接 DEL 大 Key | 优先 UNLINK 或分批删除 |
| 只看 MQ 积压量 | 同时看生产速率、消费速率、分区分布 |
| 盲目加消费者 | 先确认分区数、Rebalance 和下游瓶颈 |

---

## 下一阶段衔接

阶段 9b 解决单个中间件。阶段 10 会把数据库、中间件和服务串成分布式链路，处理超时传播、重试风暴和一致性问题。

