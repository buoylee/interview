# Redis 各类型的底层编码与转换阈值是什么？

## 一句话回答

每个 type 按数据规模在「紧凑编码」与「高效结构」间**单向升级**：String `int/embstr(≤44B)/raw`；List/Hash/ZSet `listpack → quicklist/hashtable/skiplist`；Set `intset → listpack(7.2+) → hashtable`。超阈值后**不回退**（避免抖动）。

## 阈值表

| Type | 紧凑 | 升级后 | 触发参数（默认） |
|---|---|---|---|
| String | int / embstr(≤44B) | raw | 44 字节硬边界；APPEND/SETRANGE 必转 raw；超 int64 的数字串是 embstr 不是 int |
| List | listpack | quicklist | `list-max-listpack-size`(128) |
| Hash | listpack | hashtable | entries 128 **或** value 64B（任一，严格 >） |
| Set | intset / listpack | hashtable | intset ≤512；listpack entries 128/value 64B；超 512 整数跳过 listpack 直奔 hashtable |
| ZSet | listpack | skiplist(+dict) | entries 128 **或** value 64B |

## 易追问的延伸

- **embstr 为什么是 44 字节？** redisObject(16B)+SDS header+终止符 凑满 64B jemalloc 块 → 本体 ≤44B 可一次分配。证据：[scenario 03](../02-data-structures/scenarios/03-string-int-embstr-raw.md)
- **listpack 比 skiplist 省多少？** 200 元素时 listpack 1840B vs skiplist 17880B，约 10 倍。证据：[scenario 02](../02-data-structures/scenarios/02-zset-listpack-to-skiplist.md)
- **ZSet 为什么 skiplist + dict 两个结构？** 跳表给范围/排名 O(logN)，dict 给 member→score O(1)。
- **listpack 凭什么取代 ziplist？** 消除 ziplist 的连锁更新（级联 realloc）。
- **转换可逆吗？** 不可逆。hash 删到 1 个字段仍是 hashtable。证据：[scenario 01 步骤 4](../02-data-structures/scenarios/01-hash-listpack-to-hashtable.md)
- **Set 三态是哪个版本来的？** listpack 编码是 7.2+ 引入；之前 Set 只有 intset/hashtable。证据：[scenario 04](../02-data-structures/scenarios/04-set-intset-listpack-hashtable.md)

## 证据链接

- 章节原理：[02-data-structures §3](../02-data-structures/README.md)
- 实测：scenarios 01-04（全部在 Redis 7.4.9 实跑过）
