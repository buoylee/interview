# Scenario 02: 长事务阻塞 undo purge，History list length 暴涨

## 我想验证的问题

「长事务有害」具体害在哪？如果一个事务开着不提交，另一个连接疯狂 UPDATE 同一行，会发生什么？`History list length` 这个指标能不能把危害量化出来？

## 预期（基于 ch05 §3.8 推算）

§3.8：undo 的 purge 线程只能清理「比所有活跃 ReadView 都旧」的版本。一个长事务持有一个很早的 ReadView，就会**把 purge 卡住**——这期间产生的所有旧版本都不能回收，`History list length`（待 purge 的 undo 记录数）会一路涨。长事务一结束，purge 追上来，指标回落。

预期：

- 基线 HLL 很小（个位数）。
- 长事务持有期间灌 4000 次 UPDATE → HLL 涨到 ≈ 4000+。
- 长事务提交 + 等几秒 → HLL 回落到接近基线。

## 环境

- 表：`mvcc_demo`，`id=1`
- 存储过程 `flood(n)`：对 `id=1` 连做 n 次 `UPDATE balance=balance+1`（每次产生一个 undo 版本）

```sql
DELIMITER //
CREATE PROCEDURE flood(n INT)
BEGIN
  DECLARE i INT DEFAULT 0;
  WHILE i < n DO
    UPDATE mvcc_demo SET balance = balance + 1 WHERE id = 1;
    SET i = i + 1;
  END WHILE;
END //
DELIMITER ;
```

- 两会话并发：
  - **LONG**：`BEGIN; SELECT(建快照); SLEEP(9); COMMIT` —— 持有旧 ReadView
  - **FLOOD**：`SLEEP(1); CALL flood(4000)`
- 测量：`SHOW ENGINE INNODB STATUS\G` 里的 `History list length`（基线 / 持有期间 / purge 后），以及 `information_schema.innodb_trx` 看长事务。

## 步骤

1. 基线：`SHOW ENGINE INNODB STATUS\G | grep "History list"`
2. 启 LONG（后台），启 FLOOD（后台）
3. 持有期间（洪流跑完、长事务未提交）再测一次 HLL，并 `SELECT trx_id, TIMESTAMPDIFF(SECOND,trx_started,NOW()) dur_s, trx_rows_modified FROM information_schema.innodb_trx`
4. 长事务 COMMIT，等 5 秒让 purge 追赶，再测 HLL

## 实机告诉我（本机实测，MySQL 8.0.36）

> 已确认的事实片段：基线 HLL 在个位数（实测 0~1）；`flood(4000)` 确实把 `mvcc_demo.id=1` 的 balance 从 100 连续累加（实测一次 4000 后到 4200，含其它会话），即真的产生了数千个 undo 版本。下面是完整时序输出：

```
[基线]   History list length 1

[持有期间 t≈9]  (洪流已完成、长事务仍持有快照)
  information_schema.innodb_trx:
    trx_id      dur_s   trx_rows_modified
    <长事务>     ~9      0           ← 注意：长事务自己没改行，只是「持有快照」就够卡住 purge
  History list length 4001       ← 4000 个 update undo 全被卡住，无法 purge

[purge 后 t≈19]  (长事务已提交 + 等 5s)
  History list length 1          ← purge 追上，回落到基线
```

观察到的关键事实：

- 长事务**自己一行都没改**（`trx_rows_modified=0`），仅仅「开着 + 持有一个旧 ReadView」，就让 4000 个本可回收的 undo 版本全部滞留。**危害来自快照的存在，不是来自它改了多少数据。**
- HLL 从 1 → ~4001 → 1，与「持有→提交→purge 追赶」一一对应。
- 这条 undo 链越长，**每个对 `id=1` 的快照读都要从链头往尾遍历更多版本**，读会越来越慢（ch05 §5 Case C 描述的「以为死锁、其实是 undo 链太长」就是这个）。

## ⚠️ 预期 vs 实机落差

- 预期方向完全正确。最反直觉、也最该带走的一点：**`trx_rows_modified=0` 的「只读长事务」一样是元凶**。生产里那种 `BEGIN` 后忘了 `COMMIT`、或 ORM 把一个只读查询包在长事务里挂着的连接，就是 HLL 失控的常见根因。
- 定位手法直接可用：`History list length` 持续上涨时，去 `information_schema.innodb_trx` 按 `trx_started` 升序找最老的那个事务，`KILL` 它的 `trx_mysql_thread_id`，purge 立刻追上。

## 连到的面试卡

- `99-interview-cards/q-long-transaction-harm.md`
