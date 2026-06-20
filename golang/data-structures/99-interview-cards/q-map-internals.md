# map 底层:hmap/bmap、渐进扩容、无序、并发 fatal

## 一句话回答

Go map 是哈希表:`hmap` 头 + bucket 数组,**每个 bucket 装最多 8 对 KV + tophash(高 8 位指纹)+ overflow 指针**。查找 = hash **低 B 位选桶**、桶内**比 tophash 快筛**、再比完整 key、未中走 overflow。扩容(**负载因子 > 6.5 翻倍** / overflow 太多**等量整理**)走**渐进式 evacuate**——每次写顺手搬一两个旧桶、把成本摊薄(不像 Java 一次性 rehash)。遍历**故意随机化**;元素**不可寻址**;**并发写直接 `fatal error` crash 进程、recover 接不住**。

## 白板图

```
hmap{ count, B, buckets→, oldbuckets→(搬迁中) }
bucket(bmap): [tophash×8][key×8][value×8][overflow→]
              ↑ key 和 value 分开连续存,减少对齐 padding
```

## 关键追问点

- **为什么无序?** 主动随机起始桶 + 桶内起始槽,防程序员依赖顺序 + 防哈希碰撞攻击。要有序:收集 key 到 slice 再 sort。
- **为什么元素不可寻址?** 扩容 evacuate 会把元素搬到新桶、地址失效,故禁止 `&m[k]`;不能改字段/调指针方法。用 `map[K]*V` 或取出改写回。
- **并发写为什么是 fatal 不是 panic?** 并发写会破坏内部结构(搬迁中尤危险),Go 检测到「正在写」标志冲突就 `fatal error: concurrent map writes` 当场 crash 暴露,recover 救不了。用 `sync.RWMutex` + map 或 `sync.Map`。
- **会缩容吗?** 不会,删元素不释放桶;要回收内存重建新 map。
- **key 要求?** 可比较类型(slice/map/func 及含它们的 struct 不行)。

## 证据链接

- 正文:[`01 map`](../01-map/README.md);可比较性 [`type-system/00`](../../type-system/00-values-layout/README.md);并发安全 [`concurrency/06`](../../concurrency/06-sync-memory-model/README.md)

## 易追问的延伸

- **负载因子 6.5 什么意思?** 平均每桶元素数超 6.5 就翻倍扩容。
- **渐进扩容期间查找?** 同时查新旧桶,直到旧桶搬完。
- **和 Java HashMap 区别?** Java:桶内链表/红黑树、一次性 resize、遍历顺序虽不保证但稳定、并发写是数据错乱不 crash;Go:桶内 8 槽+tophash、渐进搬迁、主动随机遍历、并发写直接 fatal。
