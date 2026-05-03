# Kafka Boundaries

本章使用真实 Docker Kafka：`apache/kafka:4.1.1`。Kafka topic 是 `funds.transfer.events`，Spring 应用通过配置的 host 端口连接 broker，脚本和容器内管理命令通过容器网络连接 broker。

生产者配置里的 `acks=all` 表示 broker 端复制条件已经接受这条 record。在当前单 broker 实验环境里，它证明的是 broker 已经按配置完成写入确认；它不是消费者处理完成证明。

生产者配置里的 `enable.idempotence=true` 会降低生产者因为重试导致 broker 端重复写入的风险。它解决的是生产者到 broker 之间的重复写问题，不证明下游消费者已经执行业务处理，也不替代消费者自己的幂等表。

Kafka transactions 没有作为本章主线。这里刻意把边界拆开：MySQL 本地事务先提交业务事实和 Outbox，发布器再把已提交事件送到 Kafka，消费者再用自己的本地处理事实证明业务消费完成。这样能直接观察每个阶段失败后应由哪个事实负责恢复。

Docker Kafka 暴露了两类 listener：

- 容器内管理命令使用 `kafka:9092`，例如脚本里创建 topic 和健康检查。
- 宿主机上的 Spring Boot 应用使用外部 listener，`KAFKA_HOST_PORT` 默认映射到宿主机 `9092`，实际容器端口是 `9094`。

因此 `docker-compose.yml` 中的内部地址是 `INTERNAL://kafka:9092`，外部地址是 `EXTERNAL://localhost:${KAFKA_HOST_PORT:-9092}`。应用配置里的 `spring.kafka.bootstrap-servers` 是 `localhost:${KAFKA_HOST_PORT:9092}`。
