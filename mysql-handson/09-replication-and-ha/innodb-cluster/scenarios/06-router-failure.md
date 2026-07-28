# Scenario 06: 双 Router 解决入口单点

## 我想验证的问题

Router A 失败时，Router B 是否仍能在故障窗口继续完成写入。

## 预期

Router A worker 失败或未知，Router B worker 在故障窗仍有 SUCCESS。

## 环境与命令

```bash
make scenario SCENARIO=router-failure
```

## 客户端证据

- 指定成功 run ID：`20260728T052430Z`。本机生成且被 Git ignore 的 archive 为 `mysql-handson/00-lab/ha/evidence/runs/router-failure/20260728T052430Z/`；追溯本节至少读取 `verification.json`、`scenario-verification.json`、`events.jsonl`，两入口各自结果来自 `ledger-router-a.jsonl`、`ledger-router-b.jsonl`，写入分布来自 `written-by.txt`。archive 不是本次 commit 的内容，run ID 才是本地证据索引。
- `fault_begin=2026-07-28T05:24:09.563474+00:00`，`fault_active=05:24:09.849046`，`fault_end=05:24:24.225745`。
- 故障窗内 Router A 为 8 SUCCESS、10 FAILURE；Router B 为 113 SUCCESS、0 FAILURE、0 UNKNOWN。窗口整体为 121 SUCCESS、11 FAILURE，`rto_ms=123`。
- 全程 Router A 为 90 SUCCESS、11 FAILURE、1 UNKNOWN；Router B 为 197 SUCCESS。

## Cluster／成员证据

- 数据库 topology 未切主：最终仍为 `db1=PRIMARY/ONLINE`，`db2`、`db3=SECONDARY/ONLINE`。
- 故障发生在接入层，不是 Group Replication 选主或数据复制故障。

## 数据一致性证据

- base verifier 为 `ok:true`；287 个 acknowledged request 加 1 个已提交 UNKNOWN，三个成员最终各有 288 行。
- UNKNOWN 对账结果为 committed，absent 集为空；`written_by=db1:288`。

## 实机告诉我

- 两个 Router 不会互相接管连接；Router A 的 worker 会失败，而独立使用 Router B 的 worker 可以持续成功。

## 预期 vs 实机落差

- Router B 故障窗 113 次全部 SUCCESS，符合预期；同时 Router A 在 stop 边界仍完成 8 次 SUCCESS，说明容器停止与客户端观察到入口失效不是同一瞬间。

## 生产边界

- “部署两个 Router”还不够，应用必须实际配置多个端点或在其前方部署健康检查负载均衡；单个客户端若只知道 Router A，仍会失败。

## 连到的面试卡

- [README：§3.7 MySQL Router 双实例生产边界](../../README.md)
- [README：§3.7 MySQL Router 端口与路由职责](../../README.md)
