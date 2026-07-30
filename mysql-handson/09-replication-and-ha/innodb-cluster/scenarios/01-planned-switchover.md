# Scenario 01: 计划内切换不是零断线

## 我想验证的问题

计划内切换后，新旧 Primary 是否唯一；既有连接是否可能断开，以及写入何时恢复。

## 预期

新旧 Primary 唯一、既有连接可断、写入恢复、量出 RTO。

## 环境与命令

```bash
make scenario SCENARIO=planned-switchover
```

## 客户端证据

- 指定成功 run ID：`20260726T094213Z`。本机生成且被 Git ignore 的 archive 为 `mysql-handson/00-lab/ha/evidence/runs/planned-switchover/20260726T094213Z/`；追溯本节至少读取 `verification.json`、`scenario-verification.json`、`events.jsonl`，session／分段 RTO 另来自 `session.json`、`timeline.jsonl`，写入分布来自 `written-by.txt`。archive 不是本次 commit 的内容，run ID 才是本地证据索引。
- `fault_begin=2026-07-26T09:41:48.494226+00:00`，`fault_active=09:41:53.023409`，`fault_end=09:42:05.669761`。
- `SUCCESS=386`、`FAILURE=2`、`UNKNOWN=0`；故障窗口内有 180 次 SUCCESS。
- 旧 session 从 `db1` 断开，新 session 在 `db2` 重连；`rto_ms=194`。
- 五段观测为 detection `3727ms`、election `1ms`、backlog fence `51ms`、Router refresh `143ms`、application reconnect `129ms`，观测链总长 `4052ms`。

## Cluster／成员证据

- 切换后 `db2=PRIMARY/ONLINE`，`db1`、`db3=SECONDARY/ONLINE`，仍只有一个 Primary。
- `written_by` 分布为 `db1=125`、`db2=261`，证明切换前后都确实产生了写入。

## 数据一致性证据

- base verifier 为 `ok:true`；386 个 acknowledged request 在 `db1`、`db2`、`db3` 都各有 386 行，无缺失 UNKNOWN。

## 实机告诉我

- 计划内切换仍会断开既有 session；Router 保证的是新连接找到当前 Primary，不会把旧 TCP／数据库 session 无缝搬家。

## 预期 vs 实机落差

- 唯一 Primary、断线与恢复均符合预期，但切换动作本身只观察到 `194ms` 写恢复，完整 observer 分段链为 `4052ms`；两者的测量边界不同，不能混成一个 RTO 数字。

## 生产边界

- 上线前要让连接池具备 bounded retry、幂等 request ID 与连接重建；计划内不等于零失败，也不应把旧 session 保活当作切换成功标准。

## 连到的面试卡

- [README：Case B「切主流程（计划内切换）」](../../README.md)
- [README：§3.7 MySQL Router](../../README.md)
