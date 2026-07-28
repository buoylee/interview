# Scenario 02: Primary crash 后谁完成 failover

## 我想验证的问题

Primary crash 后，多数派、Router 与客户端如何完成 failover。

## 预期

多数派选新 Primary、Router 只迁移新连接、所有 SUCCESS 存在，并量出 detection／election／backlog fence／Router refresh／application reconnect 五段 RTO。

## 环境与命令

```bash
make scenario SCENARIO=primary-crash
```

## 客户端证据

- `fault_begin=2026-07-26T09:57:24.427729+00:00`，`fault_active=09:57:24.789710`，`rejoin_begin=09:57:58.674634`，`rejoin_online=09:58:21.194205`，`fault_end=09:58:21.373353`。
- `SUCCESS=542`、`FAILURE=51`、`UNKNOWN=0`；故障窗口内为 380 SUCCESS、51 FAILURE。
- 旧 session 在 `db1` 断开，新 session 连到 `db2`；`rto_ms=21496`。
- 五段为 detection `5357ms`、election `16001ms`、backlog fence `18ms`、Router refresh `184ms`、application reconnect `195ms`，总长 `21758ms`。

## Cluster／成员证据

- 多数派选出 `db2=PRIMARY/ONLINE`；原 Primary `db1` rejoin 后成为 SECONDARY，`db3` 仍为 SECONDARY。
- `written_by` 为 `db1=84`、`db2=458`，新 Primary 承接了后续写入。

## 数据一致性证据

- base verifier 为 `ok:true`；542 个 acknowledged request 在三个成员上都各有 542 行，无未对账 UNKNOWN。

## 实机告诉我

- crash 后不是 Router 选主：多数派先选出 `db2`，Router 再把新连接导向它；旧连接直接失效。

## 预期 vs 实机落差

- 预期中的五段全部量到，最大段不是 Router refresh，而是 election `16001ms`；实际恢复瓶颈在组内选主，不在 Router 的 `184ms` 刷新。

## 生产边界

- `SUCCESS` 的最终存在性由三成员 ID 对账证明；客户端看到连接错误时仍要以 request ID 查询结果，不能把超时直接重放成第二笔业务操作。

## 连到的面试卡

- [MGR 多数派与三节点生产基线](../../README.md#34-mgrmysql-group-replication)
- [MySQL Router 的职责边界](../../README.md#方案-dmysql-routerinnodb-cluster)
