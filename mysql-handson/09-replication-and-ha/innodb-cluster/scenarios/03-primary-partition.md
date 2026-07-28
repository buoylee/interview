# Scenario 03: 少数派 Primary 必须被 fencing

## 我想验证的问题

Primary 被隔离为少数派时，是否会被 fencing，且多数派能否继续写入。

## 预期

隔离节点进入 `OFFLINE_MODE`／不可写，多数派继续写，重连后安全 rejoin。

## 环境与命令

```bash
make scenario SCENARIO=primary-partition
```

## 客户端证据

- 指定成功 run ID：`20260726T100107Z`。本机生成且被 Git ignore 的 archive 为 `mysql-handson/00-lab/ha/evidence/runs/primary-partition/20260726T100107Z/`；追溯本节至少读取 `verification.json`、`scenario-verification.json`、`events.jsonl`，少数派写栅栏来自 `fencing.json`，session／分段 RTO 来自 `session.json`、`timeline.jsonl`，写入分布来自 `written-by.txt`。archive 不是本次 commit 的内容，run ID 才是本地证据索引。
- `fault_begin=2026-07-26T10:00:09.725464+00:00`，`fault_active=10:00:20.348304`，`rejoin_begin=10:00:44.370201`，`rejoin_online=10:01:00.006653`，`fault_end=10:01:00.204404`。
- `SUCCESS=503`、`FAILURE=46`、`UNKNOWN=0`；故障窗口内为 347 SUCCESS、30 FAILURE。
- 旧 session 从隔离的 `db1` 断开，新 session 连到 `db2`；`rto_ms=21922`。

## Cluster／成员证据

- `db1` 被隔离后观测到 `offline_mode=0`、`super_read_only=1`，直接应用写探针被拒绝。
- 多数派选出 `db2=PRIMARY/ONLINE`；`db1` 重连后安全回到 SECONDARY，最终三成员 ONLINE。
- `written_by` 为 `db1=82`、`db2=421`。

## 数据一致性证据

- base verifier 为 `ok:true`；503 个 acknowledged request 在三个成员上各有 503 行，无未对账 UNKNOWN。

## 实机告诉我

- fencing 的充分证据不是一定要进入 `OFFLINE_MODE`；本次由 `super_read_only=1` 加直接写入被拒绝共同证明旧 Primary 不可写。

## 预期 vs 实机落差

- 预测写了 `OFFLINE_MODE／不可写`，实机状态是 `offline_mode=0`、`super_read_only=1`；安全不变量成立，但具体 fencing 状态与字面预期不同。

## 生产边界

- 只能以服务端写栅栏和写探针判断旧 Primary 是否安全；网络隔离、Router 摘除或 UI 状态本身都不足以证明不可写。

## 连到的面试卡

- [README：Case D「MGR 节点离群（UNREACHABLE／ERROR）」](../../README.md)
- [README：§3.6 MGR 简述（Paxos／单主多主／流控）](../../README.md)
