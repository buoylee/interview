# RC 和 RR 的区别，根在哪？

## 一句话回答

根在 **ReadView 的建立时机**：**RC 每条 SELECT 都新建一个 ReadView**（所以能读到别人刚提交的修改 → 不可重复读）；**RR 整个事务只在第一条快照读时建一次、之后复用**（所以同一事务内多次读一致 → 可重复读）。底层机制（ReadView + undo 链）两者完全一样，只差「建视图的频率」这一个开关。

## 要点

- ReadView 四字段：`m_ids`（建视图时的活跃事务集）、`min_trx_id`、`max_trx_id`、`creator_trx_id`。
- RR 的「可重复读」不是靠锁，而是靠**不再重建快照**——读到的是一张定格的旧照片。
- RR 的视图建在**第一条快照读**，不是 `BEGIN`。`BEGIN` 后 sleep 很久再 SELECT，视图才在那条 SELECT 建立。

## 证据链接

- 双会话实测 RR 两读都 100、RC 第二读变 200：[ch05 Scenario 01](../05-mvcc-and-transaction/scenarios/01-rc-vs-rr-readview-timing.md)
- 章节原理：[ch05 §3.7](../05-mvcc-and-transaction/README.md)

## 易追问的延伸

- **Q: 为什么大多数业务用 RR 而不是 RC？** → MySQL 默认 RR，且 RR 下 binlog（早期 STATEMENT）更安全；但高并发写、长扫描场景 RC 锁更少（无 Gap Lock）。
- **Q: RC 下还有 Gap Lock 吗？** → 没有，RC 只有 Record Lock，所以并发插入更顺，代价是不可重复读 + 可能幻读。
