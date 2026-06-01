# 高级类型（bitmap / HyperLogLog / GEO / Stream / bitfield）

## 1. 核心问题

5 个基础类型之外，Redis 还有几个「专用武器」。本章解决:**什么业务场景该掏哪个高级类型**,以及它们为什么在那个场景下比基础类型省得多。

## 2. 直觉理解

它们都是「用极小空间解一类特定问题」:
- **bitmap**:每个用户 1 个 bit → 签到/在线状态/布隆,千万用户也才几 MB。
- **HyperLogLog**:用 ~12KB 估算「有多少个不同元素」(UV/去重计数),误差 ~1%,**不存元素本身**。
- **GEO**:经纬度 → 附近的人/范围查(底层是 ZSet + GeoHash 编码)。
- **Stream**:持久化的消息队列(消费组/ack/重放),见 09 章。
- **bitfield**:在一个 string 上当紧凑的「整数数组」操作(计数器矩阵等)。

口诀:**「是否存在/统计个数」用 bitmap,「有多少个不同的」用 HLL,「附近」用 GEO,「消息队列」用 Stream。**

## 3. 原理深入

### 3.1 bitmap（位图）
- `SETBIT key offset 0/1` / `GETBIT` / `BITCOUNT` / `BITOP`。底层就是 string,offset 即第几个 bit。
- 场景:**签到**(`SETBIT sign:<日> <userid> 1`,`BITCOUNT` 数当天签到数)、**在线状态**、**布隆过滤器底层**(06 章 sc01)。
- sc01 实测:10 万用户签到,bitmap 仅 **16KB**,而用 Set 存 10 万 id 要 **4.77MB**(~290 倍)。
- 注意:offset 是用户 id 时,id 稀疏会让 bitmap 变大(按最大 id 分配);id 连续才省。

### 3.2 HyperLogLog（基数估算）
- `PFADD key elem...` / `PFCOUNT key` / `PFMERGE`。估算**不同元素的个数**(基数)。
- **不存元素本身**,固定 ~12KB,标准误差 ~0.81%。sc02 实测:100 万 UV,`PFCOUNT`=1009972(误差 ~1%),内存 **14KB**;用 Set 精确存要 **40MB**(~2800 倍)。
- 场景:**UV 统计**、海量去重计数——**能容忍 ~1% 误差、且不需要拿出具体元素**时。要精确或要取元素 → 用 Set。

### 3.3 GEO（地理位置）
- `GEOADD key 经度 纬度 member` / `GEOSEARCH`(按半径/矩形) / `GEODIST` / `GEOPOS`。
- 底层是 **ZSet**:把经纬度用 GeoHash 编码成一个 score,范围查就是 ZSet 的 score 范围 + 过滤。
- sc03 实测:`GEOSEARCH ... byradius 500 km` 查附近;`GEODIST` 上海↔广州 1212km。
- 场景:附近的人/店、配送范围。

### 3.4 Stream（消息队列）
- `XADD`/`XREADGROUP`/`XACK`/`XPENDING`,持久化 + 消费组 + ack + 重放。是 Redis 当 MQ 的正主。**详见 09 章**(与 pub/sub、List 对比)。

### 3.5 bitfield
- `BITFIELD key SET u8 0 255 GET u8 0 INCRBY ...`:把一个 string 当「紧凑的定宽整数数组」,可设位宽(u8/i16…)、原子增减、溢出策略。
- 场景:一个 key 里塞多个小计数器(如用户多维度计数),比多个 key 省。

## 4. 日常开发应用（选型）

| 业务 | 选 | 理由 |
|---|---|---|
| 签到 / 在线状态 | bitmap | 1 bit/用户,`BITCOUNT` 统计 |
| UV / 海量去重计数(容忍 ~1% 误差) | HyperLogLog | ~12KB 恒定,不存元素 |
| 精确去重 / 要取出元素 | Set | HLL 取不出元素、有误差 |
| 附近的人 / 范围查 | GEO | GeoHash + ZSet |
| 消息队列(持久/消费组) | Stream | 见 09 章 |
| 一个 key 多个小整数 | bitfield | 紧凑定宽数组 |

## 5. 调优实战

- **bitmap 内存比预期大** → offset(用户 id)太稀疏,bitmap 按最大 offset 分配;考虑映射成连续 id 或分片。
- **要 UV 又要明细** → HLL 只给个数;要明细另存(Set/外部),HLL 只做快速计数。
- **GEO 数据量大** → 它就是 ZSet,注意大 key(12 章);按城市/区域分 key。

## 6. 面试高频考点

- **签到用什么?** bitmap(`SETBIT`/`BITCOUNT`),省内存(sc01 ~290 倍)。
- **UV 用什么?为什么不用 Set?** HLL,~12KB 估算、误差 ~1%、不存元素(sc02 ~2800 倍);Set 精确但费内存。
- **HLL 能取出具体元素吗?** 不能,只能估个数。
- **GEO 底层是什么?** ZSet + GeoHash 编码经纬度成 score。
- **bitmap 的坑?** offset 稀疏会撑大(按最大 offset 分配)。

## 7. 一句话总结

「是否存在/统计」用 **bitmap**(1bit/对象,~290 倍省),「有多少个不同的」用 **HyperLogLog**(~12KB、误差 1%、不存元素),「附近」用 **GEO**(ZSet+GeoHash),「消息队列」用 **Stream**(09 章)。选型先问业务语义,再看能不能容忍误差/要不要取出元素。

## Scenarios

- [01 - bitmap 签到 vs Set 内存对比](scenarios/01-bitmap-signin-vs-set.md)
- [02 - HyperLogLog UV 估算:误差与内存](scenarios/02-hyperloglog-uv.md)
- [03 - GEO 附近的人与距离](scenarios/03-geo-nearby.md)
