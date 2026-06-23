# Scenario 03: 经典死锁复现 + 读懂 `SHOW ENGINE INNODB STATUS` 死锁日志

## 我想验证的问题

两个事务**交叉**锁两行（A 先锁 1 再要 2，B 先锁 2 再要 1），一定死锁吗？InnoDB 怎么发现的？它牺牲谁？死锁日志里那一堆 hex 怎么读？

## 预期（基于 ch06 §3.7 推算）

交叉加锁形成「A 等 B、B 等 A」的环。InnoDB 有**死锁检测**（维护一张等待图 wait-for graph），一旦检测到环，立刻**回滚其中一个事务**（通常选 undo 量较小、回滚代价低的那个）打破环，另一个继续。被回滚的事务收到 `ERROR 1213`。死锁详情记到 `SHOW ENGINE INNODB STATUS` 的 `LATEST DETECTED DEADLOCK` 段。

## 环境

- 表：`dl(id PK, v)`，初始 `(1,1),(2,2)`
- 会话 A：`BEGIN; UPDATE dl SET v=v+1 WHERE id=1; SLEEP; UPDATE ... WHERE id=2;`
- 会话 B：`BEGIN; UPDATE dl SET v=v+1 WHERE id=2; SLEEP; UPDATE ... WHERE id=1;`
- 两者并发，中间的 SLEEP 保证先各拿一把、再去抢对方的。

## 步骤

```sql
-- 会话 A                              -- 会话 B
BEGIN;                                 BEGIN;
UPDATE dl SET v=v+1 WHERE id=1;        UPDATE dl SET v=v+1 WHERE id=2;
-- (各持有一把 X 锁)
UPDATE dl SET v=v+1 WHERE id=2;        UPDATE dl SET v=v+1 WHERE id=1;
--   ↑ 等 B 的 id=2                       ↑ 等 A 的 id=1  → 环 → 死锁
COMMIT;                                COMMIT;

-- 事后查看
SHOW ENGINE INNODB STATUS\G   -- 看 LATEST DETECTED DEADLOCK 段
```

## 实机告诉我（本机实测，MySQL 8.0.36）

会话 B 立刻收到：

```
ERROR 1213 (40001): Deadlock found when trying to get lock; try restarting transaction
```

`SHOW ENGINE INNODB STATUS\G` 的死锁段（节选）：

```
LATEST DETECTED DEADLOCK
------------------------
*** (1) TRANSACTION:
TRANSACTION 111565, ACTIVE 2 sec starting index read
LOCK WAIT 3 lock struct(s), ... 2 row lock(s), undo log entries 1
UPDATE dl SET v=v+1 WHERE id=2                        ← 事务1 卡在要 id=2
*** (1) HOLDS THE LOCK(S):
  ... index PRIMARY of table `sbtest`.`dl` ... lock_mode X locks rec but not gap
  Record lock, heap no 2 ... 0: len 4; hex 80000001 ...   ← 持有 id=1 (hex 80000001)
*** (1) WAITING FOR THIS LOCK TO BE GRANTED:
  ... lock_mode X locks rec but not gap waiting
  Record lock, heap no 3 ... 0: len 4; hex 80000002 ...   ← 想要 id=2 (hex 80000002)

*** (2) TRANSACTION:
TRANSACTION 111566, ACTIVE 2 sec ...
UPDATE dl SET v=v+1 WHERE id=1                        ← 事务2 卡在要 id=1
*** (2) HOLDS THE LOCK(S):
  ... heap no 3 ... hex 80000002 ...                      ← 持有 id=2
*** (2) WAITING FOR THIS LOCK TO BE GRANTED:
  ... heap no 2 ... hex 80000001 waiting                  ← 想要 id=1

*** WE ROLL BACK TRANSACTION (2)                     ← InnoDB 牺牲了事务2
```

怎么读这段日志（面试常考）：

- **`*** (1)` / `*** (2)`** 是卷入死锁的两个事务。每个都有 `HOLDS THE LOCK(S)`（已持有）和 `WAITING FOR`（在等）两块。
- **`hex 80000001` = id 1**：InnoDB 存 INT 主键时把符号位翻转（`0x80000000 + 1`），所以 `80000001`→1、`80000002`→2。一眼就能对出「谁持有哪行、在等哪行」。
- **`lock_mode X locks rec but not gap`**：纯记录锁（无间隙），因为这里是主键等值更新。
- **`WE ROLL BACK TRANSACTION (2)`**：InnoDB 选了事务2 回滚（这里两者 undo 都是 1 条，按内部权重择一）。被回滚方拿到 1213，**应用要捕获 1213 并重试整个事务**。

## ⚠️ 预期 vs 实机落差

- 预期完全对上。亲手读一遍日志，比背「持有/等待」强一百倍——下次线上死锁，直接 `SHOW ENGINE INNODB STATUS\G` 抓这段，按 hex 对出两条冲突 SQL 和加锁顺序，就知道该怎么调整。
- 根治死锁的两条标准答法：① **统一加锁顺序**（所有事务都先改小 id 再改大 id，环就不会形成）；② **缩短事务、按索引精确加锁**减少持锁面。检测只是兜底，不是解决方案。
- 注意 `innodb_deadlock_detect=ON` 默认开，但**检测本身有成本**（每次等锁都要遍历等待图）。超高并发热点行场景，有时反而关掉检测、靠 `innodb_lock_wait_timeout` 兜底更稳（ch06 §6 / ch11）。

## 连到的面试卡

- `99-interview-cards/q-deadlock-reproduce-and-resolve.md`
