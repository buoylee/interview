# 大 key / 热 key 是什么，怎么定位和治理？

## 一句话回答

**大 key**=单 key 体积过大（O(N) 操作阻塞单线程 + 占内存），用 `--bigkeys`/`--memkeys`/`MEMORY USAGE` 定位，**拆分 + `UNLINK` + `SCAN`** 治理。**热 key**=单 key QPS 过高（打爆单分片），用 `--hotkeys`（需 LFU）定位，**本地缓存 / 读副本 / key 打散** 治理。

## 对比

| | 大 key | 热 key |
|---|---|---|
| 问题 | 单 key 太大 → O(N) 阻塞、占内存、迁移慢 | 单 key 太热 → 单分片/单线程被打爆 |
| 定位 | `--bigkeys`(按类型)、`--memkeys`(按内存)、`MEMORY USAGE` | `--hotkeys`(需 LFU)、`OBJECT FREQ` |
| 治理 | 拆分(分片落 listpack 还省内存)、`UNLINK` 异步删、`HSCAN` 渐进读 | 本地缓存、读副本分摊、key 加随机后缀打散到多分片 |

## 实测证据

- 大 key 双重危害:50000 字段 hash = hashtable / 2.78MB,`HGETALL` 阻塞 4ms;拆 500 个 listpack 分片 → **内存降到 0.87MB(1/3)** + 单次操作变小。[sc01](../12-production-ops/scenarios/01-bigkey-locate-and-split.md)
- `OBJECT FREQ` 是**对数衰减计数**,5000 次访问只到 38——是相对热度不是 QPS。[sc02](../12-production-ops/scenarios/02-hotkey-locate-lfu.md)

## 易追问的延伸

- **`UNLINK` vs `DEL`?** UNLINK 把内存回收丢给后台线程,不阻塞主线程;删大 key 必用 UNLINK。
- **为什么拆分还省内存?** 每片落紧凑编码(listpack)省掉 hashtable 的指针开销(见 02 章)。
- **cluster 下热 key 怎么办?** 打散到多 key(落不同 slot)或客户端本地缓存;单纯加副本只分摊读。
- **怎么线上扫大 key 不阻塞?** `--bigkeys` 内部用 `SCAN` 采样;别自己 `KEYS` + `MEMORY USAGE` 全量。

## 证据链接

- 章节原理:[12-production-ops §3.1/§3.2](../12-production-ops/README.md)
- 实测:[sc01 大key](../12-production-ops/scenarios/01-bigkey-locate-and-split.md)、[sc02 热key](../12-production-ops/scenarios/02-hotkey-locate-lfu.md)
