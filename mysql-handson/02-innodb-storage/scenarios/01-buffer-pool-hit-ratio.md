# Scenario 01: Buffer Pool 命中率——冷扫 vs 热扫，working set 装不装得下

## 我想验证的问题

「Buffer Pool 命中率」到底怎么量？同一张表扫两遍，第二遍会不会因为页都进了 Buffer Pool 而几乎零磁盘 IO？如果一张表比 Buffer Pool 还大，命中率会怎样？

## 预期（基于 ch02 §3.3 推算）

命中率 = `1 − 物理读 / 逻辑读`，其中：
- **逻辑读** `Innodb_buffer_pool_read_requests`：向 Buffer Pool 要页的次数。
- **物理读** `Innodb_buffer_pool_reads`：Buffer Pool 没有、不得不从磁盘读的次数。

预期：

- 表能装进 Buffer Pool：**第一遍扫**有物理读（冷，页还没进来），**第二遍扫**几乎零物理读（页都在内存里）→ 命中率 ~100%。
- 表比 Buffer Pool 大（working set 装不下）：每遍扫都要从磁盘换页，命中率压不满。

## 环境

- `innodb_buffer_pool_size=256MB`（16384 个 16KB 页）
- 小表 `up2`（~3MB，远小于 BP）；大表 `bigtab`（CHAR(255) 灌到几百 MB）
- 用 `SELECT COUNT(*) ... WHERE pad LIKE '%zzz%'` 强制全表扫所有数据页

## 步骤

```sql
-- 取指标的辅助查询
SELECT VARIABLE_VALUE FROM performance_schema.global_status
 WHERE VARIABLE_NAME IN ('Innodb_buffer_pool_read_requests','Innodb_buffer_pool_reads');

-- 小表扫两遍，前后各取一次指标算差值
SELECT COUNT(*) FROM up2 WHERE name LIKE '%zzz%';   -- 第一遍
SELECT COUNT(*) FROM up2 WHERE name LIKE '%zzz%';   -- 第二遍

-- 整体命中率
SELECT HIT_RATE FROM information_schema.INNODB_BUFFER_POOL_STATS;
```

## 实机告诉我（本机实测，MySQL 8.0.36）

```
### 小表 up2(~3MB, 远小于 256MB BP) 扫两遍:
  扫描1: 逻辑读+758  物理读+98  命中率=87.1%    ← 冷:有些页要从磁盘搬进来
  扫描2: 逻辑读+628  物理读+0   命中率=100.0%   ← 热:页全在 BP, 零磁盘 IO

### INNODB_BUFFER_POOL_STATS:
  POOL_SIZE=16383 页   used=16379   free=0   dirty=1276   HIT_RATE=703(‰)
```

观察到的关键事实：

- **小表的「冷→热」非常干净**：第一遍 98 次物理读（页冷），第二遍 **0 次物理读、命中率 100%**——页一旦进了 Buffer Pool，后续读全在内存命中。这就是「为什么第二次跑同一个查询快很多」。
- `HIT_RATE` 是 `INNODB_BUFFER_POOL_STATS` 给的**窗口内**命中率（千分比）：703‰ = 70.3%，因为统计窗口里夹了大表的冷扫，把整体拉低了——它反映的是「最近一段时间」，不是某一条 SQL。
- 大表 `bigtab` 扫两遍命中率仍有 ~99%：因为全表扫是**顺序读 + 预读（read-ahead）**，加上 LRU 把热页留住，working set 只要不远超 BP，顺序重扫也大多命中。真正把命中率打下来的是**随机访问一个远大于 BP 的数据集**（每次访问都可能 miss），不是顺序全表扫。

## ⚠️ 预期 vs 实机落差

- 小表冷热对比完全符合预期，「第二遍 0 物理读」是肌肉记忆级的结论。
- 一个修正：原以为「表比 BP 大，命中率就崩」。实机看到**顺序全表扫 + 预读 + LRU** 能让大表重扫仍 ~99% 命中——命中率崩塌的真正条件是「**随机**访问 + 工作集**远超** BP」（典型如大表上低命中的二级索引随机回表）。
- 工程判断：
  - 监控 `Innodb_buffer_pool_reads`（物理读）的**增速**，比看瞬时 HIT_RATE 更能反映「BP 是否够大」。持续高物理读 = working set 装不下，考虑加大 `innodb_buffer_pool_size`（RAM × 0.5~0.75）。
  - 命中率长期 < 95% 且物理读高 = 内存不足或有大范围随机扫描的坏查询。
  - 重启后想快速预热：`innodb_buffer_pool_dump_at_shutdown` / `_load_at_startup`（默认开）把热页清单 dump 出来、重启自动加载。

## 连到的面试卡

- `99-interview-cards/q-buffer-pool-hit-ratio.md`
