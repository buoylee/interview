# InnoDB Cluster 故障切换时各组件做什么？

## 一句话回答

Group Replication 完成成员视图与 Primary 选举，`BEFORE_ON_PRIMARY_FAILOVER` 挡住新 Primary 直到 backlog 处理完成，Router 更新新连接目标，应用负责丢弃旧连接并重连。

## 要点

- Group Replication 负责成员资格、quorum、选主与数据复制；Router 不参与选举。
- `BEFORE_ON_PRIMARY_FAILOVER` 是开放新 Primary 写入前的 backlog fence，不等于零切换延迟。
- 旧 session 不会迁移；应用必须 bounded reconnect，并按原 `request_id` 对账 UNKNOWN。

## 证据链接

- 理论边界：[HA 基础 §7：RPO／RTO 与分段测量](../09-replication-and-ha/ha-foundations.md#7-rporto-与分段测量)
- 产品落地：[InnoDB Cluster §5：Primary failover 时序](../09-replication-and-ha/innodb-cluster/README.md#5-primary-failover-时序)
- 实测：[Scenario 01：planned switchover](../09-replication-and-ha/innodb-cluster/scenarios/01-planned-switchover.md)、[Scenario 02：Primary crash](../09-replication-and-ha/innodb-cluster/scenarios/02-primary-crash.md)

## 易追问的延伸

- Router 为何不能把旧 TCP／数据库 session 搬到新 Primary？
- backlog fence、Router refresh 与应用重连各自如何计时？
