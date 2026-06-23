# 为什么「没走索引的 UPDATE 会锁全表」？

## 一句话回答

InnoDB 的行锁加在**索引记录**上。WHERE 列没索引时，InnoDB 没法只锁匹配行，只能沿聚簇索引**逐行扫描**判断，而扫到的**每一行 + 每个间隙都被加 Next-Key Lock**，直到事务结束。结果不是一把表锁，而是**几万把行锁铺满全表**——效果等同锁表，任何写入都被挡。

## 要点

- 实测：5 万行表对无索引列做一条 UPDATE，`performance_schema.data_locks` 里出现 **50130 把 X RECORD 锁**（比行数还多，多的是间隙锁 + supremum）+ 1 把 IX TABLE 意向锁。
- 这是「行锁退化」，不是 InnoDB 升级成了表锁。
- 连「插入一行匹配值」也被挡，因为间隙也锁了。

## 证据链接

- 实测 50130 把行锁：[ch06 Scenario 01](../06-locking/scenarios/01-no-index-locks-whole-table.md)
- 章节原理：[ch06 §3.4](../06-locking/README.md)

## 易追问的延伸

- **Q: 怎么避免？** → 线上对大表 UPDATE/DELETE，WHERE 列必须有索引；`EXPLAIN` 确认 `type` 不是 `ALL`。
- **Q: 那把 IX TABLE 锁是什么？** → 意向排他锁，不锁数据，只是「我在表里持有行锁」的 O(1) 冲突标记。
