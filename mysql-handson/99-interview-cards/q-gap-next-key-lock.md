# Gap Lock / Next-Key Lock 是什么？怎么防幻读？

## 一句话回答

**Next-Key Lock = Record Lock（锁记录）+ Gap Lock（锁记录前的间隙）**，左开右闭。RR 下当前读默认加 Next-Key Lock，**连「不存在的值所在的间隙」也锁住**，于是别人没法往这个范围里 INSERT 新行——这就是 RR 当前读防幻读的机制。代价是并发写下降，相邻间隙插入易死锁。

## 要点

- 间隙锁锁的是「不存在的东西」——阻止范围内冒出新行。
- 等值命中唯一索引时退化为 Record Lock（无间隙）；非唯一/范围扫描才是 Next-Key。
- RC 级别没有 Gap/Next-Key Lock，只有 Record Lock，所以并发插入更顺但会幻读。

## 证据链接

- 实测 A 锁范围间隙、B 插入落间隙 → `ERROR 1205` 超时：[ch06 Scenario 02](../06-locking/scenarios/02-gap-lock-blocks-insert.md)
- 章节原理：[ch06 §3.5](../06-locking/README.md)

## 易追问的延伸

- **Q: 为什么高并发写有时选 RC？** → RC 去掉间隙锁，插入冲突少；代价是要自己用唯一索引/业务幂等防重复，并接受不可重复读。
- **Q: 插入意向锁是什么？** → INSERT 前申请的一种特殊间隙锁意向，与已有 Gap Lock 冲突则等待，是间隙锁挡 INSERT 的具体执行者。
