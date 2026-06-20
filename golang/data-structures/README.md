# Go 数据结构底层 —— 给 Java 后端的「header + 底层数组/桶」

> slice/map/string 在 Go 里都是**含指针的小 header**,真正的数据在 header 指向的底层数组/桶里。理解「header 与底层的关系」,扩容、别名坑、map 无序、逃逸就全通了。这是面试「黑盒内幕」最高频的一组题。
>
> 总钥匙(承接 [`type-system/00`](../type-system/00-values-layout/README.md)):**这些「引用类型」= 拷贝便宜的 header + 共享的底层数据**;再叠加贯穿性能的**逃逸分析**与**内存对齐**。
>
> 设计来源：`docs/superpowers/specs/2026-06-20-go-data-structures-track-design.md`｜Go 版本基线 1.22+

## 怎么用这个 track

1. **按顺序读**：`00` slice、`01` map 是两大主角(扩容/别名/内幕/无序),`02` string·rune,`03` 逃逸分析(决定栈还是堆),`04` struct 对齐(省内存)。
2. **每章固定 7 段**：核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结。
3. **双向桥**：对照 **Java**(ArrayList/HashMap/String UTF-16/JVM 逃逸/对象 padding)与 **Python**(list/dict/str)。
4. **想答面试**：去 `99-interview-cards/` 找卡,链回正文做证据。

## 容易忘时先看这里

- [slice 扩容公式 + 共享底层数组的别名坑](00-slice/README.md) — 白板高频。
- [map 渐进式扩容 / 为什么无序 / 并发为什么 fatal](01-map/README.md) — 内幕重头。
- [什么会逃逸到堆](03-escape-analysis/README.md) — 性能题常问。

## 章节地图

| 章节 | 主题 | 一句话 |
|---|---|---|
| [`00-slice/`](00-slice/) | slice 底层 | 三元组 header / 扩容(1.18 前后)/ 别名坑 / 三索引切片 / copy / nil vs 空 ← 从这开始 |
| [`01-map/`](01-map/) | **map 底层** | hmap+bmap / tophash / overflow / 渐进扩容 / 负载因子 6.5 / 无序 / 不可寻址 / 并发 fatal |
| [`02-string-bytes-rune/`](02-string-bytes-rune/) | string·[]byte·rune | 不可变 / UTF-8 / len 是字节 / index vs range / 转换拷贝 / Builder / unsafe 零拷贝 |
| [`03-escape-analysis/`](03-escape-analysis/) | 逃逸分析与栈堆 | 栈 vs 堆 / 逃逸规则 / `-gcflags=-m` / 装接口·返指针·闭包为什么逃逸 |
| [`04-struct-alignment/`](04-struct-alignment/) | struct 内存对齐 | 对齐 / padding / 字段重排省内存 / 空 struct / `unsafe.Sizeof` / false sharing |
| [`99-interview-cards/`](99-interview-cards/) | 面试卡 | 速答表 + 深题卡 |

每章 7 段：**核心问题 / 直觉理解 / 原理深入 / 日常开发应用 / 生产&调优实战 / 面试高频考点 / 一句话总结**。

## 进度地图

| 章节 | 状态 | 备注 |
|---|---|---|
| 设计 spec | ✅ | `docs/superpowers/specs/2026-06-20-go-data-structures-track-design.md` |
| 骨架 + 进度地图 | ✅ | 本文件 |
| 00-slice | ✅ | 三元组 header / 扩容(1.18 前后)/ 别名坑 / 三索引 / copy |
| 01-map | ✅ | hmap·bmap / tophash / 渐进 evacuate / 无序 / 不可寻址 / 并发 fatal |
| 02-string-bytes-rune | ✅ | 不可变 / UTF-8 字节vs rune / 转换拷贝 / Builder / unsafe 零拷贝 |
| 03-escape-analysis | ✅ | 栈vs堆 / 逃逸规则 / `-gcflags=-m` / 装接口·返指针逃逸 |
| 04-struct-alignment | ✅ | 对齐/padding / 字段重排省内存 / 空 struct / false sharing |
| 99-interview-cards | ✅ | 速答表(28 条) + 5 张深题卡 |

**本 track 全部完成。**

## 关联已有笔记（复用不重复）

- [`type-system/00`](../type-system/00-values-layout/README.md) — 值语义:slice/map 是含指针的 header(本 track 是底层展开)
- [`type-system/05`](../type-system/05-nil/README.md) — nil slice/map 语义(本 track 只简提反链)
- GC 机制 → `performance-tuning-roadmap/05a-go-profiling/03-go-gc-runtime.md`(`03` 逃逸章引用,不重讲 GC)
- `java/` — ArrayList/HashMap/String 对标锚点

← 回 [`golang/` master 索引](../README.md)
