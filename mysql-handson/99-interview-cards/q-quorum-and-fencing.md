# quorum 和 fencing 分别解决什么问题？

## 一句话回答

三节点用 2/3 多数派保证只有一个可继续决策的分区，fencing 再让失去资格的旧 Primary 不可写；只有选主没有 fencing，仍可能形成双写。

## 要点

- quorum 决定哪一侧仍有资格作出成员与 Primary 决策，不是健康节点计数装饰。
- fencing 必须用旧 Primary 的拒写事实取证；只看到新 Primary 出现还不够。
- 失去多数派时宁可停止 SUCCESS，也不能让两个分区都继续写。

## 证据链接

- 理论边界：[HA 基础 §5：Quorum、选主与 fencing](../09-replication-and-ha/ha-foundations.md#5-quorum选主与-fencing)
- 产品落地：[InnoDB Cluster §3：三节点 Single-Primary 拓扑](../09-replication-and-ha/innodb-cluster/README.md#3-三节点-single-primary-拓扑)
- 实测：[Scenario 03：Primary partition](../09-replication-and-ha/innodb-cluster/scenarios/03-primary-partition.md)、[Scenario 04：quorum loss](../09-replication-and-ha/innodb-cluster/scenarios/04-quorum-loss.md)

## 易追问的延伸

- 两节点为何不能同时做到自动续写与避免 split-brain？
- `super_read_only=1` 加直接写被拒绝为何可作为 fencing 证据？
