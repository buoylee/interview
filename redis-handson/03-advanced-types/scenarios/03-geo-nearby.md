# Scenario 03: GEO 附近的人与距离

## 我想验证的问题

用 GEO 存几个城市的经纬度，能不能查「某点半径内的成员」和「两点距离」？GEO 底层到底是什么结构？

## 预期（写实验前的假设）

> **请在跑 lab 之前填这一段**（基于 README §3.3，不要查）：
>
> - `GEOSEARCH cities frommember beijing byradius 500 km` 会返回哪些城市？_____
> - 上海到广州大约 _____ km。
> - GEO 底层用的是哪种数据结构？_____
>
> 填完单独 commit 一次。

## 环境

- 起 lab：`make up`。`R(){ docker compose exec -T redis redis-cli "$@"; }`

## 步骤

```bash
cd 00-lab && make up
R(){ docker compose exec -T redis redis-cli "$@"; }
R flushall
R geoadd cities 116.40 39.90 beijing 121.47 31.23 shanghai 113.26 23.13 guangzhou
echo "北京 500km 内: $(R geosearch cities frommember beijing byradius 500 km asc)"
echo "北京 1500km 内(带距离): $(R geosearch cities frommember beijing byradius 1500 km asc withdist)"
echo "上海->广州: $(R geodist cities shanghai guangzhou km) km"
echo "GEO 底层其实是 ZSet → TYPE cities = $(R type cities)"
echo "  ZRANGE 看 score(GeoHash 编码): $(R zrange cities 0 -1 withscores | tr '\n' ' ')"
```

## 实机告诉我（2026-06-02，Redis 7.4.9 实跑）

```
北京 500km 内: beijing                              ← 上海/广州都 >500km
上海->广州: 1212.1702 km
TYPE cities = zset                                  ← GEO 底层就是 ZSet!
ZRANGE withscores: guangzhou 4046... shanghai 4054... beijing 4069...  ← score 是 GeoHash 编码
```

观察到的关键事实：

- `GEOSEARCH ... byradius 500 km` 只返回 beijing（其他城市超 500km）；放大到 1500km 能带出 shanghai/guangzhou 及距离。
- `GEODIST` 上海→广州 = 1212km。
- **`TYPE cities` 是 `zset`**——GEO 不是独立类型,而是把经纬度用 **GeoHash 编码成一个 double score** 存进 ZSet;范围查就是 ZSet 的 score 范围扫 + 精确距离过滤。

## ⚠️ 预期 vs 实机落差

- 我以为：GEO 是个独立的地理专用结构。
- 实际:GEO **就是 ZSet 的语法糖**——`GEOADD` 把经纬度 GeoHash 编码成 score `ZADD` 进去,`GEOSEARCH` 本质是 score 范围查。所以 `TYPE` 返回 zset,还能直接 `ZRANGE` 看。
- 我学到:(1) 附近的人/店、配送范围用 GEO(`GEOSEARCH byradius/bybox`)。(2) 因为底层是 ZSet,**大量点会变大 key**(12 章),按城市/区域分 key。(3) GeoHash 把二维经纬度降维成一维可排序的 score——这是「能用一维有序结构做二维范围查」的关键技巧。

## 连到的面试卡

- `99-interview-cards/q-redis-advanced-types.md`
