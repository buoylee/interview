# 死锁怎么产生、InnoDB 怎么处理、怎么根治？

## 一句话回答

两个事务**交叉加锁**（A 持 1 等 2，B 持 2 等 1）形成等待环。InnoDB 维护**等待图（wait-for graph）**做死锁检测，发现环就**回滚代价较小的那个事务**（被回滚方收 `ERROR 1213`），另一个继续。根治不是靠检测，而是：**① 统一加锁顺序**（都先改小 id 再改大 id，环不成立）；**② 缩短事务、按索引精确加锁**减少持锁面。

## 要点

- 死锁详情在 `SHOW ENGINE INNODB STATUS` 的 `LATEST DETECTED DEADLOCK` 段：每个事务有 `HOLDS THE LOCK(S)` 和 `WAITING FOR`。
- INT 主键在日志里是 hex（符号位翻转）：`80000001`→1、`80000002`→2，用来对出谁持有/等待哪行。
- 应用必须**捕获 1213 并重试整个事务**。

## 证据链接

- 实测交叉更新 → 1213 + 逐字解读死锁日志：[ch06 Scenario 03](../06-locking/scenarios/03-deadlock-reproduce-and-read-log.md)
- 章节原理：[ch06 §3.7](../06-locking/README.md)

## 易追问的延伸

- **Q: 检测有成本吗？** → 有，每次等锁都要遍历等待图。超高并发热点行场景可关 `innodb_deadlock_detect`，靠 `innodb_lock_wait_timeout` 兜底。
- **Q: 它怎么选牺牲者？** → 通常选 undo 量小、回滚代价低的事务。
