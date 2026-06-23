# 长事务到底有什么危害？

## 一句话回答

长事务持有一个**很早的 ReadView**，会**卡住 undo 的 purge**——这期间产生的所有旧版本都不能回收，`History list length` 一路涨：undo 表空间膨胀、版本链变长拖慢 MVCC 读、还可能长时间持锁阻塞别人。关键是：**哪怕这个长事务一行都没改（只读），只要它开着，就足以卡住 purge。**

## 要点

- purge 线程只能清理「比所有活跃 ReadView 都旧」的 undo；一个老视图就把整条链钉住。
- `History list length`（`SHOW ENGINE INNODB STATUS`）是核心指标：持续上涨 = purge 被卡。
- 定位：`information_schema.innodb_trx` 按 `trx_started` 升序找最老事务，`KILL` 它。

## 证据链接

- 实测只读长事务（`trx_rows_modified=0`）把 4000 个 undo 卡住、HLL 1→4001→1：[ch05 Scenario 02](../05-mvcc-and-transaction/scenarios/02-long-txn-blocks-purge.md)
- 章节原理：[ch05 §3.8](../05-mvcc-and-transaction/README.md)

## 易追问的延伸

- **Q: 怎么预防？** → 事务内只放必要 DML，把 RPC/MQ/复杂计算移出事务；设 `innodb_lock_wait_timeout`；监控 HLL 告警。
- **Q: 为什么读也会卡 purge？** → MVCC 读要保留它能看到的历史版本，所以「持有快照」本身就是保留理由。
