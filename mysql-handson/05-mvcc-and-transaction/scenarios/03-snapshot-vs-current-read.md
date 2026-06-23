# Scenario 03: 快照读看不到、当前读看得到——RR 下的「读不一致」陷阱

## 我想验证的问题

RR 隔离级别下，事务 A 先用普通 SELECT 数了一遍行数（快照读），中间事务 B 插了一行并提交。然后 A：

- 再普通 SELECT —— 还是原来的行数吗？
- 改成 `SELECT ... FOR UPDATE`（当前读）—— 行数会变吗？

如果两者不一致，就是库存超卖类 bug 的根源。

## 预期（基于 ch05 §3.5 / §3.6 推算）

- **快照读**（普通 SELECT）走 ReadView + undo 链，看历史版本。B 晚于 A 的视图，不可见 → A 再读**仍是旧行数**。
- **当前读**（`FOR UPDATE` / `UPDATE` / `DELETE`）绕过 ReadView，**直接读最新已提交版本** → 看到 B 插入的新行。

所以 A 会出现「快照读 = N，当前读 = N+1」的不一致。这正是「先 `SELECT` 判断库存够、再 `UPDATE` 扣减」会超卖的机制：判断用的是旧快照，扣减用的是新数据。

## 环境

- 表：`inv(id PK, qty)`，初始 2 行 `qty=10`
- 两会话并发：
  - **A**（RR）：`BEGIN; A1 快照读 count; SLEEP(3); A2 快照读 count; A3 当前读 count FOR UPDATE; COMMIT`
  - **B**：`SLEEP(1); INSERT INTO inv VALUES(3,10);`（autocommit）

## 步骤

```sql
-- 会话 A（RR）
SET SESSION transaction_isolation='REPEATABLE-READ';
BEGIN;
SELECT 'A1 快照读' tag, COUNT(*) n FROM inv WHERE qty>0;            -- 建 ReadView
SELECT SLEEP(3) INTO @x;
SELECT 'A2 快照读(B已插)' tag, COUNT(*) n FROM inv WHERE qty>0;     -- 仍旧
SELECT 'A3 当前读 FOR UPDATE' tag, COUNT(*) n FROM inv WHERE qty>0 FOR UPDATE;  -- 看到新行
COMMIT;

-- 会话 B
DO SLEEP(1);
INSERT INTO inv VALUES (3,10);
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
+----------------------+---+
| tag                  | n |
+----------------------+---+
| A1 快照读            | 2 |   ← 建 ReadView，2 行
+----------------------+---+
+----------------------+---+
| A2 快照读(B已插)     | 2 |   ← B 已提交插入，但快照读仍是 2
+----------------------+---+
+----------------------+---+
| A3 当前读 FOR UPDATE | 3 |   ← 当前读直接看最新，3 行！
+----------------------+---+
```

观察到的关键事实：

- 同一个事务、同一个 WHERE，**A2（快照读）和 A3（当前读）在同一时刻给出不同行数**。这不是 bug，是 MVCC 的设计：两种读走两条完全不同的路径。
- A3 用 `FOR UPDATE` 不仅「看见」了第 3 行，还**对它加了锁**——如果 A 是在 t0（B 插入前）就用 `FOR UPDATE` 扫的，Next-Key Lock 会锁住间隙，B 的 INSERT 会被阻塞，幻读从源头被挡（见 [ch06 Scenario 02](../../06-locking/scenarios/02-gap-lock-blocks-insert.md)）。

## ⚠️ 预期 vs 实机落差

- 预期完全对上。这条 scenario 的价值在于**亲眼看到「读不一致」**：很多人背得出「快照读/当前读」的定义，但没意识到它们能在**同一瞬间给出矛盾结果**。
- 工程结论刻进肌肉记忆：**任何「读了再据此写」的逻辑（扣库存、抢座、改状态机），那个「读」必须是当前读（`FOR UPDATE`）**，否则两个并发事务都基于旧快照判断通过，双双写入 → 超卖。修复就是把判断用的 `SELECT` 加 `FOR UPDATE`。

## 连到的面试卡

- `99-interview-cards/q-snapshot-vs-current-read.md`
