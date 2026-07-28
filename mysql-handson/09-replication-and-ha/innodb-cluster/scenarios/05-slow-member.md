# Scenario 05: 慢成员如何触发 backlog 与 flow control

## 我想验证的问题

慢成员是否会使 applier queue 跨过生效中的 QUOTA threshold，并在恢复后追平。

## 预期

core Performance Schema 的 applier queue 跨过生效中的 QUOTA threshold；记录前后 p95 写延迟但不把易受环境噪声影响的延迟升高设为硬断言；成员最终追平。

## 环境与命令

```bash
make scenario SCENARIO=slow-member
```

## 客户端证据

- `fault_begin=2026-07-28T05:20:19.797890+00:00`，`fault_active=05:20:20.305006`，`fault_end=05:22:31.689642`。
- 全程 `SUCCESS=5447`、`FAILURE=0`、`UNKNOWN=0`；故障窗口内 5260 次 SUCCESS，`rto_ms=148`。
- before p95 为 `440ms`，active p95 为 `271ms`。

## Cluster／成员证据

- 注入目标为 `db3`；active applier queue 为 `27`，生效中的 QUOTA threshold 为 `10`，`flow_control_triggered=true`。
- 恢复后 `db1=PRIMARY/ONLINE`，`db2`、`db3=SECONDARY/ONLINE`。

## 数据一致性证据

- base verifier 为 `ok:true`；5447 个 acknowledged request 在三个成员上各有 5447 行，`written_by=db1:5447`。

## 实机告诉我

- 核心触发证据是目标成员 queue `27 > 10`，不是延迟曲线必须升高；flow control 生效时业务仍可能全部成功。

## 预期 vs 实机落差

- queue 跨阈值与成员追平符合预期，但 active p95 `271ms` 反而低于 before `440ms`；这验证了预测中“不把延迟升高设为硬断言”的必要性。

## 生产边界

- 调高 threshold 只会延后背压，不会消除慢 applier；生产上应同时看 queue、flow-control mode、吞吐和节点资源，再决定扩容、限流或修复慢成员。

## 连到的面试卡

- [MGR Flow Control](../../README.md#34-mgrmysql-group-replication)
- [三节点生产基线](../../README.md#34-mgrmysql-group-replication)
