# Buffer Pool 命中率怎么算？什么时候会崩？

## 一句话回答

命中率 = `1 − Innodb_buffer_pool_reads(物理读) / Innodb_buffer_pool_read_requests(逻辑读)`。页一旦进 Buffer Pool，后续读全在内存命中——所以「同一查询第二次快很多」。命中率真正崩塌的条件不是「表比 BP 大」，而是「**随机访问一个远大于 BP 的工作集**」（每次访问都可能 miss）；顺序全表扫有预读 + LRU 兜着，重扫仍大多命中。

## 要点

- 实测小表 up2：第一遍扫 98 次物理读（冷），**第二遍 0 物理读、命中率 100%**（热）。
- `INNODB_BUFFER_POOL_STATS.HIT_RATE` 是**窗口内**千分比，不是某条 SQL 的命中率。
- 看 `Innodb_buffer_pool_reads` 的**增速**比看瞬时命中率更能判断「BP 够不够大」。

## 证据链接

- 实测冷扫 vs 热扫 + working set 原理：[ch02 Scenario 01](../02-innodb-storage/scenarios/01-buffer-pool-hit-ratio.md)
- 章节原理：[ch02 §3.3](../02-innodb-storage/README.md)

## 易追问的延伸

- **Q: 命中率低怎么办？** → 加大 `innodb_buffer_pool_size`（RAM × 0.5~0.75）；排查有没有大范围随机扫描的坏 SQL（低命中的二级索引随机回表是典型）。
- **Q: 重启后命中率暴跌怎么避免？** → `innodb_buffer_pool_dump_at_shutdown` / `_load_at_startup`（默认开）dump 热页清单、重启自动预热。
