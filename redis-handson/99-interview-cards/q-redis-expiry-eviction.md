# Redis 的过期删除和内存淘汰机制是什么？

## 一句话回答

**过期删除**(删 TTL key):惰性(访问才删)+ 定期(后台随机采样删),没有 per-key 定时器。**内存淘汰**(`maxmemory` 满了删谁):8 种 `maxmemory-policy`,默认 `noeviction` 会**拒写报 OOM**。两者独立。

## 过期 vs 淘汰（别混）

| | 过期删除 | 内存淘汰 |
|---|---|---|
| 触发 | key 的 TTL 到期 | `used_memory` 到 `maxmemory` |
| 机制 | 惰性 + 定期采样 | `maxmemory-policy`(8 种) |
| 统计 | `expired_keys` | `evicted_keys` |

## 8 种淘汰策略

`noeviction`(默认,拒写)、`allkeys-{lru,lfu,random}`、`volatile-{lru,lfu,ttl,random}`(volatile 只动带 TTL 的 key)。

## 实测证据

- 定期删除:5万个 2s TTL key 全程不访问,3s 后 dbsize 50000→~700、expired≈49955。[sc02](../04-expiry-eviction/scenarios/02-expiry-active-vs-lazy.md)
- 淘汰:撑满后 `noeviction` 写报 OOM;切 `allkeys-lru` 淘汰 7.7 万 key、内存压回 maxmemory、写成功。[sc01](../04-expiry-eviction/scenarios/01-maxmemory-noeviction-vs-lru.md)

## 易追问的延伸

- **为什么不用 per-key 定时器?** 千万级 key 起千万个定时器太贵;采样 + 惰性是 CPU/内存折中,代价是过期不精确。
- **LRU 为什么是近似的?** 采样 `maxmemory-samples`(默认5)个而非全局链表;样本大越准越耗 CPU。
- **LRU vs LFU?** 有稳定热点用 LFU,抗「全表扫一遍把热点冲掉」(LRU 会被冲)。[12 章 sc02 OBJECT FREQ]
- **生产最常见的过期/淘汰事故?** 默认 `noeviction` 内存满了拒写;大量 key 同时过期 CPU 尖刺(雪崩,加 TTL 抖动)。

## 证据链接

- 章节原理:[04-expiry-eviction](../04-expiry-eviction/README.md)
- 实测:[sc01 淘汰](../04-expiry-eviction/scenarios/01-maxmemory-noeviction-vs-lru.md)、[sc02 过期](../04-expiry-eviction/scenarios/02-expiry-active-vs-lazy.md)
