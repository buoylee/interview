# 过期与淘汰（Expiry & Eviction）

## 1. 核心问题

两件**容易混的**事:**过期删除**（key 设了 TTL，到点怎么被删）和**内存淘汰**（内存满了、还要写，删谁）。本章讲清:过期的惰性+定期机制、`maxmemory` 满了的 8 种淘汰策略、LRU 近似 vs LFU 的区别。

## 2. 直觉理解

- **过期删除**回答「设了 TTL 的 key 到期后怎么消失」——Redis **不**为每个 key 起定时器,而是「**惰性**（访问到过期 key 才删）+ **定期**（后台每隔一会儿随机采样一批,删掉其中过期的）」两手。
- **内存淘汰**回答「`maxmemory` 满了、还有写请求,删谁腾地方」——按 `maxmemory-policy` 选 8 种策略之一;选错（`noeviction`）会直接拒绝写入。

两者独立:**没设 TTL 的 key 也可能被淘汰**（`allkeys-*` 策略）；**设了 TTL 的 key 在内存没满时靠过期机制删,满了可能被淘汰提前删**。

## 3. 原理深入

### 3.1 过期删除:惰性 + 定期
- **惰性删除**:访问一个 key 时检查是否过期,过期了当场删并返回 nil（sc02 实测:过期后 `GET` 返空、`TTL=-2`）。问题:不访问就不删,内存占着。
- **定期删除**:后台 `serverCron` 每秒若干次,**随机采样**一批设了过期的 key,删掉其中过期的;若过期比例高就继续多删几轮。sc02 实测:5 万个 2s TTL 的 key 全程不访问,2 秒后 `dbsize` 从 50000 掉到 ~700、`expired_keys≈49955`——全是定期删除干的。
- 两者配合:惰性兜「访问到的」,定期兜「没人访问的」,平衡 CPU 与内存。

### 3.2 内存淘汰:maxmemory + 8 策略
`maxmemory` 设上限,`maxmemory-policy` 定满了删谁:

| 策略 | 范围 | 依据 |
|---|---|---|
| `noeviction` | —— | 不淘汰,写直接报 **OOM**（默认）|
| `allkeys-lru` | 所有 key | 最近最少使用 |
| `allkeys-lfu` | 所有 key | 最不经常使用（按频率）|
| `allkeys-random` | 所有 key | 随机 |
| `volatile-lru` | 仅带 TTL 的 | 最近最少使用 |
| `volatile-lfu` | 仅带 TTL 的 | 最不经常使用 |
| `volatile-ttl` | 仅带 TTL 的 | 剩余 TTL 最短 |
| `volatile-random` | 仅带 TTL 的 | 随机 |

sc01 实测:撑满后 `noeviction` 让 `SET` 报 `OOM command not allowed`;切 `allkeys-lru` 后同样的 `SET` 成功,Redis 淘汰了 7 万多 key 把内存压回 `maxmemory` 以下。

### 3.3 LRU 近似 vs LFU
- **Redis 的 LRU 是近似的**:不维护全局链表（太贵），而是采样 `maxmemory-samples`（默认 5）个 key、淘汰其中最久未用的。样本越大越准、越耗 CPU。
- **LFU（4.0+）**:按**访问频率**淘汰,用对数衰减计数器(见 12 章 sc02:`OBJECT FREQ` 访问 5000 次只到 38)。适合「有稳定热点」的场景——LRU 会被「偶尔扫一遍全表」冲掉热点,LFU 不会。

## 4. 日常开发应用

- **一定设 `maxmemory` + 合适的 `maxmemory-policy`**,别用默认 `noeviction` 裸奔（满了直接拒写,线上事故）。
- 纯缓存场景用 `allkeys-lru`/`allkeys-lfu`;有「绝不能丢」的 key 就别给它设 TTL 且用 `volatile-*`（只淘汰带 TTL 的）。
- 有稳定热点 → `allkeys-lfu`(抗全表扫冲刷)。
- TTL 加随机抖动防雪崩(见 06 章)。

## 5. 调优实战

- **写入突然报 OOM** → `INFO memory` 看 `used_memory` vs `maxmemory`;是不是 `noeviction` + 内存满了 → 调策略或扩容。
- **内存涨不下去** → 大量 key 没 TTL 或惰性删除没触发;`INFO stats` 看 `expired_keys`/`evicted_keys` 趋势。
- **热点被冲掉、命中率掉** → LRU 被全表扫冲刷,换 `allkeys-lfu`。

## 6. 面试高频考点

- **过期删除策略?** 惰性 + 定期(随机采样),没有「每 key 定时器」。
- **过期 key 一定立刻删吗?** 不,惰性要访问才删、定期是采样;不访问的过期 key 会占内存直到被采样到（sc02）。
- **8 种淘汰策略 + `noeviction` 的坑**(满了拒写)。
- **LRU 为什么是「近似」?** 采样而非全局链表;`maxmemory-samples` 权衡精度与 CPU。
- **LRU vs LFU 怎么选?** 有稳定热点用 LFU(抗扫表冲刷)。

## 7. 一句话总结

**过期**靠「惰性 + 定期采样」删 TTL key(没定时器);**淘汰**靠 `maxmemory` + 8 策略决定满了删谁,默认 `noeviction` 会拒写——线上必设策略。LRU 是采样近似,有稳定热点用 LFU。

## Scenarios

- [01 - maxmemory 撑满:noeviction 报 OOM vs allkeys-lru 淘汰](scenarios/01-maxmemory-noeviction-vs-lru.md)
- [02 - 过期删除:定期采样（不访问也删）+ 惰性](scenarios/02-expiry-active-vs-lazy.md)
