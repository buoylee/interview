# Scenario 02: 间隙锁挡住 INSERT —— Next-Key Lock 怎么防当前读幻读

## 我想验证的问题

RR 下，事务 A 用 `SELECT ... FOR UPDATE` 锁了一个**范围**（不是单行）。另一个事务 B 想往这个范围的「空隙」里 INSERT 一行——会成功，还是被挡？这就是间隙锁/Next-Key Lock 防幻读的核心动作。

## 预期（基于 ch06 §3.5 推算）

RR 下当前读（`FOR UPDATE`）会对扫描范围加 **Next-Key Lock**（记录锁 + 前面的间隙锁）。即使范围内某些值不存在（间隙），间隙也被锁住。B 往间隙里 INSERT 时，会先申请**插入意向锁**，与 A 的间隙锁冲突 → B 阻塞，直到 A 提交或 B 等锁超时。

预期：表里有 `v=5,10,15`，A 锁 `v BETWEEN 8 AND 12 FOR UPDATE`（覆盖间隙 (5,10]、(10,15)），B 插入落在间隙的 `id=12` → 被挡 → `Lock wait timeout`。

## 环境

- 表：`gaps(id PK, v, KEY idx_v(v))`，初始 `(5,5),(10,10),(15,15)`
- 会话 A（RR）：`BEGIN; SELECT * FROM gaps WHERE v BETWEEN 8 AND 12 FOR UPDATE;` 持有
- 会话 B：`SET innodb_lock_wait_timeout=3; INSERT INTO gaps VALUES (12,12);`

## 步骤

```sql
-- 会话 A（RR）
BEGIN;
SELECT * FROM gaps WHERE v BETWEEN 8 AND 12 FOR UPDATE;   -- 锁住相关间隙
-- 保持不提交

-- 会话 B
SET SESSION innodb_lock_wait_timeout=3;
INSERT INTO gaps VALUES (12,12);   -- v=12 落在 (10,15) 间隙
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
-- 会话 B：
[B] ERROR 1205 (HY000) at line 5: Lock wait timeout exceeded; try restarting transaction
    （等了 3 秒 innodb_lock_wait_timeout 后超时——说明被 A 的间隙锁挡住了）
```

> 注：本机一次运行里，B 在 A 持锁期间发起 INSERT，等满 3 秒抛 1205。把 A 改成 `COMMIT` 后再让 B 插，则瞬间成功——证明阻塞确实来自 A 的间隙锁而非别的原因。
> （`data_locks` 里 A 持有的锁形如 `idx_v` 上的 `X,GAP` / `X` Next-Key 锁；具体 `LOCK_DATA` 会标出被锁的边界值。）

## ⚠️ 预期 vs 实机落差

- 预期对上。最该带走的认知：**间隙锁锁的是「不存在的东西」**——`v=12` 这行原本不存在，A 也没读到它，但 A 锁住了「10 和 15 之间的空隙」，于是 B 没法在这里凭空造出一行。这就是 RR 当前读防住幻读的机制：不让范围里冒出新行。
- 代价的另一面（接 [Scenario 01](01-no-index-locks-whole-table.md)）：间隙锁是并发杀手。两个事务往相邻间隙插入，很容易因为「插入意向锁 vs 间隙锁」互相等待而**死锁**。所以 RC（不加间隙锁）在高并发写场景反而更顺——代价是要自己用唯一索引/业务逻辑防重复，并接受不可重复读。

## 连到的面试卡

- `99-interview-cards/q-gap-next-key-lock.md`
