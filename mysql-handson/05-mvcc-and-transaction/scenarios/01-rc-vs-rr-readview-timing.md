# Scenario 01: RC 与 RR 的 ReadView 建立时机差异

## 我想验证的问题

同一个事务里读两次同一行，中间有另一个事务把它改了并提交。

- 在 **RR** 下，第二次读会看到新值吗？
- 在 **RC** 下呢？
- 这个差异的根，是不是「ReadView 什么时候建」？

## 预期（基于 ch05 §3.7 推算）

§3.7 的结论：**RC 每条 SELECT 都建一个新 ReadView；RR 整个事务只在第一条快照读时建一次，之后复用**。

所以：

- **RR**：A 第一次读建 ReadView-1（活跃事务集合在那一刻定格）。B 是在 A 建视图之后才提交的，`DB_TRX_ID(B) >= max_trx_id`，对 ReadView-1 不可见。A 第二次读复用 ReadView-1 → **仍是旧值 100**。
- **RC**：A 第二次读会**重新建 ReadView-2**，此刻 B 已提交、不在活跃列表里 → **看到新值 200**。这正是「不可重复读」。

## 环境

- compose: `00-lab/docker-compose.yml`，`make up`
- 表：`mvcc_demo(id PK, name, balance)`，`id=1` 初始 `balance=100`
- 两个会话用「MySQL 内 `SLEEP` 控时序 + 并发」复现：
  - A：`BEGIN; 读(t0); SLEEP(4); 读(t4); COMMIT`
  - B：`SLEEP(2); UPDATE balance=200; (autocommit)`
  - A 在 t0 建视图，B 在 t2 提交，A 在 t4 再读 —— 看 t4 是否变。

## 步骤

```sql
-- 重置
UPDATE mvcc_demo SET balance=100 WHERE id=1;

-- 会话 A（设 RR 或 RC）
SET SESSION transaction_isolation='REPEATABLE-READ';   -- 或 'READ-COMMITTED'
BEGIN;
SELECT 'A-read1 (t0, 建ReadView)' AS step, balance FROM mvcc_demo WHERE id=1;
SELECT SLEEP(4) INTO @x;
SELECT 'A-read2 (t4, 同事务再读)' AS step, balance FROM mvcc_demo WHERE id=1;
COMMIT;

-- 会话 B（与 A 并发，t2 时执行）
DO SLEEP(2);
UPDATE mvcc_demo SET balance=200 WHERE id=1;
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
===== REPEATABLE-READ =====
+---------------------------+---------+
| step                      | balance |
+---------------------------+---------+
| A-read1 (t0, 建ReadView)  |     100 |
+---------------------------+---------+
+---------------------------+---------+
| step                      | balance |
+---------------------------+---------+
| A-read2 (t4, 同事务再读)  |     100 |   ← B 已在 t2 提交 200，A 仍看到 100
+---------------------------+---------+

===== READ-COMMITTED =====
+---------------------------+---------+
| A-read1 (t0, 建ReadView)  |     100 |
+---------------------------+---------+
+---------------------------+---------+
| A-read2 (t4, 同事务再读)  |     200 |   ← 新建 ReadView，看到 B 的提交
+---------------------------+---------+
```

观察到的关键事实：

- **RR**：两次读都是 100。A 第一条 SELECT 建的 ReadView 被第二条复用，B（晚于视图）的提交对 A 不可见。这就是 RR「可重复读」。
- **RC**：第二次读变 200。每条 SELECT 重新采样活跃事务集合，B 已提交故可见。这就是 RC「不可重复读」。
- 两者底层机制**完全一样**（都是 ReadView + undo 链），唯一区别是**建视图的频率**——这一个开关，决定了两个隔离级别的全部行为差异。

## ⚠️ 预期 vs 实机落差

- 预期完全对上。值得记的反直觉点：**RR 的「可重复读」不是靠锁，而是靠「不再重建快照」**——读到的是一张定格的旧照片，世界变了它也不知道。
- 衍生认知：RR 下「BEGIN 之后立刻 SLEEP 很久再第一次 SELECT」，视图建立时间是**那条 SELECT**，不是 BEGIN。所以长事务真正的快照点要数到「第一条快照读」。

## 连到的面试卡

- `99-interview-cards/q-rc-vs-rr-readview.md`
