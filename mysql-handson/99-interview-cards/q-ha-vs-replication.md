# 复制和 HA 有什么区别？

## 一句话回答

复制回答「数据怎么到另一台」，HA 还必须回答故障检测、quorum、选主、fencing、连接重建、业务结果与恢复；有副本不等于系统已经高可用。

## 要点

- 复制是数据面 primitive；HA 还要串起控制面、路由面、应用面与存储面。
- 可验证的 HA 要定义 SUCCESS／FAILURE／UNKNOWN、RPO／RTO、fencing 与恢复门槛。
- Router 只路由新连接，Group Replication 才维护成员视图、quorum 与 Primary 角色。

## 证据链接

- 理论边界：[HA 基础 §3：五个平面](../09-replication-and-ha/ha-foundations.md#3-五个平面应用路由控制数据存储)
- 产品落地：[InnoDB Cluster §1：解决与不解决](../09-replication-and-ha/innodb-cluster/README.md#1-这套方案解决什么不解决什么)
- 实测：[Scenario 06：Router failure](../09-replication-and-ha/innodb-cluster/scenarios/06-router-failure.md)

## 易追问的延伸

- 有三个在线副本为什么仍不能恢复误删？
- 只有自动选主但应用不处理 UNKNOWN，业务结果会发生什么？
