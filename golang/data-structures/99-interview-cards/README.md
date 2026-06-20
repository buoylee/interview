# 99 · 面试卡 —— Go 数据结构底层高频题速查

> 速答表(背诵)+ 深题卡(讲清,链回正文做证据)。
>
> 总钥匙:**这些「引用类型」= 拷贝便宜的 header + 共享的底层数组/桶。**

## 卡片索引(深题卡)

- [slice 扩容策略与共享底层数组的别名坑](q-slice-growth.md)
- [map 底层:hmap/bmap、渐进扩容、无序、并发 fatal](q-map-internals.md)
- [string·[]byte·rune:不可变、UTF-8、转换拷贝](q-string-bytes-rune.md)
- [逃逸分析:什么在栈、什么在堆](q-escape-analysis.md)
- [struct 内存对齐与字段重排](q-struct-alignment.md)

## 速答表(一行一条,背诵用)

| 问题 | 速答 | 详 |
|---|---|---|
| slice 底层 | 三元组 `{ptr,len,cap}`;数据在共享底层数组;reslice 不拷贝 | [00](../00-slice/README.md) |
| append 扩容多少 | 小翻倍、大约 1.25×;阈值 1.18 起 256(前 1024);再按 size class 取整 | [00](../00-slice/README.md) |
| 函数里 append 外面看不到 | 传 header 副本,扩容后副本指新数组;须 `s=append(s,x)` 接返回值 | [00](../00-slice/README.md) |
| 共享底层数组的坑 | reslice 共享,改元素互见;append 在 cap 内会覆盖别的 slice;用 `a[i:j:j]`/copy 隔离 | [00](../00-slice/README.md) |
| 子切片内存泄漏 | 小 slice 引用大底层数组使其不回收;copy/Clone 出独立副本 | [00](../00-slice/README.md) |
| make 的 len vs cap | `make([]T,5)` 含 5 个零值;预分配空的是 `make([]T,0,5)` | [00](../00-slice/README.md) |
| map 底层 | hmap 头 + bucket(8 对 KV + tophash 指纹 + overflow);低位选桶高8位快筛 | [01](../01-map/README.md) |
| map 怎么扩容 | 负载因子>6.5 翻倍 / overflow 多等量整理;渐进式 evacuate 摊薄 | [01](../01-map/README.md) |
| map 为什么无序 | 主动随机化起始桶+槽,防依赖顺序+防碰撞攻击 | [01](../01-map/README.md) |
| map 并发写 | `fatal error` crash 进程,recover 接不住(非 panic);用 RWMutex/sync.Map | [01](../01-map/README.md) |
| map 元素为什么不可寻址 | 扩容搬迁让地址失效;不能取址/改字段;用 `map[K]*V` 或取出改写回 | [01](../01-map/README.md) |
| map 会缩容吗 | 不会,删元素不释放桶;要回收重建新 map | [01](../01-map/README.md) |
| string 底层 | `{ptr,len}` 两字、只读字节、不可变;能共享/当 key/并发读无锁/子串零拷贝 | [02](../02-string-bytes-rune/README.md) |
| len(s) 是什么 | 字节数(UTF-8 变长);数字符用 utf8.RuneCountInString | [02](../02-string-bytes-rune/README.md) |
| s[i] 取什么 | 第 i 个字节(byte);range 出 rune(int32 码点)+ 起始字节下标 | [02](../02-string-bytes-rune/README.md) |
| []byte(s) 为什么拷贝 | 只读 vs 可写语义冲突;unsafe.String/Slice(1.20)可零拷贝但危险 | [02](../02-string-bytes-rune/README.md) |
| 高效拼接 | strings.Builder(内部[]byte,O(n));循环 += 是 O(n²) | [02](../02-string-bytes-rune/README.md) |
| 栈还是堆谁决定 | 编译期逃逸分析;能证明不超函数生命周期就栈,否则堆 | [03](../03-escape-analysis/README.md) |
| 什么会逃逸 | 返回局部指针/装接口(fmt)/逃出的闭包捕获/编译期大小不定的大对象 | [03](../03-escape-analysis/README.md) |
| 返回 &x 为什么安全 | 编译器发现逃逸自动改放堆,无 C 悬垂指针 | [03](../03-escape-analysis/README.md) |
| & 取地址一定逃逸吗 | 不一定,地址不逃出函数可留栈 | [03](../03-escape-analysis/README.md) |
| 怎么看逃逸 | `go build -gcflags=-m`;基准 `-benchmem` 看 allocs/op | [03](../03-escape-analysis/README.md) |
| struct 大小为何≠字段和 | 内存对齐 + padding;大小向上取整到最大字段对齐倍数 | [04](../04-struct-alignment/README.md) |
| 怎么省内存 | 字段从大到小排(padding 最少);fieldalignment -fix 自动修 | [04](../04-struct-alignment/README.md) |
| 空 struct 多大/何用 | 0 字节;map[K]struct{} 当 set、chan struct{} 当信号 | [04](../04-struct-alignment/README.md) |
| map 为何 key/value 分开存 | 减少对齐 padding(分开紧排 vs 交错补齐) | [04](../04-struct-alignment/README.md) |
| false sharing | 不同核高频写的字段落同一 cache line(64B)互相失效;padding 隔开 | [04](../04-struct-alignment/README.md) |

← 回 [`data-structures` 索引](../README.md)
