# RedLock 是什么？它安全吗？为什么需要 fencing token？

## 一句话回答

单实例 Redis 锁有**异步复制丢锁窗口**（主从切换后锁可能蒸发 → 双重持有）。**RedLock** 向 N 个独立 master 各加锁、过半成功才算获得，消除单点。但 **Martin Kleppmann** 指出 GC/时钟漂移下 RedLock 仍不保证正确；真正的正确性靠 **fencing token**——单调递增的令牌，被保护资源拒绝比已见过的更小的 token。

## 单实例丢锁窗口（实测）

[sc03](../07-distributed-locks/scenarios/03-failover-lock-loss.md)：master 加锁成功后、复制到 slave 之前宕机 → 新主无锁 → 第二个客户端 `SET NX=OK`，**双重持有**。
- 反直觉发现：`pause` 冻结 replica 进程**复现不出丢锁**（TCP 缓冲补传，锁幸存）；**只有真网络分区**（字节没发出去）才丢锁——说明窗口「窄但真实」。

## fencing token 机制

每次获锁返回一个**单调递增**的 token（如 Redis `INCR`）。客户端带着 token 去写被保护资源，资源端记录「见过的最大 token」，**拒绝更小的 token**：
```
客户端1 拿到 token=33,GC 暂停...
客户端2 拿到 token=34,写入资源(资源记下 34)
客户端1 醒来,带 token=33 写入 → 资源发现 33 < 34,拒绝
```
→ 即使旧持有者"复活"也写不进去。**锁只是性能优化，fencing 才是正确性保证。**

## 何时用 / 不用

- **锁仅用于效率**（避免重复干活，偶尔重复无害）→ 单实例 + 看门狗够了，antirez 认为 RedLock 也 OK。
- **锁用于正确性**（钱、库存、不可重复操作）→ 别只靠锁，加 fencing token；或用有共识的系统（ZooKeeper/etcd，天然有单调 zxid/revision）。

## 易追问的延伸

- **RedLock 为什么要 N 个独立 master 而非主从？** 主从是同一份数据的异步副本(有丢锁窗口);RedLock 的 N 个是相互独立的实例,过半才算,容忍少数宕机。
- **ZooKeeper/etcd 做锁比 Redis 好在哪？** 强一致(共识)+ 天然单调版本号(zxid/revision)可直接当 fencing token + 临时节点/lease 自动释放。
- **时钟漂移为什么影响 RedLock？** RedLock 用本地时间判断「获锁总耗时 < ttl」,时钟跳变会误判锁仍有效。

## 证据链接

- 章节原理：[07-distributed-locks §3.4](../07-distributed-locks/README.md)
- 实测主从丢锁 + 双重持有：[sc03](../07-distributed-locks/scenarios/03-failover-lock-loss.md)
- 旧笔记：`redis/redlock.md`、`redis/分布式锁-redlock.md`
