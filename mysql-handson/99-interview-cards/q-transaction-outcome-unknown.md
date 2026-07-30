# 事务超时后为什么不能直接重试？

## 一句话回答

SQL 已发出但成功响应丢失时，事务可能提交也可能未提交；应用必须用原 `request_id` 查明并保持幂等，不能把超时直接当失败生成新业务操作。

## 要点

- UNKNOWN 是应用不知道数据库事实，不是数据库的第三种事务状态。
- 重试必须复用原 `request_id`，由唯一约束、查询与对账收敛结果。
- application SUCCESS 是业务结果；复制 ACK 只描述复制确认边界，不能混用。

## 证据链接

- 理论边界：[HA 基础 §2：三态请求结果](../09-replication-and-ha/ha-foundations.md#2-三态请求结果成功失败未知)
- 产品落地：[InnoDB Cluster §4：正常提交时序](../09-replication-and-ha/innodb-cluster/README.md#4-正常提交时序)
- 实测：[Scenario 02：Primary crash](../09-replication-and-ha/innodb-cluster/scenarios/02-primary-crash.md)

## 易追问的延伸

- 怎样区分「SQL 明确未发送」和「提交后响应丢失」？
- 为什么换一个订单号重试会把一次操作变成两次业务事实？
