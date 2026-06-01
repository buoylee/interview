# 复制与哨兵（Replication & Sentinel）

## 1. 核心问题

单机 Redis 挂了就不可用、数据也可能丢。主从复制做「数据多副本 + 读扩展」，哨兵做「主挂了自动选新主」。本章讲清:psync 全量/部分复制怎么回事、复制是异步的（丢数据边界）、哨兵故障转移流程、以及脑裂怎么防。

## 2. 直觉理解

- **主从复制**:从节点（replica）复制主节点（master）的数据,只读;主写、从读,分摊读压力 + 做热备。
- **复制是异步的**:master 写完就回客户端,**不等从确认**——所以 master 突然挂、新数据还没到从,会丢(07 章 sc03 实证的丢锁就是这个)。
- **哨兵(Sentinel)**:一组独立进程盯着主从,主挂了就投票选一个从升主、改路由、通知客户端——**自动故障转移**。

## 3. 原理深入

### 3.1 psync:全量 vs 部分复制
从节点连主时发 `PSYNC <replid> <offset>`:
- **全量复制(FULLRESYNC)**:第一次连(没有 replid/offset)→ 主 `BGSAVE` 出 RDB 发给从,从清库加载,期间主把新写命令缓存到**复制积压缓冲区(repl-backlog)**再补发。sc01 实测:从首次连接 `sync_full` 计数 +1。
- **部分复制(CONTINUE)**:从**短暂断线重连**,带着自己的 offset → 主在 repl-backlog 里找得到这段 → 只补发缺失的命令(不重做全量)。sc01 实测:`CLIENT KILL` 断开复制连接后重连,`sync_partial_ok` +1(走了部分复制)。
- **repl-backlog 溢出**则退化为全量:断线太久、缺的数据超出缓冲区大小,只能全量。

### 3.2 复制是异步的（丢数据边界）
- master 执行写 → 回客户端 OK → **异步**传播给从。master 在传播前宕机,这条就丢。
- `WAIT numreplicas timeout` 可让客户端等若干从确认(半同步),但会牺牲延迟,且仍非强一致。
- **07 章 sc03 实证**:master 加锁成功后、复制到从之前宕机,新主没这把锁 → 双重持有。这就是异步复制丢数据的真实后果。

### 3.3 哨兵故障转移流程
1. **主观下线(SDOWN)**:单个哨兵 `down-after-milliseconds` 内 ping 不通主 → 标记主观下线。
2. **客观下线(ODOWN)**:足够多哨兵(quorum)都认为主下线 → 客观下线,触发故障转移。
3. **选举 + 提升**:哨兵间选一个 leader 哨兵,它从健康的从里挑一个(按优先级/复制进度/runid)`REPLICAOF NO ONE` 升为新主,其余从改 `REPLICAOF` 新主。
4. **通知**:客户端通过 `SENTINEL get-master-addr-by-name` 拿到新主地址。**07 章 sc03 实证**:kill 主后 ~18-29s 完成转移,地址从旧主变新主。

### 3.4 脑裂(split-brain）与防护
- **脑裂**:网络分区下旧主还在一侧接受写、哨兵在另一侧已选了新主 → 两个主,旧主的写在它被降级后丢失。
- **防护 `min-replicas-to-write` + `min-replicas-max-lag`**:主在「健康从数 < 阈值」时**拒绝写入**。sc02 实测:失去所有从且超 max-lag 后,主 `SET` 返回 `NOREPLICAS Not enough good replicas`——宁可不可写,也不在孤岛上接受会丢的写。

## 4. 日常开发应用

- 读多写少 → 主从 + 读写分离(从分摊读);但注意**主从延迟**导致从读到旧数据(最终一致)。
- 要高可用自动切换 → 哨兵(≥3 个哨兵,奇数,quorum 过半)。
- 对「不能丢的写」→ 配 `min-replicas-to-write`(牺牲分区下的可写性换一致性);或用 `WAIT` 半同步;真要强一致考虑别用 Redis 存。

## 5. 调优实战

- **主从延迟大** → `INFO replication` 看从的 offset 滞后;查网络/从负载;用 toxiproxy 可注入延迟复现。
- **频繁全量复制(sync_full 涨)** → repl-backlog 太小、断线频繁;调大 `repl-backlog-size`。
- **故障转移没切/切错** → 哨兵数不足 quorum、`down-after`/`failover-timeout` 配置不当。
- **分区后数据丢** → 脑裂;配 `min-replicas-to-write`。

## 6. 面试高频考点

- **psync 全量 vs 部分?** 首连全量(FULLRESYNC + RDB);短断重连走部分(CONTINUE,从 repl-backlog 补);溢出退化全量。(sc01 实测 sync_full/sync_partial_ok)
- **复制是同步还是异步?会丢数据吗?** 异步,master 不等从确认,宕机会丢(07 章 sc03)。
- **哨兵故障转移流程?** SDOWN → ODOWN(quorum)→ 选 leader 哨兵 → 提升从 → 通知客户端。
- **脑裂怎么防?** `min-replicas-to-write`/`max-lag`,健康从不足就拒写(sc02 NOREPLICAS)。
- **从能写吗?** 默认只读(`replica-read-only yes`),写报 READONLY(sc01)。

## 7. 一句话总结

主从**异步**复制(首连全量 FULLRESYNC、短断部分 CONTINUE,靠 repl-backlog),从只读;异步意味着 master 宕机有**丢数据窗口**(07 章 sc03)。哨兵做自动故障转移(SDOWN→ODOWN→选主);脑裂用 `min-replicas-to-write` 拒写防护(sc02)。

## Scenarios

- [01 - 主从复制 + 只读 + psync 全量/部分](scenarios/01-replication-psync.md)
- [02 - 脑裂防护:min-replicas-to-write 拒写](scenarios/02-split-brain-min-replicas.md)
- 故障转移实证见 [07 章 sc03](../07-distributed-locks/scenarios/03-failover-lock-loss.md)（kill 主 → 哨兵选新主）
