# Scenario 04: 没有多数派宁可停止写

## 我想验证的问题

失去多数派时，故障窗口内是否停止接受新写入，并在 quorum 恢复后才继续。

## 预期

在 `fault_active` 后才开始、并于 `quorum_restore_begin` 前完成的请求零 SUCCESS，避免把故障前已跨过提交边界的 in-flight 请求误判为无 quorum 写入；默认 3 秒窗口保持在 Lab 的 5 秒 unreachable-majority timeout 内；恢复 quorum 后才继续。

## 环境与命令

```bash
make scenario SCENARIO=quorum-loss
```

## 客户端证据

- 指定成功 run ID：`20260728T051412Z`。本机生成且被 Git ignore 的 archive 为 `mysql-handson/00-lab/ha/evidence/runs/quorum-loss/20260728T051412Z/`；追溯本节至少读取 `verification.json`、`scenario-verification.json`、`events.jsonl`，完整恢复断言另来自 `quorum-recovery-fence-initial.jsonl`、`quorum-recovery-fence-final.jsonl`、`quorum-recovery-gtid-initial.jsonl`、`quorum-recovery-gtid-final.jsonl`、`quorum-recovery-stop-status.jsonl`、`quorum-recovery-reboot-dry-run.txt`、`quorum-recovery-reboot-actual.txt`、`quorum-recovery-topology.txt`、`quorum-recovery-writable-primary.txt`、`quorum-recovery-router-rollback-probe.json`，写入分布来自 `written-by.txt`。archive 不是本次 commit 的内容，run ID 才是本地证据索引。
- `fault_begin=2026-07-28T05:12:11.853741+00:00`，`fault_active=05:12:12.744917`，`quorum_blocked=05:12:23.575762`，`quorum_restore_begin=05:12:29.220116`，`fault_end=05:14:04.949834`。
- grace window 为 `10830ms`：0 SUCCESS、2 FAILURE、4 UNKNOWN；明确 blocked window 为 `5644ms`：14 FAILURE、0 SUCCESS、0 UNKNOWN。
- 整段故障窗为 0 SUCCESS、18 FAILURE、6 UNKNOWN；`rto_ms=109818`。

## Cluster／成员证据

- 两个 Secondary 被非自愿终止后，旧 Primary 确认进入 fencing；恢复路径先 quiesce Router、三成员服务端 fencing、GTID 复核，再停止 GR，并执行 dry-run／actual complete-outage reboot。
- 恢复证据为 `3 ONLINE / 1 PRIMARY`，唯一可写 Primary 是 `db1`；Router rollback probe 留存行数为 0。

## 数据一致性证据

- base verifier 为 `ok:true`；189 个 acknowledged request 在三个成员上各有 189 行。
- 6 个 UNKNOWN 全部对账为 absent，没有把失败或未知误报成已提交；`written_by` 为 `db1=189`。

## 实机告诉我

- 真正的硬阻塞边界是 `quorum_blocked`，不是 `fault_active`。失去多数派并等待 fencing 后，普通 rejoin 已不足够，恢复属于 complete-outage 管理流程。

## 预期 vs 实机落差

- 原预测保留了“3 秒窗口小于 5 秒 timeout”，但实机若只跑 3 秒仍处于 grace，不能证明无 quorum 后已停止写；最终批准的实测改为等待真实 fencing，grace 达 `10830ms`，blocked window 才满足零 SUCCESS。预测未被倒改，矛盾由实测明确纠正。

## 生产边界

- 不得用 `force:true` 跳过 GTID／fencing 检查；必须先停 Router／客户端流量、复核各成员 GTID 和写栅栏，再 dry-run、actual reboot、唯一可写 Primary、Router rollback 与全量 ID 对账。

## 连到的面试卡

- [README：§3.6 MGR 简述（Paxos／单主多主／流控）](../../README.md)
- [README：Case D「MGR 节点离群（UNREACHABLE／ERROR）」](../../README.md)
