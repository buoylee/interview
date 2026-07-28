# Scenario 07: 离群成员不能直接恢复服务

## 我想验证的问题

离群成员是否必须经过显式恢复阶段，才回到 Cluster 服务。

## 预期

`rejoin_begin` 先于 `rejoin_online`，成员经恢复阶段回到 ONLINE，三成员 ID 集完全相同。

## 环境与命令

```bash
make scenario SCENARIO=member-rejoin
```

## 客户端证据

- 指定成功 run ID：`20260728T052648Z`。本机生成且被 Git ignore 的 archive 为 `mysql-handson/00-lab/ha/evidence/runs/member-rejoin/20260728T052648Z/`；追溯本节至少读取 `verification.json`、`scenario-verification.json`、`events.jsonl`，请求结果来自 `ledger-router-a.jsonl`、`ledger-router-b.jsonl`，写入分布来自 `written-by.txt`。archive 不是本次 commit 的内容，run ID 才是本地证据索引。
- `fault_begin=2026-07-28T05:26:08.814658+00:00`，`fault_active=05:26:09.143865`，`rejoin_begin=05:26:21.453441`，`rejoin_online=05:26:41.507255`，`fault_end=05:26:41.609658`。
- 全程 `SUCCESS=420`、`UNKNOWN=2`；故障窗口内 254 SUCCESS、0 FAILURE、2 UNKNOWN，`rto_ms=5459`。

## Cluster／成员证据

- 离群目标是 `db2`；`rejoin_begin` 明确早于 `rejoin_online`，成员经过显式恢复阶段后才重新进入 ONLINE。
- 最终 `db1=PRIMARY/ONLINE`，`db2`、`db3=SECONDARY/ONLINE`。

## 数据一致性证据

- 两个 UNKNOWN 都对账为 committed；三个成员最终各有完全相同的 422 个 request ID，`written_by=db1:422`。
- base verifier 与 scenario verifier 均为 `ok:true`。

## 实机告诉我

- 容器重新 running 或 mysqld 能 ping 不等于成员已恢复服务；必须等到 rejoin 完成并在组视图中成为 ONLINE。

## 预期 vs 实机落差

- 状态顺序符合预期，但从 `rejoin_begin` 到 `rejoin_online` 实际约 `20.054s`，明显长于 `rto_ms=5459` 的客户端写恢复边界；成员修复时间与服务写可用时间不是同一个指标。

## 生产边界

- rejoin 前要检查 GTID／errant transaction 与恢复方式；低 GTID、分叉或数据已损坏的成员不能因为进程启动就重新导流。

## 连到的面试卡

- [README：Case D「MGR 节点离群与 rejoin」](../../README.md)
- [GTID 自动续传与 errant transaction](../../../99-interview-cards/q-gtid-auto-resume.md)
