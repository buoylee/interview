# 快照读和当前读有什么区别？为什么「读后写」要用当前读？

## 一句话回答

**快照读**（普通 `SELECT`）走 ReadView + undo 链读**历史版本**、不加锁；**当前读**（`SELECT ... FOR UPDATE/SHARE`、`UPDATE`、`DELETE`、`INSERT`）读**最新已提交版本**、加锁。二者能在**同一瞬间给出不同结果**。所以「先读后写」（查库存→扣减、抢座、改状态机）那个「读」必须是当前读（`FOR UPDATE`），否则两个并发事务都基于旧快照判断通过 → 双双写入 → 超卖。

## 要点

- 快照读看的是「事务开始时的世界」，当前读看的是「此刻的世界」。
- 当前读不仅看最新，还**加锁**（Record / Gap / Next-Key），从而能在 RR 下防当前读幻读。
- `UPDATE t SET x=x+1` 必须是当前读——读历史版本算出来的结果是错的。

## 证据链接

- 实测同一事务同一 WHERE：快照读=2、当前读 FOR UPDATE=3：[ch05 Scenario 03](../05-mvcc-and-transaction/scenarios/03-snapshot-vs-current-read.md)
- 章节原理：[ch05 §3.5 / §3.6](../05-mvcc-and-transaction/README.md)

## 易追问的延伸

- **Q: 怎么修超卖？** → 把判断用的 `SELECT` 加 `FOR UPDATE`（当前读 + 持锁），或用 `UPDATE ... WHERE qty>0` 的影响行数判断。
- **Q: FOR UPDATE 在 t0 加锁能防住幻读吗？** → 能，Next-Key Lock 锁住间隙，别人的 INSERT 被挡（见 [ch06 Scenario 02](../06-locking/scenarios/02-gap-lock-blocks-insert.md)）。
