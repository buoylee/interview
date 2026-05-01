# 旧笔记索引

本文件只做归档索引，不移动旧文档。后续新文档会按“金融级一致性实现”的主线重新组织这些材料。

## 事务、锁、隔离级别

- [MySQL 事务、隔离级别、锁](../mysql/事务-隔离级别-锁.md)
- [MySQL MVCC 与 Buffer Pool](../mysql/MVCC-BufferPool.md)
- [MySQL 死锁](../mysql/deadlock.md)
- [MySQL binlog](../mysql/binlog.md)
- [MySQL 执行原理与 binlog](../mysql/执行原理-binlog.md)
- [MySQL 高可用](../mysql/高可用.md)

## MQ、Outbox、事务消息

- [消息幂等](../MQ/消息幂等.md)
- [消息防丢](../MQ/消息防丢.md)
- [本地消息表与事务 MQ](../MQ/distr-tx基于mq/本地消息表-and-事务mq.md)
- [Kafka 事务](../MQ/kafka/kafka事务.md)
- [Kafka 消息防丢](../MQ/kafka/kafka-消息防丢.md)
- [Kafka producer](../MQ/kafka/producer.md)
- [Kafka consumer](../MQ/kafka/consumer.md)

## 分布式事务模式

- [分布式事务基础与 Saga](../transaction/basic.md)
- [Seata TCC 与 AT 区别](../distr-tx/SEATA/tcc-at区别.md)
- [Seata GlobalLock](../distr-tx/SEATA/GlobalLock.md)

## Redis、锁与原子操作

- [Redis 事务与 Lua](../redis/事务-lua.md)
- [Redis Redlock](../redis/redlock.md)
- [Redis 分布式锁 Redlock](../redis/分布式锁-redlock.md)
- [Redis 持久化](../redis/持久化.md)

## 支付等待、回调与实时性

- [轮询：异步等待与支付双通道](../network/polling.md)
- [HTTP 幂等性与安全性](../network/http.md)
- [SSE](../network/sse.md)
- [WebSocket](../network/websocket.md)

## 分布式一致性与协调系统

- [ZooKeeper 一致性问题](../zookeeper/zk-一致性问题.md)
- [ZooKeeper 分布式锁](../zookeeper/zk-分布式锁.md)
- [ZooKeeper ZAB](../zookeeper/zab.md)
- [etcd 概述](../etcd/概述.md)
