# Redis 主从复制 + 哨兵:psync、丢数据、故障转移、脑裂？

## 一句话回答

主从**异步**复制:从只读,首连**全量**(PSYNC→FULLRESYNC+RDB)、短断重连**部分**(CONTINUE,从 repl-backlog 补)。异步 → master 宕机有**丢数据窗口**。哨兵自动故障转移(SDOWN→ODOWN→选主)。脑裂用 `min-replicas-to-write` 拒写防护。

## 关键点

- **psync 全量 vs 部分**(sc01 实测):首连/backlog 溢出 → 全量(BGSAVE 出 RDB);短断重连且 offset 还在 backlog → 部分(只补差量)。`sync_full` / `sync_partial_ok` 计数可看。
- **复制异步、会丢**:master 写完即回、不等从;宕机丢未传播的写(07 章 sc03 双重持有就是这个)。`WAIT` 可半同步但伤延迟。
- **哨兵故障转移流程**:① 主观下线 SDOWN(单哨兵 ping 不通)② 客观下线 ODOWN(quorum 过半同意)③ 选 leader 哨兵 → 挑最优从 `REPLICAOF NO ONE` 升主 ④ 其余从改指向、通知客户端。(07 章 sc03 实证 ~20s)
- **脑裂防护**(sc02 实测):`min-replicas-to-write 1`+`min-replicas-max-lag` → 健康从不足时主返回 `NOREPLICAS` 拒写,牺牲可用性换一致性。

## 易追问的延伸

- **为什么会频繁全量?** repl-backlog 太小 + 断线频繁;调大 `repl-backlog-size`。
- **从能写吗?** 默认只读(READONLY);读写分离要注意主从延迟读到旧值。
- **哨兵几个合适?** ≥3、奇数,quorum 过半,避免脑裂误判。
- **故障转移会丢数据吗?** 可能——被选中的从如果落后于旧主,旧主独有的写就丢(异步复制);所以关键场景配 min-replicas / WAIT。

## 证据链接

- 章节原理:[10-replication-sentinel](../10-replication-sentinel/README.md)
- 实测:[sc01 复制+psync](../10-replication-sentinel/scenarios/01-replication-psync.md)、[sc02 脑裂防护](../10-replication-sentinel/scenarios/02-split-brain-min-replicas.md)
- 故障转移 + 异步丢数据实证:[07 章 sc03](../07-distributed-locks/scenarios/03-failover-lock-loss.md)
