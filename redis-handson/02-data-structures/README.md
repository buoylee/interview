# 数据结构与底层编码（Data Structures & Encodings）

## 1. 核心问题

Redis 对外是 5 个基础类型（String/List/Hash/Set/ZSet），但每个类型底层**根据数据规模选不同编码**。本章解决三件事：
**(a)** 每个类型有哪些底层编码、各自的数据结构；
**(b)** 编码在什么阈值下、朝哪个方向转换（为什么不可逆）；
**(c)** 写业务时**什么场景该掏哪个类型**，以及编码对内存/性能的影响。

## 2. 直觉理解

Redis 的每个 value 都是一个「对象」（`redisObject`：type + encoding + lru + refcount + 指向真正数据的指针）。**同一个 type，数据少时用紧凑编码省内存，数据大了自动换成高效结构**——像快递：一两件用信封（listpack，连续内存、省空间但插入要挪动），几百件换成货架（hashtable/skiplist，有指针开销但增删快）。换货架是**单向的**：一旦升级，删到很小也不会退回信封（避免在阈值附近反复抖动）。

## 3. 原理深入

### 3.1 redisObject 与编码

`OBJECT ENCODING key` 看当前编码。每个 type 的编码与触发转换的参数：

| Type | 小数据编码 | 大数据编码 | 触发转换的参数（默认） |
|---|---|---|---|
| String | `int`（整数）/ `embstr`（≤44字节） | `raw`（>44字节 或被 APPEND/SETRANGE 改过） | embstr↔raw 边界 = 44 字节（硬编码） |
| List | `listpack` | `quicklist`（listpack 链表） | `list-max-listpack-size`（128） |
| Hash | `listpack` | `hashtable` | `hash-max-listpack-entries`(128) **或** `hash-max-listpack-value`(64B) |
| Set | `intset`（全整数）/ `listpack`（7.2+，小且非全整数） | `hashtable` | `set-max-intset-entries`(512)、`set-max-listpack-entries`(128)、`set-max-listpack-value`(64B) |
| ZSet | `listpack` | `skiplist`（+ dict） | `zset-max-listpack-entries`(128) **或** `zset-max-listpack-value`(64B) |

**转换是单向的**：超阈值升级后不会因删除而回退。

### 3.2 关键底层结构

- **SDS**（Simple Dynamic String）：String 的底层。记录 len/alloc，O(1) 取长度、二进制安全、预分配减少 realloc。`embstr` 把 redisObject 和 SDS 连续分配（一次 malloc，≤44 字节）；`raw` 分开两次分配。
- **listpack**（7.0 取代 ziplist）：一块连续内存，每个 entry 自带长度，**没有 ziplist 的「连锁更新」隐患**（ziplist 每个 entry 存前一个 entry 的长度，中间膨胀会引发级联 realloc）。
- **quicklist**：listpack 节点串成的双向链表，兼顾内存与两端操作。
- **intset**：全整数的 Set，有序整型数组，二分查找；插入非整数或超 512 个 → 升级。
- **skiplist + dict**：ZSet 用跳表（按 score 有序、支持范围）+ 字典（member→score O(1)）双结构，空间换 O(logN) 范围 + O(1) 单查。

## 4. 日常开发应用

**选型决策表（业务 → 类型）**：

| 业务场景 | 选 | 理由 |
|---|---|---|
| 计数器 / 限流计数 | String + `INCR` | 原子自增 |
| 对象/实体字段 | Hash | 部分字段读写，比整体 JSON 省带宽 |
| 队列 / 最近 N 条 | List（`LPUSH`/`LRANGE`/`LTRIM`） | 两端 O(1) |
| 去重 / 标签 / 共同好友 | Set（`SADD`/`SINTER`） | 集合运算 |
| 排行榜 / 延迟队列 / 范围查 | ZSet（`ZADD`/`ZRANGEBYSCORE`） | 按 score 有序 |
| 签到 / 布隆底层 / 在线状态 | bitmap（见 03 章） | 1 bit/用户 |

**写业务时**：
- 大 key 警惕：单个 hash/zset/list 元素数别让它无限涨（见 12 章 `--bigkeys`）。大 hash 用 `field` 分桶或拆 key。
- 想省内存就让数据待在紧凑编码内（控制元素数 < 阈值、value < 64 字节），用 `make encoding K=` 确认。

## 5. 调优实战

**Case A：「这个 hash 占内存比预期大很多」**
1. `make encoding K=h` → 若是 `hashtable`，说明超了阈值，每个 entry 有 dictEntry + SDS 指针开销。
2. 若元素数不多但都是大 value（>64B）→ 是 `hash-max-listpack-value` 触发的，考虑压缩 value 或拆字段。
3. 对照 `make mem K=h` 看实际字节。

**Case B：「想多塞点进 listpack 省内存，能不能调大阈值」**
→ 可以调 `hash-max-listpack-entries`，但 listpack 是 O(N) 查找/插入，调太大单次操作变慢、且大块连续内存易触发 realloc。**省内存 vs CPU 的权衡**，scenario 01/02 实测拐点。

## 6. 面试高频考点

### 编码转换阈值（必背 + 能讲所以然）
见 §3.1 表。追问「为什么单向不回退」→ 避免在阈值附近反复抖动。

### embstr vs raw 为什么是 44 字节
redisObject 16 字节 + SDS header + 终止符等，凑够一个 64 字节内存块（jemalloc 分配粒度）→ 字符串本体 ≤44 字节时能和 redisObject 一次分配（embstr）。

### ZSet 为什么用 skiplist + dict 两个结构
跳表给「按 score 范围/排名」O(logN)，dict 给「member→score」O(1)。少了 dict，`ZSCORE` 要 O(N)。

### listpack 为什么取代 ziplist
ziplist 每个 entry 存前驱长度，中部 entry 变长会引发**连锁更新**（级联 realloc，最坏 O(N²)）。listpack 每个 entry 只存自身长度，消除连锁更新。

## 7. 一句话总结

Redis 每个 value 是 redisObject，同 type 按数据规模在「紧凑编码（listpack/intset/embstr）」与「高效结构（hashtable/skiplist/quicklist/raw）」间**单向升级**。选型先按业务语义挑 type（计数→String、对象→Hash、排行→ZSet…），再用 `OBJECT ENCODING` 确认是否还在紧凑编码内省内存。详见 Scenarios 01-04。

## Scenarios

- [01 - hash listpack → hashtable 转换阈值](scenarios/01-hash-listpack-to-hashtable.md)
- [02 - zset listpack → skiplist + 内存对比](scenarios/02-zset-listpack-to-skiplist.md)
- [03 - String int / embstr / raw 三态与 44 字节边界](scenarios/03-string-int-embstr-raw.md)
- [04 - Set intset / listpack / hashtable 三编码](scenarios/04-set-intset-listpack-hashtable.md)
