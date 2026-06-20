# Go 数据结构底层 track —— 设计 spec

> 日期：2026-06-20
> 目录：`golang/data-structures/`
> 上级：`docs/superpowers/specs/2026-06-20-go-senior-interview-master-design.md`（umbrella）

## 背景与目标

slice/map/string 的底层是 Go 面试「黑盒内幕」最高频的一组:**slice 扩容与共享底层数组的别名坑**、**map 的 hmap/bucket/渐进式扩容/为什么无序/并发为什么直接 fatal**、**string 不可变与 []byte 转换拷贝**、再加上贯穿性能的**逃逸分析**和**struct 内存对齐**。用户从 Java(ArrayList/HashMap/String)来,正好对照。

目标:读完能在白板画 slice 三元组 header + 扩容、画 hmap+bmap+tophash + 渐进扩容、讲清 string 不可变与零拷贝、说清什么会逃逸、会用字段重排省内存。

## 核心设计决策

- **形式**：5 章,照搬已认可模板(7 段 + `99-interview-cards/`)。
- **主线钥匙 = 「这些类型都是含指针的小 header(承接 type-system/00),底层数组/桶才是数据;理解 header 与底层的关系,扩容/别名/无序/逃逸全通」**。
- **双向桥**：Java `ArrayList`/`HashMap`/`String`(UTF-16)/JVM 逃逸分析/对象 padding ←→ Go slice/map/string(UTF-8)/编译期逃逸/struct 对齐;Python list/dict/str。
- **底层内幕进正文**:slice header 三元组 + 扩容公式(含 1.18 变化)+ 三索引切片;hmap/bmap 结构 + tophash + overflow + 渐进 evacuate + 负载因子 6.5 + 随机遍历 + 并发 fatal;string header 不可变 + UTF-8 + 转换拷贝 + `unsafe.String/Slice`(1.20);逃逸规则 + `-gcflags=-m`;对齐/padding/字段重排 + `unsafe.Sizeof`。
- **Go 版本**:1.22+;slice 扩容公式标注 1.18 前后差异;`unsafe.String/Slice` 标 1.20。

## 章节地图（每章 7 段）

| 章节 | 主题 | 一句话 |
|---|---|---|
| `00-slice/` | slice 底层 | 三元组 header / 扩容策略(1.18 前后)/ 共享底层数组的别名坑 / 三索引切片 / copy / nil vs 空 ← 高频 |
| `01-map/` | map 底层 | hmap+bmap / tophash / overflow 桶 / 渐进式扩容(evacuate)/ 负载因子 6.5 / 为什么无序 / 元素不可寻址 / 并发 fatal |
| `02-string-bytes-rune/` | string·[]byte·rune | header 不可变 / UTF-8 / len 是字节数 / index vs range / 转换拷贝 / strings.Builder / unsafe 零拷贝 |
| `03-escape-analysis/` | 逃逸分析与栈堆 | 栈 vs 堆 / 逃逸规则 / `-gcflags=-m` / 装接口·返回指针·闭包捕获为什么逃逸 / 性能含义 |
| `04-struct-alignment/` | struct 内存对齐 | 对齐规则 / padding / 字段重排省内存 / 空 struct / `unsafe.Sizeof` / false sharing(点到) |
| `99-interview-cards/` | 面试卡 | 速答表 + 深题卡(slice 扩容、map 内幕、string·rune、逃逸、对齐) |

## 已有素材的处理

- 承接 [`type-system/00`](值语义:slice/map 是含指针的 header)——本 track 是其底层展开。
- typed nil / nil slice·map 已在 type-system/05 讲;本 track `00`/`01` 只在「nil vs 空」处简提并反链。
- GC/逃逸的运行时细节:`03` 讲逃逸**判定**与含义,GC 机制本身链接 `performance-tuning-roadmap/05a-go-profiling/03-go-gc-runtime.md`,不重讲。
- false sharing/cache line:`04` 点到,深入链 concurrency / perf-roadmap。
- 现有顶层 stub `collections.md`(22 行)内容被本 track 吸收,本 track 完成后删除(删前看)。

## 交付节奏

1. 写本 spec。2. 骨架 README + 5 章目录。3. 写 00(slice)确认,逐章推进 + 面试卡。4. track 完成后清理 `collections.md` stub。

## 验收标准

- 00 能画 slice header + 解释「传 slice 改元素可见、append 扩容不可见」、三索引切片防别名。
- 01 能画 hmap/bmap + 讲渐进扩容、为什么无序、并发为什么 fatal、元素为什么不可寻址。
- 02 能讲 string 不可变 + `len` 是字节、`range` 出 rune、转换拷贝与零拷贝。
- 03 能说出 3-4 种典型逃逸场景 + 怎么用 `-gcflags=-m` 看。
- 04 能用字段重排把一个 struct 从 padding 浪费改到紧凑。

## 非目标（YAGNI）

- 不重讲 GC 机制(链接 perf-roadmap)。
- 不展开 sync.Map(归 concurrency)、不展开泛型容器(归 generics)。
- 不逐行读 runtime/map.go,深到「结构 + 关键流程 + 为什么」即可。
