# bitmap / HyperLogLog / GEO 各用在什么场景？为什么省？

## 一句话回答

「是否存在/统计个数」用 **bitmap**(1bit/对象);「有多少个不同的」用 **HyperLogLog**(~12KB 估算、误差~1%、不存元素);「附近」用 **GEO**(底层 ZSet+GeoHash);「消息队列」用 **Stream**(09 章)。

## 选型 + 实测省了多少

| 业务 | 类型 | 实测对比 |
|---|---|---|
| 签到/在线/布隆 | bitmap | 10万用户 **16KB** vs Set **4.77MB**(~290倍) |
| UV/海量去重(容忍~1%误差) | HyperLogLog | 100万 UV **14KB** vs Set **40MB**(~2800倍),误差~1% |
| 附近的人/范围查 | GEO | 底层 zset,`GEOSEARCH byradius` |
| 精确去重/要取元素 | Set | HLL 取不出元素、有误差 |

## 实测证据

- bitmap 签到 16KB vs Set 4.77MB(290倍)。[sc01](../03-advanced-types/scenarios/01-bitmap-signin-vs-set.md)
- HLL 100万 UV:PFCOUNT=1009972(误差~1%)、14KB vs Set 40MB(2800倍)。[sc02](../03-advanced-types/scenarios/02-hyperloglog-uv.md)
- GEO `TYPE`=zset、上海↔广州 1212km。[sc03](../03-advanced-types/scenarios/03-geo-nearby.md)

## 易追问的延伸

- **HLL 能取出具体元素吗?** 不能,只估个数;`PFMERGE` 可合并(按天 HLL 合周 UV)。
- **bitmap 的坑?** offset 用户 id 稀疏会按最大 offset 撑大,要映射成连续序号。
- **GEO 底层?** ZSet + GeoHash 把经纬度降维成一维 score,范围查=score 范围扫。
- **bitfield 干嘛的?** 把一个 string 当紧凑定宽整数数组(多个小计数器塞一个 key)。

## 证据链接

- 章节原理:[03-advanced-types](../03-advanced-types/README.md)
- 实测:scenarios 01-03;Stream 见 [09 章](../09-pubsub-streams-mq/README.md)
