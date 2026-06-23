# Scenario 01: WHERE 列没索引，行锁退化成「锁全表」

## 我想验证的问题

「没走索引的 UPDATE 会锁全表」这句话是真的吗？到底锁了多少行？是真·表锁，还是「给每一行都加了行锁」？用 `performance_schema.data_locks` 数一数。

## 预期（基于 ch06 §3.4 推算）

InnoDB 的行锁是加在**索引记录**上的。如果 WHERE 列没有索引，InnoDB 没法「只锁匹配的行」——它必须沿聚簇索引**扫描每一行**来判断是否匹配，而扫到的每一行都会被加上 Next-Key Lock（直到事务结束才放）。结果不是一把表级锁，而是**几万把行锁覆盖了整张表的每条记录 + 每个间隙**，效果等同锁表：任何其它写入都被挡。

预期：对 5 万行的表做无索引列的 UPDATE，`data_locks` 里 RECORD 锁数量 ≈ 表行数（5 万左右）。

## 环境

- 表：`up2(id PK, name, age, city)`，`KEY idx_city(city)`，**`age` 无索引**，5 万行
- 会话 A：`BEGIN; UPDATE up2 SET name=name WHERE age=45;`（匹配的行其实没几行，但 age 无索引）持有不提交
- 会话 B（测量）：`SELECT COUNT(*), LOCK_MODE, LOCK_TYPE FROM performance_schema.data_locks WHERE OBJECT_NAME='up2' GROUP BY ...`

## 步骤

```sql
-- 会话 A
SET SESSION transaction_isolation='REPEATABLE-READ';
BEGIN;
UPDATE up2 SET name=name WHERE age=45;   -- age 无索引
-- 不提交，保持持锁

-- 会话 B（A 持锁期间）
SELECT COUNT(*) AS locks_held, LOCK_MODE, LOCK_TYPE
FROM performance_schema.data_locks
WHERE OBJECT_NAME='up2'
GROUP BY LOCK_MODE, LOCK_TYPE;

SELECT COUNT(*) AS total_rows FROM up2;
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
+------------+-----------+-----------+
| locks_held | LOCK_MODE | LOCK_TYPE |
+------------+-----------+-----------+
|          1 | IX        | TABLE     |   ← 一把表级意向排他锁(IX)
|      50130 | X         | RECORD    |   ← 5 万多把行级 X 锁!
+------------+-----------+-----------+

+------------+
| total_rows |
+------------+
|      50000 |
+------------+
```

观察到的关键事实：

- 表只有 5 万行，`age=45` 真正匹配的可能就几百行，但 InnoDB 加了 **50130 把 X RECORD 锁**——比行数还多（多出来的是记录之间的**间隙锁**和 supremum）。整张表的每条记录 + 每个间隙都被锁住。
- 这不是「表锁」那一把锁，而是「**几万把行锁铺满全表**」。效果一样（别人写不进去），但机制是行锁退化，不是 InnoDB 升级成了表锁。
- 那 1 把 `IX TABLE` 是**意向锁**——它不锁数据，只是「我在这张表里持有行锁」的快速标记，让别人想加表锁时 O(1) 就能发现冲突（ch06 §3.3）。

## ⚠️ 预期 vs 实机落差

- 预期方向对，但「锁的数量比行数还多」是亲手数才会注意到的细节——**间隙也被锁了**，所以连「插入一行 age=45」都会被挡，这正是 RR 下无索引扫描会顺带防住幻读、却也代价巨大的原因。
- 工程铁律：**线上对大表做 UPDATE/DELETE，WHERE 列必须有索引**。否则一条「只想改几行」的语句会把全表锁住几十毫秒到几秒，瞬间堆起一片 `Lock wait timeout`。排查锁等待时，第一反应就是去看那条持锁 SQL 的 WHERE 有没有走索引（`EXPLAIN` 看 `type` 是不是 `ALL`）。

## 连到的面试卡

- `99-interview-cards/q-no-index-lock-escalation.md`
