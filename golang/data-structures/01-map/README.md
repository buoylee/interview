# 01 · map 底层:hmap / bmap、渐进式扩容、为什么无序

> map 是面试内幕重头戏。Go 的 map 是**哈希表**,但实现细节(桶里塞 8 个、tophash 快筛、overflow 链、**渐进式扩容**、**故意随机的遍历顺序**、**并发写直接 fatal**)和 Java HashMap 差别很大,每个都能追问。
>
> 桥接锚点:Java `HashMap` 也是数组 + 桶,但桶内是链表/红黑树、扩容是一次性 rehash、遍历顺序虽不保证但稳定。Go map 是桶内 8 槽 + tophash + **渐进搬迁** + **主动随机化遍历** + **并发不安全到直接 crash**。

---

## 1. 核心问题

```go
m := map[string]int{"a": 1, "b": 2, "c": 3}
for k := range m { fmt.Print(k) }   // 每次运行顺序一样吗?
m2 := m["x"]                         // 不存在的 key 读出来是什么?
// 两个 goroutine 同时写 m 会怎样?
```

- map 底层怎么组织?一次查找经历什么?
- 扩容怎么扩?会不会像 Java 那样一次性 rehash 卡顿?
- 为什么遍历**故意**无序?为什么并发写不是数据错乱而是**直接 crash**?
- 为什么 `m[k].field = x` 编译报错(元素不可寻址)?

---

## 2. 直觉理解

### map = hmap 头 + 一堆 bucket,每个 bucket 装 8 个 KV

```
hmap{ count, B, buckets→ }            B = log2(桶数), count = 元素数
buckets: [bucket0][bucket1]...        每个 bucket(bmap)装最多 8 个 key/value
bucket:  [tophash×8][key×8][value×8][overflow→]
```

- 一个 bucket 最多放 **8 对** KV;放满了挂一个 **overflow 桶**(链下去)。
- key 的 hash:**低 B 位**选哪个 bucket,**高 8 位**存进 `tophash` 数组当「快速指纹」。

### 一次查找:选桶 → tophash 快筛 → 比 key

`m["a"]`:算 hash → 低位定位 bucket → 在桶内 8 个槽里**先比 1 字节 tophash**(快速排除不匹配的)→ tophash 命中再比完整 key → 命中返回 value,没命中走 overflow 桶继续。tophash 这层「1 字节快筛」避免每次都比完整 key,是性能关键。

### 渐进式扩容:不一次性 rehash,边用边搬

负载太高时 map 要扩容,但 Go **不一次性搬完**(那会造成单次操作长卡顿)。它分配新桶后,把旧桶留着,**每次写操作顺手搬迁一两个旧桶**(evacuate),直到搬完。这样把 rehash 成本**摊薄**到多次操作里——和 Java HashMap 一次性 resize 不同。

### 遍历无序是**故意**的

Go 在 `range` map 时**随机选起始桶 + 桶内随机起始槽**。这不是「实现碰巧无序」,是**主动随机化**——防止程序员依赖遍历顺序(那是未定义行为),也避免哈希碰撞攻击。所以同一个 map 每次 range 顺序都可能不同。

---

## 3. 原理深入

### 3.1 hmap / bmap 关键字段

```go
type hmap struct {
    count     int            // len(m),元素个数
    B         uint8          // 桶数 = 2^B
    buckets   unsafe.Pointer // 当前桶数组
    oldbuckets unsafe.Pointer// 扩容时的旧桶数组(搬迁中非 nil)
    // ... flags(含并发检测标志)、hash0(哈希种子)等
}
// 每个 bucket:
type bmap struct {
    tophash [8]uint8         // 8 个槽的高 8 位指纹(也用作空/已搬迁状态标记)
    // 编译期附加: keys[8], values[8], overflow 指针
}
```

> **key 和 value 分开连续存**(`key×8` 再 `value×8`),不是 KV 交错——这样能减少因对齐产生的 padding(承接 [`04 对齐`](../04-struct-alignment/README.md))。

### 3.2 两种扩容

- **翻倍扩容(增量扩容)**:元素太多、**负载因子 > 6.5**(平均每桶超 6.5 个)→ 桶数翻倍(B+1),元素重新分配到新桶。
- **等量扩容(整理)**:元素没超标但 **overflow 桶太多**(大量增删导致桶稀疏)→ 桶数不变,重新紧凑排布,回收 overflow。

两者都走**渐进式 evacuate**:`oldbuckets` 保留,每次写搬一部分,期间查找要**同时查新旧桶**。

### 3.3 为什么元素不可寻址(`&m[k]` 非法)

```go
type P struct{ n int }
m := map[string]P{"a": {1}}
m["a"].n = 2        // ❌ 编译错误:cannot assign to struct field m["a"].n
p := &m["a"]        // ❌ 编译错误:cannot take address of m["a"]
```

因为**扩容会把元素搬到新桶**(地址变了),所以 Go 干脆禁止对 map 元素取地址——否则你手里的指针会在扩容后失效。这也呼应 [`type-system/02`](../../type-system/02-method-sets/README.md):map 元素不可寻址 → 不能调指针接收者方法。**绕法**:取出→改→写回,或用 `map[K]*V`(value 是指针,指针本身不随桶搬迁而失效)。

### 3.4 并发写为什么直接 fatal(不是 panic)

map **不是并发安全**的。Go 在 map 操作时检查一个「正在写」标志,发现并发写(或写时并发读)就直接:

```
fatal error: concurrent map read and map write
```

注意是 **fatal error,不是 panic**——**recover 接不住**,直接 crash 整个进程。这是 Go 故意的:并发写 map 会破坏内部结构(搬迁中尤其危险),与其留下隐蔽的内存损坏,不如当场 crash 暴露。**解法**:`sync.RWMutex` + map,或 `sync.Map`(读多写少场景,见 concurrency track)。

### 3.5 key 的要求

key 必须**可比较**(承接 [`type-system/00`](../../type-system/00-values-layout/README.md)):不能用 slice/map/func 作 key,含这些字段的 struct 也不行。

---

## 4. 日常开发应用

- **预估大小用 `make(map[K]V, hint)`**:提前按 hint 分配桶,减少插入期的渐进扩容搬迁。
- **读不存在的 key 返回零值**,判存在用 comma-ok:`v, ok := m[k]`。
- **要改 map 里的 struct 字段**:`map[K]*V`(存指针),或 `v := m[k]; v.X=1; m[k]=v`。
- **并发用 map**:`sync.RWMutex` 包,或 `sync.Map`(读多写少 / key 集合稳定)。别裸并发写。
- **别依赖遍历顺序**:要有序就把 key 收集到 slice 再 `sort`。
- **删除用 `delete(m, k)`**;遍历中删当前 key 是安全的。

---

## 5. 生产&调优实战

- **并发写 map 是高频线上事故**:fatal 且 recover 不了,直接拖垮进程。code review 重点查「多 goroutine 共享 map 无锁」。压测 + `-race` 能抓(race detector 会报)。
- **渐进扩容期间性能抖动**:大量插入触发扩容,查找要查新旧桶、写要搬迁,延迟略升;预分配 hint 缓解。
- **map 不会缩容**:删除大量元素后桶不释放,内存不还(只是等量扩容整理 overflow)。需要释放就**重建一个新 map**。
- **大 map 的 GC 扫描成本**:key/value 含指针时,GC 要扫所有桶;海量小对象 map 是 GC 压力点,考虑 `map[K]V`(V 非指针)或分片。
- **map 作为值不可寻址带来的拷贝**:`map[K]BigStruct` 取值是拷贝;频繁取大 value 用 `map[K]*BigStruct`。

---

## 6. 面试高频考点

- **map 底层结构?** hmap 头 + bucket 数组;每个 bucket 装 8 对 KV + tophash(高8位指纹)+ overflow 指针。hash 低 B 位选桶、高 8 位做桶内快筛。
- **一次查找过程?** 算 hash→低位定桶→桶内比 tophash 快筛→命中再比完整 key→未中走 overflow。
- **怎么扩容?和 Java 区别?** 负载因子>6.5 翻倍扩容、overflow 过多等量整理;都是**渐进式 evacuate**(每次写搬一部分,摊薄成本)。Java HashMap 是一次性 resize。
- **为什么遍历无序?** Go **主动随机化**起始桶+槽,防依赖顺序 + 防碰撞攻击。要有序自己 sort key。
- **并发写会怎样?** `fatal error: concurrent map writes`,**recover 接不住、直接 crash**(不是 panic)。用 RWMutex 或 sync.Map。
- **为什么 map 元素不可寻址?** 扩容搬迁会让地址失效,故禁止取址;不能调指针方法/改字段。用 `map[K]*V` 或取出改写回。
- **map 会缩容吗?** 不会,删元素不释放桶;要回收内存重建新 map。
- **什么能当 key?** 可比较类型;slice/map/func 及含它们的 struct 不行。

---

## 7. 一句话总结

> **Go map 是哈希表:hmap 头 + bucket 数组,每桶装 8 对 KV + tophash 指纹 + overflow 链。** 查找 = hash 低位选桶、高 8 位快筛、再比完整 key。扩容(负载因子>6.5 翻倍 / overflow 过多等量整理)走**渐进式 evacuate**——每次写搬一点、摊薄成本(不像 Java 一次性 rehash);期间查新旧两套桶。遍历**故意随机**(防依赖顺序 + 防攻击)。元素**不可寻址**(扩容搬迁会让地址失效)→ 不能取址/改字段,用 `map[K]*V`。**并发写直接 `fatal error` crash 进程、recover 不了**——必须 RWMutex 或 `sync.Map`。map 不缩容、key 必须可比较。

← 上一章 [`00 slice`](../00-slice/README.md) ｜ 下一章 → [`02 string·[]byte·rune`](../02-string-bytes-rune/README.md):string 为什么不可变、`len` 为什么是字节数、`range` 为什么出 rune、`[]byte(s)` 为什么拷贝。｜ 回 [`data-structures` 索引](../README.md)
